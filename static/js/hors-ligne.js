// Mode hors ligne (CDC 4) : sujets gardés sur le téléphone, quiz téléchargés et rejoués sans réseau.
// Les textes affichés viennent du serveur (attributs data-texte-*), déjà traduits.
(function () {
  "use strict";

  var CLE = "btshnd-hors-ligne";
  var CACHE_SUJETS = "sujets-hors-ligne";
  var disponible = "serviceWorker" in navigator && "caches" in window;

  if (disponible) {
    navigator.serviceWorker.register("/sw.js").catch(function () {});
  }

  // --- Mémoire du téléphone ---------------------------------------------------------

  function lire() {
    try {
      var donnees = JSON.parse(window.localStorage.getItem(CLE));
      if (donnees && donnees.sujets && donnees.quiz) return donnees;
    } catch (erreur) {}
    return { sujets: {}, quiz: {} };
  }

  function ecrire(donnees) {
    try {
      window.localStorage.setItem(CLE, JSON.stringify(donnees));
      return true;
    } catch (erreur) {
      return false; // Mémoire pleine ou navigation privée.
    }
  }

  function jetonCsrf() {
    var trouve = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    return trouve ? decodeURIComponent(trouve[1]) : "";
  }

  function montrer(element) {
    if (element) element.classList.remove("hidden");
  }

  // --- Sujets gardés hors ligne (fiche sujet) ---------------------------------------

  function preparerBoutonSujet(bouton) {
    if (!disponible) return;
    var id = bouton.dataset.id;
    var urls = JSON.parse(bouton.dataset.urls);

    function afficher() {
      bouton.textContent = lire().sujets[id] ? bouton.dataset.texteGarde : bouton.dataset.texteGarder;
    }

    bouton.addEventListener("click", function () {
      var donnees = lire();
      bouton.disabled = true;
      caches.open(CACHE_SUJETS).then(function (cache) {
        if (donnees.sujets[id]) {
          delete donnees.sujets[id];
          return Promise.all(urls.map(function (url) { return cache.delete(url); }));
        }
        return cache.addAll(urls).then(function () {
          donnees.sujets[id] = { titre: bouton.dataset.titre, url: urls[0], garde_le: new Date().toISOString() };
        });
      }).then(function () {
        ecrire(donnees);
        afficher();
      }).catch(function () {
        bouton.textContent = bouton.dataset.texteErreur;
      }).then(function () {
        bouton.disabled = false;
      });
    });

    afficher();
    montrer(bouton);
  }

  // --- Téléchargement d'un quiz (page Entraînement) ----------------------------------

  function preparerBoutonQuiz(bouton) {
    if (!disponible) return;
    bouton.addEventListener("click", function () {
      var corps = new URLSearchParams({ matiere: bouton.dataset.matiere });
      var chapitre = document.querySelector(bouton.dataset.chapitre);
      if (chapitre && chapitre.value) corps.set("chapitre", chapitre.value);
      bouton.disabled = true;
      fetch(bouton.dataset.url, { method: "POST", body: corps, headers: { "X-CSRFToken": jetonCsrf() }, credentials: "same-origin" })
        .then(function (reponse) {
          return reponse.json().then(function (paquet) {
            if (!reponse.ok) throw new Error(paquet.erreur || "");
            return paquet;
          });
        })
        .then(function (paquet) {
          var donnees = lire();
          paquet.reponses = {};
          donnees.quiz[paquet.tentative] = paquet;
          if (!ecrire(donnees)) throw new Error(bouton.dataset.texteErreur);
          bouton.textContent = bouton.dataset.texteTelecharge;
        })
        .catch(function (erreur) {
          bouton.textContent = erreur.message || bouton.dataset.texteErreur;
          bouton.disabled = false;
        });
    });
    montrer(bouton);
  }

  // --- Page « Hors ligne » : listes et lecteur de quiz -------------------------------

  function normaliser(texte) {
    // Même tolérance que le serveur (entrainement/correction.py) : casse, accents, espaces, virgule.
    return texte.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, "").replace(/,/g, ".");
  }

  function estCorrecte(question, reponse) {
    if (question.type === "reponse_courte") {
      return question.acceptees.some(function (acceptee) { return normaliser(acceptee) === normaliser(reponse); });
    }
    var bonnes = question.choix.filter(function (c) { return c.correct; }).map(function (c) { return c.id; }).sort();
    var cochees = reponse.slice().sort();
    return bonnes.length === cochees.length && bonnes.every(function (id, i) { return id === cochees[i]; });
  }

  function element(balise, classes, html) {
    var noeud = document.createElement(balise);
    if (classes) noeud.className = classes;
    if (html !== undefined) noeud.innerHTML = html; // HTML déjà nettoyé par le serveur (sujets/rendu.py).
    return noeud;
  }

  function synchroniser(page) {
    var donnees = lire();
    Object.keys(donnees.quiz).forEach(function (id) {
      var paquet = donnees.quiz[id];
      if (paquet.synchronise || !Object.keys(paquet.reponses).length || !navigator.onLine) return;
      fetch(paquet.url_synchro, {
        method: "POST",
        body: JSON.stringify({ reponses: paquet.reponses }),
        headers: { "Content-Type": "application/json", "X-CSRFToken": jetonCsrf() },
        credentials: "same-origin",
      })
        .then(function (reponse) { return reponse.ok ? reponse.json() : null; })
        .then(function (resultat) {
          if (!resultat) return;
          var aJour = lire();
          if (!aJour.quiz[id]) return;
          aJour.quiz[id].note_serveur = resultat.note;
          aJour.quiz[id].synchronise = resultat.repondues === paquet.questions.length;
          ecrire(aJour);
          if (page) afficherListes(page);
        })
        .catch(function () {});
    });
  }

  function afficherListes(page) {
    var donnees = lire();
    var listeSujets = page.querySelector("#sujets-gardes");
    var listeQuiz = page.querySelector("#quiz-telecharges");
    listeSujets.innerHTML = "";
    listeQuiz.innerHTML = "";

    Object.keys(donnees.sujets).forEach(function (id) {
      var sujet = donnees.sujets[id];
      var item = element("li");
      var lien = element("a", "carte block hover:border-vert");
      lien.href = sujet.url;
      lien.textContent = sujet.titre;
      item.appendChild(lien);
      listeSujets.appendChild(item);
    });
    if (!listeSujets.children.length) listeSujets.appendChild(element("li", "text-sm text-gris", page.dataset.texteAucunSujet));

    Object.keys(donnees.quiz).forEach(function (id) {
      var paquet = donnees.quiz[id];
      var faites = Object.keys(paquet.reponses).length;
      var item = element("li", "carte flex flex-wrap items-center justify-between gap-3");
      var nom = element("span");
      nom.textContent = paquet.matiere + " · " + paquet.titre + " (" + faites + "/" + paquet.questions.length + ")";
      item.appendChild(nom);
      if (faites < paquet.questions.length) {
        var jouer = element("button", "bouton-plein");
        jouer.type = "button";
        jouer.textContent = faites ? page.dataset.texteReprendre : page.dataset.texteJouer;
        jouer.addEventListener("click", function () { jouerQuiz(page, id); });
        item.appendChild(jouer);
      } else {
        item.appendChild(element("span", "text-sm " + (paquet.synchronise ? "text-vert" : "text-ambre"),
          paquet.synchronise ? page.dataset.texteSynchronise.replace("%s", String(Number(paquet.note_serveur))) : page.dataset.texteEnAttente));
      }
      var oublier = element("button", "text-xs text-gris underline");
      oublier.type = "button";
      oublier.textContent = page.dataset.texteOublier;
      oublier.addEventListener("click", function () {
        var aJour = lire();
        delete aJour.quiz[id];
        ecrire(aJour);
        afficherListes(page);
      });
      item.appendChild(oublier);
      listeQuiz.appendChild(item);
    });
    if (!listeQuiz.children.length) listeQuiz.appendChild(element("li", "text-sm text-gris", page.dataset.texteAucunQuiz));
  }

  function jouerQuiz(page, id) {
    var zone = page.querySelector("#lecteur-quiz");
    var donnees = lire();
    var paquet = donnees.quiz[id];
    var question = paquet.questions.filter(function (q) { return !(String(q.id) in paquet.reponses); })[0];
    zone.innerHTML = "";
    montrer(zone);
    if (!question) {
      zone.classList.add("hidden");
      afficherListes(page);
      synchroniser(page);
      return;
    }

    var numero = paquet.questions.indexOf(question) + 1;
    zone.appendChild(element("p", "text-sm text-gris", "")).textContent = paquet.titre + " · " + numero + "/" + paquet.questions.length;
    zone.appendChild(element("div", "corrige text-lg font-medium", question.enonce));
    var formulaire = element("form", "space-y-2");
    if (question.type === "reponse_courte") {
      var champ = element("input", "champ");
      champ.name = "reponse";
      champ.autocomplete = "off";
      formulaire.appendChild(champ);
    } else {
      question.choix.forEach(function (choix) {
        var etiquette = element("label", "carte flex cursor-pointer items-start gap-3 p-4");
        var case_ = element("input", "mt-1 h-5 w-5 shrink-0 accent-vert");
        case_.type = question.type === "choix_multiple" ? "checkbox" : "radio";
        case_.name = "choix";
        case_.value = choix.id;
        etiquette.appendChild(case_);
        etiquette.appendChild(element("span", "", choix.texte));
        formulaire.appendChild(etiquette);
      });
    }
    var valider = element("button", "bouton-plein");
    valider.textContent = page.dataset.texteValider;
    formulaire.appendChild(valider);
    zone.appendChild(formulaire);

    formulaire.addEventListener("submit", function (evenement) {
      evenement.preventDefault();
      var reponse = question.type === "reponse_courte"
        ? formulaire.querySelector("[name=reponse]").value.trim()
        : Array.prototype.map.call(formulaire.querySelectorAll("input:checked"), function (c) { return Number(c.value); });
      if (!reponse.length) return;
      var aJour = lire();
      aJour.quiz[id].reponses[question.id] = reponse;
      ecrire(aJour);

      var juste = estCorrecte(question, reponse);
      formulaire.remove();
      zone.appendChild(element("p", juste ? "rounded-lg bg-vert-clair p-3 font-semibold text-vert-fonce" : "rounded-lg border border-red-300 bg-red-50 p-3 font-semibold text-red-800",
        juste ? page.dataset.texteJuste : page.dataset.texteFaux));
      if (question.type === "reponse_courte") {
        zone.appendChild(element("p", "text-sm", "")).textContent = page.dataset.texteAttendue + " " + question.acceptees[0];
      } else {
        var bonnes = element("ul", "space-y-1 text-sm");
        question.choix.filter(function (c) { return c.correct; }).forEach(function (c) { bonnes.appendChild(element("li", "", "✓ " + c.texte)); });
        zone.appendChild(bonnes);
      }
      if (question.explication) zone.appendChild(element("div", "corrige carte text-sm", question.explication));
      var suivante = element("button", "bouton-plein");
      suivante.type = "button";
      suivante.textContent = page.dataset.texteSuivante;
      suivante.addEventListener("click", function () { jouerQuiz(page, id); });
      zone.appendChild(suivante);
    });
  }

  // --- Démarrage ---------------------------------------------------------------------

  document.querySelectorAll("[data-garder-sujet]").forEach(preparerBoutonSujet);
  document.querySelectorAll("[data-telecharger-quiz]").forEach(preparerBoutonQuiz);

  var page = document.getElementById("page-hors-ligne");
  if (page) {
    montrer(page.querySelector("#contenu-hors-ligne"));
    var sansJs = page.querySelector("#sans-javascript");
    if (sansJs) sansJs.remove();
    afficherListes(page);
  }
  synchroniser(page);
  window.addEventListener("online", function () { synchroniser(page); });

  // Tests (jsdom) : accès aux fonctions pures sans les exposer en production.
  if (window.__TEST_HORS_LIGNE__) window.__HORS_LIGNE__ = { estCorrecte: estCorrecte, normaliser: normaliser, lire: lire };
})();
