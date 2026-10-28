// Copie locale des réponses d'examen blanc pas encore reçues par le serveur (bandeau « Connexion perdue »).
// Une entrée par tentative : son identifiant, la version, l'heure de saisie et les réponses ; rien d'autre.
// IndexedDB, sinon localStorage ; si aucun des deux ne marche (navigation privée), tout se résout à vide
// et l'examen fonctionne comme sans copie locale. Effacée à chaque confirmation du serveur, après la remise
// (page suivante) et à la déconnexion (téléphones partagés).
(function () {
  "use strict";
  var BASE = "bts-hnd-prep", MAGASIN = "copies-examen", PREFIXE = "copie-examen:";

  function ouvrirBase() {
    return new Promise(function (resoudre) {
      try {
        if (!window.indexedDB) return resoudre(null);
        var demande = window.indexedDB.open(BASE, 1);
        demande.onupgradeneeded = function () { demande.result.createObjectStore(MAGASIN, { keyPath: "tentative" }); };
        demande.onsuccess = function () { resoudre(demande.result); };
        demande.onerror = demande.onblocked = function () { resoudre(null); };
      } catch (e) { resoudre(null); }
    });
  }
  var base = null;
  function laBase() { return base || (base = ouvrirBase()); }

  // Une opération sur le magasin ; « repli » si IndexedDB est indisponible ou échoue.
  function operation(mode, agir, repli) {
    return laBase().then(function (db) {
      if (!db) return repli();
      return new Promise(function (resoudre) {
        try {
          var transaction = db.transaction(MAGASIN, mode);
          var resultat = agir(transaction.objectStore(MAGASIN));
          transaction.oncomplete = function () { resoudre(resultat && resultat.result); };
          transaction.onerror = transaction.onabort = function () { resoudre(repli()); };
        } catch (e) { resoudre(repli()); }
      });
    }).catch(function () { return null; });
  }

  function lireLocal(tentative) {
    try { return JSON.parse(window.localStorage.getItem(PREFIXE + tentative)) || null; } catch (e) { return null; }
  }
  function effacerLocal(tentative) {
    try { window.localStorage.removeItem(PREFIXE + tentative); } catch (e) { /* stockage indisponible */ }
  }

  var copie = {
    lire: function (tentative) {
      tentative = String(tentative);
      return operation("readonly", function (magasin) { return magasin.get(tentative); }, function () { return lireLocal(tentative); })
        .then(function (entree) { return entree || lireLocal(tentative); });
    },
    ecrire: function (tentative, version, reponses) {
      var entree = { tentative: String(tentative), version: version, saisie_le: new Date().toISOString(), reponses: reponses };
      return operation("readwrite", function (magasin) { magasin.put(entree); }, function () {
        try { window.localStorage.setItem(PREFIXE + entree.tentative, JSON.stringify(entree)); } catch (e) { /* plein ou interdit */ }
      });
    },
    // Le serveur a reçu jusqu'à `version` : on efface, sauf si une saisie plus récente attend encore.
    effacerJusqua: function (tentative, version) {
      tentative = String(tentative);
      var locale = lireLocal(tentative);
      if (locale && locale.version <= version) effacerLocal(tentative);
      return operation("readwrite", function (magasin) {
        var demande = magasin.get(tentative);
        demande.onsuccess = function () {
          if (demande.result && demande.result.version <= version) magasin.delete(tentative);
        };
      }, function () { return null; });
    },
    toutEffacer: function () {
      try {
        for (var i = window.localStorage.length - 1; i >= 0; i--) {
          var cle = window.localStorage.key(i);
          if (cle && cle.indexOf(PREFIXE) === 0) window.localStorage.removeItem(cle);
        }
      } catch (e) { /* stockage indisponible */ }
      return operation("readwrite", function (magasin) { magasin.clear(); }, function () { return null; });
    },
  };
  window.copieLocale = copie;

  // Déconnexion ou suppression du compte : la copie part avant la page (au plus une seconde d'attente).
  document.addEventListener("submit", function (evenement) {
    var formulaire = evenement.target;
    if (!formulaire.hasAttribute("data-efface-copie-locale") || formulaire.dataset.copieEffacee) return;
    evenement.preventDefault();
    formulaire.dataset.copieEffacee = "1";
    var delai = new Promise(function (resoudre) { setTimeout(resoudre, 1000); });
    Promise.race([copie.toutEffacer(), delai]).then(function () { formulaire.submit(); });
  });

  // Page d'une épreuve terminée : une copie locale plus récente que ce que le serveur a reçu est renvoyée.
  // Le serveur la refuse (409 : arrivée après la fin plus 90 s) ; on le dit à l'étudiant, puis on l'efface.
  var tardive = document.querySelector("[data-copie-tardive]");
  if (tardive) {
    var tentative = tardive.dataset.tentative;
    var recue = Number(tardive.dataset.versionRecue);
    copie.lire(tentative).then(function (entree) {
      if (!entree) return;
      if (entree.version <= recue) return copie.effacerJusqua(tentative, entree.version);
      var donnees = new FormData();
      entree.reponses.forEach(function (paire) { donnees.append(paire[0], paire[1]); });
      donnees.set("version", entree.version);
      donnees.set("csrfmiddlewaretoken", tardive.querySelector("[name=csrfmiddlewaretoken]").value);
      return fetch(tardive.dataset.adresse, { method: "POST", body: donnees, credentials: "same-origin" }).then(function (reponse) {
        if (reponse.status === 409) tardive.hidden = false;
        if (reponse.ok || reponse.status === 409) return copie.effacerJusqua(tentative, entree.version);
      });
    }).catch(function () { /* hors connexion : on réessaiera à la prochaine ouverture */ });
  }
})();
