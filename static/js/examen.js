// Minuteur d'examen blanc (CDC 3.5) : compte à rebours depuis le temps restant donné par le serveur,
// copie rendue automatiquement à zéro, et état de la sauvegarde quand la connexion tombe.
(function () {
  "use strict";
  var minuteur = document.getElementById("minuteur");
  if (!minuteur) return;
  var formulaire = document.getElementById("epreuve");
  var boutonRendre = formulaire.querySelector("[data-rendre]");
  var etat = document.getElementById("etat-sauvegarde");
  var fin = Date.now() + Number(minuteur.dataset.secondes) * 1000;
  var rendu = false;
  var verrouille = false;

  // Copie locale (copie-locale.js) : chaque saisie reçoit un numéro de version, envoyé avec les réponses ;
  // le serveur renvoie la dernière version reçue, et la copie locale s'efface jusqu'à elle.
  var copieLocale = window.copieLocale;
  var tentative = formulaire.dataset.tentative;
  var champVersion = document.getElementById("version-copie");
  var version = Number(formulaire.dataset.versionRecue) || 0;

  function paires() {
    var liste = [];
    new FormData(formulaire).forEach(function (valeur, nom) {
      if (nom !== "csrfmiddlewaretoken" && nom !== "version") liste.push([nom, valeur]);
    });
    return liste;
  }

  // À 0:00, la copie se ferme : plus rien ne se modifie dans la page (la marge du serveur, 90 s, ne sert
  // qu'au transport des réponses déjà données). « inert » d'abord ; lecture seule et blocage des clics et
  // des touches en plus, pour les navigateurs qui ignorent « inert ».
  // Ce qui est envoyé est figé à 0:00 : toute modification ensuite est annulée (réponses de 0:00 rétablies).
  var reponsesFigees = null;

  function champsDeReponse() {
    return formulaire.querySelectorAll("[data-panneau] input, [data-panneau] textarea");
  }

  function remplir(champs, valeursDe) {
    champs.forEach(function (champ) {
      var valeurs = valeursDe(champ.name);
      if (champ.type === "radio" || champ.type === "checkbox") champ.checked = valeurs.indexOf(champ.value) !== -1;
      else champ.value = valeurs.length ? valeurs[0] : "";
    });
  }

  function retablir() {
    remplir(champsDeReponse(), function (nom) { return reponsesFigees.getAll(nom); });
  }

  // Réponses gardées sur le téléphone et pas encore reçues (page rouverte après une coupure) : remises dans la
  // page, puis envoyées tout de suite.
  function restaurer(entree) {
    var champs = Array.prototype.filter.call(formulaire.querySelectorAll("input[name], textarea[name]"), function (champ) {
      return champ.name !== "csrfmiddlewaretoken" && champ.name !== "version";
    });
    remplir(champs, function (nom) {
      return entree.reponses.filter(function (paire) { return paire[0] === nom; }).map(function (paire) { return paire[1]; });
    });
    version = entree.version;
    champVersion.value = version;
  }

  // Avant HTMX (phase de capture) : la requête de sauvegarde part avec la version de cette saisie.
  function memoriser() {
    if (verrouille || !copieLocale) return;
    version += 1;
    champVersion.value = version;
    copieLocale.ecrire(tentative, version, paires());
  }
  formulaire.addEventListener("input", memoriser, true);
  formulaire.addEventListener("change", memoriser, true);

  function verrouiller() {
    verrouille = true;
    reponsesFigees = new FormData(formulaire);
    formulaire.querySelectorAll("[data-panneau], [data-grille]").forEach(function (zone) { zone.setAttribute("inert", ""); });
    formulaire.querySelectorAll("input[type=text], input:not([type]), textarea").forEach(function (champ) { champ.readOnly = true; });
    if (etat) etat.textContent = etat.dataset.tempsEcoule;
  }
  ["click", "keydown", "beforeinput", "paste", "drop", "input", "change"].forEach(function (type) {
    formulaire.addEventListener(type, function (evenement) {
      if (verrouille && evenement.target.closest("[data-panneau]")) {
        retablir();
        evenement.preventDefault();
        evenement.stopImmediatePropagation();  // ni grille ni sauvegarde automatique
      }
    }, true);
  });
  // Plus aucune sauvegarde automatique après 0:00 (y compris celle des 30 s) : seule la copie figée part.
  formulaire.addEventListener("htmx:beforeRequest", function (evenement) {
    if (verrouille) evenement.preventDefault();
  });

  function envoyerLaCopie() {
    // Hors connexion à 0:00 : la copie part au retour du réseau (le serveur l'accepte encore 90 s).
    if (navigator.onLine === false) {
      window.addEventListener("online", envoyerLaCopie, { once: true });
      return;
    }
    formulaire.requestSubmit(boutonRendre);
  }

  function deuxChiffres(n) {
    return (n < 10 ? "0" : "") + n;
  }

  function afficher() {
    var reste = Math.max(0, Math.round((fin - Date.now()) / 1000));
    var heures = Math.floor(reste / 3600);
    var minutes = Math.floor((reste % 3600) / 60);
    minuteur.textContent = (heures ? heures + ":" : "") + deuxChiffres(minutes) + ":" + deuxChiffres(reste % 60);
    if (reste <= 300) minuteur.classList.add("text-red-700");
    if (reste === 0 && !rendu) {
      rendu = true;
      verrouiller();
      envoyerLaCopie();
    }
  }


  // HTMX n'a pas pu joindre le serveur : les réponses restent dans la page, le bandeau le dit, et elles
  // repartent dès que le réseau revient (événement « online », ou nouvel essai toutes les 5 s) ; seules les
  // toutes dernières réponses restent alors en jeu si la coupure dure au-delà de la fin du temps.
  var bandeau = document.getElementById("bandeau-hors-ligne");
  var nouvelEssai = null;

  function sauvegarderMaintenant() {
    if (nouvelEssai) { clearTimeout(nouvelEssai); nouvelEssai = null; }
    if (!verrouille) formulaire.dispatchEvent(new Event("sauvegarder"));
  }

  document.body.addEventListener("htmx:sendError", function () {
    if (etat && !verrouille) etat.textContent = etat.dataset.horsLigne;
    if (bandeau) bandeau.hidden = false;
    if (!nouvelEssai) nouvelEssai = setTimeout(function () { nouvelEssai = null; sauvegarderMaintenant(); }, 5000);
  });
  document.body.addEventListener("htmx:afterRequest", function (evenement) {
    if (!evenement.detail || !evenement.detail.successful) return;
    if (bandeau) bandeau.hidden = true;
    var recue = Number(evenement.detail.xhr && evenement.detail.xhr.getResponseHeader("X-Version-Recue"));
    if (copieLocale && recue) copieLocale.effacerJusqua(tentative, recue);
  });
  window.addEventListener("online", sauvegarderMaintenant);

  // 409 : l'épreuve est close côté serveur (temps écoulé) ; la page suivante montre la correction.
  document.body.addEventListener("htmx:responseError", function (evenement) {
    if (evenement.detail.xhr.status === 409) window.location.reload();
  });

  // Entrée dans un champ de réponse ne doit pas rendre la copie (premier bouton d'envoi du formulaire).
  formulaire.addEventListener("keydown", function (evenement) {
    if (evenement.key === "Enter" && evenement.target.tagName === "INPUT") evenement.preventDefault();
  });

  // Remise volontaire : confirmée ; à zéro, le minuteur rend sans demander.
  boutonRendre.addEventListener("click", function (evenement) {
    if (!rendu && !window.confirm(boutonRendre.dataset.confirmer)) evenement.preventDefault();
  });

  // --- Démarrage : copie locale d'abord (elle peut changer les réponses affichées), puis minuteur et navigation.
  function quandHtmxEstPret(fonction) {
    // HTMX branche ses déclencheurs au chargement complet du document : « sauvegarder » attend jusque-là.
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { setTimeout(fonction, 0); });
    else setTimeout(fonction, 0);
  }

  var lecture = copieLocale ? copieLocale.lire(tentative) : Promise.resolve(null);
  lecture.then(function (entree) {
    if (!entree) return false;
    if (entree.version <= version) {
      copieLocale.effacerJusqua(tentative, entree.version);  // déjà reçue par le serveur
      return false;
    }
    restaurer(entree);
    return true;
  }).catch(function () { return false; }).then(function (restauree) {
    navigation();
    afficher();
    setInterval(afficher, 1000);
    if (restauree) quandHtmxEstPret(sauvegarderMaintenant);
  });

  // --- Une question à la fois (maquette) : Précédente / Suivante, grille, questions marquées ----------
  function navigation() {
  var panneaux = Array.prototype.slice.call(formulaire.querySelectorAll("[data-panneau]"));
  var grille = document.querySelector("[data-grille]");
  var cases = Array.prototype.slice.call(document.querySelectorAll("[data-case]"));
  var precedente = formulaire.querySelector("[data-precedente]");
  var suivante = formulaire.querySelector("[data-suivante]");
  var champMarquees = document.getElementById("marquees");
  if (!panneaux.length || cases.length !== panneaux.length) return;
  var marquees = champMarquees.value ? champMarquees.value.split(",") : [];
  var courant = 0;

  function estRepondu(panneau) {
    return Array.prototype.some.call(panneau.querySelectorAll("input, textarea"), function (champ) {
      return champ.type === "radio" || champ.type === "checkbox" ? champ.checked : champ.value.trim() !== "";
    });
  }

  function rafraichirGrille() {
    cases.forEach(function (bouton, index) {
      var panneau = panneaux[index];
      var repondue = estRepondu(panneau);
      var marquee = marquees.indexOf(panneau.dataset.question) !== -1;
      bouton.dataset.repondue = repondue ? "1" : "0";
      bouton.dataset.marquee = marquee ? "1" : "0";
      if (index === courant) bouton.setAttribute("aria-current", "step");
      else bouton.removeAttribute("aria-current");
      // Lecteurs d'écran : l'état est dit en mots, pas seulement en couleur.
      var etats = [];
      if (repondue) etats.push(grille.dataset.texteRepondue);
      if (marquee) etats.push(grille.dataset.texteMarquee);
      bouton.setAttribute("aria-label", bouton.dataset.nom + (etats.length ? " (" + etats.join(", ") + ")" : ""));
    });
  }

  function afficherPanneau(index, deplacerFocus) {
    courant = Math.max(0, Math.min(index, panneaux.length - 1));
    panneaux.forEach(function (panneau, i) { panneau.hidden = i !== courant; });
    precedente.disabled = courant === 0;
    suivante.disabled = courant === panneaux.length - 1;
    rafraichirGrille();
    if (deplacerFocus) panneaux[courant].querySelector("[data-titre-panneau]").focus();
  }

  formulaire.querySelectorAll("[data-marquer]").forEach(function (bouton) {
    var panneau = bouton.closest("[data-panneau]");
    bouton.classList.remove("hidden");
    bouton.classList.add("inline-flex");
    bouton.addEventListener("click", function () {
      var pk = panneau.dataset.question;
      var position = marquees.indexOf(pk);
      if (position === -1) marquees.push(pk);
      else marquees.splice(position, 1);
      var marquee = position === -1;
      bouton.setAttribute("aria-pressed", marquee ? "true" : "false");
      bouton.querySelector("span").textContent = marquee ? bouton.dataset.texteMarquee : bouton.dataset.texteMarquer;
      champMarquees.value = marquees.join(",");
      // Enregistrée avec les réponses : la marque survit à un rechargement de la page.
      champMarquees.dispatchEvent(new Event("change", { bubbles: true }));
      rafraichirGrille();
    });
  });

  cases.forEach(function (bouton, index) {
    bouton.addEventListener("click", function () { afficherPanneau(index, true); });
  });
  precedente.addEventListener("click", function () { afficherPanneau(courant - 1, true); });
  suivante.addEventListener("click", function () { afficherPanneau(courant + 1, true); });
  formulaire.addEventListener("change", rafraichirGrille);
  formulaire.addEventListener("input", rafraichirGrille);

  grille.classList.remove("hidden");
  formulaire.querySelector("[data-navigation]").classList.remove("hidden");
  formulaire.querySelector("[data-navigation]").classList.add("grid");
  afficherPanneau(0, false);
  }
})();
