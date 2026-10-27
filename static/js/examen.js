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

  // À 0:00, la copie se ferme : plus rien ne se modifie dans la page (la marge du serveur, 90 s, ne sert
  // qu'au transport des réponses déjà données). « inert » d'abord ; lecture seule et blocage des clics et
  // des touches en plus, pour les navigateurs qui ignorent « inert ».
  // Ce qui est envoyé est figé à 0:00 : toute modification ensuite est annulée (réponses de 0:00 rétablies).
  var reponsesFigees = null;

  function champsDeReponse() {
    return formulaire.querySelectorAll("[data-panneau] input, [data-panneau] textarea");
  }

  function retablir() {
    champsDeReponse().forEach(function (champ) {
      var valeurs = reponsesFigees.getAll(champ.name);
      if (champ.type === "radio" || champ.type === "checkbox") champ.checked = valeurs.indexOf(champ.value) !== -1;
      else champ.value = valeurs.length ? valeurs[0] : "";
    });
  }

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

  afficher();
  setInterval(afficher, 1000);

  // HTMX n'a pas pu joindre le serveur : les réponses restent dans la page et repartent
  // à la prochaine sauvegarde (toutes les 30 s ou au prochain changement).
  document.body.addEventListener("htmx:sendError", function () {
    if (etat) etat.textContent = etat.dataset.horsLigne;
  });

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

  // --- Une question à la fois (maquette) : Précédente / Suivante, grille, questions marquées ----------
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
})();
