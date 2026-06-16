# -*- coding: utf-8 -*-
"""
Parser de releves bancaires PDF.

Strategie best-effort : extraction texte ligne a ligne via pdfplumber, puis
identification heuristique des lignes de mouvement (date + libelle + debit
ou credit). Le comptable revoit toujours dans une UI de validation avant
l'import final.

Supporte les formats courants au Senegal :
  - SUNU BANK (releves multi-pages avec date / libelle / debit / credit / solde)
  - CBAO
  - Banque Atlantique
  - BOA

Pour les PDF non standards ou scannes, le parser remonte ce qu'il peut et
laisse le comptable completer manuellement.
"""

import re
from datetime import date as date_cls
from decimal import Decimal, InvalidOperation

import pdfplumber


# Regex pour reperer une date au format dd/mm/yyyy ou dd-mm-yyyy
DATE_RE = re.compile(r"(\d{2})[/.\-](\d{2})[/.\-](\d{2,4})")
# Montant : 1 234 567,89 ou 1.234.567,89 ou 1234567.89 ou 1234567
AMOUNT_RE = re.compile(r"-?\d{1,3}(?:[\s.,]?\d{3})*(?:[.,]\d{1,2})?")


def _parse_date(s: str) -> date_cls | None:
    m = DATE_RE.search(s)
    if not m:
        return None
    d, mo, y = m.groups()
    try:
        y = int(y)
        if y < 100:
            y += 2000
        return date_cls(int(y), int(mo), int(d))
    except (ValueError, TypeError):
        return None


def _parse_amount(s: str) -> Decimal | None:
    """Convertit '1 234 567,89' ou '1234567.89' en Decimal."""
    if not s:
        return None
    s = s.strip().replace(" ", "").replace(" ", "")
    # Format FR : 1.234.567,89 -> 1234567.89
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        v = Decimal(s)
        return v if v != 0 else None
    except InvalidOperation:
        return None


def _is_movement_line(line: str) -> bool:
    """Heuristique : la ligne contient une date ET au moins un montant > 0."""
    if not DATE_RE.search(line):
        return False
    amounts = AMOUNT_RE.findall(line)
    return any(_parse_amount(a) for a in amounts)


class ScannedPDFError(Exception):
    """Le PDF ne contient aucune couche texte (PDF scan / image)."""
    pass


def is_text_pdf(pdf_file) -> tuple[bool, int, int]:
    """Verifie si le PDF contient une couche texte exploitable.

    Retourne (is_text, nb_chars_total, nb_pages).
    """
    pdf_file.seek(0)
    with pdfplumber.open(pdf_file) as pdf:
        nb_pages = len(pdf.pages)
        nb_chars = sum(len(p.chars) for p in pdf.pages)
    pdf_file.seek(0)
    return (nb_chars > 100, nb_chars, nb_pages)


def extract_text_lines(pdf_file) -> list[str]:
    """Extrait toutes les lignes de texte du PDF, page par page.

    Leve ScannedPDFError si le PDF est un scan (aucune couche texte).
    """
    is_text, nb_chars, nb_pages = is_text_pdf(pdf_file)
    if not is_text:
        raise ScannedPDFError(
            f"Ce PDF est un scan ({nb_pages} page(s), seulement {nb_chars} caractere(s) texte detecte(s)). "
            "Pour l'utiliser dans l'assistant d'import, deux options :\n"
            "  1. Demander a la banque un export texte (PDF natif, CSV ou XLSX) - generalement gratuit ;\n"
            "  2. Faire un OCR du PDF avant de le televerser (Adobe Acrobat, ABBYY FineReader, etc.).\n"
            "Pour ce releve, vous pouvez aussi saisir les mouvements manuellement via 'Saisir un mouvement bancaire'."
        )
    lines = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw in text.split("\n"):
                stripped = raw.strip()
                if stripped:
                    lines.append(stripped)
    return lines


# Mots-cles indiquant une sortie d'argent (debit)
DEBIT_KEYWORDS = re.compile(
    r"PAIEMENT|REGLMT|RETRAIT|DEBIT|FRAIS|COMMISSION|AGIOS|VRS\s*PERSONNEL|"
    r"REGL\.CHQ|CHEQUE\s+(AU\s+PORTEUR|EMIS)|VIRT?\s+EMIS|IPRES|CSS|IRPP|"
    r"VRS[\s/-]*BRS|CFCE|TRIMF|TAXE|IMPOT|LOYER|ELECTRIC|SENELEC|SDE|"
    r"ORANGE|TELECOM|CARBURANT|TOTAL\s+CARB|HONORAIRE|CONSULTANT|"
    r"SALAIRE|PRIME|PERDIEM|TRANSPORT|REGLEMENT",
    re.IGNORECASE,
)
# Mots-cles indiquant une entree d'argent (credit)
CREDIT_KEYWORDS = re.compile(
    r"VIR\.?\s*RECU|VIREMENT\s+RECU|VERSEMENT|DEPOT|CRED|ENCAISS|"
    r"NOUS[\s-]*CIMS|ONAS|AXA|OXFAM|CHILDFUND|STONEX|FNC|OGHOGHO",
    re.IGNORECASE,
)


def _classify_operation(label: str) -> str | None:
    """Detecte si la ligne est une SORTIE (debit) ou ENTREE (credit) au libelle.

    Retourne 'DEBIT', 'CREDIT' ou None si indecis.
    """
    if not label:
        return None
    is_debit = bool(DEBIT_KEYWORDS.search(label))
    is_credit = bool(CREDIT_KEYWORDS.search(label))
    if is_debit and not is_credit:
        return "DEBIT"
    if is_credit and not is_debit:
        return "CREDIT"
    return None


# Seuil minimal pour qu'un nombre soit considere comme montant reel
MIN_REAL_AMOUNT = Decimal("1000")


def parse_statement(pdf_file) -> list[dict]:
    """Parse un releve bancaire PDF.

    Retourne une liste de dicts:
        {
            "date_operation": "YYYY-MM-DD" | None,
            "reference": str,
            "label": str,
            "debit": str (Decimal as str) | "",
            "credit": str | "",
            "balance_after": str | "",
            "raw_text": str,  # la ligne brute pour audit
        }
    """
    lines = extract_text_lines(pdf_file)
    movements = []
    for raw in lines:
        if not _is_movement_line(raw):
            continue
        d = _parse_date(raw)
        # Extrait tous les montants - les 2 ou 3 derniers sont generalement
        # debit/credit/solde (selon le format de la banque).
        amounts_str = AMOUNT_RE.findall(raw)
        amounts_dec = [(_parse_amount(a), a) for a in amounts_str]
        amounts_dec = [(v, a) for v, a in amounts_dec if v is not None]

        if not amounts_dec:
            continue

        # Libelle = ce qui reste apres avoir vire la date et les montants finals
        label_text = raw
        if d:
            label_text = DATE_RE.sub("", label_text, count=1).strip()
        # Vire les montants en partant de la fin
        for _, a in reversed(amounts_dec[-3:]):
            idx = label_text.rfind(a)
            if idx >= 0:
                label_text = (label_text[:idx] + " " + label_text[idx + len(a):]).strip()
        label_text = re.sub(r"\s{2,}", " ", label_text).strip()

        # Filtre les nombres bruit (< 1000) issus des dates/references
        # ex : "02.03.2026" extrait "202" et "6" qui ne sont pas des montants.
        real_amounts = [(v, a) for v, a in amounts_dec if abs(v) >= MIN_REAL_AMOUNT]

        debit = credit = balance_after = ""

        # Detection du sens depuis le libelle (PAIEMENT, Vir.recu, etc.)
        op_type = _classify_operation(label_text)

        if real_amounts:
            # Dernier montant = solde, avant-dernier = montant operation
            if len(real_amounts) >= 2:
                balance_after = real_amounts[-1][0]
                main_amount = real_amounts[-2][0]
            else:
                main_amount = real_amounts[-1][0]

            # Attribution selon le sens detecte
            if op_type == "DEBIT":
                debit = abs(main_amount)
            elif op_type == "CREDIT":
                credit = abs(main_amount)
            else:
                # Indecis : on retombe sur le signe du montant
                if main_amount < 0:
                    debit = abs(main_amount)
                else:
                    credit = main_amount
        else:
            # Aucun montant >= 1000 : ligne probablement non-mouvement (entete,
            # cumul, decompte page). On la garde quand meme pour audit visuel.
            if amounts_dec:
                debit = amounts_dec[-1][0]

        movements.append({
            "date_operation": d.isoformat() if d else None,
            "reference": "",
            "label": label_text[:300],
            "debit": str(debit) if debit else "",
            "credit": str(credit) if credit else "",
            "balance_after": str(balance_after) if balance_after else "",
            "raw_text": raw[:500],
        })
    return movements
