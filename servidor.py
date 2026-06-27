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

def send(loop, msg):
    asyncio.run_coroutine_threadsafe(broadcast(msg), loop)

def pipeline(loop):
    """Hilo bloqueante: captura → whisper → traducción → broadcast.

    Cada frase va en su propio try: un fallo puntual no mata el hilo ni la llamada.
    """
    model = motor.load_model()
    send(loop, {"tipo": "uso", **motor.deepl_usage()})
    n = 0
    for pcm in captura.utterances():
        try:
            texto, lang = motor.transcribe(pcm, model)
            iv = motor.process_text(lang, texto)
            if iv:
                send(loop, iv)
                n += 1
                if n % 20 == 0:  # refresca el medidor de cuota cada ~20 frases
                    send(loop, {"tipo": "uso", **motor.deepl_usage()})
        except Exception as e:
            print("[pipeline] error en una frase, sigo:", e, flush=True)

async def main():
    loop = asyncio.get_running_loop()
    async with websockets.serve(handler, "localhost", 8765):
        print("WebSocket en ws://localhost:8765 — habla la llamada…")
        await loop.run_in_executor(None, pipeline, loop)

if __name__ == "__main__":
    asyncio.run(main())
