// Usage : node examen-copie-locale.js <page d'épreuve rendue par Django> <static/js/examen.js>
// Lancé par entrainement/tests/test_examen_js.py (sauté si Node ou jsdom manquent).
// Réponse saisie hors ligne, page rechargée, réseau revenu : la réponse part, puis la copie locale s'efface.
// IndexedDB est simulé par fake-indexeddb, partagé entre les deux « ouvertures » de la page comme sur un téléphone.
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");
const { indexedDB } = require("fake-indexeddb");
const assert = require("assert");

const html = fs.readFileSync(process.argv[2], "utf8");
const examen = fs.readFileSync(process.argv[3], "utf8");
const copieLocale = fs.readFileSync(path.join(path.dirname(process.argv[3]), "copie-locale.js"), "utf8");
const attendre = (ms = 30) => new Promise((r) => setTimeout(r, ms));

function ouvrir(enLigne) {
  const dom = new JSDOM(html, { url: "http://localhost:8000/entrainement/epreuve/1/", runScripts: "outside-only" });
  const w = dom.window;
  w.indexedDB = indexedDB;
  Object.defineProperty(w.navigator, "onLine", { value: enLigne, configurable: true });
  w.HTMLFormElement.prototype.requestSubmit = () => {};
  const formulaire = w.document.getElementById("epreuve");
  const envois = [];  // ce que HTMX enverrait à chaque « sauvegarder »
  formulaire.addEventListener("sauvegarder", () => envois.push(new w.FormData(formulaire)));
  w.eval(copieLocale);
  w.eval(examen);
  return { w, d: w.document, formulaire, envois };
}

function confirmer(page, version) {
  const xhr = { getResponseHeader: (nom) => (nom === "X-Version-Recue" ? String(version) : null) };
  page.formulaire.dispatchEvent(new page.w.CustomEvent("htmx:afterRequest", { bubbles: true, detail: { successful: true, xhr } }));
}

(async () => {
  // 1. Hors ligne : la troisième question (pas encore répondue) est cochée ; rien n'arrive au serveur.
  const hors = ouvrir(false);
  await attendre();
  const tentative = hors.formulaire.dataset.tentative;
  const troisieme = hors.d.querySelectorAll("[data-panneau]")[2];
  const choix = troisieme.querySelector("input[type=radio]");
  choix.click();
  await attendre();
  const gardee = await hors.w.copieLocale.lire(tentative);
  assert.ok(gardee, "réponse gardée sur le téléphone");
  assert.deepStrictEqual(Object.keys(gardee).sort(), ["reponses", "saisie_le", "tentative", "version"], "rien d'autre que l'essentiel");
  assert.ok(gardee.reponses.some(([nom, valeur]) => nom === choix.name && valeur === choix.value));
  assert.ok(!gardee.reponses.some(([nom]) => nom === "csrfmiddlewaretoken"), "pas de jeton dans la copie");
  hors.w.close();

  // 2. Page rouverte, réseau revenu : le serveur n'a toujours que les deux premières réponses (même HTML).
  const retour = ouvrir(true);
  await attendre(60);
  const restaure = retour.d.querySelectorAll("[data-panneau]")[2].querySelector(`input[value="${choix.value}"]`);
  assert.ok(restaure.checked, "réponse remise dans la page");
  assert.strictEqual(retour.envois.length, 1, "envoyée tout de suite à l'ouverture");
  assert.strictEqual(retour.envois[0].get(choix.name), choix.value, "la réponse fait partie de l'envoi");
  assert.strictEqual(retour.envois[0].get("version"), String(gardee.version), "avec sa version");

  // Une saisie plus récente n'est pas effacée par la confirmation d'un envoi plus ancien.
  retour.d.getElementById("copie").value = "Brouillon";
  retour.d.getElementById("copie").dispatchEvent(new retour.w.Event("input", { bubbles: true }));
  await attendre();
  confirmer(retour, gardee.version);
  await attendre();
  assert.ok(await retour.w.copieLocale.lire(tentative), "saisie plus récente gardée");

  // 3. Le serveur confirme la dernière version : la copie locale disparaît.
  confirmer(retour, gardee.version + 1);
  await attendre();
  assert.strictEqual(await retour.w.copieLocale.lire(tentative), null, "copie effacée après confirmation");

  // 4. Stockage indisponible (navigation privée) : l'examen démarre comme avant, sans erreur.
  const prive = new JSDOM(html, { url: "http://localhost:8000/entrainement/epreuve/1/", runScripts: "outside-only" });
  Object.defineProperty(prive.window, "indexedDB", { get() { throw new Error("interdit"); } });
  Object.defineProperty(prive.window, "localStorage", { get() { throw new Error("interdit"); } });
  prive.window.eval(copieLocale);
  prive.window.eval(examen);
  await attendre();
  assert.ok(!prive.window.document.querySelector("[data-grille]").classList.contains("hidden"), "examen utilisable");
  prive.window.document.querySelectorAll("[data-panneau]")[2].querySelector("input[type=radio]").click();
  await attendre();

  console.log("copie locale : 11 vérifications OK");
  process.exit(0);  // le minuteur de la page garderait Node en vie
})();
