// Petits comportements du site, sans JavaScript dans les pages (la Content-Security-Policy l'interdit).
(function () {
  "use strict";
  // Bouton « Imprimer » (reçu) : caché sans JavaScript, affiché ici.
  document.querySelectorAll("[data-imprimer]").forEach(function (bouton) {
    bouton.classList.remove("hidden");
    bouton.addEventListener("click", function () { window.print(); });
  });
})();
