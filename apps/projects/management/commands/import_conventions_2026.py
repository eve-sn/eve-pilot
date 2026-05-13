"""
Renseigne pour chaque projet la contribution au Budget General EVE.

Le mecanisme varie selon le bailleur :
- Nous-Cims : frais indirect en % sur total direct (10% standard, 7% pour ECP).
- AXA Climate : frais de gestion 10% sur le HT.
- Oghogho Meye / La Locomotiva : ligne dediee A.6 'coordination et suivi' qui
  paie directement le personnel EVE (pas un overhead, mais une enveloppe de
  fonctionnement explicite).
- ONAS-AFD : pas de % global, contributions dispersees dans le budget projet
  (Gestionnaire, location bureaux, etc.) - a documenter manuellement.
- ChildFund / P&G : non identifie dans le budget initial - a documenter
  manuellement.

Sources xlsx (dossier eve_pilot_backend) :
- Annexe 2_Budget detaille Phase Extension Pikine_EVE.xlsx (R96 'Frais indirect 10%')
- Annexe 2- Budget detaille projet de _saint louis_15-06-2025 (1).xlsx (R145 'B. Couts indirects')
- Budget _rojet ISF pour Pikine (1).xlsx (R13 'Frais de gestion (10%)')
- Budget previsionnel mise en oeuvre pilote Initiative ECO-AVENIR.xlsx (R17 A.6 5000 EUR)
- Projet Espaces communautaires ... (3).xlsx (R32 'Frais indirect (7%)')

Idempotente: update_or_create par code projet.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.projects.models import Project


# Contributions exactes lues dans les conventions / budgets detailles.
KNOWN_CONTRIBUTIONS = {
    "NOUSCIMS-PIK-MBAO-2026": {
        "amount": Decimal("15504437.74"),
        "pct": Decimal("10.00"),
        "note": (
            "Source: Annexe 2_Budget detaille Phase Extension Pikine_EVE.xlsx, "
            "ligne 'Frais indirect (10%)'. 10% du total direct 155 044 377 FCFA."
        ),
    },
    "NOUSCIMS-SL-2026": {
        "amount": Decimal("15504423.27"),
        "pct": Decimal("10.00"),
        "note": (
            "Source: Annexe 2 Budget detaille Saint-Louis 15-06-2025.xlsx, "
            "ligne 'B. Couts indirects / TOTAL B.1' sur 3 annees. "
            "10% du total direct 155 044 233 FCFA."
        ),
    },
    "NOUSCIMS-ECP-2025": {
        "amount": Decimal("1716540.00"),
        "pct": Decimal("7.00"),
        "note": (
            "Source: Projet Espaces communautaires (3).xlsx, ligne 'Frais "
            "indirect (7%)'. 7% du total direct 24 522 000 FCFA. Taux Nous-Cims "
            "inferieur au standard 10% pour cette convention specifique."
        ),
    },
    "AXA-ISF-2026": {
        "amount": Decimal("2685000.00"),
        "pct": Decimal("10.00"),
        "note": (
            "Source: Budget projet ISF pour Pikine (1).xlsx, ligne 'Frais de "
            "gestion (10%)'. 10% applique sur le HT 26 850 000 FCFA, pas sur le TTC."
        ),
    },
    "OGHOGHO-ECOAVENIR-2026": {
        # 5000 EUR convertis : 5000 * (7543506 / 11500) ≈ 3279350 FCFA
        "amount": Decimal("3279350.00"),
        "pct": None,
        "note": (
            "Source: Budget previsionnel ECO-AVENIR.xlsx, ligne A.6 'Assurer la "
            "coordination et le suivi du projet' = 5 000 EUR (43,5% du budget "
            "total 11 500 EUR). Description xlsx : 'Indemnite et frais de "
            "deplacement du personnel mobilise par EVE pour la coordination et "
            "le suivi technique et financier'. Mecanisme different d'un overhead "
            "% : ligne dediee, pas frais indirect."
        ),
    },
}


# Projets dont le mecanisme de contribution reste a documenter (lecture des
# conventions PDF pas encore faite).
PENDING_CONTRIBUTIONS = {
    "ONASAFD-PDBH-IEC-2025": (
        "A documenter. Convention ONAS-AFD (Avenant 3 PDBH PAR 2025) : pas "
        "d'overhead pourcentage explicite dans le devis detaille. Contribution "
        "dispersee via lignes : Gestionnaire (R66 = 12,8 MFCFA) + Contribution "
        "location bureaux/appoint admin (R77 = 6,6 MFCFA) + autres lignes "
        "structure. A consolider apres lecture du PDF d'avenant."
    ),
    "CHILDFUND-INONDATIONS-2025": (
        "A documenter. Budget P&G_EVE_Budget distribution_Nov.25.xlsx : "
        "structure non-classique (57 lignes x 85 colonnes). Pas de ligne "
        "overhead identifiee a la lecture rapide. A confirmer apres lecture "
        "du Grant Agreement / accord ChildFund."
    ),
}


class Command(BaseCommand):
    help = (
        "Renseigne pour chaque projet la contribution au Budget General "
        "(operating_contribution_amount/pct/note) a partir des conventions "
        "detaillees. Idempotente."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Mise a jour des contributions Budget General par projet...")

        for code, data in KNOWN_CONTRIBUTIONS.items():
            self._update(code, data["amount"], data["pct"], data["note"])

        for code, note in PENDING_CONTRIBUTIONS.items():
            self._update(code, None, None, note)

        self.stdout.write(self.style.SUCCESS("Conventions traitees."))

    def _update(self, code, amount, pct, note):
        try:
            project = Project.objects.get(
                code=code, is_active=True, deleted_at__isnull=True
            )
        except Project.DoesNotExist:
            self.stderr.write(f"  /!\\ Project {code} introuvable, ignore.")
            return

        project.operating_contribution_amount = amount
        project.operating_contribution_pct = pct
        project.operating_contribution_note = note
        project.save(
            update_fields=[
                "operating_contribution_amount",
                "operating_contribution_pct",
                "operating_contribution_note",
                "updated_at",
            ]
        )
        if amount is not None:
            self.stdout.write(
                f"  {code}: contribution {amount} FCFA "
                f"({pct}% conventionnel)" if pct is not None
                else f"  {code}: contribution {amount} FCFA (mecanisme hors %)"
            )
        else:
            self.stdout.write(f"  {code}: marque 'a documenter' (PDF non lu)")
