// Petits comportements du site, sans JavaScript dans les pages (la Content-Security-Policy l'interdit).
(function () {
  "use strict";
  // Bouton « Imprimer » (reçu) : caché sans JavaScript, affiché ici.
  document.querySelectorAll("[data-imprimer]").forEach(function (bouton) {
    bouton.classList.remove("hidden");
    bouton.addEventListener("click", function () { window.print(); });
  });

  // Œil des champs de mot de passe (templates/forms/champ.html) : on relit ce qu'on a tapé, sans confirmation.
  document.querySelectorAll("[data-afficher-mot-de-passe]").forEach(function (bouton) {
    var champ = bouton.parentNode.querySelector("input");
    bouton.classList.remove("hidden");
    bouton.classList.add("flex");
    bouton.addEventListener("click", function () {
      var visible = champ.type === "password";
      champ.type = visible ? "text" : "password";
      bouton.setAttribute("aria-pressed", visible ? "true" : "false");
      bouton.setAttribute("aria-label", visible ? bouton.dataset.texteMasquer : bouton.dataset.texteAfficher);
    });
  });
})();
