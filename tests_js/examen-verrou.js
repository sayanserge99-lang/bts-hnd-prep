// Usage : node examen-verrou.js <page d'épreuve rendue par Django> <static/js/examen.js>
// Lancé par entrainement/tests/test_examen_js.py (sauté si Node ou jsdom manquent).
// À 0:00, la copie se ferme : envoi immédiat des réponses, plus aucune modification possible dans la page.
const fs = require("fs");
const { JSDOM } = require("jsdom");
const assert = require("assert");

const html = fs.readFileSync(process.argv[2], "utf8").replace(/data-secondes="\d+"/, 'data-secondes="0"');
const code = fs.readFileSync(process.argv[3], "utf8");

function lancer(enLigne) {
  const dom = new JSDOM(html, { url: "http://localhost:8000/entrainement/epreuve/1/", runScripts: "outside-only" });
  const w = dom.window;
  Object.defineProperty(w.navigator, "onLine", { value: enLigne, configurable: true });
  const envois = [];
  w.HTMLFormElement.prototype.requestSubmit = function () {
    envois.push(new w.URLSearchParams(new w.FormData(this)).toString());
  };
  w.confirm = () => true;
  w.eval(code);
  return { w, d: w.document, envois };
}

// En ligne : la copie part tout de suite, avec les réponses d'avant 0:00.
const { w, d, envois } = lancer(true);
assert.strictEqual(envois.length, 1, "envoi immédiat à 0:00");
const avant = envois[0];
assert.ok(/temps écoulé/i.test(d.getElementById("etat-sauvegarde").textContent));

// Tentatives de modification après 0:00 : rien ne change dans ce qui serait envoyé.
const radio = [...d.querySelectorAll("[data-panneau] input[type=radio]")].find((r) => !r.checked);
radio.dispatchEvent(new w.MouseEvent("click", { bubbles: true, cancelable: true }));
assert.ok(!radio.checked, "un choix ne se coche plus après 0:00");
const espace = new w.KeyboardEvent("keydown", { key: " ", bubbles: true, cancelable: true });
radio.dispatchEvent(espace);
assert.ok(espace.defaultPrevented, "le clavier ne coche plus");
const copie = d.getElementById("copie");
assert.ok(copie.readOnly, "la copie rédigée est en lecture seule");
const saisie = new w.InputEvent("beforeinput", { bubbles: true, cancelable: true, data: "x" });
copie.dispatchEvent(saisie);
assert.ok(saisie.defaultPrevented, "la frappe est bloquée");
assert.ok(d.querySelector("[data-panneau]").hasAttribute("inert"));
const apres = new w.URLSearchParams(new w.FormData(d.getElementById("epreuve"))).toString();
if (apres !== avant) console.log("AVANT", avant, "\nAPRES", apres);
assert.strictEqual(apres, avant, "une réponse modifiée après 0:00 n'est pas envoyée");

// Hors connexion à 0:00 : verrouillé tout de suite, envoyé au retour du réseau (une seule fois).
const horsLigne = lancer(false);
assert.strictEqual(horsLigne.envois.length, 0);
assert.ok(horsLigne.d.getElementById("copie").readOnly);
Object.defineProperty(horsLigne.w.navigator, "onLine", { value: true, configurable: true });  // comme un vrai navigateur
horsLigne.w.dispatchEvent(new horsLigne.w.Event("online"));
horsLigne.w.dispatchEvent(new horsLigne.w.Event("online"));
assert.strictEqual(horsLigne.envois.length, 1, "envoi au retour du réseau");

console.log("verrou à 0:00 : 11 vérifications OK");
process.exit(0);  // le minuteur de la page garderait Node en vie
