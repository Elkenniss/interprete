# Intérprete en vivo

Transcribe y traduce en tiempo real las dos voces de una llamada OPI (el LEP y su
cliente) que se reproduce por el altavoz o monitor de la PC. Pensado para el flujo
de trabajo de Kenny: el LEP habla **español**, el cliente habla **inglés**, y la
herramienta muestra cada intervención original y traducida al instante en un panel
del navegador.

> Esta versión (rama `master`) es la **más funcional y estable hasta el momento**.
> Es un rollback: las últimas versiones experimentales (v48–v51, ramas `windows` y
> `panel-notas-ingles`) no convencieron y quedaron fuera. Aquí se documenta y se
> sube la versión de trabajo real.

---

## Cómo funciona

Pipeline de un solo hilo que recorre: **captura → Whisper → traducción → panel web**.

```
        PipeWire                    faster-whisper                DeepL / OPUS-MT           Brave
 audio monitor ──tellpcm──► Segmenter ──► transcribe() ──► translate() ──► WebSocket ──► index.html
 (parec)         corta por silencio     (vad)             (3 traductores)   (ws://:8765)   paneles
```

1. **Captura** (`captura.py`): `parec` se engancha al *monitor* del sink por defecto de
   PipeWire (lo que suena por la PC, no por el micrófono). Un `Segmenter` corta el
   audio en **intervenciones** por umbral de volumen + silencio (1s de hueco cierra
   la frase). Si `parec` muere a mitad de llamada (cambio de dispositivo, hipo del
   sistema) se **relanza solo** — una llamada puede durar horas.

2. **Transcripción** (`motor.transcribe`): `faster-whisper` con `vad_filter` para
   descartar tramos sin voz y `no_speech_prob < 0.6` para filtrar alucinaciones
   (texto fantasma). El audio se normaliza a ~0.95 de escala, porque el monitor del
   altavoz suele llegar flojo. La llamada es **solo** inglés o español: lo que no es
   inglés se fuerza a español (Whisper confunde el español con otras lenguas
   romances). Hay **dos modelos**: el preciso (`large-v3`, default) y el rápido
   (`small`), conmutables en vivo sin reiniciar.

3. **Traducción** (`motor.translate`): cascada de traductores con copia de seguridad
   automática:
   - **DeepL** (primario, `TRADUCTOR=deepl`): varias cuentas en cascada
     (`DEEPL_API_KEYS=nombre=key,...`), con *breaker* anti-429 (una key que devuelve
     429 descansa 10s y salta a la siguiente). `context` conecta frases de un mismo
     hilo. Usa la API free (`api-free.deepl.com`).
   - **OPUS-MT local** (`motor.local_translate`): sobre CTranslate2 en CPU
     (int8, 15–80ms). Ilimitado, sin red y sin throttle. Se usa para los **captions
     provisionales** (cero peticiones a DeepL) y como red de seguridad de finales.
     Modelos en `modelos/` (306MB, fuera de git).
   - **Gemini** (`gemini_translate`): último recurso (free tier ≈ 20 peticiones/día,
     casi nunca disponible). Mantiene un prompt de estilo (`estilo_glosario.md`) y
     devuelve `resaltados` (números, direcciones, nombres, fechas) que DeepL no marca
     y se generan localmente.

4. **Hilo de las ideas** (`servidor.hilo_decidir`): frases seguidas del **mismo
   idioma** continúan la misma idea: se re-traduce el hilo completo y la fila anterior
   se actualiza conectada. Habla el otro idioma, pasan 45s, o el hilo supera 600
   caracteres → idea nueva. Esto mantiene el sentido de lo que dice el cliente en
   inglés, en lugar de fragmentos sueltos.

5. **UI** (`index.html`): abierta por `interprete.sh` en Brave vía WebSocket
   (`ws://localhost:8765`). Paneles movibles que muestran el original y la traducción
   de cada intervención en vivo, más herramientas de apoyo durante la llamada.

## Paneles de la UI

- **Feed en vivo**: las intervenciones originales (en su idioma) y traducidas, con la
  hora. Botones: captions provisionales, toggle preciso/rápido, apagado de
  transcripción, **tijera ✂** (cierra a mano la idea actual), y **⚠** para reintentar
  una fila que se quedó sin traducir.
- **Notas**: apuntes en tiempo real, persisten en `localStorage`.
- **Panel ⏱ tiempos**: registrar la duración de cada llamada; totales de hoy/semana/mes.
- **Deletrear 🔤**: escribe una palabra y muestra su pronunciación (fonética hispana),
  el alfabeto OTAN y la letra por letra.
- **Chuleta 🔢**: referencia rápida móvil.
- **Ajustes ⚙**: ver el consumo por cuenta DeepL (barras) y las opciones de copiado.
- **Pronunciación**: clic en una palabra de los paneles deletrea/pronuncia.

## Requisitos del sistema

- **Linux** con **PipeWire** y las herramientas de PulseAudio (`pactl`, `parec` —
  paquete `pulseaudio-utils` en Arch/CachyOS).
- **Python 3.12** (faster-whisper no instala en 3.14). Usar `python3.12 -m venv venv`.
- **Brave** (u otro navegador) para mostrar la UI.
- **CPU moderna** (corre en CPU por defecto con el modelo `small`). GPU NVIDIA
  **opcional** con `WHISPER_DEVICE=cuda` si cuBLAS/cuDNN están disponibles; en ese
  caso el `interprete.sh` configura el `LD_LIBRARY_PATH` y detiene `voxtype` para
  liberar VRAM.
- Traductor local OPUS-MT: requiere `sentencepiece` y los modelos en `modelos/`
  (se descargan on-demand; si faltan, la app cae a DeepL sin romperse).

## Instalación y configuración local

```bash
# 1. Entorno de Python (usar 3.12 — importante)
python3.12 -m venv venv
./venv/bin/pip install -r requirements.txt

# 2. Crear el archivo de configuración con tus claves
#    (NO se versiona: está en .gitignore). Copia las claves que necesites.
```

Variables del `.env` (se leen al arrancar `interprete.sh`):

| Variable | Obligatoria | Qué hace |
|----------|-------------|----------|
| `WHISPER_MODEL` | no (default `small`) | Modelo de transcripción: `tiny`→`medium` (más grande = más preciso, más lento). El "preciso" usa `large-v3` por defecto. |
| `WHISPER_MODEL_RAPIDO` | no (default `small`) | Modelo del modo rápido. |
| `WHISPER_DEVICE` | no (default `cpu`) | `cpu` o `cuda` (GPU NVIDIA con cuBLAS/cuDNN en el venv). |
| `DEEPL_API_KEYS` | **sí** | Claves DeepL en cascada: `nombre=key,nombre=key,...` (varias cuentas dan más cuota). |
| `TRADUCTOR` | no (default `deepl`) | Traductor primario: `deepl` o `gemini`. El local es red de seguridad. |
| `GEMINI_API_KEY` | opcional | Clave de Gemini (último recurso; free ≈ 20/día). Requerida también como fallback si no hay DeepL. |

Ejemplo `.env`:

```ini
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
TRADUCTOR=deepl
DEEPL_API_KEYS=micuenta=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
GEMINI_API_KEY=
```

## Uso

```bash
./interprete.sh
```

El script: lee `.env`, abre la UI en Brave, y arranca `servidor.py` escribiendo el
log en `interprete.log` (que no se versiona). La llamada se reproduce por el
altavoz/PC y la herramienta la transcribe y traduce en vivo.

> Nota de privacidad: `respaldos/` e `interprete.log` llevan datos de llamadas reales
> (transcripciones, notas, horas, nombres de cuentas) y por eso están en `.gitignore`.

## Tests

```bash
./venv/bin/python -m pytest
```

Los `.mjs` del frontend (tiempos, chuleta) se corren aparte con `node`.

## Historial de versiones

Ver `VERSIONES.md` (bitácora v1–v44 + chuleta). La versión funcional actual es el
**rollback a v44 + panel Chuleta**.
