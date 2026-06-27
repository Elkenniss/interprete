from pathlib import Path

def test_estilo_glosario_tiene_reglas_y_glosario():
    txt = Path("estilo_glosario.md").read_text(encoding="utf-8")
    # reglas clave
    assert "primera persona" in txt.lower()
    assert "usted" in txt.lower()
    assert "nunca" in txt.lower() and "tú" in txt.lower()
    # muestras del glosario
    assert "guagua" in txt.lower()
    assert "aseguranza" in txt.lower()
    assert "troca" in txt.lower()
