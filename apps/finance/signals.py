"""
Signaux finance : auto-generation des ecritures comptables a partir des
mouvements de tresorerie des qu'ils portent un contra_account.

Le signal est volontairement defensif : toute PostingError (compte
SYCEBNL de tresorerie manquant, etc.) est avalee silencieusement pour ne
pas casser la sauvegarde du mouvement. La regeneration en lot reste
possible via la commande generate_journal_entries.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.finance.models import BankMovement, CashMovement
from apps.finance.posting import PostingError, post_bank_movement, post_cash_movement


@receiver(post_save, sender=BankMovement)
def auto_post_bank_movement(sender, instance, **kwargs):
    if instance.contra_account_id is None:
        return
    try:
        post_bank_movement(instance, regenerate=True)
    except PostingError:
        # Compte de tresorerie SYCEBNL manquant : on laisse passer, le
        # backfill via generate_journal_entries signalera le probleme.
        pass


@receiver(post_save, sender=CashMovement)
def auto_post_cash_movement(sender, instance, **kwargs):
    if instance.contra_account_id is None:
        return
    try:
        post_cash_movement(instance, regenerate=True)
    except PostingError:
        pass
