import motor

def test_deepl_keys_lista(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEYS", "k1, k2 ,,k3")
    assert motor._deepl_keys() == ["k1", "k2", "k3"]

def test_deepl_cuentas_con_nombres(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEYS", "Kenny=k1:fx, lewevog=k2:fx ,k3:fx")
    assert motor._deepl_cuentas() == [("Kenny", "k1:fx"), ("lewevog", "k2:fx"), ("API 3", "k3:fx")]
    assert motor._deepl_keys() == ["k1:fx", "k2:fx", "k3:fx"]

def test_deepl_keys_una_sola(monkeypatch):
    # DEEPL_API_KEY (singular) sigue funcionando si no hay lista
    monkeypatch.delenv("DEEPL_API_KEYS", raising=False)
    monkeypatch.setenv("DEEPL_API_KEY", "solo")
    assert motor._deepl_keys() == ["solo"]

def test_deepl_translate_cascada(monkeypatch):
    # La 1ª key falla → la 2ª responde. Simulamos urlopen sin tocar la red.
    monkeypatch.setenv("DEEPL_API_KEYS", "mala,buena")
    import json, io
    def fake_urlopen(req, timeout=None):
        if "mala" in req.headers["Authorization"]:
            raise OSError("key caída")
        class R(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): pass
        return R(json.dumps({"translations": [{"text": "hola"}]}).encode())
    monkeypatch.setattr(motor.urllib.request, "urlopen", fake_urlopen)
    assert motor.deepl_translate("hello", "en2es")["traduccion"] == "hola"

def test_deepl_translate_todas_fallan(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEYS", "mala1,mala2")
    def fake_urlopen(req, timeout=None):
        raise OSError("todo caído")
    monkeypatch.setattr(motor.urllib.request, "urlopen", fake_urlopen)
    assert motor.deepl_translate("hello", "en2es") == {"traduccion": "", "resaltados": []}

def _urlopen_contador(llamadas, excepcion):
    def fake(req, timeout=None):
        llamadas.append(req.headers["Authorization"])
        raise excepcion
    return fake

def test_solo_primera_no_cascadea(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEYS", "k1,k2,k3")
    monkeypatch.setattr(motor, "_KEY_429", {})
    llamadas = []
    monkeypatch.setattr(motor.urllib.request, "urlopen", _urlopen_contador(llamadas, OSError("x")))
    motor.deepl_translate("hello", "en2es", solo_primera=True)
    assert len(llamadas) == 1 and "k1" in llamadas[0]

def test_breaker_429_salta_la_key(monkeypatch):
    import io, urllib.error
    monkeypatch.setenv("DEEPL_API_KEYS", "k1")
    monkeypatch.setattr(motor, "_KEY_429", {})
    e429 = urllib.error.HTTPError("u", 429, "Too Many Requests", {}, io.BytesIO())
    llamadas = []
    monkeypatch.setattr(motor.urllib.request, "urlopen", _urlopen_contador(llamadas, e429))
    motor.deepl_translate("hello", "en2es")   # 1ª: pide y recibe 429
    motor.deepl_translate("hello", "en2es")   # 2ª: la key descansa, NO pide
    assert len(llamadas) == 1

def test_translate_parcial_prefiere_local(monkeypatch):
    monkeypatch.setattr(motor, "local_translate", lambda o, d: {"traduccion": "¡local!", "resaltados": []})
    def deepl_prohibido(*a, **k):
        raise AssertionError("con local disponible, el parcial no debe llamar a DeepL")
    monkeypatch.setattr(motor, "deepl_translate", deepl_prohibido)
    assert motor.translate("hello", "en2es", parcial=True)["traduccion"] == "¡local!"

def test_translate_final_cae_a_local_antes_que_gemini(monkeypatch):
    monkeypatch.setattr(motor, "deepl_translate",
                        lambda o, d, solo_primera=False: {"traduccion": "", "resaltados": []})
    monkeypatch.setattr(motor, "local_translate", lambda o, d: {"traduccion": "hola", "resaltados": []})
    def gemini_prohibido(o, d):
        raise AssertionError("si el local responde, no debe llegar a Gemini")
    monkeypatch.setattr(motor, "gemini_translate", gemini_prohibido)
    assert motor.translate("hello", "en2es")["traduccion"] == "hola"

def test_translate_parcial_no_usa_gemini(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEYS", "k1,k2")
    monkeypatch.setattr(motor, "_KEY_429", {})
    monkeypatch.setattr(motor, "local_translate", lambda o, d: {"traduccion": "", "resaltados": []})
    monkeypatch.setattr(motor, "deepl_translate",
                        lambda o, d, solo_primera=False: {"traduccion": "", "resaltados": []})
    def gemini_prohibido(o, d):
        raise AssertionError("parcial no debe llamar a Gemini")
    monkeypatch.setattr(motor, "gemini_translate", gemini_prohibido)
    assert motor.translate("hello", "en2es", parcial=True)["traduccion"] == ""
