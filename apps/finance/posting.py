"""
Generation des ecritures comptables en partie double a partir des
mouvements de tresorerie (BankMovement, CashMovement).

Convention SYCEBNL/SYSCOHADA Revise :
- Les comptes de classe 5 (tresorerie : 5211.x banques en monnaies locales,
  571.x caisse) sont des comptes d'actif : ils augmentent au debit,
  diminuent au credit.
- Pour un BankMovement :
    * credit bancaire (entree d'argent sur le compte EVE) :
        Debit  5211.x (le compte EVE s'enrichit)
        Credit contra_account (origine des fonds : produit 7x, fonds 162/462,
                               liaison 181.x...)
    * debit bancaire (sortie d'argent du compte EVE) :
        Debit  contra_account (charge 6x, liaison 181.x, etc.)
        Credit 5211.x (le compte EVE se vide)

MECANIQUE SYCEBNL PROJETS DE DEVELOPPEMENT (guide d'application chapitre 3) :
- Au decaissement bailleur sur un compte projet, on credite :
      Credit 162 (Fonds affectes aux investissements) - part invest
      Credit 462 (Fonds d'administration)              - part fonctionnement
  selon la cle Project.investment_split_pct / administration_split_pct.
  Le compte 7511/7512/... (subvention par bailleur) est ignore dans
  l'ecriture comptable (la classification analytique du bailleur reste
  portee par BankMovement.contra_account pour les rapports, mais
  l'ecriture en partie double utilise 162/462).
- A chaque charge engagee sur un projet (debit bancaire, contra_account
  de classe 6), on ajoute UNE ligne de neutralisation :
      Debit  462 (Fonds d'administration)
      Credit 702 (Quote-part de fonds d'administration transferes)
  pour que l'engagement de la charge n'impacte pas le resultat du projet
  (matching principle SYCEBNL App.8).
- Pour les acquisitions d'immobilisations (contra_account de classe 2)
  sur un projet, AUCUNE neutralisation immediate : le compte 162 reste
  intact, l'extourne en cloture est manuelle (App.8 page 20 : 162/165).

Une ecriture n'est generee que si le mouvement porte un contra_account
(ou des allocations). La generation est idempotente : si une JournalEntry
est deja liee au mouvement, on ne recree rien (on peut la regenerer via
regenerate=True).
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.finance.models import (
    BankMovement,
    CashMovement,
    ChartOfAccount,
    Commitment,
    JournalEntry,
    JournalLine,
)


class PostingError(Exception):
    """Erreur fonctionnelle empechant la generation d'une ecriture."""


def _assert_balanced(entry) -> None:
    """Invariant central : une ecriture postee DOIT etre equilibree.

    Somme des debits == somme des credits. Toute violation leve une
    PostingError ; combinee a @transaction.atomic sur les fonctions de
    posting, cela annule integralement l'ecriture au lieu de laisser une
    JournalEntry desequilibree (et donc une balance generale, un compte de
    resultat et un bilan faux) en base.
    """
    agg = entry.lines.aggregate(total_debit=Sum("debit"), total_credit=Sum("credit"))
    total_debit = agg["total_debit"] or Decimal("0")
    total_credit = agg["total_credit"] or Decimal("0")
    if total_debit != total_credit:
        raise PostingError(
            f"Ecriture desequilibree (debit={total_debit} != credit={total_credit}) "
            f"pour l'ecriture {entry.pk}. Generation annulee, rien n'est enregistre."
        )


# ---------- helpers tresorerie ----------

def _treasury_account_for_bank(bank_account):
    """Retourne le ChartOfAccount 5211.x lie a ce BankAccount."""
    account = ChartOfAccount.objects.filter(
        linked_bank_account=bank_account, is_active=True, deleted_at__isnull=True
    ).first()
    if account is None:
        raise PostingError(
            f"Aucun compte SYCEBNL 5211.x lie au compte bancaire '{bank_account.name}'. "
            "Lancer seed_chart_of_accounts."
        )
    return account


def _treasury_account_for_register(register):
    """Retourne le ChartOfAccount 571.x lie a cette CashRegister."""
    account = ChartOfAccount.objects.filter(
        linked_cash_register=register, is_active=True, deleted_at__isnull=True
    ).first()
    if account is None:
        raise PostingError(
            f"Aucun compte SYCEBNL 571.x lie a la caisse '{register.name}'. "
            "Lancer seed_chart_of_accounts."
        )
    return account


# ---------- helpers SYCEBNL projets de developpement ----------

def _get_sycebnl_account(code: str):
    """Recupere un ChartOfAccount par code SYCEBNL. Erreur si absent."""
    acc = ChartOfAccount.objects.filter(
        code=code, is_active=True, deleted_at__isnull=True
    ).first()
    if acc is None:
        raise PostingError(
            f"Compte SYCEBNL {code} introuvable. "
            "Lancer seed_chart_of_accounts."
        )
    return acc


def _is_donor_subvention_account(account) -> bool:
    """Vrai si le compte represente une subvention/don bailleur (classe 7).

    Selon le plan officiel SYCEBNL :
      - 71x = Subventions d'exploitation (bailleurs institutionnels)
      - 7041, 7042 = Dons et legs en numeraire
      - 7081 = Ventes de dons en nature
    Le decaissement bailleur ('drawdown') sur un projet est splitte en
    162/462 selon la cle du projet, peu importe le sous-compte 7x utilise
    par SAKHO pour classifier le bailleur a la saisie.
    """
    if account is None:
        return False
    if account.class_number != 7:
        return False
    code = account.code or ""
    return code.startswith(("71", "70", "75"))


def _is_operating_charge_account(account) -> bool:
    """Vrai si le compte est une charge de fonctionnement (classe 6).

    Les acquisitions d'immobilisations (classe 2) ne declenchent pas de
    neutralisation 462/702 - cf. App.8 du guide SYCEBNL.
    """
    if account is None:
        return False
    return account.class_number == 6


def _split_donor_funding(amount: Decimal, project) -> tuple[Decimal, Decimal]:
    """Decoupe un montant de decaissement bailleur en (part_invest_162, part_admin_462)
    selon Project.investment_split_pct / administration_split_pct.

    Tolere une somme != 100 : on normalise. Si les deux sont a 0, on met 100% en 462
    (fonctionnement) pour eviter une perte de fonds.
    """
    inv_pct = project.investment_split_pct or Decimal("0")
    adm_pct = project.administration_split_pct or Decimal("0")
    total = inv_pct + adm_pct
    if total == 0:
        # Fallback : 100% admin (fonctionnement) - cas par defaut EVE.
        return (Decimal("0"), amount)
    inv_share = (amount * inv_pct / total).quantize(Decimal("0.01"))
    adm_share = amount - inv_share  # complement pour eviter erreur d'arrondi
    return (inv_share, adm_share)


# ---------- helpers detection mouvement projet ----------

def _project_of_movement(movement: BankMovement):
    """Renvoie le Project rattache au mouvement, ou None.

    Sources, par ordre de priorite :
      1. movement.project (lien explicite)
      2. Si le BankAccount est rattache a EXACTEMENT 1 projet, ce projet.
    En cas d'ambiguite (compte multi-projets), renvoie None - le posting
    se rabat sur le comportement standard sans mecanique SYCEBNL projet.
    """
    if movement.project_id is not None:
        return movement.project
    bank = movement.account
    if bank is None:
        return None
    projects = list(bank.projects.filter(is_active=True, deleted_at__isnull=True))
    if len(projects) == 1:
        return projects[0]
    return None


# ---------- generation ecriture d'ENGAGEMENT (Commitment) ----------

@transaction.atomic
def post_commitment(commitment: Commitment, regenerate: bool = False):
    """Cree (ou regenere) l'ecriture d'ENGAGEMENT d'un Commitment.

    Schema SYCEBNL projets de developpement (guide d'application, Section 2.2
    'Engagement des depenses suivant la nature de charges') :
        Dr [compte de charge 6x]    (commitment.resolve_charge_account)
        Cr [compte fournisseur 401.x] (sous-compte auxiliaire du Supplier)
      + si le commitment porte sur un PROJET, neutralisation AU FUR ET A
        MESURE DE L'ENGAGEMENT :
        Dr 462 Fonds d'administration
        Cr 702 Quote-part d'administration transferes

    Le fait generateur est l'engagement, pas le decaissement : c'est ICI que
    la charge et sa neutralisation sont constatees. Le paiement ulterieur
    (BankMovement impute sur le 401.x) se contente de solder le fournisseur
    (Dr 401.x / Cr 5211) SANS re-neutraliser - le contra 401.x etant de
    classe 4, post_bank_movement ne declenche pas la neutralisation 462/702
    (reservee aux contra de classe 6). C'est la garantie structurelle contre
    la double neutralisation.

    Idempotent via JournalEntry.source_commitment. Atomic : toute ecriture
    desequilibree est annulee (cf. _assert_balanced).
    """
    amount = commitment.amount or Decimal("0")
    if amount <= 0:
        raise PostingError(
            f"Commitment {commitment.pk} : montant nul ou negatif, rien a engager."
        )

    charge = commitment.resolve_charge_account()
    if charge is None:
        raise PostingError(
            f"Commitment {commitment.pk} : aucun compte de charge (ni surcharge "
            "sur l'engagement, ni defaut sur la categorie budgetaire). "
            "Configurer BudgetCategory.default_charge_account."
        )
    supplier = commitment.supplier
    if supplier is None:
        raise PostingError(
            f"Commitment {commitment.pk} : aucun fournisseur (Supplier) rattache ; "
            "l'auxiliaire fournisseur ne peut etre credite."
        )

    # Nature de l'engagement selon la classe du compte d'emploi :
    #   classe 6 -> charge de fonctionnement (Cr 401.x + neutralisation 462/702)
    #   classe 2 -> immobilisation         (Cr 481.x, SANS neutralisation ;
    #               le fonds 162 s'extourne en fin de projet, guide S2.3/2.5)
    is_immobilisation = charge.class_number == 2
    if charge.class_number not in (2, 6):
        raise PostingError(
            f"Commitment {commitment.pk} : le compte d'emploi {charge.code} est de "
            f"classe {charge.class_number} ; un engagement attend une charge "
            "(classe 6) ou une immobilisation (classe 2)."
        )
    if is_immobilisation:
        supplier_account = supplier.ensure_investment_account()  # 481.x
    else:
        supplier_account = supplier.chart_account or supplier.ensure_chart_account()  # 401.x

    existing = JournalEntry.objects.filter(source_commitment=commitment).first()
    if existing is not None:
        if not regenerate:
            return existing
        existing.lines.all().delete()
        entry = existing
    else:
        entry = JournalEntry(source_commitment=commitment)

    project = getattr(commitment.budget_line, "project", None)
    label = (
        commitment.description
        or commitment.commitment_number
        or f"Engagement {commitment.pk}"
    )[:300]

    entry.entry_date = commitment.commitment_date
    entry.reference = commitment.commitment_number or f"ENG-{commitment.pk}"
    entry.label = label
    # Pas encore valide : `posted` n'est positionne qu'apres equilibre verifie.
    entry.posted = False
    entry.save()

    # Dr emploi (charge 6x ou immobilisation 2x) / Cr fournisseur (401.x ou 481.x)
    JournalLine.objects.create(
        entry=entry, account=charge, debit=amount, credit=Decimal("0"), label=label,
    )
    JournalLine.objects.create(
        entry=entry, account=supplier_account, debit=Decimal("0"), credit=amount,
        label=f"[{supplier_account.code} {supplier.code}] {label}"[:300],
    )

    # Neutralisation du resultat projet, A L'ENGAGEMENT : Dr 462 / Cr 702.
    # UNIQUEMENT pour les charges de fonctionnement : une immobilisation n'est
    # pas neutralisee (le fonds 162 s'extourne en fin de projet, guide S2.5).
    if project is not None and not is_immobilisation:
        fonds_admin = _get_sycebnl_account("462")
        quote_part = _get_sycebnl_account("702")
        JournalLine.objects.create(
            entry=entry, account=fonds_admin, debit=amount, credit=Decimal("0"),
            label=f"[SYCEBNL neutralisation {project.code}] {label}"[:300],
        )
        JournalLine.objects.create(
            entry=entry, account=quote_part, debit=Decimal("0"), credit=amount,
            label=f"[SYCEBNL quote-part {project.code}] {label}"[:300],
        )

    # Garde-fou : ecriture desequilibree -> PostingError -> rollback total.
    _assert_balanced(entry)
    entry.posted = True
    entry.save(update_fields=["posted"])
    return entry


# ---------- generation ecriture BankMovement ----------

@transaction.atomic
def post_bank_movement(movement: BankMovement, regenerate: bool = False):
    """Cree (ou regenere) la JournalEntry en partie double d'un BankMovement.

    Comportement standard (cas simple, sans projet de developpement) :
      - credit bancaire : Debit 5211.x / Credit contra_account
      - debit bancaire  : Debit contra_account / Credit 5211.x

    Mecanique SYCEBNL projet de developpement (si Project rattache) :
      - decaissement bailleur (credit + contra_account 75x) :
            Debit 5211.x / Credit 162 (part invest) / Credit 462 (part admin)
      - charge de fonctionnement (debit + contra_account 6x) :
            Debit contra_account / Credit 5211.x
            + Debit 462 / Credit 702 (neutralisation du resultat projet)

    Si le mouvement a des allocations (BankMovementAllocation), le journal
    cree UNE ligne tresorerie + UNE ligne par allocation (ventilation
    analytique : ex. cheque salaires equipe Saint-Louis decompose en 4
    salaires distincts sur des comptes 6611 (salaires) et 6631 (primes)).
    Pour chaque allocation rattachee a un projet, la neutralisation 462/702
    est ajoutee par allocation.

    Retourne la JournalEntry, ou None si le mouvement n'a aucune imputation
    valide.
    """
    allocations = list(movement.allocations.filter(is_active=True, deleted_at__isnull=True))
    has_allocations = bool(allocations)

    # Pas de contra_account ET pas d'allocations -> rien a comptabiliser
    if movement.contra_account_id is None and not has_allocations:
        return None

    debit = movement.debit or Decimal("0")
    credit = movement.credit or Decimal("0")

    # Rien a comptabiliser : on ne cree aucune ecriture (et on n'en laisse
    # surtout pas une vide en base).
    if credit == 0 and debit == 0:
        return None

    # Un mouvement bancaire est mono-directionnel : debit OU credit, jamais
    # les deux. Sinon une seule face serait comptabilisee silencieusement.
    if credit > 0 and debit > 0:
        raise PostingError(
            f"Mouvement BM-{movement.id} porte a la fois un debit ({debit}) et "
            f"un credit ({credit}). Un mouvement doit etre mono-directionnel."
        )

    existing = JournalEntry.objects.filter(source_bank_movement=movement).first()
    if existing is not None:
        if not regenerate:
            return existing
        existing.lines.all().delete()
        entry = existing
    else:
        entry = JournalEntry(source_bank_movement=movement)

    treasury = _treasury_account_for_bank(movement.account)
    project = _project_of_movement(movement)

    entry.entry_date = movement.date_operation
    entry.reference = movement.reference or f"BM-{movement.id}"
    entry.label = movement.label[:300]
    # Pas encore valide : on ne marque `posted` qu'apres verification d'equilibre.
    entry.posted = False
    entry.save()

    if has_allocations:
        _post_with_allocations(entry, movement, allocations, treasury, credit, debit, project)
    else:
        _post_simple(entry, movement, treasury, credit, debit, project)

    # Garde-fou final : toute ecriture desequilibree leve une PostingError,
    # ce qui annule la transaction atomique (aucune ligne ni en-tete laisses).
    _assert_balanced(entry)
    entry.posted = True
    entry.save(update_fields=["posted"])
    return entry


def _post_simple(entry, movement, treasury, credit, debit, project):
    """Ecriture simple a 2 lignes + mecaniques SYCEBNL projet le cas echeant."""
    contra = movement.contra_account
    label = movement.label[:300]

    if credit > 0:
        # Entree d'argent : Debit tresorerie / Credit contra
        JournalLine.objects.create(
            entry=entry, account=treasury, debit=credit, credit=Decimal("0"),
            label=label,
        )
        # SYCEBNL projet : si decaissement bailleur (contra=75x) sur un projet,
        # on remplace la ligne credit "75x" par 162 + 462 selon la cle projet.
        if project is not None and _is_donor_subvention_account(contra):
            fonds_invest = _get_sycebnl_account("162")
            fonds_admin = _get_sycebnl_account("462")
            inv_share, adm_share = _split_donor_funding(credit, project)
            if inv_share > 0:
                JournalLine.objects.create(
                    entry=entry, account=fonds_invest,
                    debit=Decimal("0"), credit=inv_share,
                    label=f"[SYCEBNL invest {project.code}] {label}"[:300],
                )
            if adm_share > 0:
                JournalLine.objects.create(
                    entry=entry, account=fonds_admin,
                    debit=Decimal("0"), credit=adm_share,
                    label=f"[SYCEBNL admin {project.code}] {label}"[:300],
                )
        else:
            JournalLine.objects.create(
                entry=entry, account=contra, debit=Decimal("0"), credit=credit,
                label=label,
            )
    else:
        # Sortie d'argent : Debit contra / Credit tresorerie
        JournalLine.objects.create(
            entry=entry, account=contra, debit=debit, credit=Decimal("0"),
            label=label,
        )
        JournalLine.objects.create(
            entry=entry, account=treasury, debit=Decimal("0"), credit=debit,
            label=label,
        )
        # SYCEBNL projet : si charge de fonctionnement (contra=6x) sur un
        # projet, on ajoute la neutralisation 462 / 702.
        if project is not None and _is_operating_charge_account(contra):
            fonds_admin = _get_sycebnl_account("462")
            quote_part = _get_sycebnl_account("702")
            JournalLine.objects.create(
                entry=entry, account=fonds_admin,
                debit=debit, credit=Decimal("0"),
                label=f"[SYCEBNL neutralisation {project.code}] {label}"[:300],
            )
            JournalLine.objects.create(
                entry=entry, account=quote_part,
                debit=Decimal("0"), credit=debit,
                label=f"[SYCEBNL quote-part {project.code}] {label}"[:300],
            )


def _line_label(movement_label, detail=""):
    """Garde-fou libelle d'ecriture comptable.

    Chaque ligne d'une ventilation porte d'abord le libelle DESCRIPTIF du
    mouvement (ex: 'Frais d'organisation de CDD a Bakel'), complete par le
    detail de la ligne budgetaire quand celui-ci apporte une precision reelle.
    Evite les libelles creux saisis a la ligne ('activite', 'frais', ...) qui
    seuls n'ont aucune valeur probante pour un auditeur, et evite les doublons.
    """
    base = (movement_label or "").strip()
    d = (detail or "").strip()
    if not d or d.lower() == base.lower() or d.lower() in base.lower():
        return base[:300]
    return f"{base} - {d}"[:300]


def _post_with_allocations(entry, movement, allocations, treasury, credit, debit, default_project):
    """Ventilation analytique : 1 ligne tresorerie + N lignes allocations.

    Pour chaque allocation rattachee a un projet (allocation.project ou,
    a defaut, default_project), on ajoute la mecanique SYCEBNL projet
    appropriee selon le type de compte.
    """
    label = movement.label[:300]

    # La somme des allocations DOIT egaler le mouvement total : sinon la ligne
    # tresorerie (= montant mouvement) et les lignes de ventilation (= somme
    # allocations) ne s'equilibrent pas. On refuse de comptabiliser plutot que
    # de poster une ecriture fausse ; le mouvement reste sans ecriture et sera
    # signale par generate_journal_entries.
    alloc_total = sum((a.amount for a in allocations), Decimal("0"))
    movement_amount = credit if credit > 0 else debit
    if alloc_total != movement_amount:
        raise PostingError(
            f"Ventilation incompatible pour BM-{movement.id} : somme des "
            f"allocations={alloc_total} != montant du mouvement={movement_amount}. "
            "Corriger les allocations avant comptabilisation."
        )

    fonds_invest = None
    fonds_admin = None
    quote_part = None  # paresseux : on ne lookup que si besoin

    def _ensure_sycebnl_accounts():
        nonlocal fonds_invest, fonds_admin, quote_part
        if fonds_invest is None:
            fonds_invest = _get_sycebnl_account("162")
        if fonds_admin is None:
            fonds_admin = _get_sycebnl_account("462")
        if quote_part is None:
            quote_part = _get_sycebnl_account("702")

    if credit > 0:
        # Entree : 1 ligne tresorerie debit + N lignes allocations credit
        JournalLine.objects.create(
            entry=entry, account=treasury, debit=credit, credit=Decimal("0"),
            label=label,
        )
        for a in allocations:
            a_project = a.project or default_project
            alloc_label = _line_label(movement.label, a.description)
            if a_project is not None and _is_donor_subvention_account(a.contra_account):
                _ensure_sycebnl_accounts()
                inv_share, adm_share = _split_donor_funding(a.amount, a_project)
                if inv_share > 0:
                    JournalLine.objects.create(
                        entry=entry, account=fonds_invest,
                        debit=Decimal("0"), credit=inv_share,
                        label=f"[SYCEBNL invest {a_project.code}] {alloc_label}"[:300],
                    )
                if adm_share > 0:
                    JournalLine.objects.create(
                        entry=entry, account=fonds_admin,
                        debit=Decimal("0"), credit=adm_share,
                        label=f"[SYCEBNL admin {a_project.code}] {alloc_label}"[:300],
                    )
            else:
                JournalLine.objects.create(
                    entry=entry, account=a.contra_account,
                    debit=Decimal("0"), credit=a.amount,
                    label=alloc_label,
                )
    else:
        # Sortie : N lignes allocations debit + 1 ligne tresorerie credit
        # + neutralisations 462/702 pour les allocations de charge sur projet
        for a in allocations:
            alloc_label = _line_label(movement.label, a.description)
            JournalLine.objects.create(
                entry=entry, account=a.contra_account,
                debit=a.amount, credit=Decimal("0"),
                label=alloc_label,
            )
        JournalLine.objects.create(
            entry=entry, account=treasury, debit=Decimal("0"), credit=debit,
            label=label,
        )
        for a in allocations:
            a_project = a.project or default_project
            if a_project is not None and _is_operating_charge_account(a.contra_account):
                _ensure_sycebnl_accounts()
                alloc_label = _line_label(movement.label, a.description)
                JournalLine.objects.create(
                    entry=entry, account=fonds_admin,
                    debit=a.amount, credit=Decimal("0"),
                    label=f"[SYCEBNL neutralisation {a_project.code}] {alloc_label}"[:300],
                )
                JournalLine.objects.create(
                    entry=entry, account=quote_part,
                    debit=Decimal("0"), credit=a.amount,
                    label=f"[SYCEBNL quote-part {a_project.code}] {alloc_label}"[:300],
                )


# ---------- generation ecriture CashMovement (mecanique simple, pas de SYCEBNL projet) ----------

@transaction.atomic
def post_cash_movement(movement: CashMovement, regenerate: bool = False):
    """Cree (ou regenere) la JournalEntry en partie double d'un CashMovement.

    Pas de mecanique SYCEBNL projet : la caisse est traitee comme un compte
    standard (les mouvements de caisse projet passent par recharge depuis
    le compte bancaire, et c'est la qu'on applique 162/462/702).
    """
    if movement.contra_account_id is None:
        return None

    debit = movement.debit or Decimal("0")
    credit = movement.credit or Decimal("0")

    # Rien a comptabiliser : aucune ecriture.
    if credit == 0 and debit == 0:
        return None

    # Mono-directionnel : debit OU credit, jamais les deux.
    if credit > 0 and debit > 0:
        raise PostingError(
            f"Mouvement CM-{movement.id} porte a la fois un debit ({debit}) et "
            f"un credit ({credit}). Un mouvement doit etre mono-directionnel."
        )

    existing = JournalEntry.objects.filter(source_cash_movement=movement).first()
    if existing is not None:
        if not regenerate:
            return existing
        existing.lines.all().delete()
        entry = existing
    else:
        entry = JournalEntry(source_cash_movement=movement)

    treasury = _treasury_account_for_register(movement.register)
    contra = movement.contra_account

    entry.entry_date = movement.date_operation
    entry.reference = movement.reference or f"CM-{movement.id}"
    entry.label = movement.label[:300]
    # Pas encore valide : `posted` est positionne apres verification d'equilibre.
    entry.posted = False
    entry.save()

    if credit > 0:
        JournalLine.objects.create(entry=entry, account=treasury, debit=credit, credit=Decimal("0"), label=movement.label[:300])
        JournalLine.objects.create(entry=entry, account=contra, debit=Decimal("0"), credit=credit, label=movement.label[:300])
    else:
        JournalLine.objects.create(entry=entry, account=contra, debit=debit, credit=Decimal("0"), label=movement.label[:300])
        JournalLine.objects.create(entry=entry, account=treasury, debit=Decimal("0"), credit=debit, label=movement.label[:300])

    _assert_balanced(entry)
    entry.posted = True
    entry.save(update_fields=["posted"])
    return entry
