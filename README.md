# Intérprete en vivo

Transcribe y traduce en tiempo real las dos voces de una llamada OPI.

## Uso
1. `export GEMINI_API_KEY=...`
2. `./interprete.sh`
3. Habla la llamada por la PC; lee los paneles en Brave.

## Requisitos
- CPU moderno (corre en CPU por defecto, modelo `small`). GPU NVIDIA opcional con `WHISPER_DEVICE=cuda` si cuBLAS/cuDNN están disponibles.
- PipeWire, Brave.
- `python3 -m venv venv && ./venv/bin/pip install -r requirements.txt`
- Si faster-whisper no instala en Python 3.14, usar `python3.12 -m venv venv`.
- Latencia/precisión configurable con `WHISPER_MODEL` (tiny < base < small < medium).
