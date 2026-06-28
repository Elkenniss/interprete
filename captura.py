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
    # parec se engancha al monitor por nombre de forma fiable; pw-record --target
    # por nombre no captura el monitor (cae a una fuente muda).
    return ["parec", "--device=" + monitor,
            "--rate=" + str(RATE), "--channels=1", "--format=s16le"]

def _rms(frame: bytes) -> float:
    x = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(x * x))) if len(x) else 0.0

class Segmenter:
    def __init__(self, rms_threshold=500, hang_ms=1000, min_ms=300, max_ms=15000):
        self.threshold = rms_threshold
        self.hang_frames = max(1, hang_ms // FRAME_MS)
        self.min_frames = max(1, min_ms // FRAME_MS)
        self.max_frames = max(1, max_ms // FRAME_MS)
        self.buf = []
        self.silence = 0
        self.in_speech = False

    def feed(self, frame: bytes):
        speech = _rms(frame) >= self.threshold
        if speech:
            self.in_speech = True
            self.silence = 0
            self.buf.append(frame)
            if len(self.buf) >= self.max_frames:
                out = b"".join(self.buf)
                self.buf = []
                self.silence = 0
                self.in_speech = False
                return out
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

    def flush(self):
        """Cierre forzado (botón tijera): devuelve la voz acumulada ya mismo,
        sin esperar el silencio y sin exigir min_ms. None si no hay nada."""
        if not self.buf:
            return None
        speech_frames = len(self.buf) - self.silence
        frames = self.buf[:speech_frames] if speech_frames > 0 else self.buf
        self.buf = []
        self.silence = 0
        self.in_speech = False
        return b"".join(frames) or None

def utterances(monitor=None, cortar=None):
    """Generador: lanza parec y produce PCM por intervención.

    Si parec muere a mitad de llamada (cambio de dispositivo, hipo del sistema),
    se relanza solo en vez de cortar la captura — una llamada dura horas.
    `cortar` (threading.Event opcional): si está set, fuerza el cierre inmediato
    del segmento actual (botón tijera), además del corte automático por silencio.
    """
    import time
    monitor = monitor or monitor_source()
    seg = Segmenter()
    while True:
        proc = subprocess.Popen(record_command(monitor), stdout=subprocess.PIPE)
        try:
            while True:
                frame = proc.stdout.read(FRAME_BYTES)
                if len(frame) < FRAME_BYTES:
                    break  # parec murió: salimos a relanzarlo
                out = seg.feed(frame)
                if out is not None:
                    yield out
                if cortar is not None and cortar.is_set():
                    cortar.clear()
                    forced = seg.flush()
                    if forced is not None:
                        yield forced
        finally:
            proc.terminate()
        print("[captura] parec se detuvo; relanzando en 1s…", flush=True)
        time.sleep(1)
