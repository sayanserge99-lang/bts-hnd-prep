// Usage : node copie-deconnexion.js <page d'épreuve rendue par Django> <static/js/examen.js>
// Lancé par entrainement/tests/test_examen_js.py (sauté si Node ou jsdom manquent).
// Téléphone partagé : la déconnexion efface la copie locale (IndexedDB et localStorage) avant de partir ;
// et sur la page d'une épreuve terminée, une copie arrivée trop tard est renvoyée, refusée, signalée, effacée.
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");
const { indexedDB } = require("fake-indexeddb");
const assert = require("assert");

const copieLocale = fs.readFileSync(path.join(path.dirname(process.argv[3]), "copie-locale.js"), "utf8");
const attendre = (ms = 30) => new Promise((r) => setTimeout(r, ms));

function ouvrir(corps) {
  const dom = new JSDOM(`<!doctype html><body>${corps}</body>`, { url: "http://localhost:8000/", runScripts: "outside-only" });
  dom.window.indexedDB = indexedDB;
  dom.window.eval(copieLocale);
  return dom.window;
}

(async () => {
  // Déconnexion : copie effacée, puis le formulaire part (une seule fois).
  const w = ouvrir('<form method="post" action="/compte/deconnexion/" data-efface-copie-locale><button>Déconnexion</button></form>');
  await w.copieLocale.ecrire(12, 3, [["q-1", "4"]]);
  w.localStorage.setItem("copie-examen:13", JSON.stringify({ tentative: "13", version: 1, reponses: [] }));
  w.localStorage.setItem("langue", "fr");
  assert.ok(await w.copieLocale.lire(12), "copie présente avant la déconnexion");
  const formulaire = w.document.querySelector("form");
  let envoye = 0;
  formulaire.submit = () => { envoye += 1; };
  const soumission = new w.Event("submit", { bubbles: true, cancelable: true });
  formulaire.dispatchEvent(soumission);
  assert.ok(soumission.defaultPrevented, "la déconnexion attend l'effacement");
  await attendre();
  assert.strictEqual(envoye, 1, "puis la déconnexion part");
  assert.strictEqual(await w.copieLocale.lire(12), null, "copie IndexedDB effacée");
  assert.strictEqual(w.localStorage.getItem("copie-examen:13"), null, "copie localStorage effacée");
  assert.strictEqual(w.localStorage.getItem("langue"), "fr", "le reste du site n'est pas touché");

  // Épreuve terminée, copie plus récente que ce que le serveur a reçu : renvoyée, refusée (409), signalée, effacée.
  const t = ouvrir('<div data-copie-tardive data-tentative="20" data-version-recue="2" data-adresse="/entrainement/examen/20/enregistrer/" hidden>'
    + '<input type="hidden" name="csrfmiddlewaretoken" value="jeton"><p>Ces réponses sont arrivées après la fin de l\'épreuve et n\'ont pas été comptées.</p></div>');
  await t.copieLocale.ecrire(20, 5, [["q-1", "4"]]);
  const envois = [];
  t.fetch = (adresse, options) => { envois.push([adresse, options.body]); return Promise.resolve({ ok: false, status: 409 }); };
  t.eval(copieLocale);  // la page s'ouvre avec la copie présente
  await attendre();
  assert.strictEqual(envois.length, 1, "renvoyée : c'est le serveur qui juge");
  assert.strictEqual(envois[0][1].get("q-1"), "4");
  assert.strictEqual(envois[0][1].get("version"), "5");
  assert.ok(!t.document.querySelector("[data-copie-tardive]").hidden, "message affiché à l'étudiant");
  assert.strictEqual(await t.copieLocale.lire(20), null, "puis effacée");

  console.log("déconnexion et copie tardive : 11 vérifications OK");
  process.exit(0);
})();
