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
