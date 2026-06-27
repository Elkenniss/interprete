import motor

def test_build_prompt_incluye_estilo_y_texto():
    p = motor.build_prompt("me duele la espalda", "es2en")
    assert "me duele la espalda" in p
    assert "usted" in p.lower()          # reglas inyectadas
    assert "english" in p.lower() or "inglés" in p.lower()  # dirección
    assert "JSON" in p

def test_build_prompt_direccion_en2es():
    p = motor.build_prompt("What is your address?", "en2es")
    assert "What is your address?" in p
    assert "español" in p.lower() or "spanish" in p.lower()

def test_parse_response_json_plano():
    raw = '{"traduccion":"my back hurts","resaltados":[]}'
    d = motor.parse_response(raw)
    assert d["traduccion"] == "my back hurts"
    assert d["resaltados"] == []

def test_parse_response_con_fences():
    raw = '```json\n{"traduccion":"hola","resaltados":[{"texto":"5th Ave","tipo":"direccion"}]}\n```'
    d = motor.parse_response(raw)
    assert d["traduccion"] == "hola"
    assert d["resaltados"][0]["tipo"] == "direccion"

def test_parse_response_invalido_devuelve_vacio():
    d = motor.parse_response("no soy json")
    assert d["traduccion"] == ""
    assert d["resaltados"] == []
