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
      formulaire.requestSubmit(boutonRendre);
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
})();
