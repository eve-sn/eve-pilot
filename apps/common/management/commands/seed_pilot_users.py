"""Cree les 14 comptes utilisateurs du pilote EVE + leurs roles (Palier A).

- Roles globaux (RAF/DP/SE -> tout ; ARAF -> BG + petite caisse) actifs
  immediatement via UserRole(project=None).
- Les autres roles sont crees pour l'affichage ; leur PERIMETRE projet sera
  branche au Palier B via ProjectTeam (necessite les projets + fiches Employe).
- Les mots de passe sont GENERES aleatoirement a la creation et affiches a la
  fin (jamais stockes dans le code). Idempotent : un re-run ne change pas les
  mots de passe existants, sauf --reset-passwords.

Usage :
  manage.py seed_pilot_users
  manage.py seed_pilot_users --reset-passwords   # regenere les mdp de tous
"""

import secrets
import string

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role, User, UserRole

ROLES = {
    "RAF": "Responsable Administratif et Financier",
    "DP": "Directeur de Programme",
    "SE": "Secretaire Executif",
    "ARAF": "Assistante RAF",
    "COMPTABLE": "Comptable projets",
    "CHARGE_SUIVI": "Charge(e) de suivi",
    "REFERENT": "Referent technique",
    "CHEF_PROJET": "Chef de projet / Suivi-evaluation",
    "GESTIONNAIRE": "Gestionnaire projet",
    "SECRETAIRE": "Secretaire comptable",
}

# username, prenom, nom, code role, perimetre (note lisible)
USERS = [
    ("alydiouf", "Aly", "DIOUF", "RAF", "Tout (global)"),
    ("sndiaye", "Seynabou Mbaye", "NDIAYE", "DP", "Tout (global)"),
    ("abdoudiouf", "Abdou", "DIOUF", "SE", "Tout sauf compta technique"),
    ("amyseck", "Amy", "SECK", "ARAF", "BG + petite caisse"),
    ("ssakho", "Serigne Souaibou", "SAKHO", "COMPTABLE", "10 projets (ProjectTeam, Palier B)"),
    ("ksylla", "Khady", "SYLLA", "CHARGE_SUIVI", "PDBH IEC (Palier B)"),
    ("cheikhpathe", "Cheikh Pathe", "FALL", "REFERENT", "Nutrition Pikine+SL (Palier B)"),
    ("taphafall", "Moustapha", "FALL", "CHEF_PROJET", "SL Gouvernance (Palier B)"),
    ("morndiaye", "Mor", "NDIAYE", "CHARGE_SUIVI", "YKK Kedougou (Palier B)"),
    ("habibdiouf", "El Hadji Habib Timack", "DIOUF", "GESTIONNAIRE", "YKK Dakar/Pikine/SL (Palier B)"),
    ("khalifadieng", "Khalifa Ababacar", "DIENG", "GESTIONNAIRE", "YKK Dakar/Pikine (Palier B)"),
    ("adioumandiongue", "Adiouma", "NDIONGUE", "CHARGE_SUIVI", "Pikine/Mbao (Palier B)"),
    ("maguevedrame", "Magueye", "DRAME", "CHARGE_SUIVI", "ECO-AVENIR/ONASAFD (Palier B)"),
    ("rokhayaba", "Rokhaya", "BA", "SECRETAIRE", "SL Gouvernance (Palier B)"),
]

# Comptes ayant aussi acces a l'admin Django (/admin/).
ADMIN_USERS = {"alydiouf"}

_ALPHABET = string.ascii_letters + string.digits


def _gen_password(length: int = 12) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


class Command(BaseCommand):
    help = "Cree les 14 comptes pilotes EVE + roles (Palier A)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-passwords", action="store_true",
            help="Regenere aussi les mots de passe des comptes deja existants.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        reset = opts["reset_passwords"]

        roles = {}
        for code, name in ROLES.items():
            role, _ = Role.objects.get_or_create(code=code, defaults={"name": name})
            if role.name != name:
                role.name = name
                role.save(update_fields=["name"])
            roles[code] = role

        creds = []
        for username, first, last, role_code, scope in USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@eve-sn.org",
                    "first_name": first,
                    "last_name": last,
                },
            )
            fields = []
            if not created:
                if user.first_name != first:
                    user.first_name = first; fields.append("first_name")
                if user.last_name != last:
                    user.last_name = last; fields.append("last_name")

            is_admin = username in ADMIN_USERS
            if user.is_superuser != is_admin:
                user.is_superuser = is_admin; fields.append("is_superuser")
            if getattr(user, "is_staff", False) != is_admin and hasattr(user, "is_staff"):
                user.is_staff = is_admin; fields.append("is_staff")
            if not user.is_active:
                user.is_active = True; fields.append("is_active")

            pwd_display = "(inchange)"
            if created or reset:
                pwd = _gen_password()
                user.set_password(pwd)
                fields.append("password")
                pwd_display = pwd

            if fields or created:
                user.save()

            UserRole.objects.get_or_create(user=user, role=roles[role_code], project=None)
            creds.append((username, role_code, pwd_display, f"{first} {last}", scope, created))

        # --- Recapitulatif ---
        self.stdout.write("")
        self.stdout.write("=" * 78)
        self.stdout.write("IDENTIFIANTS PILOTE EVE  (a distribuer aux testeurs, puis a detruire)")
        self.stdout.write("=" * 78)
        self.stdout.write(f"{'username':18}{'role':14}{'mot de passe':16}nom")
        self.stdout.write("-" * 78)
        for username, role, pwd, name, scope, created in creds:
            tag = "" if created else " [existant]"
            self.stdout.write(f"{username:18}{role:14}{pwd:16}{name}{tag}")
        self.stdout.write("-" * 78)
        n_new = sum(1 for c in creds if c[5])
        self.stdout.write(f"{len(creds)} comptes traites ({n_new} crees). Roles : {', '.join(ROLES)}.")
        self.stdout.write(
            "Perimetres projet (ProjectTeam) NON encore branches : Palier B "
            "(necessite les projets reels + fiches Employe)."
        )
        self.stdout.write(
            "Acces immediat : RAF/DP/SE = tout ; ARAF = BG. Les autres se "
            "connectent mais voient un perimetre vide jusqu'au Palier B."
        )
