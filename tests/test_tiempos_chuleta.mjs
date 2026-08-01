// Chequeo del parser de tiempos (⏱) y de la chuleta (🔢) sin navegador: se recortan
// los trozos de index.html y se ejecutan con stubs mínimos de document/localStorage.
// Correr con: node tests/test_tiempos_chuleta.mjs
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const entre = (a, b) => html.slice(html.indexOf(a), html.indexOf(b));
const src = entre("const DIAS = ", "function toggleAyuda")
          + entre("function minutosDe(texto){", "function fmtMin")
          + entre("// --- números → inglés hablado", "// --- deletreo:");

const stub = { style: {}, innerHTML: "", value: "" };
const ctx = { document: { getElementById: () => stub }, localStorage: { getItem: () => null, setItem: () => {} },
              hacerMovible: () => {}, Date };
const run = new Function(...Object.keys(ctx), src + "; return { minutosDe, diaMes, enPalabras };");
const { minutosDe, diaMes } = run(...Object.values(ctx));

// el bug: "1:01:22" (1h 1m 22s) se leía como 1 minuto
assert.equal(Math.round(minutosDe("1:01:22") * 60), 3682);
assert.equal(minutosDe("2:00:00"), 120);
assert.equal(minutosDe("14:3"), 14 + 3 / 60);          // min:seg sigue igual
assert.equal(minutosDe("1h 20min"), 80);
assert.equal(minutosDe("23 min"), 23);
assert.equal(minutosDe("0:40"), 40 / 60);

assert.deepEqual(diaMes(1), ["first", "férst"]);
assert.deepEqual(diaMes(20), ["twentieth", "TUÉN-ti-ez"]);
assert.deepEqual(diaMes(21), ["twenty-first", "TUÉN-ti-férst"]);
assert.deepEqual(diaMes(31), ["thirty-first", "ZÉR-ti-férst"]);
assert.equal(diaMes(14)[0], "fourteenth");
console.log("ok");
