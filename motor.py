import json
import os
import re
import time
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path

import numpy as np

_ESTILO = None
_MODELS = {}  # tamaño -> WhisperModel; conviven preciso y rápido para cambiar al vuelo

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

def log(*args):
    # Con hora: sin ella no se puede cruzar un fallo con la fila que quedó sin traducir.
    print(time.strftime("%H:%M:%S"), *args, flush=True)

def _deepl_cuentas() -> list[tuple[str, str]]:
    # Varias cuentas DeepL en cascada (DEEPL_API_KEYS=nombre=key,nombre=key,...): si una
    # falla o agota cuota, la siguiente responde. También vale sin nombre, y
    # DEEPL_API_KEY (singular) sigue funcionando.
    raw = os.environ.get("DEEPL_API_KEYS") or os.environ.get("DEEPL_API_KEY", "")
    out = []
    for i, parte in enumerate(p.strip() for p in raw.split(",") if p.strip()):
        nombre, _, key = parte.rpartition("=")
        out.append((nombre.strip() or f"API {i + 1}", key.strip()))
    return out

def _deepl_keys() -> list[str]:
    return [k for _, k in _deepl_cuentas()]

def load_estilo() -> str:
    global _ESTILO
    if _ESTILO is None:
        _ESTILO = Path(__file__).with_name("estilo_glosario.md").read_text(encoding="utf-8")
    return _ESTILO

def build_prompt(original: str, direction: str) -> str:
    destino = "inglés (English)" if direction == "es2en" else "español"
    return (
        f"{load_estilo()}\n\n"
        f"Traduce el siguiente texto al {destino}, aplicando TODAS las reglas de arriba.\n"
        f"Texto:\n\"\"\"\n{original}\n\"\"\"\n\n"
        "Responde SOLO con JSON válido, sin texto extra, con esta forma exacta:\n"
        '{"traduccion": "<la traducción>", '
        '"resaltados": [{"texto": "<fragmento del texto>", "tipo": "numero|direccion|nombre|fecha"}]}\n'
        "Incluye en resaltados los números/cantidades, direcciones, nombres propios y fechas/horas "
        "que aparezcan (en el idioma de la traducción). Si no hay, deja la lista vacía."
    )

def parse_response(raw: str) -> dict:
    s = re.sub(r"^```json\s*|\s*```$", "", raw.strip())
    try:
        d = json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if not m:
            return {"traduccion": "", "resaltados": []}
        try:
            d = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {"traduccion": "", "resaltados": []}
    return {"traduccion": str(d.get("traduccion", "")), "resaltados": d.get("resaltados", []) or []}

def gemini_translate(original: str, direction: str) -> dict:
    try:
        key = os.environ["GEMINI_API_KEY"]
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{GEMINI_MODEL}:generateContent?key={key}")
        body = json.dumps({
            "contents": [{"parts": [{"text": build_prompt(original, direction)}]}],
            "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"},
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return parse_response(text)
    except Exception as e:
        log("[gemini] falló:", e)
        return {"traduccion": "", "resaltados": []}

_KEY_429 = {}  # key -> time.monotonic() hasta el que se salta (throttle por IP de DeepL)

def deepl_translate(original: str, direction: str, solo_primera=False) -> dict:
    # DeepL traduce plano (sin resaltados), pero aguanta el volumen de una llamada
    # real sin el rate limit del free tier de Gemini. formality=prefer_more da "usted".
    # timeout corto: lo normal es <1.5s; con varias keys en cascada, esperar 15s por
    # una key caída trabaría el camino en vivo (lección v30: nada de esperas largas).
    if direction == "es2en":
        data = {"text": original, "target_lang": "EN-US", "source_lang": "ES"}
    else:
        data = {"text": original, "target_lang": "ES", "source_lang": "EN",
                "formality": "prefer_more"}
    body = urllib.parse.urlencode(data).encode("utf-8")
    cuentas = _deepl_cuentas()
    if solo_primera:
        cuentas = cuentas[:1]
    for nombre, key in cuentas:
        # Breaker anti-429: DeepL free throttlea por IP (visto 2026-07-11: las 3 cuentas
        # dieron 429 a la vez). Tras un 429 la key descansa 10s en vez de martillar,
        # que solo alarga el bloqueo. Sin esperas: se salta y sigue la siguiente.
        if time.monotonic() < _KEY_429.get(key, 0.0):
            continue
        try:
            req = urllib.request.Request("https://api-free.deepl.com/v2/translate", data=body,
                headers={"Authorization": "DeepL-Auth-Key " + key})
            with urllib.request.urlopen(req, timeout=6) as r:
                d = json.loads(r.read())
            return {"traduccion": d["translations"][0]["text"], "resaltados": []}
        except Exception as e:
            if isinstance(e, urllib.error.HTTPError) and e.code == 429:
                _KEY_429[key] = time.monotonic() + 10
            log(f"[deepl] {nombre} falló:", e)
    return {"traduccion": "", "resaltados": []}

# Números/horas/fechas numéricas en el texto: Whisper ya convierte los dígitos
# dictados a cifras (ej. "uno dos tres" → "123"), así que un patrón de dígitos basta
# para resaltar SSN, teléfonos, cantidades, modelos y horas. Gratis, sin tokens.
_NUM_RE = re.compile(r"\d[\d.,:/ -]*\d|\d")

def resaltados_locales(texto: str) -> list:
    vistos, out = set(), []
    for m in _NUM_RE.finditer(texto):
        t = m.group().strip(" .,:-/")
        if len(t) >= 1 and t not in vistos:
            vistos.add(t)
            out.append({"texto": t, "tipo": "numero"})
    return out

# Pronunciación "a la española" de una palabra inglesa: CMU da los fonemas (ARPABET)
# y los mapeamos a sílabas que un hispanohablante lee tal cual. La vocal tónica
# (stress 1) va en MAYÚSCULA para marcar dónde cargar la fuerza. Es aproximado, guía.
_VOCALES_ARPA = {"AA": "a", "AE": "a", "AH": "a", "AO": "o", "AW": "au", "AY": "ai",
                 "EH": "e", "ER": "er", "EY": "ei", "IH": "i", "IY": "i",
                 "OW": "ou", "OY": "oi", "UH": "u", "UW": "u"}
_CONS_ARPA = {"B": "b", "CH": "ch", "D": "d", "DH": "d", "F": "f", "G": "g", "HH": "j",
              "JH": "y", "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ng", "P": "p",
              "R": "r", "S": "s", "SH": "sh", "T": "t", "TH": "z", "V": "v", "W": "u",
              "Y": "i", "Z": "s", "ZH": "y"}
_CMU = None

def _cmu():
    global _CMU
    if _CMU is None:
        import cmudict
        _CMU = cmudict.dict()
    return _CMU

def pronunciacion_es(palabra: str) -> str:
    w = re.sub(r"[^a-z']", "", palabra.lower())
    fons = _cmu().get(w) if w else None
    if not fons:
        return ""
    out = []
    for f in fons[0]:
        stress = f[-1] if f[-1].isdigit() else ""
        base = f[:-1] if stress else f
        if base in _VOCALES_ARPA:
            s = _VOCALES_ARPA[base]
            out.append(s.upper() if stress == "1" else s)
        else:
            out.append(_CONS_ARPA.get(base, ""))
    return "".join(out)

# Traducción LOCAL (OPUS-MT sobre CTranslate2, en CPU): ilimitada, sin red y sin el
# throttle por IP de DeepL. Calidad menor que DeepL → se usa para captions provisionales
# y como red de seguridad de finales. Modelos en ~/interprete/modelos/opus-{en-es,es-en};
# si no están descargados (o falta sentencepiece), devuelve vacío y no estorba.
_LOCAL = {}
LOCAL_DIR = Path(__file__).with_name("modelos")

def _local(direction):
    if direction not in _LOCAL:
        try:
            import ctranslate2
            import sentencepiece as spm
            d = LOCAL_DIR / ("opus-en-es" if direction == "en2es" else "opus-es-en")
            if not (d / "model.bin").exists():
                raise FileNotFoundError(d)
            _LOCAL[direction] = (
                ctranslate2.Translator(str(d), device="cpu", compute_type="int8",
                                       intra_threads=4),
                spm.SentencePieceProcessor(str(d / "source.spm")),
                spm.SentencePieceProcessor(str(d / "target.spm")))
        except Exception:
            _LOCAL[direction] = None
    return _LOCAL[direction]

def local_translate(original: str, direction: str) -> dict:
    try:
        eq = _local(direction)
        if eq is None:
            return {"traduccion": "", "resaltados": []}
        translator, sp_in, sp_out = eq
        # "</s>" al final es obligatorio en OpusMT/CT2: sin él el decoder no ve fin
        # de frase y degenera en repeticiones infinitas.
        toks = sp_in.encode(original, out_type=str) + ["</s>"]
        res = translator.translate_batch([toks], beam_size=1)
        texto = sp_out.decode(res[0].hypotheses[0])
        return {"traduccion": texto, "resaltados": resaltados_locales(texto)}
    except Exception as e:
        log("[local] falló:", e)
        return {"traduccion": "", "resaltados": []}

def translate(original: str, direction: str, parcial=False) -> dict:
    # Primario por env (TRADUCTOR), con fallback automático al otro: si el primario
    # falla o agota cuota devuelve traducción vacía, y saltamos al secundario para
    # no quedarnos mudos a mitad de llamada.
    if parcial:
        # Caption provisional: SOLO el traductor local — cero peticiones a DeepL, así
        # los finales nunca compiten con captions por el rate de la IP (el burst limit
        # de DeepL free es de unas pocas peticiones por ~10s, visto 2026-07-11).
        # Sin modelo local descargado, cae a UN intento DeepL con la key primaria.
        res = local_translate(original, direction)
        if res["traduccion"].strip():
            return res
        res = deepl_translate(original, direction, solo_primera=True)
        if res["traduccion"].strip() and not res["resaltados"]:
            res["resaltados"] = resaltados_locales(res["traduccion"])
        return res
    funcs = {"deepl": deepl_translate, "gemini": gemini_translate}
    primario = os.environ.get("TRADUCTOR", "deepl")
    # Finales: primario → local (instantáneo, cubre 429 y hasta caída de internet) →
    # el otro remoto como último recurso (Gemini free: 20/día, casi nunca disponible).
    orden = [primario] + [t for t in funcs if t != primario]
    orden.insert(1, "local")
    funcs["local"] = lambda o, d: local_translate(o, d)
    for t in orden:
        res = funcs[t](original, direction)
        if res["traduccion"].strip():
            # DeepL no marca resaltados; los generamos localmente. Gemini ya trae los suyos.
            if not res["resaltados"]:
                res["resaltados"] = resaltados_locales(res["traduccion"])
            return res
    return {"traduccion": "", "resaltados": []}

def deepl_usage() -> dict:
    # Caracteres consumidos/límite del mes en DeepL, para saber en vivo si damos abasto.
    # El medidor del header suma todas las cuentas; "cuentas" trae el detalle por API
    # para el panel de Ajustes (limit=0 = esa key no respondió: inválida o sin red).
    cuentas = []
    for nombre, key in _deepl_cuentas():
        try:
            req = urllib.request.Request("https://api-free.deepl.com/v2/usage",
                headers={"Authorization": "DeepL-Auth-Key " + key})
            with urllib.request.urlopen(req, timeout=10) as r:
                d = json.loads(r.read())
            cuentas.append({"nombre": nombre, "count": d.get("character_count", 0),
                            "limit": d.get("character_limit", 0)})
        except Exception as e:
            log(f"[deepl] usage {nombre} falló:", e)
            cuentas.append({"nombre": nombre, "count": 0, "limit": 0})
    return {"count": sum(c["count"] for c in cuentas),
            "limit": sum(c["limit"] for c in cuentas), "cuentas": cuentas}

def lang_to_direction(lang: str) -> str:
    # El LEP habla español; Whisper rara vez confunde el inglés, pero confunde el
    # español con otras lenguas romances. Por eso solo "en" es inglés; el resto, español.
    return "en2es" if lang == "en" else "es2en"

def build_intervencion(lang, original, traduccion, resaltados, hora) -> dict:
    return {"hora": hora, "idioma": "en" if lang == "en" else "es",
            "original": original, "traduccion": traduccion, "resaltados": resaltados}

def process_text(lang: str, original: str, translate_fn=translate):
    original = original.strip()
    if not original:
        return None
    res = translate_fn(original, lang_to_direction(lang))
    return build_intervencion(lang, original, res["traduccion"], res["resaltados"],
                              time.strftime("%H:%M:%S"))

def pcm_to_float32(pcm: bytes) -> "np.ndarray":
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0

def load_model(size=None):
    size = size or os.environ.get("WHISPER_MODEL", "small")
    if size not in _MODELS:
        from faster_whisper import WhisperModel
        device = os.environ.get("WHISPER_DEVICE", "cpu")
        compute = "int8" if device == "cpu" else "int8_float16"
        m = WhisperModel(size, device=device, compute_type=compute, cpu_threads=8)
        # Warmup: la 1ª transcripción real compila los kernels CUDA (~3s de retraso en la
        # primera frase / 1ª tijera). Calentamos con RUIDO (no silencio: el VAD descartaría
        # el silencio y nunca correría el decoder) y vad_filter=False, en ambos idiomas.
        try:
            for lng in ("es", "en"):
                list(m.transcribe((0.1 * np.random.randn(16000)).astype(np.float32),
                                  beam_size=1, vad_filter=False, language=lng)[0])
        except Exception:
            pass
        _MODELS[size] = m
    return _MODELS[size]

def transcribe(pcm: bytes, model) -> tuple[str, str]:
    audio = pcm_to_float32(pcm)
    # El audio de la llamada suele llegar flojo (monitor a volumen de escucha);
    # normalizar al ~0.95 de escala evita que Whisper alucine en tramos bajos.
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak > 0:
        audio = audio / peak * 0.95
    # vad_filter descarta tramos sin voz y no_speech_prob filtra alucinaciones
    # de Whisper sobre silencio/ruido (texto fantasma).
    segments, info = model.transcribe(audio, beam_size=1, vad_filter=True)
    # La llamada es SOLO inglés o español. Si no es inglés, lo tratamos como español;
    # y si Whisper lo detectó como otra lengua (pt/it/gl…), re-transcribimos forzando
    # español para no quedarnos con texto en portugués.
    if info.language == "en":
        lang = "en"
    else:
        lang = "es"
        if info.language != "es":
            segments, info = model.transcribe(audio, beam_size=1, vad_filter=True, language="es")
    texto = " ".join(s.text for s in segments if s.no_speech_prob < 0.6).strip()
    return texto, lang
