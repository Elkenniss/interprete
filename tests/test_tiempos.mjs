// Chequeo del parser de tiempos (⏱) sin navegador: se recorta el trozo de index.html
// y se ejecuta con stubs mínimos.
// Correr con: node tests/test_tiempos.mjs
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const src = html.slice(html.indexOf("function minutosDe(texto){"), html.indexOf("function fmtMin"));
const minutosDe = new Function(src + "; return minutosDe;")();

// el bug: "1:01:22" (1h 1m 22s) se leía como 1 minuto
assert.equal(Math.round(minutosDe("1:01:22") * 60), 3682);
assert.equal(Math.round(minutosDe("2:00:00") * 60), 7200);

// la convención de Kenny sigue intacta: "14:3" = 14 min 3 seg, NUNCA h:mm
assert.equal(Math.round(minutosDe("14:3") * 60), 843);
assert.equal(Math.round(minutosDe("7:21") * 60), 441);

// y las otras formas de anotar
assert.equal(minutosDe("2h"), 120);
assert.equal(minutosDe("1h 20min"), 80);
assert.equal(minutosDe("23 min"), 23);
assert.equal(minutosDe("15"), 15);          // número pelado = minutos

console.log("ok — parser de tiempos ⏱");
