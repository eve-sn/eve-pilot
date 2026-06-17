# -*- coding: utf-8 -*-
"""Reconcilie les projets EVE selon le modele « Programme -> financements ».

Les projets « par bailleur » (NOUSCIMS-*, OGHOGHO-*, etc.) sont replies dans les
PROGRAMMES (les 7 + les nouveaux), le bailleur devenant un financement (Donor +
ProjectDonor + BudgetLine.donor). On NE casse PAS le plan d'action : les
activites sont deplacees (pas supprimees) vers le programme.

Sans danger par defaut : mode APERCU (dry-run). Rien n'est ecrit tant que
--apply n'est pas passe. ECO-AVENIR est volontairement EXCLU (projet du test en
cours).

Usage :
  manage.py reconcile_projects_programmes            # apercu
  manage.py reconcile_projects_programmes --apply    # applique (transaction)
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.activities.models import Activity
from apps.finance.models import BudgetLine
from apps.projects.models import Donor, Project, ProjectDonor

# Programmes a creer s'ils n'existent pas (code -> titre).
NEW_PROGRAMMES = {
    "CLIMAT-2026": "Climat et resilience - adaptation au changement climatique",
    "URGENCES-2026": "Urgences et reponse aux inondations",
    "PNBSF-2026": "PNBSF / PAPSA - bourses de securite familiale",
}

# Financement (projet-bailleur)  ->  Programme cible.
MAPPING = {
    "NOUSCIMS-PIK-MBAO-2026": "AGRI-NUT-2026",
    "NOUSCIMS-ECP-2025": "AGRI-NUT-2026",
    "NOUSCIMS-GT-WALLU-DOOM-2025": "AGRI-NUT-2026",
    "NOUSCIMS-SL-2026": "GOUV-NUT-2026",
    "ONASAFD-PDBH-IEC-2025": "PDBH-2026",
    "AXA-ISF-2026": "CLIMAT-2026",
    "CHILDFUND-INONDATIONS-2025": "URGENCES-2026",
    "PNBSF-DAK-2026": "PNBSF-2026",
    "PNBSF-KED-2026": "PNBSF-2026",
}

# Projets a ne PAS toucher (test en cours).
EXCLUDE = {"OGHOGHO-ECOAVENIR-2026"}


class Command(BaseCommand):
    help = "Replie les projets-bailleurs dans les programmes (Programme -> financements)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Applique reellement (sinon apercu seul).")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        mode = "APPLICATION" if apply else "APERCU (dry-run, rien n'est ecrit)"
        self.stdout.write(self.style.WARNING(f"=== Reconciliation projets : {mode} ==="))

        if apply:
            with transaction.atomic():
                self._run(apply=True)
        else:
            self._run(apply=False)

    def _ensure_programme(self, code, apply):
        p = Project.objects.filter(code=code).first()
        if p:
            return p
        if code in NEW_PROGRAMMES:
            self.stdout.write(f"  [programme] creer {code} : {NEW_PROGRAMMES[code]}")
            if apply:
                p, _ = Project.objects.update_or_create(
                    code=code,
                    defaults={
                        "title": NEW_PROGRAMMES[code][:200],
                        "status": Project.Status.ACTIVE,
                        "start_date": "2026-01-01",
                        "end_date": "2026-12-31",
                        "currency": "XOF",
                        "is_active": True, "deleted_at": None,
                    },
                )
                return p
            return None  # apercu : pas encore cree
        return None

    def _run(self, apply):
        # 1) Programmes manquants
        for code in NEW_PROGRAMMES:
            self._ensure_programme(code, apply)

        # 2) Replis
        tot_lines = tot_acts = folded = 0
        for grant_code, prog_code in MAPPING.items():
            if grant_code in EXCLUDE:
                continue
            grant = Project.objects.filter(code=grant_code).first()
            if grant is None:
                self.stdout.write(f"  [skip] {grant_code} : absent de cette base.")
                continue
            prog = self._ensure_programme(prog_code, apply)
            nbl = BudgetLine.objects.filter(project=grant, deleted_at__isnull=True).count()
            nact = Activity.objects.filter(project=grant, deleted_at__isnull=True).count()
            donor = grant.primary_donor
            donor_label = donor.name if donor else "(aucun bailleur)"
            self.stdout.write(
                f"  {grant_code:30s} -> {prog_code:16s} | {nbl:3d} lignes, "
                f"{nact:2d} activites | financement: {donor_label} | desactive {grant_code}"
            )
            tot_lines += nbl
            tot_acts += nact
            folded += 1

            if apply and prog is not None:
                if donor:
                    ProjectDonor.objects.get_or_create(project=prog, donor=donor)
                    BudgetLine.objects.filter(project=grant).update(project=prog, donor=donor)
                else:
                    BudgetLine.objects.filter(project=grant).update(project=prog)
                Activity.objects.filter(project=grant).update(project=prog)
                for bank in grant.bank_accounts.all():
                    prog.bank_accounts.add(bank)
                grant.is_active = False
                grant.status = Project.Status.ARCHIVED
                grant.save(update_fields=["is_active", "status", "updated_at"])

        self.stdout.write(self.style.SUCCESS(
            f"\n{folded} financements replies, {tot_lines} lignes et {tot_acts} activites "
            f"{'deplacees' if apply else 'a deplacer'}. ECO-AVENIR exclu (test en cours)."
        ))
        if not apply:
            self.stdout.write("Relancer avec --apply pour executer.")
