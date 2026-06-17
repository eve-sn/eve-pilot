# -*- coding: utf-8 -*-
"""Renseigne les adresses email reelles des comptes pilotes EVE.

seed_pilot_users genere des emails par defaut (username@eve-sn.org) qui ne
correspondent pas toujours a la vraie boite. Les notifications du workflow de
depense (soumission, validations) s'appuient sur User.email : sans la bonne
adresse, les valideurs ne recoivent rien.

Idempotent : ne touche que les comptes listes, ne change que si l'email differe.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User

# username -> adresse mail reelle (source : liste EVE du 17/06/2026).
EMAILS = {
    "alydiouf": "alydiouf@eve-sn.org",
    "sndiaye": "seynabou.ndiaye@eve-sn.org",
    "abdoudiouf": "abdoudiouf@eve-sn.org",
    "amyseck": "amyseck@eve-sn.org",
    "ssakho": "abomadiyana@eve-sn.org",
    "ksylla": "khady.sylla@eve-sn.org",
    "cheikhpathe": "cheikh-pathe.fall@eve-sn.org",
    "taphafall": "moustaphafall@eve-sn.org",
    "morndiaye": "mor.ndiaye@eve-sn.org",
    "habibdiouf": "habibdiouf@eve-sn.org",
    "khalifadieng": "khalifadieng@eve-sn.org",
    "adioumandiongue": "adiou@eve-sn.org",
    "maguevedrame": "magueye.drame@eve-sn.org",
    "rokhayaba": "rokhayaba@eve-sn.org",
    "dioumandour": "dioumandour@eve-sn.org",
}


class Command(BaseCommand):
    help = "Pose les adresses email reelles des comptes pilotes EVE."

    @transaction.atomic
    def handle(self, *args, **opts):
        changed = unchanged = missing = 0
        for username, email in EMAILS.items():
            user = User.objects.filter(username=username).first()
            if user is None:
                self.stderr.write(self.style.WARNING(f"  /!\\ compte '{username}' introuvable."))
                missing += 1
                continue
            if user.email == email:
                unchanged += 1
                continue
            old = user.email or "(vide)"
            user.email = email
            user.save(update_fields=["email"])
            changed += 1
            self.stdout.write(f"  {username:18s} {old}  ->  {email}")
        self.stdout.write(self.style.SUCCESS(
            f"\nEmails pilotes : {changed} mis a jour, {unchanged} inchanges, {missing} absents."
        ))
