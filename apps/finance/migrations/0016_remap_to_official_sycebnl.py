"""Remap des codes EVE non-conformes vers leurs equivalents officiels SYCEBNL.

Apres execution du seed seed_chart_of_accounts_official, certains codes EVE
inventes (1101 Report a nouveau, 23 Batiments, 40x Fournisseurs, etc.)
existent encore en parallele des codes officiels (1211, 481, ...).
Cette migration :
  1) renomme cycliquement les codes EVE inventes vers leur equivalent
     officiel SYCEBNL le plus proche semantiquement,
  2) repointe les FK BankMovement.contra_account et JournalLine.account,
  3) soft-delete les anciens records (suffixe Z2_<pk>).

Pour les codes EVE qui n'ont AUCUN equivalent officiel direct (ex.
inventions completes type 6231 "Documentation generale"), on les supprime
purement (soft-delete) - SAKHO devra reimputer manuellement si besoin.

Cette migration est ECRITE EN DUR (pas via call_command). Apres execution,
lancer pour completer :
  python manage.py seed_chart_of_accounts_official

Non-reversible. Backup pg_dump prealable obligatoire (scripts/backup_uat.ps1).
"""

from django.db import migrations


# Mapping ancien_code -> nouveau_code officiel.
# None = soft-delete sans remap (code purement invente sans equivalent direct).
RENAME_MAP = [
    # ============ Report a nouveau (1101/1102 -> 121x officiel) ============
    ("1101", "1211"),    # Report a nouveau excedents-resultat
    ("1102", "1218"),    # Report a nouveau excedents-autres reports

    # ============ Immobilisations - racines inventees ============
    # EVE avait cree 23/24/25/28 comme racines de classe alors que SYCEBNL
    # utilise des codes 4 chiffres directement. Soft-delete simple.
    ("23",   None),       # parent invente "Batiments installations" - sous-comptes 23xx existent en officiel
    ("24",   None),       # parent invente "Materiel, mobilier"
    ("25",   None),       # parent invente "Avances et acomptes immo"
    ("28",   None),       # parent invente "Amortissements" - mais 28xx officiel existe

    # ============ Fournisseurs et tiers (40x/41x EVE -> 48x officiel) ============
    # Le plan officiel SYCEBNL EBNL n'a PAS de 40x ordinaire (uniquement 481x
    # Fournisseurs d'investissement). Les paiements directs passent par
    # 5211/charges sans transit fournisseur.
    ("40",   "481"),      # Fournisseurs -> Fournisseurs d'investissement
    ("401",  "481"),      # Fournisseurs exploitation -> id.
    ("4011", "4811"),     # Fournisseurs locaux -> Fournisseurs immo incorporelles
    ("41",   None),       # parent invente "Adherents, clients"
    ("411",  None),       # Adherents - le plan officiel n'a pas ce code
    ("412",  None),       # Clients-usagers
    ("4161", None),       # Adherents cotisations douteuses

    # ============ TVA (4451/4453 EVE -> 445/443 officiel) ============
    ("4451", "445"),      # TVA recuperable
    ("4453", "443"),      # TVA facturee

    # ============ Banques (512 EVE -> 521 officiel) ============
    ("512",  "521"),      # Banques en monnaie locale

    # ============ Transports (611 EVE -> 614 officiel) ============
    ("611",  "614"),      # Transports sur achats -> transports utilisateurs
    ("6131", None),       # invention "Transport quotidien personnel"
    ("6132", None),       # invention "Perdiem mission"
    ("6181", None),       # invention "Voyages mission terrain"

    # ============ Services exterieurs A / B inventes ============
    ("6231", None),       # Documentation generale (deja en 626x officiel)
    ("6263", None),       # Documentation generale et abonnements
    ("6282", None),       # Internet et fibre

    # ============ Impots et taxes 64x ============
    ("643",  None),       # parent "Impots indirects (TVA)"
    ("6451", "6453"),     # CFCE - mapper vers code officiel le plus proche

    # ============ Autres charges 65x ============
    ("6581", "6581"),     # Dons et cotisations - existe officiellement (verifier)
    ("6582", None),       # Frais de reception (invention)
    ("6583", None),       # Frais de representation (invention)

    # ============ Charges de personnel 66x ============
    ("6643", None),       # Alloc fam - le plan officiel a 6641/6642 seulement
    ("6644", None),       # AT
    ("6645", None),       # IPM

    # ============ Produits 7x - sous-comptes EVE inventes ============
    # Beaucoup de mes sous-comptes 75x EVE ne sont pas dans le plan officiel.
    # Le plan officiel SYCEBNL EBNL utilise une racine plus large et les
    # bailleurs sont differencies analytiquement, pas par sous-compte.
    ("701",  None),       # Cotisations adherents - voir 7041 officiel
    ("706",  None),       # Revenus manifestations
    ("751",  None),       # parent "Subventions bailleurs internationaux"
    ("7511", None),       # Subventions Nous-Cims
    ("7512", None),       # Subventions AXA
    ("7513", None),       # Subventions Oghogho
    ("7514", None),       # Subventions ChildFund
    ("7515", None),       # Subventions ONAS-AFD
    ("7516", None),       # Subventions OXFAM
    ("7517", None),       # Subventions FNC
    ("7518", None),       # Autres subventions bailleurs
    ("752",  None),       # Contribution du fondateur
    ("753",  None),       # Subventions institutions locales
    ("754",  None),       # Subventions particuliers
]


def forwards(apps, schema_editor):
    ChartOfAccount = apps.get_model("finance", "ChartOfAccount")
    BankMovement = apps.get_model("finance", "BankMovement")
    JournalLine = apps.get_model("finance", "JournalLine")
    BankMovementAllocation = apps.get_model("finance", "BankMovementAllocation")
    from django.utils import timezone

    by_code = {a.code: a for a in ChartOfAccount.objects.all()}

    print()
    print("Migration 0016 SYCEBNL : remap codes EVE -> codes officiels.")
    n_renamed = 0
    n_merged = 0
    n_dropped = 0
    n_refs_remapped = 0

    for old_code, new_code in RENAME_MAP:
        old_acc = by_code.get(old_code)
        if old_acc is None:
            continue

        # Compte les references
        n_bm = BankMovement.objects.filter(contra_account_id=old_acc.pk).count()
        n_jl = JournalLine.objects.filter(account_id=old_acc.pk).count()
        n_alloc = BankMovementAllocation.objects.filter(contra_account_id=old_acc.pk).count()
        n_total = n_bm + n_jl + n_alloc

        if new_code is None:
            # Soft-delete sans remap. Mais s'il y a des refs, on doit prevenir.
            if n_total > 0:
                print(f"  WARN drop {old_code:8s} ({n_total} refs) - SAKHO devra reimputer manuellement")
                # On laisse les refs intactes mais on soft-delete le compte.
                # Les rapports afficheront le code avec [DEPRECATED] tag.
            old_acc.is_active = False
            old_acc.deleted_at = timezone.now()
            old_acc.code = f"Z2_{old_acc.pk}"
            old_acc.save(update_fields=["is_active", "deleted_at", "code", "updated_at"])
            by_code.pop(old_code, None)
            n_dropped += 1
            continue

        new_acc = by_code.get(new_code)
        if new_acc is None:
            # Le nouveau code n'existe pas encore (seed pas tourne) : on
            # rename simplement.
            old_acc.code = new_code
            old_acc.save(update_fields=["code", "updated_at"])
            by_code.pop(old_code, None)
            by_code[new_code] = old_acc
            print(f"  rename : {old_code:8s} -> {new_code}")
            n_renamed += 1
            continue

        # Collision : merge old dans new. Repointe les FK.
        if old_acc.pk == new_acc.pk:
            continue
        bm_n = BankMovement.objects.filter(contra_account_id=old_acc.pk).update(
            contra_account_id=new_acc.pk
        )
        jl_n = JournalLine.objects.filter(account_id=old_acc.pk).update(
            account_id=new_acc.pk
        )
        alloc_n = BankMovementAllocation.objects.filter(contra_account_id=old_acc.pk).update(
            contra_account_id=new_acc.pk
        )
        refs = bm_n + jl_n + alloc_n
        old_acc.is_active = False
        old_acc.deleted_at = timezone.now()
        old_acc.code = f"Z2_{old_acc.pk}"
        old_acc.save(update_fields=["is_active", "deleted_at", "code", "updated_at"])
        by_code.pop(old_code, None)
        print(f"  merge  : {old_code:8s} -> {new_code:8s} ({refs} ref(s) repointee(s))")
        n_merged += 1
        n_refs_remapped += refs

    print(f"  TOTAL : {n_renamed} renames, {n_merged} merges, "
          f"{n_dropped} drops, {n_refs_remapped} refs repointees.")


def reverse(apps, schema_editor):
    raise NotImplementedError(
        "La migration 0016 est non-reversible : restaurer un pg_dump anterieur "
        "(cf. scripts/backup_uat.ps1) si vous voulez revenir en arriere."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0015_chart_of_accounts_sycebnl_renumber"),
        ("projects", "0004_sycebnl_split_pct"),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
