"""Remap des sous-comptes bancaires 512.x EVE vers 5211.x officiel.

La migration 0016 a renomme `512` (parent invente) -> `521` (officiel), mais
les sous-comptes 512.10/.20/.../.60 etaient des codes EVE-specifiques et
n'etaient pas dans RENAME_MAP. Resultat : ils sont restes en place avec
leurs FK BankMovement/JournalLine, mais en parallele de nouveaux 5211.x
ont ete crees par seed_chart_of_accounts_official (vide, sans FK).

Cette migration :
  1) Pour chaque pair (512.X, 5211.X) ou les deux existent : repointe les
     FK de 512.X vers 5211.X, puis soft-delete 512.X.
  2) Conserve le lien linked_bank_account sur 5211.X (deja correct).
"""

from django.db import migrations


PAIRS = [
    ("512.10", "5211.10"),
    ("512.20", "5211.20"),
    ("512.30", "5211.30"),
    ("512.40", "5211.40"),
    ("512.50", "5211.50"),
    ("512.60", "5211.60"),
]


def forwards(apps, schema_editor):
    ChartOfAccount = apps.get_model("finance", "ChartOfAccount")
    BankMovement = apps.get_model("finance", "BankMovement")
    JournalLine = apps.get_model("finance", "JournalLine")
    BankMovementAllocation = apps.get_model("finance", "BankMovementAllocation")
    from django.utils import timezone

    print()
    print("Migration 0017 : remap 512.x -> 5211.x.")
    for old_code, new_code in PAIRS:
        old_acc = ChartOfAccount.objects.filter(code=old_code).first()
        new_acc = ChartOfAccount.objects.filter(code=new_code).first()
        if old_acc is None:
            continue
        if new_acc is None:
            # Pas de doublon, on rename simplement
            old_acc.code = new_code
            old_acc.save(update_fields=["code", "updated_at"])
            print(f"  rename : {old_code} -> {new_code}")
            continue
        # Doublon : on transfere linked_bank_account et FK vers new_acc puis on
        # supprime old_acc.
        if old_acc.linked_bank_account_id and not new_acc.linked_bank_account_id:
            new_acc.linked_bank_account_id = old_acc.linked_bank_account_id
            new_acc.save(update_fields=["linked_bank_account", "updated_at"])
        bm = BankMovement.objects.filter(contra_account_id=old_acc.pk).update(
            contra_account_id=new_acc.pk
        )
        jl = JournalLine.objects.filter(account_id=old_acc.pk).update(
            account_id=new_acc.pk
        )
        alloc = BankMovementAllocation.objects.filter(contra_account_id=old_acc.pk).update(
            contra_account_id=new_acc.pk
        )
        old_acc.is_active = False
        old_acc.deleted_at = timezone.now()
        old_acc.code = f"Z3_{old_acc.pk}"
        old_acc.linked_bank_account = None
        old_acc.save(update_fields=["is_active", "deleted_at", "code", "linked_bank_account", "updated_at"])
        print(f"  merge  : {old_code:8} -> {new_code:8} ({bm + jl + alloc} ref(s) repointee(s))")


def reverse(apps, schema_editor):
    raise NotImplementedError(
        "La migration 0017 est non-reversible : restaurer un pg_dump anterieur."
    )


class Migration(migrations.Migration):
    dependencies = [("finance", "0016_remap_to_official_sycebnl")]
    operations = [migrations.RunPython(forwards, reverse)]
