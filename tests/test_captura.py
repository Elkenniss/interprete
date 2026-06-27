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
