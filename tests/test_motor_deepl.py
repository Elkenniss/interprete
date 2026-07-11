import motor

def test_deepl_keys_lista(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEYS", "k1, k2 ,,k3")
    assert motor._deepl_keys() == ["k1", "k2", "k3"]

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
