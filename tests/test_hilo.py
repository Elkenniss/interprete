import json
import io

import motor
import servidor

def _reset():
    servidor.HILO.update(lang=None, texto="", hora="", t=0.0)

def test_mismo_idioma_continua():
    _reset()
    t1, ctx1, cont1 = servidor.hilo_decidir("es", "A veces saco tiempo para ir a")
    t2, ctx2, cont2 = servidor.hilo_decidir("es", "la montaña a dar un paseo.")
    assert (t1, cont1) == ("A veces saco tiempo para ir a", False)
    assert t2 == "A veces saco tiempo para ir a la montaña a dar un paseo."
    assert cont2 is True and ctx2 == ""

def test_otro_idioma_reinicia():
    _reset()
    servidor.hilo_decidir("es", "buenos días")
    t, ctx, cont = servidor.hilo_decidir("en", "good morning")
    assert (t, ctx, cont) == ("good morning", "", False)
    # y al volver el español, también parte de cero (el inglés cerró su idea)
    t, ctx, cont = servidor.hilo_decidir("es", "sí, claro")
    assert (t, ctx, cont) == ("sí, claro", "", False)

def test_pausa_larga_reinicia():
    _reset()
    servidor.hilo_decidir("es", "hola")
    servidor.HILO["t"] -= servidor.HILO_VENTANA + 1
    t, ctx, cont = servidor.hilo_decidir("es", "otra idea")
    assert (t, ctx, cont) == ("otra idea", "", False)

def test_hilo_largo_corta_con_contexto():
    _reset()
    servidor.hilo_decidir("es", "x" * (servidor.HILO_MAX + 10))
    t, ctx, cont = servidor.hilo_decidir("es", "sigue la historia")
    assert cont is False and t == "sigue la historia"
    assert ctx and len(ctx) <= 300  # fila nueva pero conectada vía context

def test_tijera_manual_cierra_idea():
    _reset()
    servidor.hilo_decidir("en", "And the name on the account?")
    servidor.hilo_cerrar()
    t, ctx, cont = servidor.hilo_decidir("en", "Can you tell me your date of birth?")
    assert (t, ctx, cont) == ("Can you tell me your date of birth?", "", False)

def test_deepl_manda_contexto(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEYS", "k1")
    monkeypatch.setattr(motor, "_KEY_429", {})
    cuerpos = []
    def fake_urlopen(req, timeout=None):
        cuerpos.append(req.data.decode())
        class R(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): pass
        return R(json.dumps({"translations": [{"text": "ok"}]}).encode())
    monkeypatch.setattr(motor.urllib.request, "urlopen", fake_urlopen)
    motor.deepl_translate("la montaña", "es2en", contexto="A veces saco tiempo")
    assert "context=" in cuerpos[0]
    motor.deepl_translate("hola", "es2en")
    assert "context=" not in cuerpos[1]
