"""Notifications email du workflow de demande de depense.

Evenements qui declenchent un mail :
  1. Soumission (DRAFT -> SUBMITTED) : les 3 valideurs RAF/DP/SE sont prevenus
     EN MEME TEMPS qu'une demande attend leur signature.
  2. Chaque signature (RAF/DP/SE) : le demandeur ET les autres valideurs sont
     prevenus de la progression ("untel a signe, il reste X").
  3. Decision finale (APPROVED/REJECTED) : le demandeur est prevenu du resultat.

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


def _other_validator_emails(expense, exclude_role_code: str) -> list[str]:
    """Emails des autres valideurs (hors role exclu) qui doivent etre informes.

    Utile pour signaler la progression aux autres signataires : si la DP signe
    APPROVE, RAF et SE recoivent un avis indiquant qu'une etape est franchie.
    """
    other_codes = [c for c in VALIDATOR_ROLE_CODES if c != exclude_role_code]
    if not other_codes:
        return []
    emails = (
        User.objects.filter(
            is_active=True,
            deleted_at__isnull=True,
            user_roles__role__code__in=other_codes,
            user_roles__project__isnull=True,
        )
        .exclude(email="")
        .values_list("email", flat=True)
        .distinct()
    )
    return sorted(set(emails))


def notify_after_signature(expense, validation) -> bool:
    """Notification apres chaque signature individuelle (RAF/DP/SE).

    Politique de notification (decidee par EVE) :
      - Demandeur SEUL est notifie. Les valideurs gerent leur inbox
        directement sur le dashboard Finance (bandeau notifications).

    En cas de rejet d'une ligne, le contenu signale qu'il n'est pas necessaire
    de signer les autres lignes (la demande est deja rejetee).
    """
    role_code = validation.role.code if validation.role_id else "?"
    decision_label = validation.get_decision_display()
    validator_name = (
        f"{validation.validator.first_name} {validation.validator.last_name}".strip()
        or (validation.validator.username if validation.validator_id else "Valideur")
    )
    project_label = expense.project.code if expense.project_id else "Budget General"
    status_label = expense.get_status_display()

    # Nombre de lignes restant a signer (PENDING).
    pending = expense.validations.filter(
        is_active=True, deleted_at__isnull=True, decision="PENDING",
    ).values_list("role__code", flat=True)
    pending_codes = sorted(set(pending))

    if expense.status == expense.Status.APPROVED:
        progress_line = "Toutes les signatures ont ete recueillies : la demande est APPROUVEE."
    elif expense.status == expense.Status.REJECTED:
        progress_line = "La demande est REJETEE : aucune autre signature n'est requise."
    elif pending_codes:
        progress_line = (
            f"Etape franchie : la demande reste SOUMISE et attend encore "
            f"{len(pending_codes)} signature(s) : {', '.join(pending_codes)}."
        )
    else:
        progress_line = f"Etape franchie. Statut actuel : {status_label}."

    base_body = (
        f"  Reference   : DD-{expense.id}\n"
        f"  Intitule    : {expense.title}\n"
        f"  Montant     : {expense.requested_amount} {expense.currency}\n"
        f"  Imputation  : {project_label}\n"
        f"  Ligne budg. : {expense.budget_line}\n"
        f"  Demandeur   : {expense.requester}\n\n"
        f"Signature : {role_code} - {decision_label} par {validator_name}\n"
        f"{progress_line}\n\n"
        f"Ouvrir la demande : {_expense_url(expense)}\n\n"
        f"-- EVE Pilot Finance"
    )

    subject = (
        f"[EVE Pilot] DD-{expense.id} : signature {role_code} {decision_label}"
    )

    # Politique EVE : a chaque signature on previent (1) le demandeur, et
    # (2) les AUTRES valideurs RAF/DP/SE pour le suivi de progression
    # ("untel a signe, il reste X").
    sent_any = False

    requester_mail = _requester_email(expense)
    if requester_mail:
        intro_req = (
            f"Bonjour,\n\nVotre demande de depense vient d'etre {decision_label.lower()} "
            f"par le {role_code} ({validator_name}).\n\n"
        )
        sent_any = _send(subject, intro_req + base_body, [requester_mail]) or sent_any
    else:
        logger.info(
            "Signature DD-%s : pas d'email connu pour le demandeur %s.",
            expense.id, expense.requester_id,
        )

    other_validators = _other_validator_emails(expense, role_code)
    if other_validators:
        intro_val = (
            f"Bonjour,\n\nLa demande de depense DD-{expense.id} vient de recevoir une "
            f"signature ({role_code} - {decision_label} par {validator_name}).\n\n"
        )
        sent_any = _send(subject, intro_val + base_body, other_validators) or sent_any

    return sent_any


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
