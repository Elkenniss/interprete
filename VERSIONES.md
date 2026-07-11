# Bitácora de versiones — Intérprete en vivo

Cada cambio queda como un commit de git (la "versión"). Aquí va el check manual de Kenny:
- ✅ funciona bien (probado en llamada real)
- ❌ falló — anotar DÓNDE falló, para no repetir el error en la siguiente versión
- ⏳ pendiente de probar

Rollback: pedirle a Claude "regresame a la vN" (git guarda todas).

| Versión | Commit | Fecha | Qué se hizo | Check | Comentario |
|---------|---------|-------|-------------|-------|------------|
| v36 | 9b6f353 | 2026-07-11 | 3 APIs DeepL en cascada con nombre (Kenny/lewevog/pijosot = 3M chars/mes); panel ⚙ Ajustes (movible) con consumo por API en barras + ⚠ en header solo si una llega a su límite; en Notas: 📅 días+meses (inglés→español+pronunciación) y 🔢 números→inglés hablado con pronunciación (año, dígito a dígito, decimales) — todo local, 0 tokens. | ⏳ | Reiniciada por Claude (+90a2134: consumo llega al conectar). Pestaña vieja de Brave: Limpiar y cerrar. |
| v35 | 41eefa0 | 2026-07-11 | Bug "filas sin traducción": DeepL falló en ráfaga (11:24–11:26) y el respaldo Gemini ya estaba muerto (free tier ahora = 20 peticiones/DÍA). Fix: (1) varias keys DeepL en cascada (`DEEPL_API_KEYS=k1,k2,...` en .env; Gemini queda de último recurso), (2) botón ⚠ reintentar en filas sin traducción, (3) logs a `interprete.log` (antes iban a /dev/null desde el ícono), (4) timeout DeepL 15s→6s (fail-fast). | ⏳ | Requiere reiniciar la app. Faltan las 2 keys DeepL extra de Kenny. |
| v34 | 5c08bde | 2026-07-11 | Fix: Notas no abrían — un click en la cabecera sin arrastrar guardaba posición vacía y el panel quedaba fuera de pantalla al recargar. Ahora solo guarda con arrastre real y sujeta la posición al viewport (se autocura solo). | ✅ | Probado por Kenny 2026-07-11: las Notas vuelven a abrir. Aplica también a Deletrear. |
| v33 | 00c3197 | 2026-07-05 | Deletreo: corrige E (`Ii`→`Íi`) y U (`Iu`→`Yu`); la I mayúscula se veía como l. | ⏳ | Recargar Brave (F5). |
| v32 | 93656d1 | 2026-07-05 | Panel de deletreo movible (arrastre reutilizable `hacerMovible`, aplicado a Notas y Deletreo). Regla: toda ventana flotante debe ser movible. | ⏳ | Recargar Brave (F5). Se arrastra por la cabecera negra. |
| v31 | 126590c | 2026-07-05 | Panel 🔤 Deletrear: escribir palabra → filas letra a letra (nombre inglés + OTAN + pronunciación) + botón Ver A-Z. Solo frontend. | ⏳ | Recargar la pestaña de Brave (F5) para verlo. |
| v30 | 5508ecc | 2026-07-05 | Captions en vivo (~0.6-1.3s), toggle preciso/rápido, botón de apagado, log de errores de traducción | ⏳ | Se probó un reintento x3 de DeepL y se revirtió el mismo día: trababa las traducciones hasta 45s. Lección: nada de esperas largas en el camino en vivo. |
| v29 | 9e8f2dc | 2026-07-04 | Quitar delay de la primera frase y bajar latencia de captura | ✅ | Usada en llamadas reales sin problema. |
| v1–v28 | — | 2026-06/07 | Historia previa: ver `git log --oneline` | ✅ | Base estable: captura, Whisper GPU, DeepL/Gemini, UI, notas, tijera, pronunciación. |
