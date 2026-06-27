import numpy as np
import motor

def test_pcm_a_float32_normaliza():
    pcm = np.array([0, 32767, -32768], dtype=np.int16).tobytes()
    f = motor.pcm_to_float32(pcm)
    assert f.dtype == np.float32
    assert abs(f[1] - 1.0) < 0.01
    assert abs(f[2] + 1.0) < 0.01
