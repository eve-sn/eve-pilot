# -*- coding: utf-8 -*-
"""Lie chaque compte utilisateur a sa fiche Employee par correspondance de nom.

Indispensable AVANT le test du workflow de depense : `expense_create` refuse une
demande si le compte n'est pas rattache a un Employee (requester). Les comptes
pilotes crees par seed_pilot_users ne portent pas ce lien.

Appariement robuste aux homonymes (plusieurs DIOUF / FALL / NDIAYE) : on compare
l'ENSEMBLE des jetons du nom (prenom + nom), sans accents ni casse. Un compte
n'est lie que si UN SEUL employe correspond exactement. Les ambiguites et les
comptes sans fiche (personnel d'appui, stagiaires) sont signales, jamais devines.

Idempotent : ne retouche pas un compte deja lie (sauf --relink) et ne vole pas
une fiche deja rattachee a un autre compte.

Usage :
  manage.py link_users_employees
  manage.py link_users_employees --relink   # recalcule meme les comptes deja lies
"""

import unicodedata

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.hr.models import Employee


def _tokens(*parts) -> frozenset:
    """Jetons normalises (sans accents, minuscules) d'un nom compose."""
    raw = " ".join(p or "" for p in parts)
    norm = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    return frozenset(t for t in norm.lower().replace("-", " ").split() if t)


class Command(BaseCommand):
    help = "Lie les comptes utilisateurs a leur fiche Employee par nom."

    def add_arguments(self, parser):
        parser.add_argument(
            "--relink", action="store_true",
            help="Recalcule le lien meme pour les comptes deja rattaches.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        relink = opts["relink"]

        employees = list(
            Employee.objects.filter(is_active=True, deleted_at__isnull=True)
        )
        # Index : jetons -> liste d'employes (pour detecter les ambiguites).
        by_tokens = {}
        for emp in employees:
            by_tokens.setdefault(_tokens(emp.first_name, emp.last_name), []).append(emp)

        already_taken = set(
            User.objects.filter(employee__isnull=False).values_list("employee_id", flat=True)
        )

        linked, skipped, ambiguous, unmatched = 0, 0, [], []
        for user in User.objects.all().order_by("username"):
            if user.employee_id and not relink:
                skipped += 1
                continue

            utok = _tokens(user.first_name, user.last_name)
            if not utok:
                unmatched.append((user.username, "compte sans nom"))
                continue

            candidates = by_tokens.get(utok, [])
            if not candidates:
                # Tentative souple : sous-ensemble unique (prenom compose tronque).
                soft = [
                    e for e in employees
                    if utok and (utok <= _tokens(e.first_name, e.last_name)
                                 or _tokens(e.first_name, e.last_name) <= utok)
                ]
                candidates = soft

            # Retire les fiches deja prises par un autre compte.
            free = [e for e in candidates if e.id not in already_taken or e.id == user.employee_id]

            if len(free) == 1:
                emp = free[0]
                user.employee = emp
                user.save(update_fields=["employee", "updated_at"] if hasattr(user, "updated_at") else ["employee"])
                already_taken.add(emp.id)
                linked += 1
                self.stdout.write(f"  OK  {user.username:18s} -> {emp.matricule} {emp.first_name} {emp.last_name}")
            elif len(free) > 1:
                ambiguous.append((user.username, [f"{e.matricule} {e.first_name} {e.last_name}" for e in free]))
            else:
                unmatched.append((user.username, f"{user.first_name} {user.last_name}".strip()))

        self.stdout.write(self.style.SUCCESS(
            f"\nLiaison terminee : {linked} lies, {skipped} deja lies (ignores)."
        ))
        if ambiguous:
            self.stdout.write(self.style.WARNING("\nAMBIGUS (plusieurs fiches possibles, a lier a la main) :"))
            for u, opts_ in ambiguous:
                self.stdout.write(f"  {u} : {', '.join(opts_)}")
        if unmatched:
            self.stdout.write(self.style.WARNING("\nSANS FICHE EMPLOYE (normal pour appui/stagiaires) :"))
            for u, label in unmatched:
                self.stdout.write(f"  {u} : {label}")
