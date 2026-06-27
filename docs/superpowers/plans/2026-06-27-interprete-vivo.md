# Intérprete en vivo — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Herramienta local que captura las dos voces de una llamada OPI, las transcribe y traduce en tiempo real, y las muestra en dos paneles (español izquierda / inglés derecha) con resaltado de datos clave.

**Architecture:** Un proceso Python captura el audio del monitor de salida de PipeWire, segmenta por silencios (VAD por energía, sin dependencias C), transcribe con faster-whisper en la GPU, traduce con Gemini (REST por urllib) aplicando reglas de estilo + glosario LEP, y empuja cada intervención por WebSocket a una página HTML local que se abre en Brave.

**Tech Stack:** Python 3 (venv), faster-whisper (CUDA), `websockets`, stdlib `urllib`/`asyncio`/`json`, numpy (viene con faster-whisper), HTML/CSS/JS sin frameworks.

## Global Constraints

- Proyecto en `~/interprete/`, ya es repo git. venv en `~/interprete/venv` (ignorado por git).
- Dependencias pip permitidas: **solo** `faster-whisper` y `websockets`. Gemini se llama por REST con `urllib` (sin SDK). Sin más dependencias.
- Audio: PCM `s16le`, 16000 Hz, mono, desde el `.monitor` del sink por defecto. Nunca el micrófono.
- VAD por energía RMS en Python puro + numpy (NO usar `audioop` — eliminado en Python 3.13+; NO añadir `webrtcvad`).
- Whisper: modelo `medium`, `device="cuda"`, `compute_type="int8_float16"`. Idiomas tratados: español → resto se trata como inglés.
- Estilo de traducción (verbatim, va en el prompt de Gemini): **primera persona / habla directa**; **siempre "usted / le", nunca "tú / te"**; resolver glosario LEP; LEP nunca se nombra en la salida.
- Resaltados, tipos exactos: `numero`, `direccion`, `nombre`, `fecha`.
- Salida de Gemini, JSON exacto: `{"traduccion": "...", "resaltados": [{"texto":"...","tipo":"numero|direccion|nombre|fecha"}]}`.
- Intervención (mensaje WebSocket), forma exacta: `{"hora":"HH:MM:SS","idioma":"es|en","original":"...","traduccion":"...","resaltados":[...]}`. `idioma":"es"` → panel izquierdo; `"en"` → panel derecho.
- WebSocket en `ws://localhost:8765`. La página se abre con `file://` en Brave (no hace falta servidor HTTP).
- API key de Gemini en variable de entorno `GEMINI_API_KEY`. Modelo en `GEMINI_MODEL` (default `gemini-2.5-flash` — verificado con cuota gratuita; `gemini-2.0-flash` ya no tiene free tier, da 429).
- Tests con `pytest`. Commits frecuentes.

---

### Task 1: Setup del proyecto (venv, dependencias, estructura, guard de entorno)

**Files:**
- Create: `~/interprete/requirements.txt`
- Create: `~/interprete/README.md`
- Modify: `~/interprete/.gitignore` (ya existe; añadir `venv/`, `pytest` cache)
- Create: `~/interprete/tests/__init__.py`

**Interfaces:**
- Produces: venv funcional en `~/interprete/venv` con faster-whisper (CUDA OK), websockets, pytest, numpy.

- [ ] **Step 1: Crear venv y requirements**

`requirements.txt`:
```
faster-whisper
websockets
pytest
```

```bash
cd ~/interprete
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

- [ ] **Step 2: Verificar que faster-whisper carga con CUDA**

Run:
```bash
./venv/bin/python -c "from faster_whisper import WhisperModel; m=WhisperModel('tiny', device='cuda', compute_type='int8_float16'); print('CUDA OK')"
```
Expected: imprime `CUDA OK` (descarga el modelo tiny la primera vez).
Si falla por wheels de ctranslate2/Python 3.14: recrear venv con `python3.12 -m venv venv` y reinstalar. Documentarlo en README.

- [ ] **Step 3: Actualizar .gitignore y crear estructura de tests**

Añadir a `.gitignore`:
```
venv/
.pytest_cache/
__pycache__/
*.pyc
.env
```
Crear `tests/__init__.py` vacío.

- [ ] **Step 4: README mínimo**

`README.md`:
```markdown
# Intérprete en vivo

Transcribe y traduce en tiempo real las dos voces de una llamada OPI.

## Uso
1. `export GEMINI_API_KEY=...`
2. `./interprete.sh`
3. Habla la llamada por la PC; lee los paneles en Brave.

## Requisitos
- GPU NVIDIA con CUDA, PipeWire, Brave.
- `python3 -m venv venv && ./venv/bin/pip install -r requirements.txt`
- Si faster-whisper no instala en Python 3.14, usar `python3.12 -m venv venv`.
```

- [ ] **Step 5: Commit**

```bash
cd ~/interprete
git add requirements.txt README.md .gitignore tests/__init__.py
git commit -m "chore: setup proyecto intérprete (venv, deps, estructura)"
```

---

### Task 2: estilo_glosario.md (reglas de estilo + glosario LEP limpio)

**Files:**
- Create: `~/interprete/estilo_glosario.md`
- Test: `tests/test_estilo.py`

**Interfaces:**
- Produces: archivo de texto `estilo_glosario.md` que `motor.py` lee íntegro e inyecta en el prompt de Gemini.

- [ ] **Step 1: Escribir el test que valida contenido mínimo**

`tests/test_estilo.py`:
```python
from pathlib import Path

def test_estilo_glosario_tiene_reglas_y_glosario():
    txt = Path("estilo_glosario.md").read_text(encoding="utf-8")
    # reglas clave
    assert "primera persona" in txt.lower()
    assert "usted" in txt.lower()
    assert "nunca" in txt.lower() and "tú" in txt.lower()
    # muestras del glosario
    assert "guagua" in txt.lower()
    assert "aseguranza" in txt.lower()
    assert "troca" in txt.lower()
```

- [ ] **Step 2: Run test, debe fallar**

Run: `./venv/bin/pytest tests/test_estilo.py -v`
Expected: FAIL (archivo no existe).

- [ ] **Step 3: Crear estilo_glosario.md**

```markdown
# Reglas de estilo (obligatorias)

1. Interpreta en PRIMERA PERSONA (habla directa). Si el inglés dice "I'm glad to see you",
   traduces "Me alegra verle hoy", NO "el doctor dice que se alegra".
   Excepción: usa tercera persona solo si la primera confunde al hispanohablante
   (salud mental, niños) o en emergencias.
2. Registro SIEMPRE formal y respetuoso: usa "usted" y "le". NUNCA uses "tú" ni "te"
   para nadie. Ejemplo correcto: "¿qué le gusta comer a usted?".
3. Resuelve los regionalismos del glosario de abajo a su significado real antes de traducir.
4. El término "LEP" es interno: nunca aparece en la traducción.

# Glosario LEP (español regional → significado / inglés)

Aliviar → dar a luz (contexto médico/OBGYN)
Rabadilla → coxis / base de la columna
Esquechar / esquecho → agendar una cita (schedule an appointment)
Piscar / la pisca / corrida → cosechar fruta o plantas (picking)
Coyunturas → articulaciones (joints)
Chamorro → pantorrilla (calf)
Cava → parte de atrás de la rodilla
Puyar / me puya → punzada / dolor punzante (prick / stabbing pain)
Campo → finca (farm)
Envoi → factura (invoice)
Troca → camioneta pickup (pickup truck)
Reca → grúa (tow truck)
Pacha → biberón (baby bottle)
La Yaré → IRS
Aseguranza → compañía de seguros (insurance company)
Ocupar → necesitar (need)
Elenai → LNI / Labor & Industries
Camión → bus
Guagua → bus
Alberca → piscina (pool)
Wachar → mirar, vigilar (watch)
Banqueta → acera (sidewalk)
Traila → casa móvil (trailer home)
Culebrilla / el chingo → herpes zóster (shingles)
Billes → cuentas / facturas (bills)
Talones de cheque → recibos de pago (pay stubs)
Sonografía → ecografía (ultrasound)
Citología / Papanicolado → Pap smear
Baisam → sótano (basement)
Conerico → Connecticut
Visícula → vesícula (gallbladder)
Chocho → área pélvica / vagina
Patilla → sandía (watermelon)
Cheve → cerveza (beer)
Espinazo → columna (spine)
Pachar → presionar / empujar (push, a menudo botones)
Estampillas / Fucstan → cupones de alimentos (food stamps / SNAP)
Las ayudas → beneficios / programas de apoyo (benefits)
Amasar → masaje (massage)
Carcañal → talón / hueso calcáneo (heel)
Juntados → pareja que vive junta (estado civil)
Chai sopol → manutención infantil (child support)
Menear → moverse de un lugar a otro
Chismanyir → gestor de caso (case manager)

# Expresiones
"Dímele tú a ella" → Please, tell her.
"¿Cómo así, oiga?" → I didn't understand.
"Le llamo pa'tras" → I'll call you back.
"Me llegó una calta" → (señal de que será una llamada larga)
```

- [ ] **Step 4: Run test, debe pasar**

Run: `./venv/bin/pytest tests/test_estilo.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add estilo_glosario.md tests/test_estilo.py
git commit -m "feat: reglas de estilo y glosario LEP"
```

---

### Task 3: motor.py — construcción de prompt y parseo de respuesta (lógica pura, TDD)

**Files:**
- Create: `~/interprete/motor.py`
- Test: `tests/test_motor_prompt.py`

**Interfaces:**
- Produces:
  - `load_estilo() -> str` — lee `estilo_glosario.md`.
  - `build_prompt(original: str, direction: str) -> str` — `direction` ∈ {`"es2en"`,`"en2es"`}.
  - `parse_response(raw: str) -> dict` — devuelve `{"traduccion": str, "resaltados": list}`; tolera fences ```json.

- [ ] **Step 1: Test de build_prompt y parse_response**

`tests/test_motor_prompt.py`:
```python
import motor

def test_build_prompt_incluye_estilo_y_texto():
    p = motor.build_prompt("me duele la espalda", "es2en")
    assert "me duele la espalda" in p
    assert "usted" in p.lower()          # reglas inyectadas
    assert "english" in p.lower() or "inglés" in p.lower()  # dirección
    assert "JSON" in p

def test_build_prompt_direccion_en2es():
    p = motor.build_prompt("What is your address?", "en2es")
    assert "What is your address?" in p
    assert "español" in p.lower() or "spanish" in p.lower()

def test_parse_response_json_plano():
    raw = '{"traduccion":"my back hurts","resaltados":[]}'
    d = motor.parse_response(raw)
    assert d["traduccion"] == "my back hurts"
    assert d["resaltados"] == []

def test_parse_response_con_fences():
    raw = '```json\n{"traduccion":"hola","resaltados":[{"texto":"5th Ave","tipo":"direccion"}]}\n```'
    d = motor.parse_response(raw)
    assert d["traduccion"] == "hola"
    assert d["resaltados"][0]["tipo"] == "direccion"

def test_parse_response_invalido_devuelve_vacio():
    d = motor.parse_response("no soy json")
    assert d["traduccion"] == ""
    assert d["resaltados"] == []
```

- [ ] **Step 2: Run test, debe fallar**

Run: `./venv/bin/pytest tests/test_motor_prompt.py -v`
Expected: FAIL (módulo no existe).

- [ ] **Step 3: Implementar motor.py (parte de prompt/parseo)**

```python
import json
import re
from pathlib import Path

_ESTILO = None

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
    s = raw.strip()
    m = re.search(r"\{.*\}", s, re.DOTALL)  # extrae el objeto JSON aunque venga con fences
    if m:
        try:
            d = json.loads(m.group(0))
            return {
                "traduccion": str(d.get("traduccion", "")),
                "resaltados": d.get("resaltados", []) or [],
            }
        except json.JSONDecodeError:
            pass
    return {"traduccion": "", "resaltados": []}
```

- [ ] **Step 4: Run test, debe pasar**

Run: `./venv/bin/pytest tests/test_motor_prompt.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add motor.py tests/test_motor_prompt.py
git commit -m "feat: motor build_prompt y parse_response"
```

---

### Task 4: motor.py — llamada a Gemini (REST) y orquestación de una intervención

**Files:**
- Modify: `~/interprete/motor.py`
- Test: `tests/test_motor_proceso.py`

**Interfaces:**
- Consumes: `build_prompt`, `parse_response` (Task 3).
- Produces:
  - `gemini_translate(original: str, direction: str) -> dict` — llama Gemini por REST, devuelve `parse_response(...)`.
  - `lang_to_direction(lang: str) -> str` — `"es"` → `"es2en"`, cualquier otro → `"en2es"`.
  - `build_intervencion(lang, original, traduccion, resaltados, hora) -> dict` — arma el dict del WebSocket.
  - `process_text(lang: str, original: str, translate_fn=gemini_translate) -> dict|None` — orquesta; `None` si `original` vacío. (translate_fn inyectable para test.)

- [ ] **Step 1: Test de orquestación con translate_fn falso**

`tests/test_motor_proceso.py`:
```python
import motor

def fake_translate(original, direction):
    return {"traduccion": "TRAD:" + original, "resaltados": [{"texto": "x", "tipo": "numero"}]}

def test_lang_to_direction():
    assert motor.lang_to_direction("es") == "es2en"
    assert motor.lang_to_direction("en") == "en2es"
    assert motor.lang_to_direction("fr") == "en2es"

def test_process_text_es_va_a_izquierda():
    iv = motor.process_text("es", "me duele", translate_fn=fake_translate)
    assert iv["idioma"] == "es"
    assert iv["original"] == "me duele"
    assert iv["traduccion"] == "TRAD:me duele"
    assert iv["resaltados"][0]["tipo"] == "numero"
    assert len(iv["hora"]) == 8  # HH:MM:SS

def test_process_text_en_normaliza_idioma():
    iv = motor.process_text("fr", "hello", translate_fn=fake_translate)
    assert iv["idioma"] == "en"

def test_process_text_vacio_devuelve_none():
    assert motor.process_text("es", "   ", translate_fn=fake_translate) is None
```

- [ ] **Step 2: Run test, debe fallar**

Run: `./venv/bin/pytest tests/test_motor_proceso.py -v`
Expected: FAIL (funciones no existen).

- [ ] **Step 3: Añadir a motor.py**

```python
import os
import time
import urllib.request

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

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
```

- [ ] **Step 4: Run test, debe pasar**

Run: `./venv/bin/pytest tests/test_motor_proceso.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: (Manual) Verificar Gemini real**

Con `GEMINI_API_KEY` exportada:
```bash
./venv/bin/python -c "import motor; print(motor.gemini_translate('me duele la espalda', 'es2en'))"
```
Expected: dict con `traduccion` tipo "my back hurts". Si `traduccion` vacía, revisar key/modelo (`GEMINI_MODEL`).

- [ ] **Step 6: Commit**

```bash
git add motor.py tests/test_motor_proceso.py
git commit -m "feat: motor Gemini REST y orquestación de intervención"
```

---

### Task 5: motor.py — transcripción con Whisper

**Files:**
- Modify: `~/interprete/motor.py`
- Test: `tests/test_motor_whisper.py`

**Interfaces:**
- Produces:
  - `load_model() -> WhisperModel` — carga `medium` en cuda/int8_float16 una sola vez (singleton).
  - `transcribe(pcm: bytes, model) -> tuple[str, str]` — PCM s16le 16k mono → `(texto, idioma)`.

- [ ] **Step 1: Test de conversión PCM (sin cargar Whisper)**

`tests/test_motor_whisper.py`:
```python
import numpy as np
import motor

def test_pcm_a_float32_normaliza():
    pcm = np.array([0, 32767, -32768], dtype=np.int16).tobytes()
    f = motor.pcm_to_float32(pcm)
    assert f.dtype == np.float32
    assert abs(f[1] - 1.0) < 0.01
    assert abs(f[2] + 1.0) < 0.01
```

- [ ] **Step 2: Run test, debe fallar**

Run: `./venv/bin/pytest tests/test_motor_whisper.py -v`
Expected: FAIL (`pcm_to_float32` no existe).

- [ ] **Step 3: Añadir a motor.py**

```python
import numpy as np

_MODEL = None

def pcm_to_float32(pcm: bytes):
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0

def load_model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel("medium", device="cuda", compute_type="int8_float16")
    return _MODEL

def transcribe(pcm: bytes, model) -> tuple[str, str]:
    audio = pcm_to_float32(pcm)
    segments, info = model.transcribe(audio, beam_size=1, vad_filter=False)
    texto = " ".join(s.text for s in segments).strip()
    return texto, info.language
```

- [ ] **Step 4: Run test, debe pasar**

Run: `./venv/bin/pytest tests/test_motor_whisper.py -v`
Expected: PASS.

- [ ] **Step 5: (Manual) Verificar que el modelo carga**

La transcripción real se prueba en Task 8 (end-to-end). Aquí basta con que `load_model()` cargue sin error:
```bash
./venv/bin/python -c "import motor; motor.load_model(); print('modelo cargado')"
```
Expected: `modelo cargado` (descarga el modelo `medium` la primera vez).

- [ ] **Step 6: Commit**

```bash
git add motor.py tests/test_motor_whisper.py
git commit -m "feat: motor transcripción Whisper"
```

---

### Task 6: captura.py — descubrimiento del monitor, comando pw-record y segmentador VAD

**Files:**
- Create: `~/interprete/captura.py`
- Test: `tests/test_captura.py`

**Interfaces:**
- Produces:
  - `monitor_source() -> str` — `pactl get-default-sink` + `".monitor"`.
  - `record_command(monitor: str) -> list[str]` — args de `pw-record` (s16, 16k, mono, stdout).
  - `Segmenter(rms_threshold=500, hang_ms=700, min_ms=300)` con `feed(frame: bytes) -> bytes|None` (frame = 30 ms = 960 bytes); devuelve PCM de la intervención al detectar fin de habla, si no `None`.
  - `FRAME_BYTES = 960`.

- [ ] **Step 1: Tests del segmentador y helpers**

`tests/test_captura.py`:
```python
import numpy as np
import captura

def _frame(amp):
    return (np.ones(480, dtype=np.int16) * amp).tobytes()  # 480 samples = 30ms

def test_frame_bytes():
    assert captura.FRAME_BYTES == 960

def test_record_command_tiene_formato():
    cmd = captura.record_command("foo.monitor")
    assert "pw-record" in cmd[0]
    assert "foo.monitor" in cmd
    assert "16000" in cmd

def test_segmenter_emite_tras_silencio():
    seg = captura.Segmenter(rms_threshold=500, hang_ms=90, min_ms=30)
    out = None
    # 5 frames fuertes (habla) ~150ms
    for _ in range(5):
        assert seg.feed(_frame(3000)) is None
    # 3 frames de silencio (hang_ms=90 => 3 frames) dispara la emisión
    for _ in range(2):
        assert seg.feed(_frame(0)) is None
    out = seg.feed(_frame(0))
    assert out is not None
    assert len(out) == 5 * captura.FRAME_BYTES

def test_segmenter_descarta_intervencion_corta():
    seg = captura.Segmenter(rms_threshold=500, hang_ms=90, min_ms=300)
    seg.feed(_frame(3000))            # solo 30ms de habla < min_ms
    for _ in range(3):
        r = seg.feed(_frame(0))
    assert r is None                  # demasiado corta, no emite
```

- [ ] **Step 2: Run test, debe fallar**

Run: `./venv/bin/pytest tests/test_captura.py -v`
Expected: FAIL (módulo no existe).

- [ ] **Step 3: Implementar captura.py**

```python
import subprocess
import numpy as np

RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = RATE * FRAME_MS // 1000   # 480
FRAME_BYTES = FRAME_SAMPLES * 2           # 960

def monitor_source() -> str:
    sink = subprocess.check_output(["pactl", "get-default-sink"]).decode().strip()
    return sink + ".monitor"

def record_command(monitor: str) -> list[str]:
    return ["pw-record", "--target", monitor,
            "--rate", str(RATE), "--channels", "1", "--format", "s16", "-"]

def _rms(frame: bytes) -> float:
    x = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(x * x))) if len(x) else 0.0

class Segmenter:
    def __init__(self, rms_threshold=500, hang_ms=700, min_ms=300):
        self.threshold = rms_threshold
        self.hang_frames = max(1, hang_ms // FRAME_MS)
        self.min_frames = max(1, min_ms // FRAME_MS)
        self.buf = []
        self.silence = 0
        self.in_speech = False

    def feed(self, frame: bytes):
        speech = _rms(frame) >= self.threshold
        if speech:
            self.in_speech = True
            self.silence = 0
            self.buf.append(frame)
            return None
        if not self.in_speech:
            return None
        self.silence += 1
        self.buf.append(frame)
        if self.silence >= self.hang_frames:
            speech_frames = len(self.buf) - self.silence
            out = b"".join(self.buf[:speech_frames])
            self.buf = []
            self.silence = 0
            self.in_speech = False
            return out if speech_frames >= self.min_frames else None
        return None

def utterances(monitor=None):
    """Generador: lanza pw-record y produce PCM por intervención."""
    monitor = monitor or monitor_source()
    proc = subprocess.Popen(record_command(monitor), stdout=subprocess.PIPE)
    seg = Segmenter()
    try:
        while True:
            frame = proc.stdout.read(FRAME_BYTES)
            if len(frame) < FRAME_BYTES:
                break
            out = seg.feed(frame)
            if out:
                yield out
    finally:
        proc.terminate()
```

- [ ] **Step 4: Run test, debe pasar**

Run: `./venv/bin/pytest tests/test_captura.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add captura.py tests/test_captura.py
git commit -m "feat: captura de audio y segmentador VAD por energía"
```

---

### Task 7: index.html — UI de dos paneles

**Files:**
- Create: `~/interprete/index.html`

**Interfaces:**
- Consumes: mensajes WebSocket con forma `{"hora","idioma","original","traduccion","resaltados"}` desde `ws://localhost:8765`.

- [ ] **Step 1: Crear index.html**

```html
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Intérprete en vivo</title>
<style>
  body { margin:0; font-family:system-ui, sans-serif; background:#111; color:#eee; }
  header { padding:6px 12px; background:#000; font-size:14px; }
  #estado { float:right; }
  .grid { display:grid; grid-template-columns:1fr 1fr; height:calc(100vh - 34px); }
  .panel { display:flex; flex-direction:column; overflow:hidden; border-left:1px solid #333; }
  .panel h2 { margin:0; padding:6px 10px; font-size:14px; background:#1b1b1b; position:sticky; top:0; }
  .es h2 { background:#14331f; } .en h2 { background:#142033; }
  .feed { overflow-y:auto; padding:8px; flex:1; }
  .row { display:grid; grid-template-columns:1fr 1fr; gap:8px; padding:6px 4px; border-bottom:1px solid #222; }
  .orig { color:#bbb; } .trad { color:#fff; font-weight:600; }
  .hora { font-size:11px; color:#666; }
  .nuevo { animation:flash 1s; }
  @keyframes flash { from { background:#3a3a00; } to { background:transparent; } }
  .chip { display:inline-block; font-size:11px; padding:1px 6px; border-radius:8px; margin:2px 2px 0 0; }
  .numero{background:#553;} .direccion{background:#355;} .nombre{background:#535;} .fecha{background:#544;}
</style>
</head>
<body>
<header>Intérprete en vivo <span id="estado">conectando…</span></header>
<div class="grid">
  <section class="panel es"><h2>🇪🇸 Cliente (español) — original · interpretación</h2><div class="feed" id="feed-es"></div></section>
  <section class="panel en"><h2>🇺🇸 Representante (inglés) — original · interpretación</h2><div class="feed" id="feed-en"></div></section>
</div>
<script>
const estado = document.getElementById("estado");
function chips(res){
  return (res||[]).map(r => `<span class="chip ${r.tipo}">${r.texto}</span>`).join("");
}
function add(iv){
  const feed = document.getElementById(iv.idioma === "es" ? "feed-es" : "feed-en");
  const row = document.createElement("div");
  row.className = "row nuevo";
  row.innerHTML = `<div class="orig"><span class="hora">${iv.hora}</span><br>${iv.original}</div>`
                + `<div class="trad">${iv.traduccion}<br>${chips(iv.resaltados)}</div>`;
  feed.appendChild(row);
  feed.scrollTop = feed.scrollHeight;
}
function connect(){
  const ws = new WebSocket("ws://localhost:8765");
  ws.onopen = () => estado.textContent = "● en vivo";
  ws.onclose = () => { estado.textContent = "desconectado, reintentando…"; setTimeout(connect, 1500); };
  ws.onmessage = e => add(JSON.parse(e.data));
}
connect();
</script>
</body>
</html>
```

- [ ] **Step 2: Verificación visual (sin backend)**

Abrir el archivo y comprobar que cargan los dos paneles:
```bash
brave "file://$HOME/interprete/index.html" &
```
Expected: dos columnas (verde español izquierda, azul inglés derecha), estado "desconectado, reintentando…". Cerrar.

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat: UI de dos paneles"
```

---

### Task 8: servidor.py + interprete.sh — pipeline en vivo end-to-end

**Files:**
- Create: `~/interprete/servidor.py`
- Create: `~/interprete/interprete.sh`

**Interfaces:**
- Consumes: `captura.utterances`, `motor.load_model`, `motor.transcribe`, `motor.process_text` (translate real por defecto).
- Produces: servidor WebSocket en `localhost:8765` que emite intervenciones; script `interprete.sh` que arranca todo y abre Brave.

- [ ] **Step 1: Implementar servidor.py**

```python
import asyncio
import json
import websockets

import captura
import motor

CLIENTS = set()

async def broadcast(iv: dict):
    if CLIENTS:
        msg = json.dumps(iv, ensure_ascii=False)
        await asyncio.gather(*(c.send(msg) for c in list(CLIENTS)), return_exceptions=True)

async def handler(ws):
    CLIENTS.add(ws)
    try:
        await ws.wait_closed()
    finally:
        CLIENTS.discard(ws)

def pipeline(loop):
    """Hilo bloqueante: captura → whisper → gemini → broadcast."""
    model = motor.load_model()
    for pcm in captura.utterances():
        texto, lang = motor.transcribe(pcm, model)
        iv = motor.process_text(lang, texto)
        if iv:
            asyncio.run_coroutine_threadsafe(broadcast(iv), loop)

async def main():
    loop = asyncio.get_running_loop()
    async with websockets.serve(handler, "localhost", 8765):
        print("WebSocket en ws://localhost:8765 — habla la llamada…")
        await loop.run_in_executor(None, pipeline, loop)

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Crear interprete.sh**

```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ -z "$GEMINI_API_KEY" ]; then
  echo "Falta GEMINI_API_KEY. Exporta tu key: export GEMINI_API_KEY=..." >&2
  exit 1
fi
brave "file://$PWD/index.html" >/dev/null 2>&1 &
exec ./venv/bin/python servidor.py
```

```bash
chmod +x interprete.sh
```

- [ ] **Step 3: Verificación end-to-end real**

Con `GEMINI_API_KEY` exportada y reproduciendo audio en inglés y español por la PC (p. ej. un video de YouTube bilingüe o una llamada de prueba):
```bash
export GEMINI_API_KEY=...   # la key real
./interprete.sh
```
Expected:
- Brave abre los dos paneles, estado "● en vivo".
- Al sonar voz en inglés: aparece fila en el panel derecho (original EN + traducción ES).
- Al sonar voz en español: aparece fila en el panel izquierdo (original ES + traducción EN, en primera persona y con "usted").
- Datos como números/fechas/direcciones salen como chips.
- Latencia ~1–1.5 s tras dejar de hablar.

Verificar manualmente: que NO aparezca tu propia voz del micrófono (solo lo que suena por la salida).

- [ ] **Step 4: Commit**

```bash
git add servidor.py interprete.sh
git commit -m "feat: servidor WebSocket, pipeline en vivo y launcher"
```

---

## Notas de ejecución

- **Prerrequisito antes de Task 4 Step 5 y Task 8:** crear API key nueva de Gemini en Google AI Studio y `export GEMINI_API_KEY=...`. (Se abrirá AI Studio en Brave en ese momento.)
- Si Whisper `medium` va justo de VRAM (6 GB) junto a otras apps, bajar a `small` en `motor.load_model()`.
- Ajustes finos de captura: si corta frases (emite demasiado pronto) subir `hang_ms`; si junta a dos personas, bajarlo. Si capta ruido como habla, subir `rms_threshold`.
