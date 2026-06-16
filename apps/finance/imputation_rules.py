# -*- coding: utf-8 -*-
"""
Regles d'auto-suggestion des comptes SYCEBNL de contrepartie a partir du
libelle d'un mouvement bancaire.

NUMEROTATION CONFORME SYSCOHADA REVISE :
  - charges salariales en 66x (et non 64x)
  - impots et taxes sur salaires en 64x (et non 63x)
  - frais bancaires en 631x (et non 6281)
  - frais financiers en 67x (et non 66x)
  - subventions versees aux beneficiaires en 65x (et non 67x)

Utilise par l'assistant d'import de releves bancaires : pour chaque ligne
extraite du PDF, on tente de matcher le libelle contre une liste ordonnee
de patterns regex. Premier match gagne.

Chaque regle = (pattern_regex, contra_account_code, libelle_hint).
contra_account_code = None signifie "pas de suggestion confiante - a imputer
manuellement par le comptable".
"""

import re

# Regles ordonnees du plus specifique au plus generique. Premier match gagne.
# Patterns insensibles a la casse.
RULES = [
    # === RECETTES (credits typiques) - subventions et dons bailleurs ===
    # Plan officiel SYCEBNL : les subventions d'exploitation sont en classe
    # 71 et les dons en 7041. Pas de sous-compte par bailleur dans le plan
    # officiel - la classification par bailleur est ANALYTIQUE (champ
    # BankMovement.recipient ou allocation projet).
    # Sur un projet de developpement, le decaissement est SPLITTE en 162/462
    # par posting.py selon la cle Project.investment_split_pct (App.8).
    (r"NOUS[\s-]*CIMS|NOUSCIMS|PNBSF", "71", "Subvention d'exploitation Nous-Cims"),
    (r"\bONAS\b|\bAFD\b", "71", "Subvention d'exploitation ONAS-AFD"),
    (r"AXA[\s-]*CLIMATE|\bISF\b|ISF[\s-]*AXA", "71", "Subvention d'exploitation AXA-Climate"),
    (r"OGHOGHO|LA[\s-]*LOCOMOTIVA|ECO[\s-]*AVENIR", "71", "Subvention d'exploitation Oghogho"),
    (r"CHILDFUND|P[\s&]*G", "7041", "Don ChildFund / P&G"),
    (r"OXFAM", "71", "Subvention d'exploitation OXFAM"),
    (r"\bFNC\b", "71", "Subvention d'exploitation FNC"),

    # === Frais bancaires (SYCEBNL classe 63) ===
    (r"FRAIS\s+(BANC|TENUE|GEST)|COMMISSION\s+(BANC|TENUE|MENSUELLE)", "6311", "Commissions bancaires"),
    (r"\bAGIOS?\b|INTERET\s+DEBI|DECOUVERT", "672", "Agios / interets decouvert"),

    # === Impots et taxes payes a l'Etat (dette 4421) ===
    # En SYCEBNL officiel, IRPP/TRIMF/CFCE retenus sont des dettes 4421
    # (Etat impots et taxes d'Etat), pas des charges de la classe 64.
    # La charge correspondante est portee sur 6411 cote employeur uniquement
    # pour la part patronale CFCE. L'IRPP retenu est neutralise (4421/5211).
    (r"\bIRPP\b|IR[\s-]?PP\b|VRS[\s/-]*BRS|VRS\s+ETAT", "4421", "IRPP - dette Etat"),
    (r"\bTRIMF\b", "4421", "TRIMF - dette Etat"),
    (r"\bCFCE\b", "6453", "CFCE - charge patronale"),

    # === Charges sociales (SYCEBNL 6641/6642 officiels) ===
    (r"\bIPRES\b", "6641", "Cotisation IPRES (charges sociales national)"),
    (r"\bCSS\b|SECURIT.{0,3}SOCIAL|CAISSE\s+SECU", "6641", "Cotisation CSS (charges sociales national)"),
    (r"\bIPM\b", "6641", "Cotisation IPM (charges sociales national)"),

    # === Salaires et indemnites (SYCEBNL 6611 officiel) ===
    (r"VIREMENT\s+SALAIRE|VIRT?\s+SAL|VRS\s+SAL|SALAIRE\s+(PERS|DU)|PAIEMENT\s+SALAIRE", "6611", "Salaire personnel national"),
    (r"PRIME|GRATIFICATION", "6611", "Prime / gratification (salaires)"),
    (r"INDEMNIT", "6611", "Indemnite prestataire"),
    (r"PERDIEM|PER\s*DIEM", "614", "Perdiem mission - transports utilisateurs"),
    (r"VACATION|VACATAIRE|HONORAIRES?\s+PERS", "6611", "Vacation / heure supp"),

    # === Locations (SYCEBNL 622x) ===
    (r"LOYER|BAIL\s+LOCATION|LOCATION\s+BUREAU", "6221", "Loyer bureau"),
    (r"LOCATION\s+VEHICUL", "6222", "Location vehicule"),
    (r"LOCATION\s+(MATERIEL|OUTILLAGE|SONO|VIDEO)", "6223", "Location materiel"),

    # === Energies, eau, telecom (SYCEBNL 605x / 628 officiels) ===
    (r"SENELEC|ELECTRIC|\bELEC\b", "6052", "Electricite"),
    (r"\bSDE\b|FACTURE\s+EAU|SONES", "6051", "Eau"),
    (r"ORANGE|EXPRESSO|FREE[\s-]*SENEGAL|TIGO|TELECOM|SONATEL|FORFAIT\s+TEL", "6053", "Telephone mobile"),
    (r"INTERNET|FIBRE|WIFI|ADSL", "628", "Frais de telecommunications"),
    (r"FRAIS\s+POSTAUX|DHL|UPS|ENVOI\s+POSTAL", "628", "Frais postaux et telecoms"),

    # === Carburant et transport (SYCEBNL 6057 / 614 officiels) ===
    (r"CARBURANT|TOTAL\s+CARB|TOTAL\s+STATION|SHELL|VIVO\s+ENERG|OILIBYA|EDK|STAR\s+OIL", "6057", "Carburant"),
    (r"TRANSPORT|TAXI|YANGO|HEETCH", "614", "Transports utilisateurs"),
    (r"MISSION\s+(TERRAIN|SUPERV)|VOYAGE\s+MISSION|BILLET\s+(AVION|TRAIN|BUS)", "614", "Voyage / mission terrain"),

    # === Restauration / hospitalites (SYCEBNL 658 officiel) ===
    (r"RESTAURATION|RESTO|REPAS|TRAITEUR|CATERING|HOSP|RECEPTION|INVITES?", "658", "Reception / hospitalites"),
    (r"DEJEUNER|DINER|PETIT[\s-]+DEJ", "658", "Restauration / hospitalites"),

    # === Fournitures, materiel, entretien (SYCEBNL 605x / 624 officiels) ===
    (r"FOURNITURE|PAPETERIE|TONER|CARTOUCHE|STYLO|RAMETTE", "6054", "Fournitures bureau"),
    (r"PRODUITS?\s+ENTRETIEN|JAVEL|DETERGENT|HYGIENE", "6055", "Produits entretien"),
    (r"PETIT\s+MATERIEL|USTENSILE|VAISSELLE|CUISINE", "6056", "Petit materiel"),
    (r"ENTRETIEN\s+VEHIC|REPARATION\s+VEHIC|VIDANGE|PNEU|GARAGE", "624", "Entretien et reparations"),
    (r"ENTRETIEN\s+BAT|PEINTURE|PLOMBERIE", "624", "Entretien batiments"),

    # === Honoraires et services intellectuels (SYCEBNL 638 officiel) ===
    (r"HONORAIRES?\s+CONSULTANT|CONSULTANT|EXPERT", "638", "Honoraires consultants"),
    (r"AUDIT|COMMISSAIRE|EXPERTISE\s+COMPT", "638", "Honoraires audit"),
    (r"AVOCAT|JURIDIQUE|NOTAIRE", "638", "Honoraires juridiques"),
    (r"FORMATION|SEMINAIRE", "632", "Frais de formation"),

    # === Assurances (SYCEBNL 625 officiel) ===
    (r"ASSURANCE\s+VEHIC|SUNU\s+ASSUR|NSIA\s+VEHIC", "625", "Assurance vehicule"),
    (r"ASSURANCE\s+(LOCAL|BUREAU)|SUNU\s+ASSUR\s+LOC", "625", "Assurance locaux"),
    (r"RESPONSABILIT[\s-]+CIVIL|\bRC\b", "625", "Responsabilite civile"),

    # === Visibilite / communication bailleurs (SYCEBNL 627 officiel) ===
    (r"VISIBILIT|BANDEROLE|T[\s-]?SHIRT|BRANDING|SUPPORT\s+COMM", "627", "Publicite / visibilite"),
    (r"IMPRESSION|FLYER|BROCHURE", "627", "Publications / impressions"),

    # === Subventions et appuis verses aux beneficiaires (SYCEBNL 65 officiel) ===
    (r"APPUI\s+BENEF|CASH\s+TRANSF|KIT\s+BENEF", "654", "Appui beneficiaires (dons distribues)"),
    (r"SUBVENTION\s+(VERS|PARTENAIRE)|COFINANC", "652", "Subvention versee partenaire"),
    (r"BOURSE|STAGIAIRE", "657", "Bourse / appui stagiaire"),

    # === Virements internes (recharge caisse, virement banque-banque) ===
    (r"VIREMENT\s+INTERNE|VIRT?\s+CAISSE|RETRAIT\s+CAISSE", "585", "Virement interne / recharge caisse"),

    # === Cas ambigus - fallback manuel ===
    (r"VERSEMENT\s+PAR\s+TIERS|VRS\s+TIERS", None, "Versement par tiers - imputer manuellement"),
    (r"REMISE\s+CHEQUE|REM[\s-]+CHQ", None, "Remise cheque - imputer manuellement"),
    (r"VIREMENT", None, "Virement generique - imputer manuellement"),
]

# Pre-compile pour la perf (les imports en lot peuvent enchainer 100+ lignes).
COMPILED = [(re.compile(p, re.IGNORECASE), code, hint) for p, code, hint in RULES]


def suggest_contra_account(label: str) -> tuple[str | None, str]:
    """Renvoie (code_compte_sycebnl_ou_None, libelle_hint).

    Premier pattern qui matche gagne. Pas de match = (None, '') pour
    indiquer "a imputer manuellement par le comptable".
    """
    if not label:
        return (None, "")
    for regex, code, hint in COMPILED:
        if regex.search(label):
            return (code, hint)
    return (None, "")
