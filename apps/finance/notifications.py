"""Notifications email du workflow de demande de depense.

Trois evenements declenchent un mail :
  1. Soumission (DRAFT -> SUBMITTED) : les valideurs RAF/DP/SE sont prevenus
     qu'une demande attend leur signature.
  2. Decision finale (SUBMITTED -> APPROVED/REJECTED) : le demandeur est
     prevenu du resultat.

Principes :
  - Aucune exception ne doit casser le workflow : l'envoi est encapsule dans
    un try/except qui journalise l'erreur et continue.
  - En dev, EMAIL_BACKEND = console : les mails s'affichent dans le terminal.
  - En prod, renseigner les EMAIL_* dans .env pour l'envoi reel via le SMTP
    d'EVE (voir config/settings.py).
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from apps.accounts.models import User

logger = logging.getLogger(__name__)

VALIDATOR_ROLE_CODES = ("RAF", "DP", "SE")


def _absolute_url(path: str) -> str:
    base = getattr(settings, "SITE_BASE_URL", "").rstrip("/")
    return f"{base}{path}"


def _expense_url(expense) -> str:
    return _absolute_url(reverse("finance:expense_detail", args=[expense.id]))


def _validator_emails() -> list[str]:
    """Adresses des utilisateurs portant un role validateur (RAF/DP/SE)."""
    emails = (
        User.objects.filter(
            is_active=True,
            deleted_at__isnull=True,
            user_roles__role__code__in=VALIDATOR_ROLE_CODES,
        )
        .exclude(email="")
        .values_list("email", flat=True)
        .distinct()
    )
    return sorted(set(emails))


def _requester_email(expense) -> str | None:
    """Adresse du demandeur.

    Priorite : compte User lie a l'Employee, puis email professionnel de
    l'Employee, puis email personnel.
    """
    employee = expense.requester
    if employee is None:
        return None
    user = (
        User.objects.filter(
            employee=employee, is_active=True, deleted_at__isnull=True
        )
        .exclude(email="")
        .first()
    )
    if user and user.email:
        return user.email
    if employee.email_professional:
        return employee.email_professional
    if employee.email_personal:
        return employee.email_personal
    return None


def _send(subject: str, body: str, recipients: list[str]) -> bool:
    """Envoi defensif : journalise et n'echoue jamais bruyamment."""
    recipients = [r for r in recipients if r]
    if not recipients:
        logger.info("Notification '%s' ignoree : aucun destinataire.", subject)
        return False
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
        logger.info("Notification '%s' envoyee a %s.", subject, recipients)
        return True
    except Exception:  # noqa: BLE001 - on ne casse jamais le workflow
        logger.exception("Echec d'envoi de la notification '%s'.", subject)
        return False


def notify_validators_on_submit(expense) -> bool:
    """Previent les valideurs RAF/DP/SE qu'une demande attend leur signature."""
    recipients = _validator_emails()
    project_label = expense.project.code if expense.project_id else "Budget General"
    subject = f"[EVE Pilot] Demande DD-{expense.id} a valider"
    body = (
        f"Bonjour,\n\n"
        f"Une demande de depense vient d'etre soumise et attend votre validation.\n\n"
        f"  Reference   : DD-{expense.id}\n"
        f"  Intitule    : {expense.title}\n"
        f"  Montant     : {expense.requested_amount} {expense.currency}\n"
        f"  Imputation  : {project_label}\n"
        f"  Ligne budg. : {expense.budget_line}\n"
        f"  Demandeur   : {expense.requester}\n\n"
        f"Ouvrir la demande : {_expense_url(expense)}\n\n"
        f"-- EVE Pilot Finance"
    )
    return _send(subject, body, recipients)


def notify_requester_on_decision(expense) -> bool:
    """Previent le demandeur du resultat de la validation (approuvee/rejetee)."""
    recipient = _requester_email(expense)
    if not recipient:
        logger.info(
            "Decision DD-%s : pas d'email connu pour le demandeur %s.",
            expense.id,
            expense.requester_id,
        )
        return False

    status_label = expense.get_status_display()
    subject = f"[EVE Pilot] Demande DD-{expense.id} : {status_label}"

    if expense.status == expense.Status.APPROVED:
        intro = (
            "Votre demande de depense a ete APPROUVEE par les trois valideurs "
            "(RAF, DP, SE). Elle peut maintenant etre executee."
        )
    elif expense.status == expense.Status.REJECTED:
        intro = (
            "Votre demande de depense a ete REJETEE. Consultez les commentaires "
            "des valideurs sur la fiche pour connaitre le motif."
        )
    else:
        intro = f"Le statut de votre demande est passe a : {status_label}."

    body = (
        f"Bonjour,\n\n"
        f"{intro}\n\n"
        f"  Reference  : DD-{expense.id}\n"
        f"  Intitule   : {expense.title}\n"
        f"  Montant    : {expense.requested_amount} {expense.currency}\n"
        f"  Statut     : {status_label}\n\n"
        f"Ouvrir la demande : {_expense_url(expense)}\n\n"
        f"-- EVE Pilot Finance"
    )
    return _send(subject, body, [recipient])
