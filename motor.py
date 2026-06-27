import json
import os
import re
import time
import urllib.request
from pathlib import Path

_ESTILO = None

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

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
        m = re.search(r"\{.*?\}", s, re.DOTALL)
        if not m:
            return {"traduccion": "", "resaltados": []}
        try:
            d = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {"traduccion": "", "resaltados": []}
    return {"traduccion": str(d.get("traduccion", "")), "resaltados": d.get("resaltados", []) or []}

def gemini_translate(original: str, direction: str) -> dict:
    key = os.environ["GEMINI_API_KEY"]
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_MODEL}:generateContent?key={key}")
    body = json.dumps({
        "contents": [{"parts": [{"text": build_prompt(original, direction)}]}],
        "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"},
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return parse_response(text)
    except Exception:
        return {"traduccion": "", "resaltados": []}

def lang_to_direction(lang: str) -> str:
    return "es2en" if lang == "es" else "en2es"

def build_intervencion(lang, original, traduccion, resaltados, hora) -> dict:
    return {"hora": hora, "idioma": "es" if lang == "es" else "en",
            "original": original, "traduccion": traduccion, "resaltados": resaltados}

def process_text(lang: str, original: str, translate_fn=gemini_translate):
    original = original.strip()
    if not original:
        return None
    res = translate_fn(original, lang_to_direction(lang))
    return build_intervencion(lang, original, res["traduccion"], res["resaltados"],
                              time.strftime("%H:%M:%S"))
