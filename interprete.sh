#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ -f .env ]; then set -a; . ./.env; set +a; fi
if [ -z "$GEMINI_API_KEY" ]; then
  echo "Falta GEMINI_API_KEY. Crea ~/interprete/.env con GEMINI_API_KEY=... o expórtala." >&2
  exit 1
fi
# faster-whisper en GPU necesita las libs CUDA del venv (cuBLAS/cuDNN) en el loader.
if [ "$WHISPER_DEVICE" = "cuda" ]; then
  SP=$(./venv/bin/python -c "import site;print(site.getsitepackages()[0])")
  export LD_LIBRARY_PATH="$SP/nvidia/cublas/lib:$SP/nvidia/cudnn/lib:$LD_LIBRARY_PATH"
  # voxtype (daemon Vulkan) compite por la VRAM con large-v3; lo paramos para dar aire
  # y lo reactivamos solos al cerrar la app (fin del servidor, Ctrl+C o kill).
  systemctl --user stop voxtype.service 2>/dev/null || true
  trap 'systemctl --user start voxtype.service 2>/dev/null || true' EXIT
fi
brave "file://$PWD/index.html" >/dev/null 2>&1 &
# Sin 'exec': así el trap de arriba corre al terminar el servidor.
./venv/bin/python servidor.py
