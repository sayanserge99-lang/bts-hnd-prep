"""Épreuves provisoires d'entraînement (BTS informatique et HND) : rédigées par BTS-HND Prep au format de
l'examen, en attendant les vrais sujets. Ce ne sont pas des sujets officiels ; chaque PDF le dit en tête.
Les épreuves de 2025 reprennent les données des corrigés et des examens blancs de démonstration."""

EPREUVES_BTS_INFORMATIQUE = {
    "Algorithmique et programmation": {
        2022: """
# Exercice 1 : algorithmique de base (6 points)
1. Écrire un algorithme qui lit un entier n et affiche la somme des entiers de 1 à n.
2. Écrire un algorithme qui lit 10 notes sur 20 et affiche la moyenne, la plus forte et la plus faible.
# Exercice 2 : tableaux (7 points)
Soit un tableau T de N entiers.
1. Écrire une fonction qui compte le nombre d'éléments pairs de T.
2. Écrire une procédure qui inverse l'ordre des éléments de T sans utiliser de second tableau.
# Exercice 3 : chaînes de caractères (7 points)
1. Écrire une fonction qui indique si un mot est un palindrome (exemple : « kayak »).
2. Donner la trace de votre fonction pour le mot « radar ».
""",
        2023: """
# Exercice 1 : tri (7 points)
1. Écrire l'algorithme du tri par sélection d'un tableau de N entiers.
2. Dérouler l'algorithme sur le tableau [7, 3, 9, 1, 5].
3. Donner sa complexité dans le pire des cas.
# Exercice 2 : enregistrements (7 points)
On gère les étudiants d'un IPES : matricule, nom, filière, moyenne.
1. Définir le type Etudiant.
2. Écrire une procédure qui affiche les étudiants admis (moyenne >= 10) d'une filière donnée.
# Exercice 3 : programmation (6 points)
Traduire en langage C ou Python la fonction de l'exercice 1 et indiquer comment la tester.
""",
        2024: """
# Exercice 1 : fichiers (6 points)
Un fichier texte contient, une par ligne, les ventes journalières d'une boutique (date;montant).
Écrire un algorithme qui calcule le total et la moyenne des ventes, et affiche le meilleur jour.
# Exercice 2 : piles et files (7 points)
1. Définir une pile et une file ; donner les opérations de base de chacune.
2. Écrire un algorithme qui utilise une pile pour vérifier qu'une expression est bien parenthésée : « (a+b)*(c-d) ».
# Exercice 3 : programmation orientée objet (7 points)
1. Définir les notions de classe, d'objet et d'encapsulation.
2. Écrire une classe CompteBancaire (titulaire, solde) avec les méthodes deposer et retirer (refus si solde insuffisant).
""",
        2025: """
# Exercice 1 : algorithme de recherche (7 points)
On dispose d'un tableau T de N entiers triés par ordre croissant.
1. Écrire l'algorithme de recherche dichotomique d'une valeur x dans T.
2. Combien de comparaisons fait-il au pire pour N = 1 024 ? Justifier.
3. Comparer avec la recherche séquentielle.
# Exercice 2 : fonction récursive (7 points)
1. Écrire une fonction récursive qui calcule la factorielle d'un entier n.
2. Écrire une fonction récursive qui calcule la somme des chiffres d'un entier (exemple : 2025 donne 9).
3. Expliquer le rôle du cas de base et ce qui se passe s'il est oublié.
# Exercice 3 : structures de données (6 points)
Expliquer la différence entre une pile et une file. Donner un exemple d'utilisation de chacune dans un logiciel de gestion de caisse.
""",
        2026: """
# Exercice 1 : listes chaînées (7 points)
1. Définir une liste simplement chaînée d'entiers.
2. Écrire les procédures d'insertion en tête et de suppression d'une valeur donnée.
# Exercice 2 : complexité (6 points)
Donner la complexité des algorithmes suivants et justifier : recherche séquentielle, tri par insertion, recherche dichotomique, deux boucles imbriquées de 1 à n.
# Exercice 3 : projet (7 points)
Une pharmacie veut un programme qui gère son stock de médicaments (code, nom, quantité, date de péremption).
1. Proposer les structures de données.
2. Écrire l'algorithme qui affiche les médicaments périmés et ceux dont la quantité est inférieure à un seuil.
""",
    },
    "Bases de données": {
        2022: """
# Exercice 1 : modélisation (8 points)
Une auto-école de Yaoundé veut gérer ses élèves, ses moniteurs, ses véhicules et les leçons de conduite (date, heure, durée).
1. Établir le modèle conceptuel des données (entités, associations, cardinalités).
2. En déduire le modèle logique relationnel.
# Exercice 2 : SQL (8 points)
Schéma : ELEVE(num, nom, prenom, telephone), LECON(id, num_eleve, date_lecon, duree).
1. Créer la table LECON avec ses clés.
2. Afficher les élèves qui n'ont encore suivi aucune leçon.
3. Afficher, pour chaque élève, le nombre total d'heures de conduite.
# Exercice 3 : cours (4 points)
Définir : clé primaire, clé étrangère, intégrité référentielle.
""",
        2023: """
# Exercice 1 : normalisation (7 points)
La relation COMMANDE(num_cmd, date, code_client, nom_client, ville_client, code_produit, libelle, quantite, prix) est en première forme normale.
1. Donner les dépendances fonctionnelles.
2. Décomposer la relation en troisième forme normale.
# Exercice 2 : SQL (9 points)
Avec les tables obtenues :
1. Lister les commandes du mois de mars avec le nom du client.
2. Calculer le chiffre d'affaires par ville.
3. Afficher le produit le plus vendu.
# Exercice 3 : sécurité (4 points)
Expliquer le rôle des instructions GRANT et REVOKE et donner un exemple.
""",
        2024: """
# Exercice 1 : modélisation (7 points)
Un centre de santé gère ses patients, ses médecins, les consultations et les ordonnances (médicaments, posologie). Établir le MCD puis le MLD.
# Exercice 2 : SQL (9 points)
1. Écrire la requête qui donne le nombre de consultations par médecin en 2024.
2. Afficher les patients consultés plus de trois fois.
3. Créer une vue des consultations du jour.
# Exercice 3 : transactions (4 points)
Définir une transaction et les propriétés ACID ; donner un exemple dans une application bancaire.
""",
        2025: """
# Exercice 1 : modèle relationnel (6 points)
Une banque de microfinance gère ses clients, ses comptes et les opérations (dépôt, retrait, date, montant).
1. Donner le schéma relationnel en soulignant les clés primaires et en indiquant les clés étrangères.
2. Expliquer pourquoi une opération ne peut pas exister sans compte.
# Exercice 2 : requêtes SQL (10 points)
1. Afficher le solde de chaque compte (somme des dépôts moins somme des retraits).
2. Lister les clients qui ont plus de deux comptes.
3. Afficher les opérations de plus de 500 000 FCFA du mois de janvier, triées par montant décroissant.
4. Écrire une jointure qui donne le nom du client pour chaque opération.
# Exercice 3 : cours (4 points)
Distinguer jointure interne et jointure externe, avec un exemple.
""",
        2026: """
# Exercice 1 : modélisation (7 points)
Une agence de voyages routiers (Douala–Yaoundé–Bafoussam) gère ses bus, ses chauffeurs, ses trajets et les réservations des passagers. Établir le MCD et le MLD.
# Exercice 2 : SQL avancé (9 points)
1. Afficher le taux de remplissage de chaque trajet.
2. Afficher les chauffeurs qui ont conduit sur tous les trajets.
3. Écrire un déclencheur (trigger) qui refuse une réservation quand le bus est complet.
# Exercice 3 : administration (4 points)
Proposer une politique de sauvegarde de la base de données de l'agence.
""",
    },
    "Réseaux et systèmes": {
        2022: """
# Exercice 1 : modèle OSI (6 points)
1. Citer les sept couches du modèle OSI et le rôle de chacune.
2. À quelles couches travaillent un switch, un routeur et un concentrateur (hub) ?
# Exercice 2 : adressage IP (8 points)
Une entreprise dispose de l'adresse 192.168.10.0/24.
1. Donner l'adresse de réseau, de diffusion et le nombre d'hôtes possibles.
2. Découper ce réseau en 4 sous-réseaux de même taille ; donner le masque et les plages d'adresses.
# Exercice 3 : systèmes (6 points)
Expliquer le rôle d'un système d'exploitation et citer quatre de ses fonctions.
""",
        2023: """
# Exercice 1 : câblage et topologies (6 points)
1. Comparer les topologies en bus, en étoile et maillée.
2. Quel câble choisir pour relier deux bâtiments distants de 300 mètres ? Justifier.
# Exercice 2 : TCP/IP (8 points)
1. Comparer TCP et UDP ; donner deux applications de chacun.
2. Expliquer le rôle du DNS et du DHCP dans un réseau d'entreprise.
# Exercice 3 : Linux (6 points)
Donner les commandes pour : créer un utilisateur, changer les droits d'un fichier, afficher l'adresse IP, tester la connexion à une machine.
""",
        2024: """
# Exercice 1 : sous-réseaux (8 points)
L'adresse 172.16.0.0/16 doit être découpée pour 6 services comptant au plus 500 postes chacun. Proposer un plan d'adressage (masque, adresses de réseau, premières et dernières adresses).
# Exercice 2 : équipements (6 points)
Un cybercafé de Bamenda veut partager une connexion internet entre 20 postes. Proposer une architecture et la configuration de base du routeur.
# Exercice 3 : sécurité (6 points)
Citer trois menaces pour ce réseau et une mesure de protection pour chacune.
""",
        2025: """
# Exercice 1 : modèle OSI et protocoles (6 points)
1. Présenter le modèle OSI et situer les protocoles TCP, UDP, IP et HTTP.
2. Pourquoi la vidéo en direct utilise-t-elle souvent UDP ?
# Exercice 2 : adressage IPv4 (8 points)
Un établissement reçoit l'adresse 10.20.0.0/22.
1. Calculer le nombre d'adresses utilisables.
2. Découper en sous-réseaux pour l'administration (60 postes), les laboratoires (200 postes) et le Wi-Fi des étudiants (500 postes).
# Exercice 3 : services réseau (6 points)
Décrire le fonctionnement du DHCP (les quatre messages) et dire ce qui se passe quand le serveur DHCP est en panne.
""",
        2026: """
# Exercice 1 : VLAN (7 points)
1. Définir un VLAN et ses avantages.
2. Proposer un découpage en VLAN pour une banque : direction, guichets, caméras, invités.
# Exercice 2 : routage (7 points)
1. Distinguer routage statique et dynamique.
2. Écrire la table de routage d'un routeur reliant deux réseaux locaux et l'accès internet.
# Exercice 3 : virtualisation (6 points)
Expliquer la virtualisation de serveurs et ses avantages pour une PME.
""",
    },
}

EPREUVES_HND = {
    "Financial Accounting": {
        2022: """
# Question 1: books of prime entry (6 marks)
Ngwa Traders, Bamenda, had the following transactions in March: bought goods on credit from Fon Ltd, 1 800 000 FCFA; sold goods for cash, 950 000 FCFA; paid rent by cheque, 250 000 FCFA; returned goods worth 120 000 FCFA to Fon Ltd.
Record the transactions in the appropriate books of prime entry and post them to the ledger.
# Question 2: trial balance (6 marks)
Explain the purpose of a trial balance and list four errors that it does not reveal.
# Question 3: bank reconciliation (8 marks)
The cash book shows a debit balance of 640 000 FCFA; the bank statement shows 712 000 FCFA. Unpresented cheques: 95 000 FCFA; bank charges not recorded: 8 000 FCFA; credit transfer from a customer not recorded: 15 000 FCFA.
Update the cash book and prepare the bank reconciliation statement.
""",
        2023: """
# Question 1: accruals and prepayments (8 marks)
At 31 December, the following adjustments are required: electricity owing 85 000 FCFA; insurance prepaid 120 000 FCFA; rent received in advance 300 000 FCFA.
Show the journal entries and the effect on the profit for the year.
# Question 2: bad debts (6 marks)
Trade receivables stand at 4 500 000 FCFA. A debt of 150 000 FCFA is written off and an allowance for doubtful debts of 5% is created on the remaining balance. Show the entries.
# Question 3: theory (6 marks)
Explain the accruals concept and the prudence concept with an example of each.
""",
        2024: """
# Question 1: disposal of assets (8 marks)
A motor vehicle bought on 1 January 2021 for 8 000 000 FCFA (straight-line, 5 years, no residual value) was sold on 31 December 2023 for 3 500 000 FCFA.
Prepare the asset disposal account and calculate the profit or loss on disposal.
# Question 2: final accounts (12 marks)
From the trial balance provided in the appendix (sales 25 000 000; purchases 15 600 000; opening inventory 2 100 000; closing inventory 2 600 000; expenses 4 300 000; non-current assets 12 000 000; receivables 3 200 000; payables 2 800 000; capital 15 000 000), prepare the income statement and the statement of financial position.
""",
        2025: """
# Question 1: straight-line depreciation (7 marks)
Moto Express Ltd, Buea, bought a delivery van for 9 000 000 FCFA. Its useful life is 4 years and its residual value 1 000 000 FCFA.
1. Calculate the annual depreciation charge using the straight-line method.
2. Prepare the depreciation schedule for the four years.
3. Calculate the charge for year 1 using the reducing balance method at 40% and compare.
# Question 2: accruals (6 marks)
Show the year-end entries for: wages owing 210 000 FCFA; rent prepaid 150 000 FCFA; commission receivable 60 000 FCFA.
# Question 3: final accounts (7 marks)
Explain the difference between capital expenditure and revenue expenditure and classify: purchase of a computer, repair of a roof, delivery cost of a new machine, fuel.
""",
        2026: """
# Question 1: control accounts (7 marks)
From the data provided (opening receivables 2 400 000; credit sales 9 800 000; cash received 8 900 000; discounts allowed 150 000; returns inwards 230 000), prepare the receivables ledger control account.
# Question 2: correction of errors (6 marks)
Show the journal entries to correct: purchase of equipment debited to purchases, 600 000 FCFA; sales undercast by 100 000 FCFA. Open a suspense account where necessary.
# Question 3: partnership (7 marks)
Ade and Bih share profits 3:2 after interest on capital at 5% (capitals 10 000 000 and 6 000 000 FCFA) and a salary of 1 200 000 FCFA to Bih. Net profit: 5 800 000 FCFA. Prepare the appropriation account.
""",
    },
    "Business Mathematics": {
        2022: """
# Question 1: percentages and ratios (6 marks)
1. A trader marks up goods by 25% on cost. What is the margin on selling price?
2. Profit of 4 500 000 FCFA is shared among three partners in the ratio 2:3:4. Find each share.
# Question 2: simple and compound interest (7 marks)
1. Find the simple interest on 1 500 000 FCFA at 8% for 9 months.
2. Find the amount of 2 000 000 FCFA invested for 4 years at 6% compounded annually.
# Question 3: equations (7 marks)
A firm's cost function is C = 50 000 + 300x and its revenue function is R = 800x. Find the break-even quantity and illustrate graphically.
""",
        2023: """
# Question 1: matrices (7 marks)
A shop sells three products. Use matrices to calculate the total revenue for two weeks from the quantity and price tables given in the appendix.
# Question 2: linear programming (8 marks)
A carpenter makes tables (profit 15 000 FCFA) and chairs (profit 5 000 FCFA). A table needs 4 hours and a chair 1 hour; 40 hours are available; at most 15 items can be stored.
Formulate the problem and solve it graphically.
# Question 3: statistics (5 marks)
Find the mean, median and mode of the daily sales: 12, 15, 11, 15, 18, 20, 15, 14.
""",
        2024: """
# Question 1: annuities (7 marks)
Find the present value of 12 monthly payments of 50 000 FCFA at 1% per month.
# Question 2: differentiation (7 marks)
The profit function of a firm is P(x) = -2x² + 120x - 500. Find the output that maximises profit and the maximum profit.
# Question 3: probability (6 marks)
In a class, 60% of students pass Accounting and 70% pass Mathematics; 50% pass both. Find the probability that a student chosen at random passes at least one subject.
""",
        2025: """
# Question 1: compound interest (6 marks)
1. Find the amount of 3 000 000 FCFA invested for 5 years at 7% compounded annually.
2. How long will it take for an investment to double at 9% compounded annually?
# Question 2: annuities (7 marks)
A loan of 5 000 000 FCFA is repaid by 6 equal annual instalments at 10%. Calculate the instalment and prepare the first two lines of the amortisation schedule.
# Question 3: linear programming (7 marks)
A bakery produces bread and cakes. Formulate and solve graphically the problem given in the appendix (two constraints: oven hours and flour).
""",
        2026: """
# Question 1: index numbers (6 marks)
Using the prices of four food items in 2024 and 2026 given in the appendix, calculate a simple aggregate price index and comment.
# Question 2: correlation (7 marks)
Calculate the coefficient of correlation between advertising expenditure and sales for the six months given, and interpret the result.
# Question 3: investment appraisal (7 marks)
A project costs 12 000 000 FCFA and yields 3 500 000 FCFA a year for 5 years. Calculate the net present value at 10% and advise management.
""",
    },
    "Business Law": {
        2022: """
# Question 1: sources of law (6 marks)
Explain the main sources of business law in Cameroon, including OHADA Uniform Acts.
# Question 2: contract (8 marks)
Ebai offers to sell his car to Tanyi for 3 000 000 FCFA. Tanyi replies: "I accept at 2 800 000 FCFA." Ebai then sells the car to Mbah.
Advise Tanyi, explaining offer, counter-offer and acceptance.
# Question 3: capacity (6 marks)
Discuss the contractual capacity of minors under Cameroonian law.
""",
        2023: """
# Question 1: the trader (6 marks)
Who is a trader (commerçant) under the OHADA Uniform Act on General Commercial Law? State three obligations of a trader.
# Question 2: companies (8 marks)
Compare the sole proprietorship and the limited liability company (SARL) in terms of formation, liability and management.
# Question 3: problem question (6 marks)
A supplier delivered defective goods to a shop in Kumba. Advise the shop owner on the remedies available.
""",
        2024: """
# Question 1: employment law (7 marks)
State the essential elements of a contract of employment under the Cameroon Labour Code and the conditions of a valid dismissal.
# Question 2: negotiable instruments (6 marks)
Distinguish a cheque from a bill of exchange.
# Question 3: case study (7 marks)
A company director signs a contract outside the company's objects. Discuss whether the company is bound.
""",
        2025: """
# Question 1: formation of contract (7 marks)
Explain the requirements for the formation of a valid contract, with examples.
# Question 2: OHADA (6 marks)
Describe the role of the OHADA and of its Common Court of Justice and Arbitration (CCJA).
# Question 3: company law (7 marks)
Under the Uniform Act on Commercial Companies, explain the formation of a public limited company (SA): minimum capital, shareholders, management bodies.
""",
        2026: """
# Question 1: consumer protection (6 marks)
Discuss the protection of consumers in Cameroon (law No. 2011/012) in relation to online sales.
# Question 2: insolvency (7 marks)
Explain the collective proceedings available to a company in financial difficulty under the OHADA Uniform Act.
# Question 3: problem question (7 marks)
Two partners disagree on the sale of a company asset. Advise them on decision-making rules in a partnership.
""",
    },
    "Principles of Marketing": {
        2022: """
# Question 1: the marketing concept (6 marks)
Explain the marketing concept and distinguish it from the selling concept.
# Question 2: marketing environment (7 marks)
Analyse the PESTEL factors affecting a new soft-drink brand in Cameroon.
# Question 3: marketing mix (7 marks)
Recommend a marketing mix for a mobile phone accessories shop in Limbe.
""",
        2023: """
# Question 1: consumer behaviour (7 marks)
Describe the stages of the buying decision process and the factors that influence it.
# Question 2: segmentation (6 marks)
Explain segmentation, targeting and positioning with the example of a microfinance institution.
# Question 3: pricing (7 marks)
Discuss three pricing strategies a new cooking-oil brand could use.
""",
        2024: """
# Question 1: product life cycle (7 marks)
Explain the stages of the product life cycle and suggest a strategy for each stage.
# Question 2: distribution (6 marks)
Compare direct and indirect channels of distribution for agricultural products.
# Question 3: promotion (7 marks)
Design a promotion campaign for a new university restaurant using social media.
""",
        2025: """
# Question 1: market research (7 marks)
Distinguish primary and secondary research and draft five questions for a survey on mobile banking.
# Question 2: segmentation and positioning (6 marks)
Propose a segmentation of the cosmetics market in Cameroon and a positioning for a shea-butter cream.
# Question 3: marketing mix and consumer behaviour (7 marks)
Explain how culture and reference groups influence the purchase of cosmetics and recommend a marketing mix.
""",
        2026: """
# Question 1: digital marketing (7 marks)
Explain how small businesses can use digital marketing tools and measure their effectiveness.
# Question 2: services marketing (6 marks)
Apply the 7 Ps of services marketing to a private clinic.
# Question 3: customer relationship management (7 marks)
Explain CRM and propose a loyalty programme for a supermarket chain.
""",
    },
    "Programming": {
        2022: """
# Question 1: algorithms (6 marks)
Write an algorithm that reads 20 integers and displays how many are positive, negative and zero.
# Question 2: arrays (7 marks)
Write a function that returns the second largest value of an array of integers.
# Question 3: programming (7 marks)
Write a program in C, Java or Python that computes the electricity bill of a customer from the number of kWh consumed (tariff bands given in the appendix).
""",
        2023: """
# Question 1: sorting (7 marks)
Write the bubble sort algorithm and trace it on the array [5, 2, 8, 1, 4].
# Question 2: records (7 marks)
Define a record type for a student (ID, name, programme, GPA) and write a procedure that displays students with a GPA above 3.0.
# Question 3: theory (6 marks)
Explain the difference between compiled and interpreted languages, with examples.
""",
        2024: """
# Question 1: object-oriented programming (8 marks)
Define class, object, inheritance and polymorphism. Write a class Employee and a subclass Manager with a bonus attribute.
# Question 2: files (6 marks)
Write a program that reads a text file of sales (one amount per line) and prints the total and the average.
# Question 3: debugging (6 marks)
Identify and correct the errors in the code extract given in the appendix.
""",
        2025: """
# Question 1: searching (7 marks)
Write the binary search algorithm for a sorted array and state its complexity.
# Question 2: recursion (7 marks)
Write recursive functions for the factorial of n and for the sum of the digits of an integer. Explain the base case.
# Question 3: object-oriented programming (6 marks)
Write a class BankAccount with deposit and withdraw methods; withdrawal must be refused when the balance is insufficient.
""",
        2026: """
# Question 1: data structures (7 marks)
Implement a stack with an array and write the push and pop operations with error handling.
# Question 2: exceptions (6 marks)
Explain exception handling and illustrate with a division-by-zero example.
# Question 3: mini project (7 marks)
Design a program to manage the stock of a pharmacy (code, name, quantity, expiry date) and list expired drugs.
""",
    },
    "Database Systems": {
        2022: """
# Question 1: database concepts (6 marks)
Explain the advantages of a database management system over a file-based system.
# Question 2: ER modelling (8 marks)
Draw an entity-relationship diagram for a library: members, books, copies, loans.
# Question 3: SQL (6 marks)
Write SQL queries to list overdue loans and the number of loans per member.
""",
        2023: """
# Question 1: normalisation (8 marks)
Normalise the relation ORDER(order_no, date, customer_id, customer_name, product_id, description, qty, price) to third normal form.
# Question 2: SQL (8 marks)
Using your tables, write queries for: total sales per customer; products never ordered; orders of the last 30 days.
# Question 3: theory (4 marks)
Define primary key, foreign key and referential integrity.
""",
        2024: """
# Question 1: ER modelling (7 marks)
A hospital records patients, doctors, appointments and prescriptions. Draw the ER diagram and derive the relational schema.
# Question 2: SQL (8 marks)
Write queries to count appointments per doctor and to list patients seen more than three times.
# Question 3: transactions (5 marks)
Explain the ACID properties with a banking example.
""",
        2025: """
# Question 1: relational model (6 marks)
A microfinance institution manages customers, accounts and transactions. Give the relational schema with primary and foreign keys.
# Question 2: SQL queries (9 marks)
Write SQL queries to: compute the balance of each account; list customers with more than two accounts; show transactions above 500 000 FCFA in January ordered by amount.
# Question 3: joins and transactions (5 marks)
Distinguish inner and outer joins and explain why a transfer between two accounts must be a transaction.
""",
        2026: """
# Question 1: database design (7 marks)
Design a database for an inter-city bus company: buses, drivers, trips and bookings.
# Question 2: advanced SQL (8 marks)
Write a query giving the occupancy rate of each trip and a trigger that rejects a booking when the bus is full.
# Question 3: administration (5 marks)
Propose a backup and recovery policy for the company's database.
""",
    },
}
