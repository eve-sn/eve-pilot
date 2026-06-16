"""Migration de mise en conformite SYCEBNL/SYSCOHADA Revise du plan comptable.

Probleme : le seed initial utilisait une numerotation incorrecte (en realite
proche du SYSCOHADA non-revise) :
  - classe 63 = "Impots et taxes"      au lieu de "Services exterieurs B"
  - classe 64 = "Charges de personnel" au lieu de "Impots et taxes"
  - classe 66 = "Charges financieres"  au lieu de "Charges de personnel"
  - classe 67 = "Subventions versees"  au lieu de "Frais financiers"

Le SYCEBNL repose sur le SYSCOHADA Revise (Acte Uniforme OHADA 2017), ou :
  - 63 = Services exterieurs B (frais bancaires, formation, recherche fonds)
  - 64 = Impots et taxes
  - 65 = Autres charges (incl. subventions versees par l'entite)
  - 66 = Charges de personnel
  - 67 = Frais financiers

Solution : renommer cycliquement les codes existants pour preserver la
semantique des donnees deja saisies (132 BankMovement + 265 JournalLine
dans la base UAT). L'ordre est critique pour eviter les collisions sur
les codes (un meme code ne peut pas exister deux fois).

Ordre :
  1) Subv versees (67 EVE) -> 65/652 SYCEBNL  (libere 67)
  2) Charges financieres (66 EVE) -> 67 SYCEBNL  (libere 66)
  3) Charges de personnel (64 EVE) -> 66 SYCEBNL  (libere 64)
  4) Impots et taxes (63 EVE) -> 64 SYCEBNL  (libere 63 pour Services ext. B)
  5) Reclassements ponctuels (62 EVE -> 628/631/638, etc.)
  6) Mise a jour des class_number sur les parents racines.

Cette migration est ECRITE EN DUR (pas via call_command) pour rester
auto-portante et reproductible sur la base de production le moment venu.

Apres execution, lancer pour completer :
  python manage.py seed_chart_of_accounts_sycebnl
  python manage.py seed_chart_of_accounts_detailed
"""

from django.db import migrations


# Mapping ancien_code -> nouveau_code. La SEMANTIQUE est preservee.
# Si nouveau_code = None, l'ancien compte est soft-deleted (orphelin a part
# pour les codes 6411 anciens "Salaires" qui maintenant rentrent en 6611).
RENAME_MAP = [
    # ============ Phase 1 : Subventions versees (67 EVE) -> 65/652 SYCEBNL ============
    # On les renomme d'abord pour liberer le code "67" pour les frais financiers.
    ("67",  "65_TMP_SUBV"),    # parent. Sera supprime apres migration (65 existe deja).
    ("671", "652"),            # subventions versees aux partenaires
    ("672", "657"),            # appuis beneficiaires
    ("673", "657"),            # bourses (fusion avec 657)

    # ============ Phase 2 : Charges financieres (66 EVE) -> 67 SYCEBNL ============
    ("66",   "67"),            # parent rename
    ("661",  "671"),           # interets sur emprunts
    ("662",  "672"),           # interets sur decouverts
    ("664",  "674"),           # pertes de change. ATTENTION : avant phase 3,
                               # car phase 3 cree "664" = Charges sociales.
    ("668",  "678"),           # autres charges financieres

    # ============ Phase 3 : Charges de personnel (64 EVE) -> 66 SYCEBNL ============
    ("64",   "66"),            # parent rename
    ("641",  "661"),           # remunerations directes
    ("6411", "6611"),          # salaires bruts nationaux
    ("6412", "6612"),          # salaires bruts expatries
    ("6413", "6631"),          # primes et indemnites -> primes / gratifications
    ("6414", "6613"),          # vacations
    ("6415", "6632"),          # indemnites prestataires terrain
    ("644",  "664"),           # charges sociales (parent)
    ("6441", "6641"),          # IPRES
    ("6442", "6642"),          # CSS
    ("6443", "6643"),          # alloc fam
    ("6444", "6644"),          # AT
    ("6445", "6645"),          # IPM
    ("647",  "6685"),          # autres charges sociales -> oeuvres sociales
    ("648",  "668"),           # autres charges de personnel
    ("6481", "6681"),          # formation
    ("6482", "6682"),          # frais medicaux personnel
    ("6483", "6683"),          # restauration personnel
    ("6484", "6684"),          # hebergement personnel mission

    # ============ Phase 4 : Impots et taxes (63 EVE) -> 64 SYCEBNL ============
    ("63",   "64"),            # parent rename
    ("631",  "641"),           # impots directs benefices (peu utilise) -> 641
    ("632",  "641"),           # impots sur le revenu -> 641 (regroupement)
    ("6321", "6411"),          # IRPP retenu source
    ("6322", "6412"),          # TRIMF
    ("633",  "643"),           # TVA charge (sera rare apres remap fin)
    ("6331", "643"),           # TVA collectee
    ("6332", "4451"),          # TVA precomptee = creance recuperable, pas charge
    ("634",  "645"),           # autres impots
    ("6341", "6451"),          # CFCE
    ("6342", "6461"),          # patente
    ("6343", "6462"),          # vignettes

    # ============ Phase 5 : Reclassements ponctuels 62 EVE ============
    # EVE 62 = "Autres services exterieurs" (sub 621-629).
    # SYCEBNL 62 = "Services exterieurs A" - le contenu 622-626 colle, mais
    # 627 (Frais postaux/telecom), 628 (Frais bancaires) et 629 (Honoraires)
    # sont mal places.
    ("627",  "628"),           # Frais postaux et telecoms -> 628 SYCEBNL
    ("6271", "6282"),          # internet
    ("6272", "6283"),          # frais postaux
    ("628",  "631"),           # Frais bancaires -> 631 SYCEBNL (Services ext B)
    ("6281", "6311"),          # commissions bancaires
    ("6282", "672"),           # agios -> 672 (frais financiers, sub interets decouvert)
    ("629",  "638"),           # Honoraires -> 638 SYCEBNL (Services ext B)
    ("6291", "6381"),          # honoraires consultants
    ("6292", "6382"),          # honoraires audit
    ("6293", "6383"),          # honoraires juridiques

    # 626 Etudes et recherches OK en SYCEBNL 626, mais le sub "Formation" doit
    # passer en 632 (frais de formation).
    ("6262", "632"),           # Formations et perfectionnement -> 632 SYCEBNL

    # 604 (achats stockes) -> 6011 (achats de fournitures)
    ("604",  "6011"),

    # ============ Phase 6 : suppression du compte temporaire ============
    # Le "65_TMP_SUBV" cree en phase 1 va etre soft-deleted en fin de migration
    # apres que ses enfants aient ete remappes.
]


def forwards(apps, schema_editor):
    ChartOfAccount = apps.get_model("finance", "ChartOfAccount")
    BankMovement = apps.get_model("finance", "BankMovement")
    JournalLine = apps.get_model("finance", "JournalLine")

    from django.utils import timezone

    # Index : code -> ChartOfAccount actuel.
    by_code = {a.code: a for a in ChartOfAccount.objects.all()}

    def get_or_create_target(new_code: str):
        """Renvoie le compte au code new_code, le creant si absent."""
        if new_code in by_code:
            return by_code[new_code]
        # Determiner la classe SYCEBNL d'apres le 1er chiffre.
        cls = int(new_code[0]) if new_code[0].isdigit() else 6
        acc = ChartOfAccount.objects.create(
            code=new_code,
            name=f"[Auto-cree migration SYCEBNL] {new_code}",
            class_number=cls,
            description=(
                "Compte cree automatiquement par la migration 0015. "
                "Sera renomme et completement decrit par "
                "seed_chart_of_accounts_sycebnl / seed_chart_of_accounts_detailed."
            ),
        )
        by_code[new_code] = acc
        return acc

    def remap_references(old_acc, new_acc):
        """Repointe tous les BankMovement et JournalLine de old_acc vers new_acc."""
        if old_acc.pk == new_acc.pk:
            return 0
        n_bm = BankMovement.objects.filter(contra_account_id=old_acc.pk).update(
            contra_account_id=new_acc.pk
        )
        n_jl = JournalLine.objects.filter(account_id=old_acc.pk).update(
            account_id=new_acc.pk
        )
        return n_bm + n_jl

    print()
    print("Migration SYCEBNL : renumerotation cyclique des classes 63/64/66/67.")
    total_remapped = 0
    total_renamed = 0
    total_merged = 0

    for old_code, new_code in RENAME_MAP:
        old_acc = by_code.get(old_code)
        if old_acc is None:
            # L'ancien compte n'existe pas (deja migre, ou jamais cree). Skip.
            continue

        # Cas A : le nouveau code n'existe pas => simple rename du record.
        if new_code not in by_code:
            old_acc.code = new_code
            old_acc.save(update_fields=["code", "updated_at"])
            by_code.pop(old_code, None)
            by_code[new_code] = old_acc
            print(f"  rename : {old_code:8s} -> {new_code}")
            total_renamed += 1
            continue

        # Cas B : le nouveau code existe deja (collision). On considere que
        # le record cible est le bon (cree par une phase precedente) et on
        # MERGE l'ancien dans le nouveau : on repointe les FK puis on
        # soft-delete l'ancien.
        new_acc = by_code[new_code]
        n = remap_references(old_acc, new_acc)
        old_acc.is_active = False
        old_acc.deleted_at = timezone.now()
        # `code` est CharField(max_length=15) : on utilise un suffixe court
        # "Z_<pk>" (max 12 chars) qui ne collisionne pas avec les codes
        # SYCEBNL (numeriques) ni entre lui-meme (pk unique).
        old_acc.code = f"Z_{old_acc.pk}"
        old_acc.save(update_fields=["is_active", "deleted_at", "code", "updated_at"])
        by_code.pop(old_code, None)
        print(f"  merge  : {old_code:8s} -> {new_code:8s} ({n} reference(s) repointee(s))")
        total_remapped += n
        total_merged += 1

    # Cleanup : le compte temporaire "65_TMP_SUBV"
    tmp = ChartOfAccount.objects.filter(code="65_TMP_SUBV").first()
    if tmp:
        target = by_code.get("65") or get_or_create_target("65")
        n = remap_references(tmp, target)
        tmp.is_active = False
        tmp.deleted_at = timezone.now()
        tmp.code = f"Z_{tmp.pk}"
        tmp.save(update_fields=["is_active", "deleted_at", "code", "updated_at"])
        print(f"  cleanup TMP : 65_TMP_SUBV -> 65 ({n} reference(s) repointee(s))")
        total_remapped += n

    # Mettre a jour le class_number des parents racines au cas ou la rename
    # ne l'a pas ajuste (le class_number etait deja 6 pour 63/64/66/67).
    # En SYCEBNL Revise, tous restent en classe 6.
    print(f"  TOTAL : {total_renamed} renames, {total_merged} merges, "
          f"{total_remapped} references repointees.")


def reverse(apps, schema_editor):
    raise NotImplementedError(
        "La migration 0015 est non-reversible : restaurer un pg_dump anterieur "
        "(cf. scripts/backup_uat.ps1) si vous voulez revenir en arriere."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0014_bankmovementallocation_bankmovementdocument"),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
