# Intérprete en vivo — Documento de diseño

Fecha: 2026-06-27
Autor: Kenny (con Claude)
Estado: aprobado para planificar

## Propósito

Herramienta personal para trabajo remoto de interpretación telefónica (OPI) inglés↔español.
Captura las dos voces de la llamada que salen por la PC, las transcribe y traduce en tiempo
real, y las muestra en pantalla en dos paneles para que Kenny lea y dé su interpretación de
voz. Sustituto local y a medida de herramientas tipo "Interpreter" / DeepL, con las reglas
de estilo profesional de Kenny incorporadas.

Trabaja "smart, not hard": Kenny no pierde números, direcciones, nombres ni fechas, y lee la
interpretación ya redactada en primera persona y registro formal.

## Alcance (y lo que NO es)

Incluye:
- Captura de audio del monitor de salida de la PC (ambas voces remotas; no el micrófono de Kenny).
- Reconocimiento de voz local en GPU con detección de idioma por intervención.
- Traducción con Gemini aplicando reglas de estilo + glosario LEP.
- Resaltado de números/cantidades, direcciones, nombres propios y fechas/horas.
- UI local de dos paneles (español izquierda, inglés derecha), cada uno con columnas
  original + interpretación, que se llena en tiempo real.

NO incluye (YAGNI):
- Síntesis de voz / TTS (Kenny habla él mismo).
- Captura/transcripción del micrófono de Kenny.
- Tira de frases de intervención (descartada por Kenny).
- Login, multiusuario, persistencia en nube, cumplimiento HIPAA formal.

## Entorno

- CachyOS (Arch), Hyprland/Wayland.
- GPU NVIDIA GTX 1660 SUPER, 6 GB VRAM (CUDA) → Whisper local en tiempo real.
- CPU i5-10400F (12 hilos), 31 GB RAM.
- PipeWire (`pw-record`, `pactl`, `wpctl`).
- Python 3.14.
- Navegador Brave.

## Enfoque elegido

Whisper local (GPU) para STT + Gemini para traducción + UI web local servida por el propio
proceso Python. Razón: STT gratis y rápido en la GPU de Kenny; Gemini da la mejor calidad
español↔inglés con coloquialismos y resaltado; todo corre en la PC con costo mínimo (solo
centavos por las llamadas de traducción).

Alternativas descartadas: todo en la nube (caro por hora, todo el audio sale de la PC);
todo local con traductor offline tipo Argos (calidad menor con la jerga del LEP).

## Arquitectura

```
Audio de la llamada (ambas voces) por la salida de la PC
   │  pw-record sobre el monitor del sink de salida
   ▼
[VAD]  segmenta por silencios → un trozo = una intervención
   ▼
[faster-whisper en CUDA]  transcribe + detecta idioma (restringido a en/es)
   ▼
   ├─ idioma = en  → Gemini traduce a español → PANEL DERECHO (rep inglés)
   └─ idioma = es  → Gemini traduce a inglés   → PANEL IZQUIERDO (LEP español)
        (Gemini devuelve JSON: { traduccion, resaltados:[{texto, tipo}] })
   ▼
[WebSocket]  empuja la intervención al navegador
   ▼
[index.html]  la pinta en la columna correcta, con chips de resaltado
```

## Componentes

Archivos en `~/interprete/`, mínimos y de responsabilidad única:

1. **`captura.py`** — Lanza `pw-record` sobre el monitor del sink de salida por defecto.
   Aplica VAD (Silero, incluido en faster-whisper, o webrtcvad) para cortar por silencios y
   entregar trozos de voz (PCM 16 kHz mono). Expone un generador de "intervenciones de audio".

2. **`motor.py`** — Carga `faster-whisper` (modelo `medium`, `compute_type=int8_float16` en
   CUDA). Por cada trozo: transcribe con `language` autodetectado restringido a {en, es},
   obtiene texto + idioma. Luego llama a Gemini con el prompt de estilo (ver abajo) y el
   glosario, recibe JSON `{ traduccion, resaltados }`. Devuelve una intervención completa:
   `{ idioma, original, traduccion, resaltados, hora }`.

3. **`servidor.py`** — Orquesta: consume audio de `captura.py`, lo pasa por `motor.py`, y
   empuja cada intervención por WebSocket. Sirve también `index.html` en `localhost`.
   Implementación mínima (p. ej. `websockets` + `http.server`, o `aiohttp` si se prefiere
   un solo runtime async). Sin framework pesado.

4. **`index.html`** — Una sola página, sin frameworks. Dos paneles principales (CSS grid):
   izquierdo 🇪🇸 LEP, derecho 🇺🇸 representante. Cada panel = 2 columnas (original | inter-
   pretación). Cada intervención es una fila con hora, original, interpretación y chips de
   resaltado por color según tipo. Autoscroll al final; la fila nueva se resalta un instante.

5. **`estilo_glosario.md`** — Texto que `motor.py` inyecta en el prompt de Gemini. Contiene
   las reglas de estilo y el glosario LEP ya limpio (ver Apéndices). Editable sin tocar código.

6. **`interprete.sh`** — Arranca `servidor.py` y abre Brave en `localhost`.

## Reglas de estilo (van en el prompt de Gemini)

1. **Primera persona / habla directa** en ambas direcciones.
   - Rep: "I'm glad to see you" → "Me alegra verle hoy" (no "el doctor dice que…").
   - LEP: "me duele la espalda" → "My back hurts".
   - Excepción a tercera persona: cuando la primera persona confunde al LEP (salud mental,
     niños) o en emergencias.
2. **Registro formal y respetuoso: SIEMPRE "usted / le", NUNCA "tú / te"**, para ambas partes.
3. **Glosario LEP**: resolver regionalismos del español a su significado real antes de traducir
   (p. ej. "guagua/camión"→bus, "aseguranza"→insurance company, "troca"→pickup truck).
4. **LEP** = el hispanohablante; término interno, jamás aparece en la traducción ni se dice.
5. Salida estricta en JSON `{ "traduccion": "...", "resaltados": [{"texto":"...","tipo":"numero|direccion|nombre|fecha"}] }`.

## Resaltado

Cuatro tipos, marcados por Gemini en la misma llamada de traducción y pintados como chips de
color en la UI:
- `numero` — teléfonos, dinero, dosis, códigos, números de caso/cuenta, porcentajes.
- `direccion` — calles, ciudades, códigos postales, direcciones completas.
- `nombre` — personas, empresas, medicamentos, lugares.
- `fecha` — fechas, horas, días, plazos, citas.

## Flujo de datos (una intervención)

1. `captura.py` detecta fin de habla → emite trozo PCM.
2. `motor.py` → Whisper: `{texto, idioma}`.
3. `motor.py` → Gemini con prompt de estilo+glosario: `{traduccion, resaltados}`.
4. `servidor.py` → WebSocket: `{idioma, original, traduccion, resaltados, hora}`.
5. `index.html` → fila en la columna del idioma detectado.

## Manejo de errores

- Whisper no detecta en/es o confianza muy baja → marca la fila como "?" y muestra solo el
  original (sin traducir) para que Kenny decida; no rompe el flujo.
- Fallo de red / Gemini → muestra el original con aviso "sin traducir (reintentar)"; la sesión
  sigue. Reintento simple una vez.
- `pw-record` o sink no disponible → mensaje claro al arrancar con el comando para listar sinks.
- Sin API key de Gemini → `interprete.sh` avisa y no arranca el motor de traducción.

## Prerrequisitos

- API key nueva de Gemini (la anterior se borró). Crearla en Google AI Studio; guardarla en
  una variable de entorno (`GEMINI_API_KEY`) o archivo local fuera de git. Se documenta en
  `.gitignore`.
- Dependencias Python: `faster-whisper`, cliente de Gemini (`google-genai`) o `requests`,
  librería de WebSocket. Instalación en venv del proyecto.

## Rendimiento esperado

Latencia ~1–1.5 s desde que la persona deja de hablar (VAD + Whisper en GPU + 1 llamada a
Gemini). Suficiente para leer y dar la interpretación.

## Criterios de éxito

- Las dos voces de una llamada real aparecen, cada una en su panel, original + interpretación.
- La interpretación sale en primera persona y en "usted/le", nunca "tú/te".
- Regionalismos del glosario se traducen correctamente (prueba: "guagua", "aseguranza", "troca").
- Números, direcciones, nombres y fechas aparecen resaltados.
- Arranca con un comando y se abre solo en Brave.

## Apéndice A — Glosario LEP (limpio, desde LEP DICTIONARY.md)

Términos (español regional → significado/inglés):
- Aliviar → dar a luz (contexto médico/OBGYN)
- Rabadilla → coxis / base de la columna
- Esquechar / esquecho → agendar una cita (schedule an appointment)
- Piscar / la pisca → cosechar fruta o plantas (picking)
- Corrida → cosecha (picking) — "la corrida de la cherry"
- Coyunturas → articulaciones (joints)
- Chamorro → pantorrilla (calf)
- Cava → parte de atrás de la rodilla
- Puyar / me puya → punzada / dolor punzante (prick / stabbing pain)
- Campo → finca (farm)
- Envoi → factura (invoice)
- Troca → camioneta pickup (pickup truck)
- Reca → grúa (tow truck)
- Pacha → biberón (baby bottle)
- La Yaré → IRS (a veces confundido con el Depto. de impuestos de NY)
- Aseguranza → compañía de seguros (insurance company, cualquier tipo)
- Ocupar → necesitar (need)
- Elenai → LNI / Labor & Industries
- Camión → bus
- Guagua → bus
- Alberca → piscina (pool)
- Wachar → mirar, vigilar (look/watch)
- Banqueta → acera (sidewalk)
- Traila → casa móvil (trailer home)
- Culebrilla / el chingo → herpes zóster (shingles)
- Billes → cuentas/facturas (bills)
- Talones de cheque → recibos de pago (pay/check stubs)
- Sonografía → ecografía (ultrasound)
- Citología / Papanicolado → Pap smear
- Baisam → sótano (basement)
- Conerico → Connecticut
- Visícula → vesícula (gallbladder)
- Chocho → área pélvica / vagina
- Patilla → sandía (watermelon)
- Cheve → cerveza (beer)
- Espinazo → columna (spine)
- Pachar → presionar/empujar, a menudo botones (push)
- Estampillas / Fucstan → SNAP / cupones de alimentos (food stamps)
- Las ayudas → beneficios, programas de apoyo (benefits)
- Amasar → masaje (massage)
- Carcañal → talón / hueso calcáneo (heel)
- Juntados → pareja que vive junta (estado civil)
- Chai sopol → manutención infantil (child support)
- Menear → moverse de un lugar a otro
- Chismanyir → gestor de caso (case manager)

Expresiones:
- "Dímele tú a ella" → Please, tell her.
- "¿Cómo así, oiga?" → I didn't understand.
- "Le llamo pa'tras" → I'll call you back.
- "Me llegó una calta" → (señal de que será una llamada larga)

Nota: el glosario se mantiene en `estilo_glosario.md` y puede crecer con el uso.
