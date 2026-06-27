import json
import re
from pathlib import Path

_ESTILO = None

def load_estilo() -> str:
    global _ESTILO
    if _ESTILO is None:
        _ESTILO = Path(__file__).with_name("estilo_glosario.md").read_text(encoding="utf-8")
    return _ESTILO

def build_prompt(original: str, direction: str) -> str:
    destino = "inglés (English)" if direction == "es2en" else "español"
    return (
        f"{load_estilo()}\n\n"
        f"Traduce el siguiente texto al {destino}, aplicando TODAS las reglas de arriba.\n"
        f"Texto:\n\"\"\"\n{original}\n\"\"\"\n\n"
        "Responde SOLO con JSON válido, sin texto extra, con esta forma exacta:\n"
        '{"traduccion": "<la traducción>", '
        '"resaltados": [{"texto": "<fragmento del texto>", "tipo": "numero|direccion|nombre|fecha"}]}\n'
        "Incluye en resaltados los números/cantidades, direcciones, nombres propios y fechas/horas "
        "que aparezcan (en el idioma de la traducción). Si no hay, deja la lista vacía."
    )

def parse_response(raw: str) -> dict:
    s = re.sub(r"^```json\s*|\s*```$", "", raw.strip())
    try:
        d = json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*?\}", s, re.DOTALL)
        if not m:
            return {"traduccion": "", "resaltados": []}
        try:
            d = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {"traduccion": "", "resaltados": []}
    return {"traduccion": str(d.get("traduccion", "")), "resaltados": d.get("resaltados", []) or []}
