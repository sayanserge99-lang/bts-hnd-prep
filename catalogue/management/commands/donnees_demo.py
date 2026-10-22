"""Données fictives pour voir les pages en développement. Les dates de session sont inventées."""

from datetime import date

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalogue.models import Chapitre, Examen, Matiere, Session, Specialite, SpecialiteMatiere
from entrainement.models import Choix, Question
from sujets.models import Corrige, Sujet

SOURCE_DEMO = "Démonstration (sujet fictif)"

SPECIALITES = {
    "BTS": [
        ("CGE", "Comptabilité et gestion des entreprises"),
        ("BF", "Banque et finance"),
        ("MCV", "Marketing, commerce, vente"),
        ("IG", "Informatique de gestion / Génie logiciel"),
    ],
    "HND": [
        ("ACC", "Accountancy"),
        ("BAF", "Banking and Finance"),
        ("MKT", "Marketing"),
        ("SWE", "Software Engineering"),
    ],
}

# (nom, {code spécialité: coefficient}, texte du sujet pour la recherche)
MATIERES = {
    "BTS": [
        ("Comptabilité générale", {"CGE": 4, "BF": 3},
         "Écritures de régularisation, amortissement dégressif, provisions et bilan de fin d'exercice."),
        ("Mathématiques financières", {"CGE": 3, "BF": 4},
         "Intérêts composés, annuités constantes, emprunt indivis et tableau d'amortissement."),
        ("Anglais", {"CGE": 2, "BF": 2, "MCV": 2, "IG": 2},
         "Reading comprehension, business letter, translation."),
        ("Économie générale", {"CGE": 2, "BF": 2, "MCV": 2, "IG": 2},
         "Inflation, croissance économique, politique monétaire de la BEAC."),
        ("Marketing fondamental", {"MCV": 4},
         "Étude de marché, segmentation, mix marketing et fidélisation de la clientèle."),
        ("Algorithmique et programmation", {"IG": 4},
         "Structures de données, tri par insertion, récursivité, base de données relationnelle."),
    ],
    "HND": [
        ("Financial Accounting", {"ACC": 4, "BAF": 3},
         "Depreciation methods, accruals, trial balance and final accounts."),
        ("Business Mathematics", {"ACC": 3, "BAF": 3, "MKT": 2, "SWE": 2},
         "Compound interest, annuities, linear programming."),
        ("Business Law", {"ACC": 2, "BAF": 2, "MKT": 2, "SWE": 2},
         "Contract formation, OHADA uniform acts, company law."),
        ("Principles of Marketing", {"MKT": 4},
         "Market research, segmentation, marketing mix and consumer behaviour."),
        ("Programming", {"SWE": 4},
         "Algorithms, object-oriented programming, sorting and recursion."),
    ],
}

ANNEES_PUBLIEES = range(2022, 2027)

MARQUE_QUESTION_DEMO = "(Démonstration)"
VRAI_FAUX = [("Vrai", True), ("Faux", False)]
FAUX_VRAI = [("Vrai", False), ("Faux", True)]
FALSE_TRUE = [("True", False), ("False", True)]

# (examen, matière, [(chapitre, [(type, énoncé, choix, réponse attendue, explication)])])
QUESTIONS = [
    ("BTS", "Comptabilité générale", [
        ("Amortissements", [
            ("choix_unique", "Un matériel de 10 000 000 FCFA est amorti en linéaire sur 5 ans. Quelle est l'annuité ?",
             [("1 000 000 FCFA", False), ("2 000 000 FCFA", True), ("2 500 000 FCFA", False), ("5 000 000 FCFA", False)], "",
             r"Annuité linéaire = $\frac{10\,000\,000}{5} = 2\,000\,000$ FCFA."),
            ("reponse_courte", "Durée 5 ans, coefficient dégressif 2 : quel est le taux d'amortissement dégressif (en %) ?",
             [], "40|40 %|40%|0,4|0.4", r"Taux linéaire $\frac{100}{5} = 20\,\%$, multiplié par le coefficient 2 : $40\,\%$."),
            ("vrai_faux", "Un terrain s'amortit en général sur sa durée d'utilisation.", FAUX_VRAI, "",
             "Un terrain ne se déprécie pas avec l'usage : il ne s'amortit pas (sauf terrains de gisement)."),
            ("choix_multiple", "Lesquels de ces biens sont des immobilisations amortissables ?",
             [("Un véhicule de livraison", True), ("Un ordinateur", True), ("Un stock de marchandises", False), ("Un fonds commercial acquis", False)], "",
             "Les stocks ne sont pas des immobilisations ; le fonds commercial ne s'amortit pas en principe."),
            ("choix_unique", "Dans quel compte enregistre-t-on la dotation aux amortissements d'exploitation ?",
             [("681", True), ("601", False), ("701", False), ("2845", False)], "",
             "La dotation se débite au 681 ; le 28 est crédité."),
        ]),
        ("Écritures de régularisation", [
            ("vrai_faux", "Une charge constatée d'avance concerne une charge payée en N mais relative à N+1.", VRAI_FAUX, "",
             "On la retire des charges de N (compte 476) pour respecter l'indépendance des exercices."),
            ("choix_unique", "Une facture d'électricité de décembre N arrive en janvier N+1. Quelle écriture en N ?",
             [("Charge à payer", True), ("Produit constaté d'avance", False), ("Charge constatée d'avance", False), ("Aucune écriture", False)], "",
             "La charge concerne N : on la constate en N (charge à payer), même si la facture arrive en N+1."),
            ("choix_multiple", "Quelles écritures sont des régularisations de fin d'exercice ?",
             [("Charges constatées d'avance", True), ("Produits à recevoir", True), ("Paiement d'un fournisseur", False), ("Dotations aux provisions", True)], "",
             "Le paiement d'un fournisseur est une opération courante, pas une régularisation."),
        ]),
    ]),
    ("BTS", "Mathématiques financières", [
        ("Intérêts composés", [
            ("choix_unique", r"Valeur acquise de 100 000 FCFA placés 2 ans à 10 % (intérêts composés) ?",
             [("120 000 FCFA", False), ("121 000 FCFA", True), ("110 000 FCFA", False), ("122 000 FCFA", False)], "",
             r"$C_2 = 100\,000 \times 1{,}1^2 = 121\,000$ FCFA."),
            ("reponse_courte", r"Que vaut $1{,}05^2$ ? (réponse décimale)", [], "1,1025|1.1025",
             r"$1{,}05 \times 1{,}05 = 1{,}1025$."),
            ("vrai_faux", "À taux égal, les intérêts composés rapportent plus que les intérêts simples au-delà d'une période.", VRAI_FAUX, "",
             "Les intérêts produisent eux-mêmes des intérêts à partir de la deuxième période."),
        ]),
    ]),
    ("HND", "Financial Accounting", [
        ("Depreciation", [
            ("choix_unique", "An asset costs 8,000,000 FCFA, residual value 0, useful life 4 years (straight line). Annual charge?",
             [("1,000,000 FCFA", False), ("2,000,000 FCFA", True), ("4,000,000 FCFA", False), ("8,000,000 FCFA", False)], "",
             r"$\frac{8\,000\,000}{4} = 2\,000\,000$ FCFA per year."),
            ("vrai_faux", "Land is normally depreciated.", FALSE_TRUE, "", "Land usually has an unlimited useful life, so it is not depreciated."),
            ("reponse_courte", "Which accounting concept requires depreciation to match an asset's cost to the periods that benefit from it? (one word)",
             [], "matching|accruals", "The matching (accruals) concept."),
        ]),
    ]),
]

# (examen, matière, année, statut, auteur, début visible par tous, suite)
CORRIGES = [
    ("BTS", "Comptabilité générale", 2025, "verifie", "M. Exemple, enseignant de comptabilité (fictif)",
     r"""## Exercice 1 : amortissement dégressif

Base amortissable : 12 000 000 FCFA, durée 5 ans, coefficient dégressif 2.

Taux dégressif : $t = \frac{100}{5} \times 2 = 40\,\%$

| Année | Base | Annuité | VNC fin d'année |
|---|---|---|---|
| N | 12 000 000 | 4 800 000 | 7 200 000 |
| N+1 | 7 200 000 | 2 880 000 | 4 320 000 |
""",
     r"""## Exercice 2 : écriture de régularisation

À la clôture, la dotation de l'exercice N se comptabilise ainsi :

| Compte | Libellé | Débit | Crédit |
|---|---|---|---|
| 681 | Dotations aux amortissements | 4 800 000 | |
| 2845 | Amortissements du matériel | | 4 800 000 |
"""),
    ("BTS", "Mathématiques financières", 2025, "communaute", "Étudiant contributeur (fictif)",
     r"""## Exercice 1 : valeur acquise

Capital de 500 000 FCFA placé 3 ans à 6 % l'an, intérêts composés :

$$C_n = C_0 (1 + i)^n = 500\,000 \times 1{,}06^3 \approx 595\,508$$
""", ""),
    ("HND", "Financial Accounting", 2025, "verifie", "Mr Example, accounting lecturer (fictitious)",
     r"""## Question 1: straight-line depreciation

Annual charge: $\frac{\text{cost} - \text{residual value}}{\text{useful life}} = \frac{9\,000\,000 - 1\,000\,000}{4} = 2\,000\,000$ FCFA
""", ""),
    ("BTS", "Comptabilité générale", 2024, "en_preparation", "M. Exemple (fictif)", "À venir.", ""),
]
ANNEE_FUTURE = 2027


def pdf_demo(titre, annee):
    """Petit PDF valide d'une page, sans dépendance."""
    texte = f"{titre} - session {annee}".encode("latin-1", "replace")
    contenu = (
        b"BT /F1 20 Tf 72 760 Td (" + texte + b") Tj 0 -32 Td /F1 12 Tf "
        b"(Sujet de demonstration - ce n'est pas un vrai sujet d'examen.) Tj ET"
    )
    objets = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(contenu)).encode() + b" >>\nstream\n" + contenu + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    sortie = bytearray(b"%PDF-1.4\n")
    positions = []
    for numero, objet in enumerate(objets, start=1):
        positions.append(len(sortie))
        sortie += f"{numero} 0 obj\n".encode() + objet + b"\nendobj\n"
    debut_xref = len(sortie)
    sortie += f"xref\n0 {len(objets) + 1}\n0000000000 65535 f \n".encode()
    for position in positions:
        sortie += f"{position:010d} 00000 n \n".encode()
    sortie += f"trailer\n<< /Size {len(objets) + 1} /Root 1 0 R >>\nstartxref\n{debut_xref}\n%%EOF\n".encode()
    return bytes(sortie)


class Command(BaseCommand):
    help = "Remplit la base avec des données fictives (développement uniquement)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Refusé : DEBUG est désactivé (base de production ?).")
        if Sujet.objects.filter(source=SOURCE_DEMO).exists():
            self.stdout.write("Les sujets de démonstration sont déjà présents.")
            self.creer_corriges()
            self.creer_questions()
            return

        with transaction.atomic():
            bts, _ = Examen.objects.get_or_create(
                code="BTS", defaults={"nom_fr": "Brevet de Technicien Supérieur", "nom_en": "Higher Technician Certificate", "langue": "fr"}
            )
            hnd, _ = Examen.objects.get_or_create(
                code="HND", defaults={"nom_fr": "Higher National Diploma", "nom_en": "Higher National Diploma", "langue": "en"}
            )
            nombre = 0
            for examen in (bts, hnd):
                champ_nom = "nom_fr" if examen.langue == "fr" else "nom_en"
                specialites = {
                    code: Specialite.objects.get_or_create(
                        examen=examen, code=code, defaults={champ_nom: nom, "filiere": "commerciale"}
                    )[0]
                    for code, nom in SPECIALITES[examen.code]
                }
                sessions = {
                    annee: Session.objects.get_or_create(
                        examen=examen,
                        annee=annee,
                        defaults={"date_debut": date(annee, 4, 20), "date_fin_officielle": date(annee, 6, 30)},
                    )[0]
                    for annee in [*ANNEES_PUBLIEES, ANNEE_FUTURE]
                }
                for nom, coefficients, texte in MATIERES[examen.code]:
                    matiere = Matiere.objects.create(examen=examen, **{champ_nom: nom})
                    for code, coefficient in coefficients.items():
                        SpecialiteMatiere.objects.create(
                            specialite=specialites[code], matiere=matiere, coefficient=coefficient
                        )
                    for annee in [*ANNEES_PUBLIEES, ANNEE_FUTURE]:
                        # La session future reste en brouillon : la règle de publication l'interdit.
                        statut = Sujet.Statut.BROUILLON if annee == ANNEE_FUTURE else Sujet.Statut.PUBLIE
                        sujet = Sujet(
                            titre=nom,
                            session=sessions[annee],
                            matiere=matiere,
                            type_epreuve=Sujet.TypeEpreuve.ECRITE,
                            duree=240 if coefficients and max(coefficients.values()) >= 4 else 180,
                            nb_pages=1,
                            texte_extrait=texte,
                            source=SOURCE_DEMO,
                            statut=statut,
                        )
                        sujet.fichier.save(f"demo-{examen.code}-{annee}.pdf", ContentFile(pdf_demo(nom, annee)), save=False)
                        sujet.save()
                        sujet.specialites.set(specialites[code] for code in coefficients)
                        nombre += 1

        self.stdout.write(self.style.SUCCESS(f"{nombre} sujets de démonstration créés (session {ANNEE_FUTURE} en brouillon)."))
        self.creer_corriges()
        self.creer_questions()

    def creer_corriges(self):
        if Corrige.objects.filter(titulaire_droits=SOURCE_DEMO).exists():
            return
        for examen, matiere, annee, statut, auteur, debut, suite in CORRIGES:
            sujet = Sujet.objects.get(source=SOURCE_DEMO, session__examen__code=examen, session__annee=annee, titre=matiere)
            Corrige.objects.create(
                sujet=sujet, statut=statut, auteur=auteur, titulaire_droits=SOURCE_DEMO,
                regime_propriete=Corrige.RegimePropriete.PLATEFORME, partie_gratuite=debut, contenu=suite,
                publication=Corrige.Publication.PUBLIE if statut != Corrige.Statut.EN_PREPARATION else Corrige.Publication.BROUILLON,
            )
        self.stdout.write(self.style.SUCCESS(f"{len(CORRIGES)} corrigés de démonstration créés."))

    def creer_questions(self):
        if Question.objects.filter(explication__startswith=MARQUE_QUESTION_DEMO).exists():
            return
        nombre = 0
        for examen, matiere_nom, chapitres in QUESTIONS:
            matiere = Matiere.objects.get(examen__code=examen, nom_fr=matiere_nom) if examen == "BTS" else Matiere.objects.get(examen__code=examen, nom_en=matiere_nom)
            for ordre, (titre, questions) in enumerate(chapitres, start=1):
                chapitre = Chapitre.objects.create(matiere=matiere, ordre=ordre, **{"titre_fr" if examen == "BTS" else "titre_en": titre})
                for type_question, enonce, choix, attendue, explication in questions:
                    question = Question.objects.create(
                        chapitre=chapitre, type=type_question, enonce=enonce, reponse_attendue=attendue,
                        explication=f"{MARQUE_QUESTION_DEMO} {explication}", langue="fr" if examen == "BTS" else "en", publiee=True,
                    )
                    for texte, correct in choix:
                        Choix.objects.create(question=question, texte=texte, est_correct=correct)
                    nombre += 1
        self.stdout.write(self.style.SUCCESS(f"{nombre} questions de démonstration créées."))
