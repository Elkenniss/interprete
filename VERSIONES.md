# Bitácora de versiones — Intérprete en vivo

Cada cambio queda como un commit de git (la "versión"). Aquí va el check manual de Kenny:
- ✅ funciona bien (probado en llamada real)
- ❌ falló — anotar DÓNDE falló, para no repetir el error en la siguiente versión
- ⏳ pendiente de probar

Rollback: pedirle a Claude "regresame a la vN" (git guarda todas).

| Versión | Commit | Fecha | Qué se hizo | Check | Comentario |
|---------|---------|-------|-------------|-------|------------|
| v30 | 5508ecc | 2026-07-05 | Captions en vivo (~0.6-1.3s), toggle preciso/rápido, botón de apagado, log de errores de traducción | ⏳ | Se probó un reintento x3 de DeepL y se revirtió el mismo día: trababa las traducciones hasta 45s. Lección: nada de esperas largas en el camino en vivo. |
| v29 | 9e8f2dc | 2026-07-04 | Quitar delay de la primera frase y bajar latencia de captura | ✅ | Usada en llamadas reales sin problema. |
| v1–v28 | — | 2026-06/07 | Historia previa: ver `git log --oneline` | ✅ | Base estable: captura, Whisper GPU, DeepL/Gemini, UI, notas, tijera, pronunciación. |
