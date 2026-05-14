"""
Impute en masse les mouvements bancaires du compte Budget General (SUNU)
a leur compte SYCEBNL contrepartie.

Strategie en 2 niveaux :
1. Mapping cible par reference VIxxxx (les virements internes projet -> BG,
   arbitres un par un par EVE car plusieurs projets partagent un meme
   compte bancaire source).
2. Regles generiques par motif de libelle (frais bancaires, cheques au
   porteur, reversements Tresor, etc.), appliquees dans l'ordre : la
   premiere qui matche gagne.

Les mouvements non resolus (versements par tiers, remises de cheques,
annulations) sont laisses sans contra_account et listes en fin
d'execution : a imputer manuellement via /admin/.

Le signal post_save de BankMovement genere automatiquement l'ecriture
comptable en partie double des que contra_account est renseigne.

Idempotent : on peut relancer, seuls les contra_account changent.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import BankMovement, ChartOfAccount


BG_ACCOUNT_NAME = "Budget General"


# --- Niveau 0 : mapping cible par reference bancaire exacte -------------
# Pour les mouvements sans VIxxxx dans le libelle mais arbitres par EVE
# (ex: les virements du 30/04 depuis Banque Atlantique, meme affectation
# que leurs equivalents de mars).
REF_MAPPING = {
    "I247986": "181.050",   # 500 000 - Pikine Phase II (equiv. VI3326 mars)
    "I248189": "181.050",   # 2 648 773 - Pikine Phase II (equiv. VI3328 mars)
    "I248190": "181.030",   # 650 000 - ECP (equiv. VI3327 mars)
}


# --- Niveau 1 : mapping cible par reference VIxxxx (arbitrage EVE) -------
# La cle est cherchee comme sous-chaine du libelle (les libelles BG portent
# 'VI2341...', 'VI3328...', etc.).
VI_MAPPING = {
    "VI2341": "181.110",   # Pikine Phase I (reliquat)
    "VI2720": "181.110",   # Pikine Phase I (reliquat)
    "VI2340": "181.110",   # Pikine Phase I (reliquat)
    "VI3328": "181.050",   # Pikine Phase II
    "VI2718": "181.050",   # Pikine Phase II
    "VI2719": "181.050",   # Pikine Phase II
    "VI3326": "181.050",   # Pikine Phase II
    "VI2339": "181.030",   # Espaces communautaires Pikine (ECP)
    "VI2721": "181.030",   # Espaces communautaires Pikine (ECP)
    "VI2717": "181.030",   # ECP - deduit du libelle 'ESPACE' (a confirmer)
    "VI3327": "181.030",   # ECP - deduit du libelle 'GESTIONNAIRE ET ANIMATEU' (a confirmer)
    "VI2992": "181.060",   # Saint-Louis (transfert tresorerie BA -> BG -> CBAO)
}


# --- Niveau 2 : regles generiques par motif (ordre = priorite) ----------
# (pattern en MAJUSCULES cherche dans le libelle, code compte SYCEBNL)
GENERIC_RULES = [
    ("SONATEL", "61"),                         # facture telecom Sonatel -> services exterieurs
    ("ST LOUIS", "181.060"),                   # virement recu Saint-Louis
    ("EAU VIE-ENVIRONNEMENT SOD", "181.080"),  # virement recu du compte ONAS/SODIS
    ("ENVIRONNEMENT SE", "181.060"),           # Vir.recu '...ENVIRONNEMENT SE...SALAIRE' = EVE SErvice (CBAO) = Saint-Louis
    ("TRESOR PUBLIC", "63"),                   # reversement impots/taxes a l'Etat
    ("FR CPT INSTIT", "66"),                   # frais de compte institutionnel
    ("COMMISSION", "66"),                      # commissions bancaires
    ("FRAIS COMPENSE", "66"),                  # frais de compensation
    ("COTISATION", "66"),                      # cotisation service bancaire (My SUNU)
    ("INTERET", "66"),                         # agios / interets debiteurs
    ("TAXE", "66"),                            # taxes bancaires
    ("TIMBRE", "66"),                          # timbres sur versements
    ("RETROCESSION", "77"),                    # retrocession en faveur d'EVE
    ("PAIEMENT DE CHEQUE AU PORTEUR", "64"),   # paie / cheques personnel
    ("VIREMENT MULTIPLE", "64"),               # virement de paie groupee
    ("RETRAIT PAR CHEQUE", "64"),              # retrait cheque personnel
]


class Command(BaseCommand):
    help = "Impute en masse les mouvements du compte Budget General a leur compte SYCEBNL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche ce qui serait fait sans rien modifier.",
        )

    @transaction.atomic
    def handle(self, *args, dry_run=False, **options):
        # Resolution des comptes SYCEBNL
        codes_needed = (
            set(REF_MAPPING.values())
            | set(VI_MAPPING.values())
            | {code for _, code in GENERIC_RULES}
        )
        accounts = {
            a.code: a
            for a in ChartOfAccount.objects.filter(
                code__in=codes_needed, is_active=True, deleted_at__isnull=True
            )
        }
        missing = codes_needed - set(accounts.keys())
        if missing:
            self.stderr.write(
                f"Comptes SYCEBNL manquants : {sorted(missing)}. "
                "Lancer seed_chart_of_accounts_sycebnl."
            )
            return

        movements = BankMovement.objects.filter(
            account__name=BG_ACCOUNT_NAME, is_active=True, deleted_at__isnull=True
        ).order_by("date_operation", "id")

        imputed_ref = 0
        imputed_vi = 0
        imputed_generic = 0
        unresolved = []

        for movement in movements:
            label_upper = movement.label.upper()
            target_code = None
            rule_kind = None

            # Niveau 0 : reference bancaire exacte
            if movement.reference and movement.reference in REF_MAPPING:
                target_code = REF_MAPPING[movement.reference]
                rule_kind = f"ref:{movement.reference}"

            # Niveau 1 : reference VIxxxx dans le libelle
            if target_code is None:
                for vi_ref, code in VI_MAPPING.items():
                    if vi_ref in label_upper:
                        target_code = code
                        rule_kind = f"VI:{vi_ref}"
                        break

            # Niveau 2 : regles generiques
            if target_code is None:
                for pattern, code in GENERIC_RULES:
                    if pattern in label_upper:
                        target_code = code
                        rule_kind = f"regle:{pattern}"
                        break

            if target_code is None:
                unresolved.append(movement)
                continue

            account = accounts[target_code]
            if not dry_run:
                if movement.contra_account_id != account.id:
                    movement.contra_account = account
                    movement.save(update_fields=["contra_account", "updated_at"])
            if rule_kind.startswith("ref:"):
                imputed_ref += 1
            elif rule_kind.startswith("VI:"):
                imputed_vi += 1
            else:
                imputed_generic += 1

        # Rapport
        prefix = "[DRY-RUN] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Imputation BG : {imputed_ref} par reference bancaire, "
                f"{imputed_vi} par reference VIxxxx, "
                f"{imputed_generic} par regle generique, "
                f"{len(unresolved)} non resolus."
            )
        )
        if unresolved:
            self.stdout.write("  Mouvements non resolus (a imputer manuellement via /admin/) :")
            for m in unresolved:
                sens = f"D{m.debit:,.0f}" if m.debit else f"C{m.credit:,.0f}"
                self.stdout.write(f"    [{m.date_operation}] {sens:>16}  {m.label[:75]}")
