import numpy as np
import captura

def _frame(amp):
    return (np.ones(480, dtype=np.int16) * amp).tobytes()  # 480 samples = 30ms

def test_frame_bytes():
    assert captura.FRAME_BYTES == 960

def test_record_command_tiene_formato():
    cmd = captura.record_command("foo.monitor")
    assert "parec" in cmd[0]
    assert "--device=foo.monitor" in cmd
    assert "--rate=16000" in cmd
    assert "--format=s16le" in cmd

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

def test_segmenter_corta_por_longitud_maxima():
    seg = captura.Segmenter(rms_threshold=500, hang_ms=700, min_ms=30, max_ms=90)  # max 3 frames
    assert seg.feed(_frame(3000)) is None
    assert seg.feed(_frame(3000)) is None
    out = seg.feed(_frame(3000))
    assert out is not None
    assert len(out) == 3 * captura.FRAME_BYTES

def test_utterances_emite_parciales(monkeypatch):
    # parec falso: 40 frames de habla (1.2s) y luego silencio hasta cerrar por hang.
    import io
    audio = _frame(3000) * 40 + _frame(0) * 40

    class FakeProc:
        def __init__(self):
            self.stdout = io.BytesIO(audio)
        def terminate(self):
            pass

    procs = iter([FakeProc()])
    monkeypatch.setattr(captura.subprocess, "Popen",
                        lambda *a, **k: next(procs))  # 2ª llamada: StopIteration corta el test
    parciales = []
    gen = captura.utterances(monitor="fake", parcial=parciales.append, parcial_ms=300)
    try:
        finales = [next(gen)]
    except StopIteration:
        finales = []
    # parcial_ms=300 => snapshot cada 10 frames de habla: crecen y llegan varios
    assert len(parciales) >= 2
    assert len(parciales[0]) < len(parciales[1])
    assert len(parciales[0]) == 10 * captura.FRAME_BYTES
    # y la frase final completa salió igual que siempre (40 frames de habla)
    assert finales and len(finales[0]) == 40 * captura.FRAME_BYTES

def test_utterances_pausado_descarta_todo(monkeypatch):
    # Mismo audio que arriba, pero con el interruptor apagado: ni parciales ni frases.
    import io, threading, time
    audio = _frame(3000) * 40 + _frame(0) * 40

    class FakeProc:
        def __init__(self):
            self.stdout = io.BytesIO(audio)
        def terminate(self):
            pass

    procs = iter([FakeProc()])
    monkeypatch.setattr(captura.subprocess, "Popen", lambda *a, **k: next(procs))
    monkeypatch.setattr(time, "sleep", lambda s: None)
    pausado = threading.Event()
    pausado.set()
    parciales = []
    gen = captura.utterances(monitor="fake", parcial=parciales.append,
                             parcial_ms=300, pausado=pausado)
    try:
        out = next(gen)
        assert False, f"apagado no debería emitir nada, emitió {len(out)} bytes"
    except RuntimeError:  # el 2º Popen agota el iter: fin del audio sin emisiones
        pass
    assert parciales == []

def test_flush_fuerza_cierre_inmediato():
    seg = captura.Segmenter(rms_threshold=500, hang_ms=700, min_ms=300)
    for _ in range(4):                 # 4 frames de habla, aún sin silencio
        assert seg.feed(_frame(3000)) is None
    out = seg.flush()                  # tijera: cierra ya, ignora hang y min_ms
    assert out is not None
    assert len(out) == 4 * captura.FRAME_BYTES
    assert seg.flush() is None         # ya vacío
