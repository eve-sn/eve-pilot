"""
Moteur de generation des etats financiers SYCEBNL EVE.

Reproduit la structure officielle (References AA/AB/.../XA/XB/.../FA/FB/...)
du modele XLSX livre par EVE (ETAT FIN SYCBNL EVE 2024.xlsx) :

  - Bilan Actif (REF AA -> BZ)
  - Bilan Passif (REF CA -> DZ)
  - Compte d'exploitation (REF RA -> XD)
  - Tableau des Flux de Tresorerie (REF FA -> ZH)

Chaque ligne REF est definie par :
  - un libelle officiel SYCEBNL
  - une liste de prefixes de codes SYCEBNL inclus
  - un sens (debit, credit, ou net solde)
  - un mode (detail, subtotal, total)

Les soldes sont agreges depuis JournalLine via la fonction publique
account_balances(). Les codes deprecated (Z_xxx) sont ignores.

Le moteur reste agnostique des templates : il retourne des structures
pures (listes de dict) que les vues / templates / exports utilisent.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable

from apps.finance.models import ChartOfAccount, JournalLine


# ============ Helpers de calcul ============

def account_balances() -> dict[str, dict]:
    """Retourne {code: {debit, credit, net, account}} pour tous les comptes
    actifs ayant des JournalLine. net = debit - credit (positif = debiteur).
    Les comptes deprecated (Z_xxx, Z2_xxx) sont exclus.
    """
    from django.db.models import Sum

    rows = (
        JournalLine.objects.filter(is_active=True, deleted_at__isnull=True)
        .values("account_id")
        .annotate(total_debit=Sum("debit"), total_credit=Sum("credit"))
    )
    account_ids = [r["account_id"] for r in rows]
    accounts = {
        a.id: a
        for a in ChartOfAccount.objects.filter(
            id__in=account_ids, is_active=True, deleted_at__isnull=True
        )
        if not a.code.startswith("Z")
    }
    result = {}
    for r in rows:
        acc = accounts.get(r["account_id"])
        if acc is None:
            continue
        debit = r["total_debit"] or Decimal("0")
        credit = r["total_credit"] or Decimal("0")
        result[acc.code] = {
            "account": acc,
            "debit": debit,
            "credit": credit,
            "net": debit - credit,
        }
    return result


def _matches_prefix(code: str, prefixes: Iterable[str]) -> bool:
    """Vrai si le code commence par un des prefixes."""
    if not code:
        return False
    return any(code.startswith(p) for p in prefixes)


def _sum_balances(
    balances: dict,
    include_prefixes: list[str],
    sign: str = "net",
    exclude_prefixes: list[str] | None = None,
) -> Decimal:
    """Somme les soldes des comptes dont le code matche un prefix.

    sign :
      - "debit"    : somme des soldes nets positifs uniquement (debiteurs)
      - "credit"   : somme des soldes nets negatifs * -1 (crediteurs)
      - "net"      : somme algebrique
      - "debit_only" : somme des debits bruts
      - "credit_only" : somme des credits bruts
    """
    exclude_prefixes = exclude_prefixes or []
    total = Decimal("0")
    for code, data in balances.items():
        if not _matches_prefix(code, include_prefixes):
            continue
        if _matches_prefix(code, exclude_prefixes):
            continue
        net = data["net"]
        if sign == "debit":
            if net > 0:
                total += net
        elif sign == "credit":
            if net < 0:
                total += -net
        elif sign == "net":
            total += net
        elif sign == "debit_only":
            total += data["debit"]
        elif sign == "credit_only":
            total += data["credit"]
    return total


# ============ Structure declarative des lignes REF ============

@dataclass
class RefLine:
    """Une ligne d'etat financier officiel SYCEBNL."""
    ref: str                                 # "AA", "AB", ..., "XA", "FA", ...
    label: str                                # libelle officiel
    note: str = ""                            # ref vers une NOTE annexe (ex: "5A")
    prefixes: tuple[str, ...] = ()            # prefixes de codes inclus
    sign: str = "debit"                       # debit | credit | net
    exclude_prefixes: tuple[str, ...] = ()    # exclus du calcul (ex. amortissements)
    kind: str = "detail"                      # detail | subtotal | total
    formula: tuple[str, ...] = ()             # pour subtotal/total : refs a sommer
    formula_minus: tuple[str, ...] = ()       # refs a soustraire


# ============ Bilan Actif (AA -> BZ) ============

BILAN_ACTIF: list[RefLine] = [
    # Immobilisations destinees a la vente (provenant de dons et legs)
    RefLine("AA", "Immobilisations destinees a la vente provenant de dons et legs",
            prefixes=("203", "204"), sign="debit", note="5"),

    # Immobilisations incorporelles
    RefLine("AE", "Brevets, licences, logiciels et droits similaires",
            prefixes=("21",), sign="debit", note="5"),
    RefLine("AF", "Autres immobilisations incorporelles",
            prefixes=("2015", "2018"), sign="debit"),
    RefLine("AG", "Avances et acomptes verses sur immobilisations incorporelles",
            prefixes=("251",), sign="debit"),
    RefLine("AB", "Immobilisations incorporelles",
            kind="subtotal", formula=("AE", "AF", "AG")),

    # Immobilisations corporelles
    RefLine("AI", "Terrains", prefixes=("22",), sign="debit", note="5"),
    RefLine("AJ", "Batiments", prefixes=("23",), sign="debit",
            exclude_prefixes=("2843", "2833")),
    RefLine("AK", "Amenagements, agencements et installations",
            prefixes=("235", "238"), sign="debit"),
    RefLine("AL", "Materiel, mobilier et actifs biologiques",
            prefixes=("244",), sign="debit", exclude_prefixes=("2844",)),
    RefLine("AM", "Materiel de transport",
            prefixes=("245",), sign="debit", exclude_prefixes=("2845",)),
    RefLine("AN", "Avances et acomptes verses sur immobilisations corporelles",
            prefixes=("252",), sign="debit"),
    RefLine("AH", "Immobilisations corporelles",
            kind="subtotal", formula=("AI", "AJ", "AK", "AL", "AM", "AN")),

    # Immobilisations financieres
    RefLine("AG2", "Titres de participation", prefixes=("26",), sign="debit"),
    RefLine("AH2", "Autres immobilisations financieres", prefixes=("27",), sign="debit"),
    RefLine("AO", "Immobilisations Financieres",
            kind="subtotal", formula=("AG2", "AH2")),

    RefLine("AC", "Immobilisations corporelles et financieres",
            kind="subtotal", formula=("AH", "AO")),

    RefLine("AZ", "TOTAL ACTIF IMMOBILISE",
            kind="total", formula=("AA", "AB", "AC")),

    # Actif circulant
    RefLine("BA", "Actif circulant HAO", prefixes=("485",), sign="debit"),
    RefLine("BB", "Stocks et encours", prefixes=("3",), sign="debit"),
    RefLine("BC", "Fournisseurs debiteurs", prefixes=("409",), sign="debit"),
    RefLine("BD", "Adherents, Clients-usagers",
            prefixes=("41", "416"), sign="debit"),
    RefLine("BE", "Autres creances",
            prefixes=("42", "43", "44", "47"), sign="debit",
            exclude_prefixes=("478", "479")),
    RefLine("BF", "TOTAL ACTIF CIRCULANT",
            kind="total", formula=("BA", "BB", "BC", "BD", "BE")),

    # Tresorerie actif
    # BUG-FIX : "51" Valeurs a encaisser capture par erreur "5211.x" qui sont
    # des comptes de banques EVE. On exclut explicitement 52/521/5211.
    RefLine("BU", "Titres de placement", prefixes=("50",), sign="debit"),
    RefLine("BV", "Valeurs a encaisser",
            prefixes=("51",), sign="debit",
            exclude_prefixes=("52", "521", "5211")),
    RefLine("BW", "Banques, etablissements financieres, caisses et assimiles",
            prefixes=("52", "53", "54", "55", "57"), sign="debit"),
    RefLine("BX", "TOTAL TRESORERIE ACTIF",
            kind="total", formula=("BU", "BV", "BW")),

    # Ecart de conversion
    RefLine("BY", "Ecart de conversion-Actif", prefixes=("478",), sign="debit"),

    RefLine("BZ", "TOTAL GENERAL",
            kind="total", formula=("AZ", "BF", "BX", "BY")),
]


# ============ Bilan Passif (CA -> DZ) ============

BILAN_PASSIF: list[RefLine] = [
    # Fonds propres
    RefLine("CA", "Dotation non consomptible sans droit de reprise",
            prefixes=("101",), sign="credit"),
    RefLine("CB", "Dotation non consomptible avec droit de reprise",
            prefixes=("102",), sign="credit"),
    RefLine("CC", "Droit d'entree", prefixes=("103",), sign="credit"),
    RefLine("CD", "Dotation consomptible", prefixes=("104",), sign="credit"),
    RefLine("CE", "Ecarts de reevaluation", prefixes=("106",), sign="credit"),
    RefLine("CF", "Reserves", prefixes=("11",), sign="credit"),
    # CG Report a nouveau : convention SYCEBNL = solde crediteur au bilan.
    # Un report excedentaire (1211) est crediteur (net < 0 en debit-credit),
    # on l'affiche en POSITIF au passif via sign="credit".
    RefLine("CG", "Report a nouveau (+ ou -)", prefixes=("12",), sign="credit"),
    RefLine("CH", "Solde des operations de l'exercice (excedent + ou deficit -)",
            kind="detail"),  # calcule a part : produits - charges
    RefLine("CI", "Subvention d'investissement", prefixes=("14",), sign="credit"),
    RefLine("CJ", "Provisions reglementees", prefixes=("15",), sign="credit"),
    RefLine("CK", "TOTAL FONDS PROPRES ET ASSIMILES",
            kind="total", formula=("CA", "CB", "CC", "CD", "CE", "CF", "CG", "CH", "CI", "CJ")),

    # Fonds affectes et reportes
    # NOTE : on exclut 165 (fonds non consommes - SYCEBNL le classe dans CX
    # fonds reportes, pas CW affectes) et 162 (fonds affectes invest qui
    # est aussi reporte si non consomme).
    RefLine("CW", "Fonds affectes et provenant de dons et legs d'immobilisations",
            prefixes=("16",), sign="credit",
            exclude_prefixes=("17", "165")),
    # CX : fonds reportes officiels (17, 165) + comptes de liaison projets
    # (181.x) qui representent les fonds projet restant a justifier - convention
    # EVE specifique (les 181 sont des comptes internes mais leur solde
    # crediteur reflete des fonds reportes du bailleur au projet).
    RefLine("CX", "Fonds reportes",
            prefixes=("17", "165", "181"), sign="credit"),
    RefLine("CY", "TOTAL FONDS AFFECTES ET REPORTES",
            kind="total", formula=("CW", "CX")),

    RefLine("CZ", "TOTAL RESSOURCES PROPRES ET ASSIMILEES",
            kind="total", formula=("CK", "CY")),

    # Dettes financieres
    # EXCLUSIONS importantes :
    #  - 181 : comptes de liaison projet/BG (internes EVE, soldes inter-comptes)
    #  - 185 : depots et cautionnements (deja en 1851 sous-classe specifique)
    RefLine("DA", "Emprunts et dettes financieres",
            prefixes=("18",), sign="credit",
            exclude_prefixes=("181", "185", "1851")),
    RefLine("DB", "Dettes de location acquisition", prefixes=("173",), sign="credit"),
    RefLine("DC", "Provisions pour risques et charges", prefixes=("19",), sign="credit"),
    RefLine("DD", "TOTAL DETTES FINANCIERES ET RESSOURCES ASSIMILEES",
            kind="total", formula=("DA", "DB", "DC")),

    RefLine("DE", "TOTAL RESSOURCES STABLES",
            kind="total", formula=("CZ", "DD")),

    # Passif circulant
    RefLine("DF", "Dettes circulantes HAO", prefixes=("482", "486"), sign="credit"),
    RefLine("DG", "Adherents, Clients-usagers crediteurs",
            prefixes=("419",), sign="credit"),
    RefLine("DH", "Fournisseurs", prefixes=("40", "481", "488"), sign="credit"),
    RefLine("DI", "Autres dettes",
            prefixes=("42", "43", "44", "47"), sign="credit",
            exclude_prefixes=("478", "479")),
    RefLine("DJ", "Provisions pour risques et charges a court terme",
            prefixes=("499",), sign="credit"),
    RefLine("DV", "TOTAL PASSIF CIRCULANT",
            kind="total", formula=("DF", "DG", "DH", "DI", "DJ")),

    # Tresorerie passif :
    # - decouverts bancaires sur 521x/52x (solde crediteur d'un compte de
    #   banque qui devrait normalement etre debiteur),
    # - credits de tresorerie formalises 56x.
    RefLine("DW", "Banques, etablissements financiers et credits de tresorerie",
            prefixes=("52", "521", "5211", "56", "564", "565"), sign="credit"),
    RefLine("DX", "TOTAL TRESORERIE PASSIF",
            kind="total", formula=("DW",)),

    # Ecart de conversion
    RefLine("DY", "Ecart de conversion-Passif", prefixes=("479",), sign="credit"),

    RefLine("DZ", "TOTAL GENERAL",
            kind="total", formula=("DE", "DV", "DX", "DY")),
]


# ============ Compte d'exploitation (RA -> XD) ============

COMPTE_EXPLOITATION: list[RefLine] = [
    # Revenus / Produits
    RefLine("RA", "Cotisations", prefixes=("701",), sign="credit"),
    RefLine("RB", "Dotations consomptibles transferees au compte de resultat",
            prefixes=("702", "703"), sign="credit"),
    RefLine("RC", "Revenus lies a la generosite",
            prefixes=("7041", "7042", "7043", "7044", "7045", "7046", "7047", "7048"),
            sign="credit"),
    RefLine("RD", "Vente de marchandises", prefixes=("7051",), sign="credit"),
    RefLine("RE", "Vente de services et produits finis",
            prefixes=("7052", "7053", "7054", "7055"), sign="credit"),
    RefLine("RF", "Subventions d'exploitations", prefixes=("71",), sign="credit"),
    RefLine("RG", "Autres produits et transfert de charges",
            prefixes=("75", "78"), sign="credit"),
    RefLine("RH", "Reprise de provisions, depreciations, subventions et autres",
            prefixes=("79",), sign="credit"),
    RefLine("XA", "REVENUS DES ACTIVITES ORDINAIRES",
            kind="subtotal", formula=("RA", "RB", "RC", "RD", "RE", "RF", "RG", "RH")),

    # Charges
    RefLine("TA", "Achats de biens et services lies a l'activite",
            prefixes=("601", "602"), sign="debit"),
    RefLine("TB", "Variation de stocks des achats de biens et services",
            prefixes=("6031", "6032"), sign="net"),
    RefLine("TC", "Achats de marchandises et matieres premieres",
            prefixes=("6041", "6042"), sign="debit"),
    RefLine("TD", "Autres achats", prefixes=("605",), sign="debit"),
    RefLine("TE", "Variation de stocks de marchandises, matieres et fournitures",
            prefixes=("6033", "6034", "6035"), sign="net"),
    RefLine("TF", "Transports", prefixes=("61",), sign="debit"),
    RefLine("TG", "Services exterieurs", prefixes=("62", "63"), sign="debit"),
    RefLine("TH", "Impots et taxes", prefixes=("64",), sign="debit"),
    RefLine("TI", "Autres charges", prefixes=("65",), sign="debit"),
    RefLine("TJ", "Charges de personnel", prefixes=("66",), sign="debit"),
    RefLine("TK", "Frais financiers et charges assimilees", prefixes=("67",), sign="debit"),
    RefLine("TL", "Dotations aux amortissements, provisions, depreciations",
            prefixes=("68", "691"), sign="debit"),
    RefLine("XB", "CHARGES DES ACTIVITES ORDINAIRES",
            kind="subtotal", formula=("TA", "TB", "TC", "TD", "TE", "TF", "TG", "TH",
                                        "TI", "TJ", "TK", "TL")),

    RefLine("XC", "RESULTAT DES ACTIVITES ORDINAIRES (XA - XB)",
            kind="subtotal", formula=("XA",), formula_minus=("XB",)),

    # Hors activites ordinaires
    RefLine("TM", "Produits H.A.O", prefixes=("82", "84", "86", "88"), sign="credit"),
    RefLine("TN", "Charges H.A.O", prefixes=("81", "83", "85", "87"), sign="debit"),
    RefLine("XD", "RESULTAT HAO (TM - TN)",
            kind="subtotal", formula=("TM",), formula_minus=("TN",)),

    RefLine("XE", "SOLDE DES OPERATIONS DE L'EXERCICE (XC + XD)",
            kind="total", formula=("XC", "XD")),
]


# ============ TFT - Tableau des Flux de Tresorerie (FA -> ZH) ============
# Note : le TFT calcule des FLUX de la periode, pas des soldes finaux.
# Sans separation explicite des mouvements de la periode, on approxime
# avec les soldes nets des comptes concernes.

TFT: list[RefLine] = [
    # Flux operationnels
    RefLine("FA", "+ Encaissement des cotisations",
            prefixes=("701",), sign="credit_only"),
    RefLine("FB", "+ Encaissement des subventions d'exploitation et d'equilibre",
            prefixes=("71",), sign="credit_only"),
    RefLine("FC", "+ Encaissement des revenus lies a la generosite",
            prefixes=("704",), sign="credit_only"),
    RefLine("FD", "+ Encaissement des revenus des manifestations",
            prefixes=("706",), sign="credit_only"),
    RefLine("FE", "+ Encaissement des autres revenus",
            prefixes=("705", "707", "708", "75"), sign="credit_only"),
    RefLine("FF", "- Decaissement des sommes versees aux fournisseurs",
            prefixes=("60", "61", "62", "63", "65"), sign="debit_only"),
    RefLine("FG", "- Decaissement des sommes versees au personnel",
            prefixes=("66",), sign="debit_only"),
    RefLine("FH", "- Autres decaissements",
            prefixes=("64", "67"), sign="debit_only"),
    RefLine("ZB", "Flux de tresorerie provenant des activites operationnelles",
            kind="subtotal",
            formula=("FA", "FB", "FC", "FD", "FE"),
            formula_minus=("FF", "FG", "FH")),

    # Flux d'investissement
    RefLine("FI", "- Decaissements lies aux acquisitions d'immobilisations incorporelles",
            prefixes=("21",), sign="debit_only"),
    RefLine("FJ", "- Decaissements lies aux acquisitions d'immobilisations corporelles",
            prefixes=("22", "23", "24"), sign="debit_only"),
    RefLine("FK", "- Decaissements lies aux acquisitions d'immobilisations financieres",
            prefixes=("26", "27"), sign="debit_only"),
    RefLine("FL", "+ Encaissements lies aux cessions d'immobilisations incorporelles",
            prefixes=("21",), sign="credit_only"),
    RefLine("FM", "+ Encaissements lies aux cessions d'immobilisations financieres",
            prefixes=("26", "27"), sign="credit_only"),
    RefLine("ZC", "Flux de tresorerie provenant des activites d'investissement",
            kind="subtotal",
            formula=("FL", "FM"),
            formula_minus=("FI", "FJ", "FK")),

    # Flux fonds propres
    RefLine("FN", "+ Encaissement des dotations et autres fonds propres",
            prefixes=("10", "11"), sign="credit_only"),
    RefLine("FO", "+ Subventions d'investissement recues",
            prefixes=("14",), sign="credit_only"),
    RefLine("FP", "- Decaissement des dotations et autres fonds propres",
            prefixes=("10", "11"), sign="debit_only"),
    RefLine("ZD", "Flux de tresorerie provenant des fonds propres",
            kind="subtotal",
            formula=("FN", "FO"),
            formula_minus=("FP",)),

    # Flux fonds etrangers
    RefLine("FQ", "+ Encaissement provenant des emprunts et autres dettes financieres",
            prefixes=("16", "18"), sign="credit_only"),
    RefLine("FR", "- Remboursements des emprunts et autres dettes financieres",
            prefixes=("16", "18"), sign="debit_only"),
    RefLine("ZE", "Flux de tresorerie provenant des capitaux etrangers",
            kind="subtotal",
            formula=("FQ",),
            formula_minus=("FR",)),

    RefLine("ZF", "Flux de tresorerie provenant des activites de financement (D+E)",
            kind="subtotal", formula=("ZD", "ZE")),

    RefLine("ZG", "VARIATION DE LA TRESORERIE NETTE DE LA PERIODE (B+C+F)",
            kind="total", formula=("ZB", "ZC", "ZF")),
]


# ============ Calcul ============

def _compute_lines(lines: list[RefLine], balances: dict) -> dict[str, dict]:
    """Calcule les montants pour chaque RefLine.

    Retourne {ref: {"ref", "label", "amount", "kind", "note", "line"}}
    Les subtotaux et totaux sont resolus apres les details.
    """
    results = {}
    # Premier passage : details
    for line in lines:
        if line.kind == "detail" and line.prefixes:
            amount = _sum_balances(
                balances,
                include_prefixes=list(line.prefixes),
                sign=line.sign,
                exclude_prefixes=list(line.exclude_prefixes),
            )
            results[line.ref] = {
                "ref": line.ref, "label": line.label, "amount": amount,
                "kind": line.kind, "note": line.note, "line": line,
            }
        elif line.kind == "detail":
            # Detail sans prefixes (cas CH solde exercice, rempli par appelant)
            results[line.ref] = {
                "ref": line.ref, "label": line.label, "amount": Decimal("0"),
                "kind": line.kind, "note": line.note, "line": line,
            }

    # Deuxieme passage : subtotaux et totaux (peuvent referencer des subtotaux)
    for _ in range(3):  # max 3 passes pour resoudre chaines de references
        for line in lines:
            if line.kind in ("subtotal", "total") and line.ref not in results:
                pos = sum(
                    (results[r]["amount"] for r in line.formula if r in results),
                    Decimal("0"),
                )
                neg = sum(
                    (results[r]["amount"] for r in line.formula_minus if r in results),
                    Decimal("0"),
                )
                # Verifie que toutes les refs sont resolues
                missing = [
                    r for r in (*line.formula, *line.formula_minus)
                    if r not in results
                ]
                if missing:
                    continue
                results[line.ref] = {
                    "ref": line.ref, "label": line.label, "amount": pos - neg,
                    "kind": line.kind, "note": line.note, "line": line,
                }

    return results


def _ordered_output(lines: list[RefLine], results: dict[str, dict]) -> list[dict]:
    """Retourne les resultats dans l'ordre de declaration des lignes."""
    return [results[line.ref] for line in lines if line.ref in results]


def compute_balance_sheet_asset() -> list[dict]:
    """Bilan Actif SYCEBNL EVE."""
    balances = account_balances()
    results = _compute_lines(BILAN_ACTIF, balances)
    return _ordered_output(BILAN_ACTIF, results)


def compute_balance_sheet_liability() -> list[dict]:
    """Bilan Passif SYCEBNL EVE.

    Le solde de l'exercice (CH) est calcule = total produits - total charges
    et injecte avant les totaux CK / DE / DZ.
    """
    balances = account_balances()
    # Calcul du resultat exercice
    total_produits = _sum_balances(balances, ["7"], sign="credit")
    total_charges = _sum_balances(balances, ["6"], sign="debit")
    result_exercise = total_produits - total_charges

    results = _compute_lines(BILAN_PASSIF, balances)
    # Injection du CH (solde des operations) calcule manuellement
    results["CH"] = {
        "ref": "CH",
        "label": "Solde des operations de l'exercice (excedent + ou deficit -)",
        "amount": result_exercise,
        "kind": "detail", "note": "", "line": None,
    }
    # Recalcule les totaux CK / CZ / DE / DZ avec CH a jour
    for ref_to_recompute in ("CK", "CZ", "DE", "DZ"):
        line = next((l for l in BILAN_PASSIF if l.ref == ref_to_recompute), None)
        if line is None:
            continue
        pos = sum((results[r]["amount"] for r in line.formula if r in results), Decimal("0"))
        neg = sum((results[r]["amount"] for r in line.formula_minus if r in results), Decimal("0"))
        results[ref_to_recompute]["amount"] = pos - neg

    return _ordered_output(BILAN_PASSIF, results)


def compute_income_statement() -> list[dict]:
    """Compte d'exploitation SYCEBNL EVE."""
    balances = account_balances()
    results = _compute_lines(COMPTE_EXPLOITATION, balances)
    return _ordered_output(COMPTE_EXPLOITATION, results)


def compute_cash_flow_statement(
    opening_treasury: Decimal | None = None
) -> dict:
    """Tableau des Flux de Tresorerie SYCEBNL EVE.

    Retourne :
      {
        "ZA": tresorerie au 1er janvier (= opening_treasury),
        "lines": [...] flux FA -> ZG,
        "ZH": tresorerie au 31 decembre (= ZA + ZG),
      }

    NOTE : sans separation explicite des mouvements de la periode, le TFT
    est approxime sur la base des soldes nets debit/credit de chaque
    compte sur la periode totale. Pour un TFT precis a la cloture, il
    faut filtrer les JournalLine par exercice et exclure les a-nouveaux.
    """
    balances = account_balances()
    if opening_treasury is None:
        opening_treasury = Decimal("0")
    results = _compute_lines(TFT, balances)
    lines = _ordered_output(TFT, results)
    variation = results.get("ZG", {}).get("amount", Decimal("0"))
    return {
        "opening_treasury": opening_treasury,
        "ZA": opening_treasury,
        "lines": lines,
        "variation": variation,
        "ZH": opening_treasury + variation,
    }
