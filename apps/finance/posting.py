"""
Generation des ecritures comptables en partie double a partir des
mouvements de tresorerie (BankMovement, CashMovement).

Convention SYCEBNL :
- Les comptes de classe 5 (tresorerie : 512.x banques, 571.x caisse) sont
  des comptes d'actif : ils augmentent au debit, diminuent au credit.
- Pour un BankMovement :
    * credit bancaire (entree d'argent sur le compte EVE) :
        Debit  512.x (le compte EVE s'enrichit)
        Credit contra_account (origine des fonds : produit 7x, liaison 18x...)
    * debit bancaire (sortie d'argent du compte EVE) :
        Debit  contra_account (charge 6x, liaison 18x, etc.)
        Credit 512.x (le compte EVE se vide)

Une ecriture n'est generee que si le mouvement porte un contra_account.
La generation est idempotente : si une JournalEntry est deja liee au
mouvement, on ne recree rien (on peut la regenerer via regenerate=True).
"""

from decimal import Decimal

from apps.finance.models import (
    BankMovement,
    CashMovement,
    ChartOfAccount,
    JournalEntry,
    JournalLine,
)


class PostingError(Exception):
    """Erreur fonctionnelle empechant la generation d'une ecriture."""


def _treasury_account_for_bank(bank_account):
    """Retourne le ChartOfAccount 512.x lie a ce BankAccount."""
    account = ChartOfAccount.objects.filter(
        linked_bank_account=bank_account, is_active=True, deleted_at__isnull=True
    ).first()
    if account is None:
        raise PostingError(
            f"Aucun compte SYCEBNL 512.x lie au compte bancaire '{bank_account.name}'. "
            "Lancer seed_chart_of_accounts_sycebnl."
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
            "Lancer seed_chart_of_accounts_sycebnl."
        )
    return account


def post_bank_movement(movement: BankMovement, regenerate: bool = False):
    """Cree (ou regenere) la JournalEntry en partie double d'un BankMovement.

    Retourne la JournalEntry, ou None si le mouvement n'a pas de
    contra_account (rien a comptabiliser tant que l'imputation manque).
    """
    if movement.contra_account_id is None:
        return None

    existing = JournalEntry.objects.filter(source_bank_movement=movement).first()
    if existing is not None:
        if not regenerate:
            return existing
        existing.lines.all().delete()
        entry = existing
    else:
        entry = JournalEntry(source_bank_movement=movement)

    treasury = _treasury_account_for_bank(movement.account)
    contra = movement.contra_account

    entry.entry_date = movement.date_operation
    entry.reference = movement.reference or f"BM-{movement.id}"
    entry.label = movement.label[:300]
    entry.posted = True
    entry.save()

    debit = movement.debit or Decimal("0")
    credit = movement.credit or Decimal("0")

    if credit > 0:
        # Entree d'argent : Debit tresorerie / Credit contrepartie
        JournalLine.objects.create(entry=entry, account=treasury, debit=credit, credit=Decimal("0"), label=movement.label[:300])
        JournalLine.objects.create(entry=entry, account=contra, debit=Decimal("0"), credit=credit, label=movement.label[:300])
    elif debit > 0:
        # Sortie d'argent : Debit contrepartie / Credit tresorerie
        JournalLine.objects.create(entry=entry, account=contra, debit=debit, credit=Decimal("0"), label=movement.label[:300])
        JournalLine.objects.create(entry=entry, account=treasury, debit=Decimal("0"), credit=debit, label=movement.label[:300])
    else:
        # Mouvement a zero : on supprime l'ecriture vide
        entry.delete()
        return None

    return entry


def post_cash_movement(movement: CashMovement, regenerate: bool = False):
    """Cree (ou regenere) la JournalEntry en partie double d'un CashMovement."""
    if movement.contra_account_id is None:
        return None

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
    entry.posted = True
    entry.save()

    debit = movement.debit or Decimal("0")
    credit = movement.credit or Decimal("0")

    if credit > 0:
        JournalLine.objects.create(entry=entry, account=treasury, debit=credit, credit=Decimal("0"), label=movement.label[:300])
        JournalLine.objects.create(entry=entry, account=contra, debit=Decimal("0"), credit=credit, label=movement.label[:300])
    elif debit > 0:
        JournalLine.objects.create(entry=entry, account=contra, debit=debit, credit=Decimal("0"), label=movement.label[:300])
        JournalLine.objects.create(entry=entry, account=treasury, debit=Decimal("0"), credit=debit, label=movement.label[:300])
    else:
        entry.delete()
        return None

    return entry
