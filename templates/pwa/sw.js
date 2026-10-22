{% load static %}// Service worker de BTS-HND Prep (CDC 4 : sujets et quiz consultables sans connexion).
// Généré par Django (catalogue.views.service_worker) : les adresses des fichiers statiques sont exactes.
const VERSION = "{{ version }}";
const COQUILLE = "coquille-" + VERSION;
const PAGES = "pages-" + VERSION;
// Sujets que l'étudiant a choisi de garder : ce cache n'est jamais vidé par une mise à jour.
const SUJETS_GARDES = "sujets-hors-ligne";
const PAGE_HORS_LIGNE = "{% url 'hors_ligne' %}";
const A_PRECHARGER = [
  PAGE_HORS_LIGNE,
  "{% static 'css/app.css' %}",
  "{% static 'js/htmx.min.js' %}",
  "{% static 'js/hors-ligne.js' %}",
  "{% static 'icons/icone-192.png' %}",
];

self.addEventListener("install", (evenement) => {
  evenement.waitUntil(caches.open(COQUILLE).then((cache) => cache.addAll(A_PRECHARGER)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (evenement) => {
  evenement.waitUntil(
    caches.keys()
      .then((noms) => Promise.all(
        noms.filter((nom) => (nom.startsWith("coquille-") || nom.startsWith("pages-")) && nom !== COQUILLE && nom !== PAGES)
          .map((nom) => caches.delete(nom))
      ))
      .then(() => self.clients.claim())
  );
});

// Pages publiques qu'on garde au passage pour les relire sans réseau. Jamais les pages personnelles
// (/compte/, /entrainement/) ni l'administration.
function pagePublique(url) {
  return url.pathname === "/" || url.pathname.startsWith("/sujets/");
}

function garderCopie(nomCache, requete, reponse) {
  const copie = reponse.clone();
  caches.open(nomCache).then((cache) => cache.put(requete, copie));
}

self.addEventListener("fetch", (evenement) => {
  const requete = evenement.request;
  const url = new URL(requete.url);
  if (requete.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/admin/")) {
    return;
  }

  if (url.pathname.startsWith("/static/") && !url.search) {
    // Fichiers statiques versionnés : le cache d'abord, ils ne changent pas.
    evenement.respondWith(
      caches.match(requete).then((trouve) => trouve || fetch(requete).then((reponse) => {
        if (reponse.ok) garderCopie(COQUILLE, requete, reponse);
        return reponse;
      }))
    );
    return;
  }

  // Le reste : le réseau d'abord (contenu à jour), la copie gardée si le réseau manque.
  evenement.respondWith(
    fetch(requete)
      .then((reponse) => {
        const html = (reponse.headers.get("Content-Type") || "").startsWith("text/html");
        if (reponse.ok && requete.mode === "navigate" && html && pagePublique(url)) garderCopie(PAGES, requete, reponse);
        return reponse;
      })
      .catch(() => caches.match(requete, { ignoreSearch: url.pathname.startsWith("/static/") }).then((trouve) => {
        if (trouve) return trouve;
        return requete.mode === "navigate" ? caches.match(PAGE_HORS_LIGNE) : Response.error();
      }))
  );
});
