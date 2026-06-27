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
