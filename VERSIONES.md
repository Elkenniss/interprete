# Bitácora de versiones — Intérprete en vivo

Cada cambio queda como un commit de git (la "versión"). Aquí va el check manual de Kenny:
- ✅ funciona bien (probado en llamada real)
- ❌ falló — anotar DÓNDE falló, para no repetir el error en la siguiente versión
- ⏳ pendiente de probar

Rollback: pedirle a Claude "regresame a la vN" (git guarda todas).

| Versión | Commit | Fecha | Qué se hizo | Check | Comentario |
|---------|---------|-------|-------------|-------|------------|
| v40 | 494a0f9 | 2026-07-11 | Conexión de ideas (regla de Kenny): fragmentos seguidos del mismo idioma se unen en la misma fila y se re-traducen completos (conectados); el otro idioma, 45s de pausa o hilo >600 chars cierran la idea (hilo largo sigue conectado vía `context` de DeepL, no facturado). Verificado e2e con audio Piper. | ⏳ | Recargar Brave (F5): el frontend cambió. |
| v39 | 3d0c9d1 | 2026-07-11 | Traductor LOCAL (OPUS-MT en↔es sobre CTranslate2, CPU int8, 15-80ms): los captions provisionales ya no tocan DeepL (cero 429 posibles, funciona sin internet) y es red de seguridad de finales antes que Gemini. DeepL queda solo para finales (~1 req/10-15s, bajo el burst limit por IP). Modelos y sentencepiece verificados por subagente de seguridad (veredicto SEGURO). requirements: sentencepiece==0.2.1; modelos/ (306MB) fuera de git. | ⏳ | Reiniciada por Claude. Probar con el video de YouTube de nuevo. |
| v38 | 104db33 | 2026-07-11 | Anti-ráfaga tras test de Kenny (12:21): DeepL free throttlea POR IP (las 3 cuentas dieron 429 a la vez) y la cascada lo alimentaba (4x peticiones). Fix: breaker 10s por key tras 429 (salta, no espera); captions parciales con UN intento (key primaria, sin cascada ni Gemini) y traducción máx cada 1.5s (menos rate y ~mitad de chars). El 2º fallo del test (12:23) fue el internet de Kenny (DNS caído ~10s), no la app. | ⏳ | Solo backend; reiniciada por Claude. Las filas ⚠ del test se recuperan con clic. |
| v37 | 6b524e2 | 2026-07-11 | Botón ⏱ en Notas: registro de tiempos en llamada — se escribe el tiempo, Enter lo guarda con fecha/hora automáticas, 🗑 por entrada; persiste en localStorage (`interprete_tiempos`), separado de las notas libres. Solo frontend. | ⏳ | Recargar la pestaña de Brave (F5) para verlo. |
| v36 | 9b6f353 | 2026-07-11 | 3 APIs DeepL en cascada con nombre (Kenny/lewevog/pijosot = 3M chars/mes); panel ⚙ Ajustes (movible) con consumo por API en barras + ⚠ en header solo si una llega a su límite; en Notas: 📅 días+meses (inglés→español+pronunciación) y 🔢 números→inglés hablado con pronunciación (año, dígito a dígito, decimales) — todo local, 0 tokens. | ⏳ | Reiniciada por Claude (+90a2134: consumo llega al conectar). Pestaña vieja de Brave: Limpiar y cerrar. |
| v35 | 41eefa0 | 2026-07-11 | Bug "filas sin traducción": DeepL falló en ráfaga (11:24–11:26) y el respaldo Gemini ya estaba muerto (free tier ahora = 20 peticiones/DÍA). Fix: (1) varias keys DeepL en cascada (`DEEPL_API_KEYS=k1,k2,...` en .env; Gemini queda de último recurso), (2) botón ⚠ reintentar en filas sin traducción, (3) logs a `interprete.log` (antes iban a /dev/null desde el ícono), (4) timeout DeepL 15s→6s (fail-fast). | ⏳ | Requiere reiniciar la app. Faltan las 2 keys DeepL extra de Kenny. |
| v34 | 5c08bde | 2026-07-11 | Fix: Notas no abrían — un click en la cabecera sin arrastrar guardaba posición vacía y el panel quedaba fuera de pantalla al recargar. Ahora solo guarda con arrastre real y sujeta la posición al viewport (se autocura solo). | ✅ | Probado por Kenny 2026-07-11: las Notas vuelven a abrir. Aplica también a Deletrear. |
| v33 | 00c3197 | 2026-07-05 | Deletreo: corrige E (`Ii`→`Íi`) y U (`Iu`→`Yu`); la I mayúscula se veía como l. | ⏳ | Recargar Brave (F5). |
| v32 | 93656d1 | 2026-07-05 | Panel de deletreo movible (arrastre reutilizable `hacerMovible`, aplicado a Notas y Deletreo). Regla: toda ventana flotante debe ser movible. | ⏳ | Recargar Brave (F5). Se arrastra por la cabecera negra. |
| v31 | 126590c | 2026-07-05 | Panel 🔤 Deletrear: escribir palabra → filas letra a letra (nombre inglés + OTAN + pronunciación) + botón Ver A-Z. Solo frontend. | ⏳ | Recargar la pestaña de Brave (F5) para verlo. |
| v30 | 5508ecc | 2026-07-05 | Captions en vivo (~0.6-1.3s), toggle preciso/rápido, botón de apagado, log de errores de traducción | ⏳ | Se probó un reintento x3 de DeepL y se revirtió el mismo día: trababa las traducciones hasta 45s. Lección: nada de esperas largas en el camino en vivo. |
| v29 | 9e8f2dc | 2026-07-04 | Quitar delay de la primera frase y bajar latencia de captura | ✅ | Usada en llamadas reales sin problema. |
| v1–v28 | — | 2026-06/07 | Historia previa: ver `git log --oneline` | ✅ | Base estable: captura, Whisper GPU, DeepL/Gemini, UI, notas, tijera, pronunciación. |
