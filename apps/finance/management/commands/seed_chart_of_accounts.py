# -*- coding: utf-8 -*-
"""
Plan comptable SYCEBNL / SYSCOHADA Revise d'EVE - SOURCE UNIQUE.

Ce seed remplace definitivement l'ancien trio
(seed_chart_of_accounts_sycebnl + _detailed + _official). Il pose un plan
comptable RESSERRE et CONFORME : les comptes que l'entite EVE utilise
reellement (engagement, paie, tresorerie, fonds dedies), nommes selon la
nomenclature SYCEBNL/SYSCOHADA, avec accents corrects et hierarchie parent.

Principes :
  - Les codes EBNL specifiques (162, 462, 702, 703, 1015/1021/1025, 1041/1049,
    165, 167, 1679, 171, 172) suivent le guide d'application SYCEBNL valide
    avec l'expert (cf. docs/SPEC_SYCEBNL_COMPTABILITE_ENGAGEMENT.md).
  - Les charges (60-69) et produits (70-79) suivent le SYSCOHADA Revise.
  - Les sous-comptes operationnels EVE (5211.x banques, 571.x caisses, 181.x
    liaison projet) sont generes a partir des objets metier.
  - Les comptes hors plan resserre qui n'ont AUCUNE ecriture sont desactives
    (is_active=False) pour garder des menus de saisie lisibles. Ceux qui
    portent des ecritures sont conserves et signales.

Idempotent (update_or_create par code, double passe pour la hierarchie).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import BankAccount, CashRegister, ChartOfAccount
from apps.projects.models import Project


# (code, parent_code, class_number, name, description)
CURATED_ACCOUNTS = [
    # ===================== CLASSE 1 - Fonds propres et fonds dedies =====================
    ("10", None, 1, "Dotations et apports des EBNL", ""),
    ("101", "10", 1, "Dotations consomptibles et non consomptibles", ""),
    ("1015", "101", 1, "Dotation non consomptible sans droit de reprise",
        "Apports definitifs des adherents, en nature ou en numeraire."),
    ("1021", "101", 1, "Dotation non consomptible avec droit de reprise en numeraire",
        "Apports provisoires des adherents en numeraire (cheque, especes)."),
    ("1025", "101", 1, "Dotation non consomptible avec droit de reprise en nature",
        "Apports provisoires des adherents en nature (mobilier, materiel)."),
    ("1041", "101", 1, "Dotation consomptible",
        "Fonds destines a couvrir les charges de fonctionnement."),
    ("1049", "101", 1, "Dotation consomptible inscrite au compte de resultat",
        "Compte d'ajustement de cloture (couverture des charges de la periode)."),
    ("103", "10", 1, "Droits d'entree et fonds d'adhesion",
        "Droits d'entree percus a l'admission de nouveaux adherents."),

    ("11", None, 1, "Reserves", ""),

    ("12", None, 1, "Report a nouveau", ""),
    ("121", "12", 1, "Report a nouveau crediteur (excedents)", ""),
    ("1211", "121", 1, "Report a nouveau des excedents - resultat",
        "Solde des exercices anterieurs reporte au bilan d'ouverture (officiel SYCEBNL)."),

    ("14", None, 1, "Subventions d'investissement", ""),
    ("1417", "14", 1, "Subventions d'equipement - Organismes internationaux",
        "Subventions d'investissement recues d'organismes internationaux."),

    ("16", None, 1, "Emprunts et dettes assimilees - EBNL", ""),
    ("162", "16", 1, "Fonds affectes aux investissements",
        "Cle SYCEBNL des projets de developpement : part investissement du "
        "decaissement du bailleur."),
    ("165", "16", 1, "Fonds non consommes en fin d'exercice",
        "Report inter-exercices des fonds d'investissement non utilises."),
    ("167", "16", 1, "Fonds provenant des dons et legs d'immobilisations",
        "Contrepartie au bilan des immobilisations recues en don."),
    ("1679", "16", 1, "Engagement aupres du donateur",
        "Contrepartie de la quote-part rapportee au resultat."),
    ("171", "16", 1, "Donation temporaire d'usufruit",
        "Usufruit temporaire d'un bien cede a titre gratuit a l'entite."),
    ("172", "16", 1, "Legs non encore recus d'immobilisations destinees a la vente",
        "Engagement recu au titre de legs d'immobilisations destinees a la vente."),

    ("18", None, 1, "Comptes de liaison et fonds dedies internes",
        "Comptes EVE internes de liaison projet <-> Budget General."),
    ("181", "18", 1, "Comptes de liaison projets EVE",
        "Parent des sous-comptes 181.x generes par projet."),
    ("1851", "18", 1, "Depots recus", "Depots de garantie recus des adherents."),

    ("192", None, 1, "Provisions pour charges sur legs et dons",
        "Provisions au passif des engagements aupres des donateurs."),

    # ===================== CLASSE 2 - Immobilisations =====================
    ("20", None, 2, "Charges immobilisees", ""),
    ("2011", "20", 2, "Usufruit temporaire",
        "Immobilisation incorporelle issue d'une donation d'usufruit."),
    ("203", "20", 2, "Batiments destines a la vente provenant de legs non encore recus", ""),
    ("204", "20", 2, "Materiels destines a la vente provenant de legs non encore recus", ""),

    ("22", None, 2, "Terrains", ""),
    ("2221", "22", 2, "Terrains a batir", ""),
    ("2234", "22", 2, "Terrains nus", ""),

    ("23", None, 2, "Batiments, installations techniques", ""),
    ("2313", "23", 2, "Batiments administratifs et commerciaux", ""),
    ("2318", "23", 2, "Autres batiments", ""),

    ("24", None, 2, "Materiel, mobilier, agencements", ""),
    ("2441", "24", 2, "Mobilier de bureau", ""),
    ("2442", "24", 2, "Materiel informatique", ""),
    ("2443", "24", 2, "Materiel telephonique et bureautique", ""),
    ("2451", "24", 2, "Materiel automobile", ""),

    ("25", None, 2, "Avances et acomptes verses sur immobilisations", ""),
    ("252", "25", 2, "Avances et acomptes verses sur immobilisations corporelles", ""),

    ("28", None, 2, "Amortissements", ""),
    ("280", "28", 2, "Amortissements d'usufruit temporaire", ""),
    ("2838", "28", 2, "Amortissements des batiments", ""),
    ("2844", "28", 2, "Amortissements du mobilier de bureau et du materiel", ""),
    ("2845", "28", 2, "Amortissements du materiel automobile", ""),

    ("29", None, 2, "Depreciations des immobilisations", ""),
    ("2902", "29", 2, "Depreciations des immobilisations destinees a la vente", ""),

    # ===================== CLASSE 4 - Tiers =====================
    ("40", None, 4, "Fournisseurs", ""),
    ("401", "40", 4, "Fournisseurs - exploitation", ""),
    ("4011", "40", 4, "Fournisseurs locaux", ""),

    ("41", None, 4, "Adherents, clients et comptes rattaches", ""),
    ("411", "41", 4, "Adherents", "Creances sur adherents (cotisations a recevoir)."),
    ("412", "41", 4, "Clients-usagers", "Creances sur usagers / beneficiaires payants."),
    ("4161", "41", 4, "Adherents, cotisations douteuses", ""),

    ("42", None, 4, "Personnel", ""),
    ("422", "42", 4, "Personnel, remunerations dues",
        "Dette envers les salaries au titre des salaires nets a payer."),

    ("43", None, 4, "Organismes sociaux", ""),
    ("431", "43", 4, "Securite sociale",
        "Dette envers la CSS (cotisations patronales et salariales)."),
    ("432", "43", 4, "Caisses de retraite", "Dette envers l'IPRES."),

    ("44", None, 4, "Etat et collectivites publiques", ""),
    ("4421", "44", 4, "Etat, impots et taxes d'Etat",
        "IRPP retenu, TRIMF, CFCE, vignettes : dette envers le Tresor."),
    ("4451", "44", 4, "Etat, TVA recuperable", ""),
    ("4453", "44", 4, "Etat, TVA collectee", ""),

    ("45", None, 4, "Apporteurs et associes", ""),
    ("4511", "45", 4, "Apporteurs en nature",
        "Souscription a la constitution / nouvelle dotation en nature."),
    ("4512", "45", 4, "Apporteurs en numeraire",
        "Souscription a la constitution / nouvelle dotation en numeraire."),

    ("46", None, 4, "Bailleurs - fonds dedies",
        "Comptes specifiques EBNL pour la mecanique des projets de developpement."),
    ("462", "46", 4, "Fonds d'administration",
        "Cle SYCEBNL des projets de developpement : part fonctionnement du "
        "decaissement du bailleur. Au fur et a mesure de l'engagement des "
        "charges, on debite 462 / credite 702."),

    ("47", None, 4, "Comptes transitoires et a regulariser", ""),
    ("4732", "47", 4, "Subventions d'equipement a recevoir - Organismes internationaux", ""),
    ("475", "47", 4, "Generosites financieres a recevoir",
        "Promesses de dons et legs en numeraire signees mais non encaissees."),
    ("476", "47", 4, "Charges comptabilisees d'avance", ""),

    ("48", None, 4, "Creances et dettes hors activites ordinaires", ""),
    ("4812", "48", 4, "Fournisseurs d'investissement - immobilisations corporelles", ""),
    ("4861", "48", 4, "Dettes des dons et legs d'immobilisations", ""),

    # ===================== CLASSE 5 - Tresorerie =====================
    ("52", None, 5, "Banques", ""),
    ("521", "52", 5, "Banques en monnaies locales", ""),
    ("5211", "521", 5, "Banques EVE - XOF",
        "Parent des sous-comptes 5211.x generes a partir des comptes bancaires EVE."),

    ("57", None, 5, "Caisse", ""),
    ("571", "57", 5, "Caisse en monnaie locale",
        "Parent des sous-comptes 571.x generes a partir des caisses EVE."),

    ("58", None, 5, "Virements internes", ""),
    ("585", "58", 5, "Virements internes - banque vers caisse / inter-comptes",
        "Compte tampon pour les transferts entre comptes EVE."),

    # ===================== CLASSE 6 - Charges (SYSCOHADA Revise) =====================
    ("60", None, 6, "Achats et variations de stocks", ""),
    ("601", "60", 6, "Achats de marchandises", ""),
    ("6011", "60", 6, "Achats de fournitures liees a l'activite",
        "Petits consommables, intrants de formation, kits beneficiaires."),
    ("6035", "60", 6, "Variation de stocks de fournitures et autres approvisionnements", ""),
    ("605", "60", 6, "Autres achats (non stockes)",
        "Eau, electricite, telecoms, fournitures de bureau, carburant."),
    ("6051", "605", 6, "Frais d'eau", ""),
    ("6052", "605", 6, "Frais d'electricite", ""),
    ("6053", "605", 6, "Frais de telecommunications - mobile",
        "Abonnements mobile, recharges, forfaits (Orange / Free / Expresso)."),
    ("6054", "605", 6, "Fournitures de bureau", "Papier, stylos, classeurs, cartouches."),
    ("6055", "605", 6, "Produits d'entretien", "Detergents, balais, sacs poubelle."),
    ("6056", "605", 6, "Petit outillage et materiel",
        "Materiel de cuisine, outils techniques, petits equipements terrain."),
    ("6057", "605", 6, "Carburants et lubrifiants",
        "Carburant vehicules, motos, generateurs."),
    ("6058", "605", 6, "Autres fournitures non stockables", ""),

    ("61", None, 6, "Transports", ""),
    ("611", "61", 6, "Transports sur achats", ""),
    ("613", "61", 6, "Transports du personnel",
        "Taxis, navettes, billets de transport du personnel."),
    ("6131", "613", 6, "Transport quotidien du personnel", "Taxis, transports urbains."),
    ("6132", "613", 6, "Perdiem et frais de mission", "Perdiem terrain, indemnites de mission."),
    ("618", "61", 6, "Voyages et deplacements", ""),
    ("6181", "618", 6, "Voyages et deplacements - mission terrain",
        "Transport sur missions terrain (avion, train, bus, location)."),

    ("62", None, 6, "Services exterieurs A", ""),
    ("622", "62", 6, "Locations et charges locatives", ""),
    ("6221", "622", 6, "Location de batiments (loyer bureau)", "Loyer des locaux administratifs."),
    ("6222", "622", 6, "Location de vehicules", "Location de voitures pour missions, supervisions."),
    ("6223", "622", 6, "Location de materiel et outillage",
        "Video-projecteur, sonorisation, generateurs."),
    ("6224", "622", 6, "Charges locatives (eau / electricite incluses)", ""),
    ("624", "62", 6, "Entretien, reparations et maintenance", ""),
    ("6241", "624", 6, "Entretien et reparations des vehicules", ""),
    ("6242", "624", 6, "Entretien et reparations du materiel de bureau", ""),
    ("6243", "624", 6, "Entretien et reparations des batiments", ""),
    ("625", "62", 6, "Primes d'assurance", ""),
    ("6251", "625", 6, "Assurance vehicules", ""),
    ("6252", "625", 6, "Assurance locaux et materiel", ""),
    ("6253", "625", 6, "Assurance responsabilite civile", ""),
    ("626", "62", 6, "Etudes, recherches et documentation", ""),
    ("6261", "626", 6, "Etudes et recherches", "Etudes de base, evaluations externes."),
    ("6263", "626", 6, "Documentation generale et abonnements", "Livres, revues, abonnements."),
    ("627", "62", 6, "Publicite, publications, relations publiques", ""),
    ("6272", "627", 6, "Publications", "Brochures, plaquettes, rapports imprimes."),
    ("6274", "627", 6, "Communication et visibilite bailleur",
        "Banderoles, t-shirts, supports terrain bailleur."),
    ("6277", "627", 6, "Frais de colloques, seminaires et conferences",
        "Organisation d'ateliers, comites locaux de developpement (CLD/CDD), rencontres."),
    ("628", "62", 6, "Frais de telecommunications - fixes et internet", ""),
    ("6281", "628", 6, "Telephone fixe", ""),
    ("6282", "628", 6, "Internet et fibre", "Abonnements internet, fibre bureau."),
    ("6283", "628", 6, "Frais postaux et courriers", "Affranchissement, envois express."),

    ("63", None, 6, "Services exterieurs B", ""),
    ("631", "63", 6, "Frais bancaires et services bancaires", ""),
    ("6311", "631", 6, "Commissions sur services bancaires",
        "Frais de virement, commissions de tenue de compte."),
    ("6312", "631", 6, "Frais sur effets et cartes", "Frais de change, frais de carte bancaire."),
    ("632", "63", 6, "Frais de formation du personnel",
        "Formations de capitalisation du personnel EVE (hors beneficiaires)."),
    ("633", "63", 6, "Frais sur formations et seminaires beneficiaires",
        "Formations beneficiaires, seminaires terrain."),
    ("636", "63", 6, "Frais de recherche de fonds",
        "Frais engages pour rechercher des dons et subventions (SYCEBNL App.12)."),
    ("637", "63", 6, "Redevances pour brevets, licences et droits", ""),
    ("638", "63", 6, "Honoraires et services intellectuels", ""),
    ("6381", "638", 6, "Honoraires consultants", "Experts ponctuels, consultants techniques."),
    ("6382", "638", 6, "Honoraires audit et expertise comptable",
        "Commissariat aux comptes, expertise comptable."),
    ("6383", "638", 6, "Honoraires juridiques", "Avocats, notaires."),

    ("64", None, 6, "Impots et taxes", ""),
    ("641", "64", 6, "Impots et taxes directs", "IRPP (retenue a la source), TRIMF cote employeur."),
    ("6411", "641", 6, "Taxes sur appointements et salaires",
        "IRPP retenu a la source sur salaires - charge de l'employeur."),
    ("6412", "641", 6, "TRIMF - taxe representative de l'impot minimum forfaitaire", ""),
    ("645", "64", 6, "Impots et taxes d'exploitation", ""),
    ("6451", "645", 6, "CFCE - Contribution Forfaitaire a la Charge de l'Employeur",
        "3% des salaires bruts - charge patronale."),
    ("646", "64", 6, "Droits d'enregistrement et autres", ""),
    ("6461", "646", 6, "Patente / Contribution economique locale", ""),
    ("6462", "646", 6, "Vignettes vehicules", ""),

    ("65", None, 6, "Autres charges", ""),
    ("651", "65", 6, "Pertes sur creances irrecouvrables", ""),
    ("652", "65", 6, "Subventions versees par l'entite",
        "Cofinancements et subventions versees aux partenaires de mise en oeuvre."),
    ("657", "65", 6, "Bourses, appuis et secours",
        "Appuis directs beneficiaires (transferts monetaires, kits), bourses."),
    ("658", "65", 6, "Charges diverses d'exploitation", ""),
    ("6581", "658", 6, "Dons et cotisations versees", "Cotisations associatives, dons divers."),
    ("6582", "658", 6, "Frais de reception et hospitalites", "Reception d'hotes, invites, partenaires."),
    ("6583", "658", 6, "Frais de representation", ""),

    ("66", None, 6, "Charges de personnel", ""),
    ("661", "66", 6, "Appointements, salaires et commissions", ""),
    ("6611", "661", 6, "Salaires bruts personnel national", "Personnel salarie EVE (national)."),
    ("6612", "661", 6, "Salaires bruts personnel expatrie", "Si applicable."),
    ("6613", "661", 6, "Vacations et heures supplementaires", ""),
    ("663", "66", 6, "Primes et indemnites", ""),
    ("6631", "663", 6, "Primes et gratifications", "Primes de performance, anciennete, fonction."),
    ("6632", "663", 6, "Indemnites prestataires terrain",
        "Animateurs, relais communautaires, vacataires."),
    ("664", "66", 6, "Charges sociales", "Cotisations patronales (SYCEBNL App.8)."),
    ("6641", "664", 6, "IPRES - cotisations patronales retraite",
        "Part patronale 8,4% (cadre) ou 14% (non-cadre)."),
    ("6642", "664", 6, "CSS - Caisse de Securite Sociale",
        "Part patronale : accidents du travail + allocations familiales."),
    ("6643", "664", 6, "Allocations familiales", ""),
    ("6644", "664", 6, "Accidents du travail", ""),
    ("6645", "664", 6, "IPM - Institut de Prevoyance Maladie", "Mutuelle medicale obligatoire."),
    ("668", "66", 6, "Autres charges de personnel", ""),
    ("6681", "668", 6, "Formation du personnel", "Formations internes EVE et seminaires."),
    ("6682", "668", 6, "Frais medicaux du personnel", "Au-dela de l'IPM."),
    ("6683", "668", 6, "Hospitalites et restauration du personnel", "Repas, evenements internes."),
    ("6684", "668", 6, "Hebergement du personnel en mission", ""),
    ("6685", "668", 6, "Oeuvres sociales et retraites complementaires", ""),

    ("67", None, 6, "Frais financiers et charges assimilees", ""),
    ("671", "67", 6, "Interets sur emprunts", ""),
    ("672", "67", 6, "Interets sur decouverts bancaires et agios", "Decouverts, interets debiteurs."),
    ("674", "67", 6, "Pertes de change", ""),
    ("678", "67", 6, "Autres charges financieres", ""),

    ("68", None, 6, "Dotations aux amortissements, provisions et depreciations", ""),
    ("680", "68", 6, "Dotations aux amortissements d'usufruit temporaire", ""),
    ("681", "68", 6, "Dotations aux amortissements d'exploitation", ""),
    ("6813", "681", 6, "Dotations aux amortissements des immobilisations corporelles", ""),

    ("69", None, 6, "Dotations aux depreciations hors activites ordinaires", ""),
    ("6952", "69", 6, "Dotations aux depreciations d'immobilisations destinees a la vente", ""),

    # ===================== CLASSE 7 - Produits =====================
    ("70", None, 7, "Ventes, cotisations et quote-parts EBNL", ""),
    ("701", "70", 7, "Cotisations des adherents", ""),
    ("702", "70", 7, "Quote-part de fonds d'administration transferes au compte de resultat",
        "Cle SYCEBNL : produit de neutralisation des charges engagees sur le "
        "fonds d'administration 462. On debite 462 / credite 702 a mesure de "
        "l'engagement pour neutraliser l'impact sur le resultat."),
    ("703", "70", 7, "Quote-part des dotations consomptibles transferees au compte de resultat",
        "Couverture des charges engagees sur dotation consomptible 1041 (cf. 1049)."),
    ("7041", "70", 7, "Dons en numeraire courants", ""),
    ("7044", "70", 7, "Zakat", ""),
    ("7045", "70", 7, "Celebrations et evenements religieux", ""),
    ("706", "70", 7, "Revenus des manifestations", ""),
    ("7081", "70", 7, "Ventes de dons en nature", ""),
    ("7082", "70", 7, "Revenus d'usufruit", ""),

    ("71", None, 7, "Subventions d'exploitation",
        "Subventions de fonctionnement recues (usage EBNL hors mecanique 162/462)."),

    ("75", None, 7, "Subventions et dons recus", ""),
    ("751", "75", 7, "Subventions bailleurs internationaux", ""),
    ("7511", "751", 7, "Subventions Nous-Cims (Espagne)", "PNBSF, Saint-Louis, ECP, Pikine, GT-Wallu."),
    ("7512", "751", 7, "Subventions AXA Climate / ISF", "ISF-AXA."),
    ("7513", "751", 7, "Subventions Oghogho Meye / La Locomotiva", "Projet ECO-AVENIR."),
    ("7514", "751", 7, "Subventions ChildFund / P&G", "Reponse urgence inondations."),
    ("7515", "751", 7, "Subventions ONAS-AFD", "PDBH IEC."),
    ("7516", "751", 7, "Subventions OXFAM", ""),
    ("7517", "751", 7, "Subventions FNC (Fonds National de la Culture)", "PAR / autres conventions FNC."),
    ("7518", "751", 7, "Autres subventions bailleurs internationaux", ""),
    ("752", "75", 7, "Contribution du fondateur",
        "Contribution annuelle du fondateur pour la couverture des frais de fonctionnement."),
    ("753", "75", 7, "Subventions et dons institutions locales",
        "Etat senegalais, collectivites territoriales."),
    ("754", "75", 7, "Subventions et dons particuliers", ""),
    ("7542", "754", 7, "Dons en nature recus a distribuer", ""),
    ("758", "75", 7, "Autres dons et appuis recus", ""),
    ("7583", "758", 7, "Benevoles - contributions en nature", ""),

    ("77", None, 7, "Revenus financiers", ""),
    ("771", "77", 7, "Interets sur depots", ""),
    ("778", "77", 7, "Autres produits financiers", "Reprises sur agios, gains de change, retrocessions."),

    ("78", None, 7, "Transferts de charges", ""),

    ("79", None, 7, "Reprises de provisions, depreciations et fonds dedies", ""),
    ("7923", "79", 7, "Fonds provenant des dons et legs - reprise au resultat", ""),
    ("7925", "79", 7, "Reprises de fonds affectes a un projet specifique", ""),
    ("7952", "79", 7, "Reprises des depreciations d'immobilisations recues", ""),
    ("7961", "79", 7, "Reprises de fonds provenant d'usufruit temporaire", ""),
    ("7962", "79", 7, "Legs non encore recus d'immobilisations destinees a la vente - reprise", ""),
    ("799", "79", 7, "Reprises de subventions d'investissement", ""),

    # ===================== CLASSE 8 - Engagements hors bilan =====================
    ("81", None, 8, "Valeurs comptables des cessions d'immobilisations", ""),
    ("818", "81", 8, "VNC des immobilisations recues destinees a la vente", ""),
    ("82", None, 8, "Produits des cessions d'immobilisations", ""),
    ("828", "82", 8, "Creances sur cessions d'immobilisations", ""),

    # ============ CLASSE 9 - Contributions volontaires en nature (analytique) ============
    ("90", None, 9, "Contributions volontaires en nature - emplois",
        "Comptabilite analytique : utilisation des contributions volontaires."),
    ("901", "90", 9, "Mise a disposition gratuite de biens", ""),
    ("904", "90", 9, "Personnel benevole", ""),
    ("91", None, 9, "Contributions volontaires en nature - ressources",
        "Comptabilite analytique : origine des contributions volontaires."),
    ("910", "91", 9, "Dons en nature", ""),
    ("914", "91", 9, "Benevolat", ""),
]


# Sous-comptes operationnels generes a partir des objets metier EVE.
BANK_TO_CODE = {
    "Banque Atlantique": ("5211.10", "Banque Atlantique - EVE"),
    "EVE-OXFAM": ("5211.20", "SUNU BANK - EVE-OXFAM (AXA + ECO)"),
    "EVE service": ("5211.30", "CBAO - EVE service (Saint-Louis)"),
    "EVE-SODIS": ("5211.40", "SUNU BANK - EVE-SODIS (ONAS PDBH)"),
    "EVE": ("5211.50", "BOA - EVE (ChildFund)"),
    "Budget General": ("5211.60", "SUNU BANK - Budget General"),
}

CASH_REGISTER_TO_CODE = {
    "Caisse centrale BG": ("571.00", "Caisse centrale BG"),
}

# Liaisons de projets clos (hors base Project active) dont le reliquat transite.
EXTRA_LIAISON_ACCOUNTS = [
    {
        "code": "181.110",
        "name": "Liaison Pikine Phase I (cloture - reliquat)",
        "description": (
            "Compte de liaison du projet AGIR Pikine Phase I, cloture en "
            "fevrier 2026 (hors base Project). Son reliquat continue de "
            "transiter par le Budget General en 2026."
        ),
    },
]


def _suffix_for_project(index: int) -> str:
    return f"{(index + 1) * 10:03d}"


class Command(BaseCommand):
    help = (
        "Pose le plan comptable SYCEBNL/SYSCOHADA resserre et conforme d'EVE "
        "(source unique), genere les sous-comptes operationnels (5211.x, 571.x, "
        "181.x) et desactive les comptes hors plan sans ecriture."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-deactivate",
            action="store_true",
            help="Ne pas desactiver les comptes hors plan (les laisse actifs).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        kept_codes = set()
        created = updated = 0

        # 1) Passe 1 : creation / mise a jour des comptes (sans parent).
        for code, _parent, cls, name, description in CURATED_ACCOUNTS:
            obj, was_created = ChartOfAccount.objects.update_or_create(
                code=code,
                defaults={
                    "name": name[:200],
                    "class_number": cls,
                    "description": description,
                    "is_liaison": code in ("18", "181"),
                    "is_active": True,
                    "deleted_at": None,
                },
            )
            kept_codes.add(code)
            created += 1 if was_created else 0
            updated += 0 if was_created else 1

        # 2) Passe 2 : rattachement des parents.
        by_code = {a.code: a for a in ChartOfAccount.objects.filter(code__in=kept_codes)}
        for code, parent_code, *_ in CURATED_ACCOUNTS:
            parent = by_code.get(parent_code) if parent_code else None
            obj = by_code[code]
            if obj.parent_id != (parent.id if parent else None):
                obj.parent = parent
                obj.save(update_fields=["parent"])

        # 3) Sous-comptes bancaires 5211.x
        parent_5211 = by_code.get("5211")
        for bank_name, (code, label) in BANK_TO_CODE.items():
            bank = BankAccount.objects.filter(
                name=bank_name, is_active=True, deleted_at__isnull=True
            ).first()
            if bank is None:
                self.stderr.write(
                    f"  /!\\ Compte bancaire '{bank_name}' introuvable, {code} non lie."
                )
                continue
            ChartOfAccount.objects.update_or_create(
                code=code,
                defaults={
                    "name": label[:200],
                    "class_number": 5,
                    "parent": parent_5211,
                    "linked_bank_account": bank,
                    "is_active": True,
                    "deleted_at": None,
                },
            )
            kept_codes.add(code)

        # 4) Sous-comptes caisses 571.x
        parent_571 = by_code.get("571")
        for register_name, (code, label) in CASH_REGISTER_TO_CODE.items():
            register = CashRegister.objects.filter(name=register_name).first()
            if register is None:
                register, _ = CashRegister.objects.get_or_create(
                    name=register_name, defaults={"currency": "XOF"}
                )
            ChartOfAccount.objects.update_or_create(
                code=code,
                defaults={
                    "name": label[:200],
                    "class_number": 5,
                    "parent": parent_571,
                    "linked_cash_register": register,
                    "is_active": True,
                    "deleted_at": None,
                },
            )
            kept_codes.add(code)

        # 5) Comptes de liaison 181.x par projet actif + liaisons speciales.
        parent_181 = by_code.get("181")
        projects = list(
            Project.objects.filter(is_active=True, deleted_at__isnull=True).order_by("code")
        )
        for index, project in enumerate(projects):
            code = f"181.{_suffix_for_project(index)}"
            name = f"Liaison {project.short_title or project.title or project.code}"
            ChartOfAccount.objects.update_or_create(
                code=code,
                defaults={
                    "name": name[:200],
                    "class_number": 1,
                    "parent": parent_181,
                    "is_liaison": True,
                    "linked_project": project,
                    "is_active": True,
                    "deleted_at": None,
                    "description": f"Compte de liaison interne EVE pour le projet {project.code}.",
                },
            )
            kept_codes.add(code)
        for spec in EXTRA_LIAISON_ACCOUNTS:
            ChartOfAccount.objects.update_or_create(
                code=spec["code"],
                defaults={
                    "name": spec["name"][:200],
                    "class_number": 1,
                    "parent": parent_181,
                    "is_liaison": True,
                    "is_active": True,
                    "deleted_at": None,
                    "description": spec.get("description", ""),
                },
            )
            kept_codes.add(spec["code"])

        # 6) Resserrement : desactive les comptes hors plan SANS ecriture.
        deactivated = 0
        kept_with_lines = []
        if not options["no_deactivate"]:
            outsiders = ChartOfAccount.objects.filter(
                is_active=True, deleted_at__isnull=True
            ).exclude(code__in=kept_codes)
            for acc in outsiders:
                if acc.journal_lines.exists():
                    kept_with_lines.append(acc.code)
                else:
                    acc.is_active = False
                    acc.save(update_fields=["is_active"])
                    deactivated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Plan comptable SYCEBNL resserre : {created} crees, {updated} mis a jour, "
            f"{len(kept_codes)} comptes actifs au plan."
        ))
        if deactivated:
            self.stdout.write(
                f"  {deactivated} comptes hors plan (sans ecriture) desactives."
            )
        if kept_with_lines:
            self.stdout.write(self.style.WARNING(
                f"  {len(kept_with_lines)} comptes hors plan CONSERVES car ils portent "
                f"des ecritures : {', '.join(sorted(kept_with_lines)[:30])}"
                + (" ..." if len(kept_with_lines) > 30 else "")
            ))
