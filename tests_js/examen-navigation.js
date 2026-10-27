// Usage : node examen-navigation.js <page d'épreuve rendue par Django> <static/js/examen.js>
// Lancé par entrainement/tests/test_examen_js.py (sauté si Node ou jsdom manquent).
// Essai de static/js/examen.js sur la vraie page d'épreuve (rendue par Django).
const fs = require("fs");
const { JSDOM } = require("jsdom");
const assert = require("assert");

const html = fs.readFileSync(process.argv[2], "utf8");
const code = fs.readFileSync(process.argv[3], "utf8");
const dom = new JSDOM(html, { url: "http://localhost:8000/entrainement/epreuve/1/", runScripts: "outside-only" });
const w = dom.window;
const d = w.document;
let envois = 0;
w.HTMLFormElement.prototype.requestSubmit = function () { envois += 1; };
let reponseConfirm = false;
w.confirm = () => reponseConfirm;
w.eval(code);

const panneaux = [...d.querySelectorAll("[data-panneau]")];
const cases = [...d.querySelectorAll("[data-case]")];
const visibles = () => panneaux.filter((p) => !p.hidden);
assert.ok(panneaux.length >= 3, "au moins 2 questions + rédaction");
assert.strictEqual(visibles().length, 1, "une seule question à la fois");
assert.strictEqual(visibles()[0], panneaux[0]);
assert.ok(!d.querySelector("[data-grille]").classList.contains("hidden"), "grille affichée");
assert.strictEqual(cases[0].getAttribute("aria-current"), "step");
// La page est rendue avec deux réponses déjà enregistrées (test_examen_js.py).
assert.strictEqual(cases[0].dataset.repondue, "1");
assert.strictEqual(cases[1].dataset.repondue, "1");
assert.strictEqual(cases[2].dataset.repondue, "0");
assert.ok(d.querySelector("[data-precedente]").disabled);

// Suivante → question 2.
d.querySelector("[data-suivante]").click();
assert.strictEqual(visibles()[0], panneaux[1]);
assert.strictEqual(cases[1].getAttribute("aria-current"), "step");
assert.ok(!cases[0].hasAttribute("aria-current"));

// Marquer la question 2 : champ caché mis à jour, sauvegarde déclenchée, case marquée, état dit en mots.
let changements = 0;
d.getElementById("epreuve").addEventListener("change", () => { changements += 1; });
const marquer = panneaux[1].querySelector("[data-marquer]");
marquer.click();
assert.strictEqual(d.getElementById("marquees").value, panneaux[1].dataset.question);
assert.strictEqual(marquer.getAttribute("aria-pressed"), "true");
assert.strictEqual(changements, 1, "la marque part avec la sauvegarde automatique");
assert.strictEqual(cases[1].dataset.marquee, "1");
assert.ok(/marquée/.test(cases[1].getAttribute("aria-label")), cases[1].getAttribute("aria-label"));
marquer.click();
assert.strictEqual(d.getElementById("marquees").value, "");

// Répondre à la question 3 depuis la grille : la case passe « répondue ».
cases[2].click();
assert.strictEqual(visibles()[0], panneaux[2]);
const champ = panneaux[2].querySelector("input");
if (champ.type === "radio" || champ.type === "checkbox") champ.checked = true; else champ.value = "40";
champ.dispatchEvent(new w.Event("change", { bubbles: true }));
assert.strictEqual(cases[2].dataset.repondue, "1");

// Dernier panneau : la rédaction, Suivante désactivée.
cases[cases.length - 1].click();
assert.ok(visibles()[0].hasAttribute("data-redaction"));
assert.ok(d.querySelector("[data-suivante]").disabled);

// Entrée dans un champ ne rend pas la copie.
const entree = new w.KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true });
d.querySelector("input[name^='q-']").dispatchEvent(entree);
assert.ok(entree.defaultPrevented, "Entrée ne doit pas envoyer le formulaire");

// « Rendre ma copie » demande confirmation ; refusée, rien ne part.
const clic = new w.MouseEvent("click", { bubbles: true, cancelable: true });
d.querySelector("[data-rendre]").dispatchEvent(clic);
assert.ok(clic.defaultPrevented, "remise sans confirmation");
reponseConfirm = true;
const clic2 = new w.MouseEvent("click", { bubbles: true, cancelable: true });
d.querySelector("[data-rendre]").dispatchEvent(clic2);
assert.ok(!clic2.defaultPrevented, "remise confirmée");

console.log("examen.js : 18 vérifications OK");
process.exit(0);  // le minuteur de la page garderait Node en vie
