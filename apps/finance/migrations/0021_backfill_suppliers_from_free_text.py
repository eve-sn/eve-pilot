"""Phase 1 bascule engagement : backfill du master fournisseurs.

Cree un Supplier par fournisseur distinct trouve dans le texte libre
historique (Commitment.supplier_name), avec son sous-compte auxiliaire
401.<code>, puis rattache chaque Commitment a son Supplier.

Dedup : cle = supplier_name normalise (strip + casefold). Les variantes de
casse/espaces sont fusionnees ; le NIF retenu est le premier non vide du
groupe. Les commitments sans supplier_name restent sans Supplier (FK null).

Migration de DONNEES : on utilise les modeles historiques (pas de save()
custom ni ensure_chart_account), donc la creation du compte 401.<code> est
reproduite ici en clair.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    Commitment = apps.get_model("finance", "Commitment")
    Supplier = apps.get_model("finance", "Supplier")
    ChartOfAccount = apps.get_model("finance", "ChartOfAccount")

    parent_401 = ChartOfAccount.objects.filter(
        code="401", is_active=True, deleted_at__isnull=True
    ).first()

    # 1) Regroupe les commitments par fournisseur normalise.
    groups = {}  # cle normalisee -> {"name": str, "nif": str, "ids": [pk]}
    qs = Commitment.objects.exclude(supplier_name="").exclude(supplier_name__isnull=True)
    for c in qs.iterator():
        key = (c.supplier_name or "").strip().casefold()
        if not key:
            continue
        g = groups.setdefault(key, {"name": c.supplier_name.strip(), "nif": "", "ids": []})
        if not g["nif"] and (c.supplier_nif or "").strip():
            g["nif"] = c.supplier_nif.strip()
        g["ids"].append(c.pk)

    # 2) Cree un Supplier + son compte 401.<code> par groupe, puis rattache.
    counter = 0
    for key in sorted(groups):
        g = groups[key]
        counter += 1
        code = f"F{counter:03d}"
        supplier = Supplier.objects.create(
            code=code,
            name=g["name"][:150],
            nif=g["nif"][:30],
        )
        ChartOfAccount.objects.update_or_create(
            code=f"401.{code}",
            defaults={
                "name": f"Fournisseur {g['name']}"[:200],
                "class_number": 4,
                "parent": parent_401,
                "linked_supplier": supplier,
                "is_active": True,
                "deleted_at": None,
            },
        )
        Commitment.objects.filter(pk__in=g["ids"]).update(supplier=supplier)

    if counter:
        print(f"  Backfill fournisseurs : {counter} Supplier(s) cree(s) depuis le texte libre.")


def reverse(apps, schema_editor):
    """Detache les commitments et supprime les Supplier backfilles.

    Les comptes 401.<code> generes sont soft-deletes (suffixe Z_supplier_<pk>)
    pour ne pas casser une eventuelle ecriture, conformement au style maison.
    """
    Commitment = apps.get_model("finance", "Commitment")
    Supplier = apps.get_model("finance", "Supplier")
    ChartOfAccount = apps.get_model("finance", "ChartOfAccount")
    from django.utils import timezone

    Commitment.objects.update(supplier=None)
    for acc in ChartOfAccount.objects.filter(linked_supplier__isnull=False):
        acc.is_active = False
        acc.deleted_at = timezone.now()
        acc.code = f"Z_supplier_{acc.pk}"
        acc.linked_supplier = None
        acc.save(update_fields=["is_active", "deleted_at", "code", "linked_supplier"])
    Supplier.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0020_commitment_charge_account_supplier_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
