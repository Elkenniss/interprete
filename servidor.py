import asyncio
import json
import os
import threading
import time
import websockets

import captura
import motor

CLIENTS = set()
CORTAR = threading.Event()  # botón tijera: fuerza el cierre del segmento actual
PAUSADO = threading.Event() # botón de apagado: set = la captura descarta todo el audio
# Dos motores: el preciso (large-v3) y uno rápido para cuando el caption tarda.
# Ambos quedan cargados en VRAM tras el primer cambio; el toggle solo mueve el puntero.
MODOS = {"preciso": os.environ.get("WHISPER_MODEL", "large-v3"),
         "rapido": os.environ.get("WHISPER_MODEL_RAPIDO", "small")}
ESTADO = {"modo": "preciso", "model": None}
# Caption provisional: la captura deposita aquí el último snapshot de audio y un
# hilo aparte lo procesa. Slot de 1 (solo el más reciente): si vamos atrasados,
# los snapshots viejos ya no interesan. "gen" invalida parciales de frases cerradas.
PARCIAL = {"pcm": None, "gen": 0}
PARCIAL_EVT = threading.Event()
MODEL_LOCK = threading.Lock()  # transcriben 2 hilos (final y parcial); de a uno

async def broadcast(iv: dict):
    if CLIENTS:
        msg = json.dumps(iv, ensure_ascii=False)
        await asyncio.gather(*(c.send(msg) for c in list(CLIENTS)), return_exceptions=True)

# Hilo de la idea (regla de Kenny): frases seguidas del MISMO idioma continúan la misma
# idea — se re-traduce el hilo completo y la fila anterior se actualiza conectada. Habla
# el otro idioma, pasa mucho rato o el hilo ya es muy largo → idea nueva.
HILO = {"lang": None, "texto": "", "hora": "", "t": 0.0}
HILO_MAX = 600      # chars que se re-traducen por continuación; más allá, fila nueva
HILO_VENTANA = 45   # s sin frases del mismo idioma = idea nueva aunque nadie más hablara

def hilo_decidir(lang, texto):
    """Devuelve (texto_a_traducir, contexto, continuar) y actualiza HILO."""
    ahora = time.monotonic()
    mismo = lang == HILO["lang"] and HILO["texto"] and (ahora - HILO["t"]) < HILO_VENTANA
    if mismo and len(HILO["texto"]) < HILO_MAX:
        HILO["texto"] = HILO["texto"] + " " + texto
        HILO["t"] = ahora
        return HILO["texto"], "", True
    # Hilo largo del mismo idioma: fila nueva, pero conectada vía context de DeepL.
    contexto = HILO["texto"][-300:] if mismo else ""
    HILO.update(lang=lang, texto=texto, t=ahora)
    return texto, contexto, False

def hilo_cerrar():
    # Mini tijera ✂ de la fila: Kenny cierra la idea a mano. Cubre el hueco de las
    # frases cortas ambiguas ("Okay", un nombre) que Whisper etiqueta con el idioma
    # equivocado y por eso no disparan el corte automático por cambio de idioma.
    HILO.update(lang=None, texto="", t=0.0)

async def enviar_uso(ws):
    # Consumo por API al conectar: sin esto, tras un F5 el panel de Ajustes quedaba
    # "sin datos" hasta el siguiente broadcast (cada 20 frases). En executor: son
    # hasta 3 llamadas de red y no deben congelar el saludo del ws.
    uso = await asyncio.get_running_loop().run_in_executor(None, motor.deepl_usage)
    try:
        await ws.send(json.dumps({"tipo": "uso", **uso}))
    except Exception:
        pass

async def retraducir(ws, d):
    # Reintento manual (botón ⚠ de una fila sin traducción). En task aparte: si se
    # hiciera await en el handler, bloquearía la tijera y el resto de botones.
    res = await asyncio.get_running_loop().run_in_executor(
        None, motor.translate, d.get("original", ""),
        motor.lang_to_direction(d.get("idioma", "en")))
    try:
        await ws.send(json.dumps({"tipo": "retrad", "i": d.get("i"), **res},
                                 ensure_ascii=False))
    except Exception:
        pass

async def handler(ws):
    CLIENTS.add(ws)
    try:
        await ws.send(json.dumps({"tipo": "motor", "modo": ESTADO["modo"]}))
        await ws.send(json.dumps({"tipo": "poder", "on": not PAUSADO.is_set()}))
        asyncio.create_task(enviar_uso(ws))
        async for msg in ws:  # el cliente pide la pronunciación de una palabra al hacer clic
            try:
                d = json.loads(msg)
                if d.get("tipo") == "pron":
                    palabra = d.get("palabra", "")
                    await ws.send(json.dumps(
                        {"tipo": "pron", "palabra": palabra, "pron": motor.pronunciacion_es(palabra)},
                        ensure_ascii=False))
                elif d.get("tipo") == "retrad":
                    asyncio.create_task(retraducir(ws, d))
                elif d.get("tipo") == "cortar":
                    CORTAR.set()
                elif d.get("tipo") == "fin_idea":
                    hilo_cerrar()
                elif d.get("tipo") == "poder":  # apagar/encender la transcripción
                    (PAUSADO.clear if PAUSADO.is_set() else PAUSADO.set)()
                    await broadcast({"tipo": "poder", "on": not PAUSADO.is_set()})
                elif d.get("tipo") == "motor":  # toggle preciso <-> rápido
                    nuevo = "rapido" if ESTADO["modo"] == "preciso" else "preciso"
                    # En executor: la 1ª carga del modelo tarda segundos y no debe congelar el ws.
                    ESTADO["model"] = await asyncio.get_running_loop().run_in_executor(
                        None, motor.load_model, MODOS[nuevo])
                    ESTADO["modo"] = nuevo
                    await broadcast({"tipo": "motor", "modo": nuevo})
            except Exception:
                pass
    finally:
        CLIENTS.discard(ws)

def send(loop, msg):
    asyncio.run_coroutine_threadsafe(broadcast(msg), loop)

def dep_parcial(pcm):
    # Corre dentro del bucle de captura: solo deposita y despierta al hilo parcial.
    PARCIAL["pcm"] = pcm
    PARCIAL_EVT.set()

def parciales(loop):
    """Hilo del caption provisional: transcribe y traduce el snapshot más reciente."""
    import time
    ult_trad = 0.0
    while True:
        PARCIAL_EVT.wait()
        PARCIAL_EVT.clear()
        pcm, gen = PARCIAL["pcm"], PARCIAL["gen"]
        if pcm is None:
            continue
        try:
            with MODEL_LOCK:
                texto, lang = motor.transcribe(pcm, ESTADO["model"])
            if texto.strip():
                idioma = "en" if lang == "en" else "es"
                # 1º el original apenas sale de Whisper (traducción vacía = "ya viene"),
                # 2º la traducción cuando DeepL responde. Así el caption no espera la red.
                if gen == PARCIAL["gen"]:
                    send(loop, {"tipo": "parcial", "idioma": idioma,
                                "original": texto, "traduccion": ""})
                # Traducción del caption como máximo cada 1.5s: retraducir el texto
                # creciente cada snapshot gastaba ~5-7x los chars de la frase y el
                # rate disparaba el 429 por IP de DeepL. El original sí va siempre.
                if time.monotonic() - ult_trad < 1.5:
                    continue
                ult_trad = time.monotonic()
                res = motor.translate(texto, motor.lang_to_direction(lang), parcial=True)
                if res["traduccion"] and gen == PARCIAL["gen"]:  # la frase sigue abierta
                    send(loop, {"tipo": "parcial", "idioma": idioma,
                                "original": texto, "traduccion": res["traduccion"]})
        except Exception as e:
            motor.log("[parcial] error, sigo:", e)

def pipeline(loop):
    """Hilo bloqueante: captura → whisper → traducción → broadcast.

    Cada frase va en su propio try: un fallo puntual no mata el hilo ni la llamada.
    """
    ESTADO["model"] = motor.load_model(MODOS[ESTADO["modo"]])
    send(loop, {"tipo": "uso", **motor.deepl_usage()})
    threading.Thread(target=parciales, args=(loop,), daemon=True).start()
    n = 0
    # parcial_ms bajo = caption casi inmediato. El hilo parcial se auto-regula:
    # procesa solo el snapshot más reciente, así que no se encola ni satura.
    for pcm in captura.utterances(cortar=CORTAR, parcial=dep_parcial,
                                  parcial_ms=700, pausado=PAUSADO):
        try:
            PARCIAL["gen"] += 1  # invalida cualquier parcial en vuelo de esta frase
            PARCIAL["pcm"] = None
            with MODEL_LOCK:
                texto, lang = motor.transcribe(pcm, ESTADO["model"])
            iv = None
            if texto.strip():
                a_traducir, ctx, continuar = hilo_decidir(lang, texto.strip())
                iv = motor.process_text(lang, a_traducir,
                        translate_fn=lambda o, d: motor.translate(o, d, contexto=ctx))
            send(loop, {"tipo": "parcial_fin"})  # borra el caption provisional
            if iv:
                if continuar:
                    iv["hora"] = HILO["hora"]  # la fila conserva la hora en que empezó la idea
                else:
                    HILO["hora"] = iv["hora"]
                iv["continuar"] = continuar
                send(loop, iv)
                n += 1
                if n % 20 == 0:  # refresca el medidor de cuota cada ~20 frases
                    send(loop, {"tipo": "uso", **motor.deepl_usage()})
        except Exception as e:
            motor.log("[pipeline] error en una frase, sigo:", e)

async def main():
    loop = asyncio.get_running_loop()
    async with websockets.serve(handler, "localhost", 8765):
        print("WebSocket en ws://localhost:8765 — habla la llamada…")
        await loop.run_in_executor(None, pipeline, loop)

if __name__ == "__main__":
    asyncio.run(main())
