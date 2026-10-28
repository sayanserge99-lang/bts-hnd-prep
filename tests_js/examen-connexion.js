// Usage : node examen-connexion.js <page d'épreuve rendue par Django> <static/js/examen.js>
// Lancé par entrainement/tests/test_examen_js.py (sauté si Node ou jsdom manquent).
// Connexion perdue pendant l'épreuve : bandeau honnête, puis sauvegarde dès le retour du réseau.
const fs = require("fs");
const { JSDOM } = require("jsdom");
const assert = require("assert");

const html = fs.readFileSync(process.argv[2], "utf8");
const code = fs.readFileSync(process.argv[3], "utf8");

const dom = new JSDOM(html, { url: "http://localhost:8000/entrainement/epreuve/1/", runScripts: "outside-only" });
const w = dom.window;
const d = w.document;
// Les nouveaux essais (setTimeout) sont relevés ici et lancés à la main : pas d'attente réelle de 5 s.
const minuteries = [];
const setTimeoutReel = w.setTimeout.bind(w);
w.setTimeout = (fn, delai) => (delai === 5000 ? minuteries.push(fn) : setTimeoutReel(fn, delai));
w.eval(code);

const formulaire = d.getElementById("epreuve");
const bandeau = d.getElementById("bandeau-hors-ligne");
const etat = d.getElementById("etat-sauvegarde");
let sauvegardes = 0;
formulaire.addEventListener("sauvegarder", () => { sauvegardes += 1; });
assert.ok(/\bsauvegarder\b/.test(formulaire.getAttribute("hx-trigger")), "HTMX écoute « sauvegarder »");

assert.ok(bandeau.hidden, "pas de bandeau tant que la connexion tient");

// Une sauvegarde échoue : le bandeau dit la vérité, y compris la limite des 90 s.
formulaire.dispatchEvent(new w.CustomEvent("htmx:sendError", { bubbles: true }));
assert.ok(!bandeau.hidden, "bandeau affiché");
assert.ok(bandeau.textContent.includes("Connexion perdue. Vos réponses sont gardées sur le téléphone"));
assert.ok(bandeau.textContent.includes("les réponses qui ne sont pas arrivées dans les 90 secondes ne sont pas comptées"));
assert.strictEqual(etat.textContent, "Connexion perdue");

// Réseau revenu : les réponses repartent tout de suite, sans attendre les 30 s.
w.dispatchEvent(new w.Event("online"));
assert.strictEqual(sauvegardes, 1, "sauvegarde au retour du réseau");

// Réseau instable sans événement « online » : nouvel essai 5 s après l'échec.
formulaire.dispatchEvent(new w.CustomEvent("htmx:sendError", { bubbles: true }));
formulaire.dispatchEvent(new w.CustomEvent("htmx:sendError", { bubbles: true }));
assert.strictEqual(minuteries.length, 2, "un seul nouvel essai en attente à la fois");  // le 1er a été annulé par « online »
minuteries[1]();
assert.strictEqual(sauvegardes, 2, "nouvel essai après 5 s");

// Sauvegarde réussie : le bandeau disparaît.
formulaire.dispatchEvent(new w.CustomEvent("htmx:afterRequest", { bubbles: true, detail: { successful: false } }));
assert.ok(!bandeau.hidden, "un échec ne cache pas le bandeau");
formulaire.dispatchEvent(new w.CustomEvent("htmx:afterRequest", { bubbles: true, detail: { successful: true } }));
assert.ok(bandeau.hidden, "bandeau caché après une sauvegarde réussie");

console.log("connexion perdue : 11 vérifications OK");
process.exit(0);  // le minuteur de la page garderait Node en vie
