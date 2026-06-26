"""Phase 0 bascule engagement : compte de charge par defaut sur la categorie.

Ajoute BudgetCategory.default_charge_account -> finance.ChartOfAccount.
Prerequis de la comptabilite d'engagement : l'ecriture Dr 6x / Cr 401 nait
a l'ENGAGEMENT, donc le compte de charge (classe 6) doit etre connu avant
tout decaissement. La categorie budgetaire porte la valeur par defaut
(location -> 6221, restauration -> 6582, ...) ; Commitment pourra la
surcharger (Phase 1).

FK inter-app volontaire : finance depend deja de references
(BudgetLine.category) ; cette FK ajoute references -> finance. Aucun cycle
de migration (la cible ChartOfAccount existe depuis finance 0008), FK
nullable.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("references", "0001_initial"),
        ("finance", "0008_chartofaccount_bankmovement_contra_account_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="budgetcategory",
            name="default_charge_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="default_for_budget_categories",
                to="finance.chartofaccount",
                help_text="Compte de charge (classe 6) impute par defaut a l'engagement.",
            ),
        ),
    ]
