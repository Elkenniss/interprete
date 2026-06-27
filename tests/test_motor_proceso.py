import motor

def fake_translate(original, direction):
    return {"traduccion": "TRAD:" + original, "resaltados": [{"texto": "x", "tipo": "numero"}]}

def test_lang_to_direction():
    assert motor.lang_to_direction("es") == "es2en"
    assert motor.lang_to_direction("en") == "en2es"
    assert motor.lang_to_direction("pt") == "es2en"  # lengua romance maldetectada → español

def test_process_text_es_va_a_izquierda():
    iv = motor.process_text("es", "me duele", translate_fn=fake_translate)
    assert iv["idioma"] == "es"
    assert iv["original"] == "me duele"
    assert iv["traduccion"] == "TRAD:me duele"
    assert iv["resaltados"][0]["tipo"] == "numero"
    assert len(iv["hora"]) == 8  # HH:MM:SS

def test_process_text_en_normaliza_idioma():
    assert motor.process_text("en", "hello", translate_fn=fake_translate)["idioma"] == "en"
    assert motor.process_text("pt", "hola", translate_fn=fake_translate)["idioma"] == "es"

def test_process_text_vacio_devuelve_none():
    assert motor.process_text("es", "   ", translate_fn=fake_translate) is None
