# -*- coding: utf-8 -*-
"""Affecte chaque testeur pilote a son/ses projet(s) via ProjectTeam.

Necessaire depuis l'activation de la restriction de visibilite : un compte non
global sans ProjectTeam ne voit RIEN. Cette commande pose le perimetre projet de
chaque chargE de suivi / gestionnaire / referent / secretaire, et donne au
COMPTABLE l'acces a tous les projets.

Aperçu par defaut (dry-run). --apply pour ecrire. Idempotent (get_or_create).
Mapping adapte aux PROGRAMMES presents sur le serveur (les 7 + ECO-AVENIR).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.projects.models import Project, ProjectTeam

ALL = "*ALL*"

# username -> liste de codes projet (ou ALL pour tous).
PERIMETERS = {
    "ssakho": ALL,                                              # COMPTABLE : tous les projets
    "ksylla": ["PDBH-2026"],
    "cheikhpathe": ["AGRI-NUT-2026", "GOUV-NUT-2026"],
    "taphafall": ["GOUV-NUT-2026"],
    "morndiaye": ["YKK-2026", "KEDOUGOU-2026"],
    "habibdiouf": ["YKK-2026", "AGRI-NUT-2026", "GOUV-NUT-2026"],
    "khalifadieng": ["YKK-2026", "AGRI-NUT-2026"],
    "adioumandiongue": ["AGRI-NUT-2026"],
    "maguevedrame": ["OGHOGHO-ECOAVENIR-2026"],                 # deja rattache (test)
    "rokhayaba": ["GOUV-NUT-2026"],
    "dioumandour": ["GLOBAL-2026"],
}


class Command(BaseCommand):
    help = "Affecte les testeurs pilotes a leurs projets (ProjectTeam)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Applique (sinon apercu).")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        self.stdout.write(self.style.WARNING(
            f"=== Affectation perimetres : {'APPLICATION' if apply else 'APERCU (dry-run)'} ==="
        ))
        all_codes = list(
            Project.objects.filter(is_active=True, deleted_at__isnull=True)
            .values_list("code", flat=True)
        )
        done = 0
        for username, codes in PERIMETERS.items():
            user = User.objects.filter(username=username).first()
            if user is None:
                self.stdout.write(f"  [skip] {username} : compte absent.")
                continue
            if not user.employee_id:
                self.stdout.write(self.style.WARNING(
                    f"  [!] {username} : pas de fiche employe (lancer link_users_employees)."
                ))
                continue
            target = all_codes if codes == ALL else codes
            present = [c for c in target if c in all_codes]
            missing = [c for c in target if c not in all_codes]
            self.stdout.write(f"  {username:18s} -> {', '.join(present) or '(aucun projet trouve)'}"
                              + (f"   [absents: {', '.join(missing)}]" if missing else ""))
            if apply:
                for code in present:
                    project = Project.objects.get(code=code)
                    ProjectTeam.objects.get_or_create(
                        project=project, employee_id=user.employee_id, start_date=None,
                        defaults={"role": "Affectation pilote", "is_active": True},
                    )
                done += 1
        self.stdout.write(self.style.SUCCESS(
            f"\n{done} testeurs traites." if apply else "\nApercu termine. Relancer avec --apply."
        ))
