from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.shortcuts import render

from apps.finance.models import BankAccount, BudgetLine, Commitment, Disbursement
from apps.projects.models import Donor, Project
from apps.references.models import BudgetCategory


ACTIVE_DOMAIN = {"is_active": True, "deleted_at__isnull": True}


def finance_dashboard(request):
    """Tableau de bord financier.

    Trois lectures cote a cote:
    1. Portefeuille projets: somme des budgets et avancement (donnees alimentees
       depuis Budget_Previsionnel_EVE_2026.xlsx onglet 6).
    2. Budget General EVE: charges fixes + masse salariale, finances par les
       contributions de fonctionnement des projets. Personnel jamais paye
       directement sur un compte projet. Donnees a importer separement.
    3. Vue bailleurs: agregation par donor (volume finance, projets actifs).
    """

    # --- Portefeuille projets ---
    projects = Project.objects.filter(**ACTIVE_DOMAIN).select_related("primary_donor")
    project_status_counts = {
        item["status"]: item["total"]
        for item in projects.values("status").annotate(total=Count("id"))
    }
    portfolio_aggregate = projects.aggregate(
        total_budget=Sum("total_budget"),
    )
    portfolio_total_budget = portfolio_aggregate["total_budget"] or Decimal("0")
    active_projects = projects.filter(status=Project.Status.ACTIVE).order_by("-total_budget", "code")
    preparation_projects = projects.filter(status=Project.Status.PREPARATION).order_by("code")

    # --- Budget General EVE (lignes sans projet) ---
    operating_lines = BudgetLine.objects.filter(project__isnull=True, **ACTIVE_DOMAIN).select_related("category")
    operating_aggregate = operating_lines.aggregate(
        planned=Sum("planned_amount"),
        committed=Sum("committed_amount"),
        disbursed=Sum("disbursed_amount"),
    )
    operating_planned = operating_aggregate["planned"] or Decimal("0")
    operating_committed = operating_aggregate["committed"] or Decimal("0")
    operating_disbursed = operating_aggregate["disbursed"] or Decimal("0")

    operating_by_category = []
    for cat in BudgetCategory.objects.filter(**ACTIVE_DOMAIN).order_by("code"):
        agg = operating_lines.filter(category=cat).aggregate(
            planned=Sum("planned_amount"),
            committed=Sum("committed_amount"),
            disbursed=Sum("disbursed_amount"),
            count=Count("id"),
        )
        if not agg["count"]:
            continue
        operating_by_category.append(
            {
                "category": cat,
                "planned": agg["planned"] or Decimal("0"),
                "committed": agg["committed"] or Decimal("0"),
                "disbursed": agg["disbursed"] or Decimal("0"),
                "count": agg["count"],
            }
        )

    operating_lines_empty = not operating_lines.exists()
    operating_lines_detail = list(
        operating_lines.order_by("category__code", "code", "description")
    )

    # --- Recettes du Budget General : contributions des projets ---
    documented_contributions = projects.filter(
        operating_contribution_amount__isnull=False,
    ).order_by("-operating_contribution_amount", "code")
    pending_contributions = projects.filter(
        operating_contribution_amount__isnull=True,
    ).order_by("code")
    operating_revenue_total = documented_contributions.aggregate(
        total=Sum("operating_contribution_amount")
    )["total"] or Decimal("0")

    # --- Bailleurs ---
    donor_rows = []
    for donor in (
        Donor.objects.filter(**ACTIVE_DOMAIN)
        .annotate(
            project_count=Count(
                "primary_projects",
                filter=Q(primary_projects__is_active=True, primary_projects__deleted_at__isnull=True),
            ),
            total_funded=Sum(
                "primary_projects__total_budget",
                filter=Q(primary_projects__is_active=True, primary_projects__deleted_at__isnull=True),
            ),
        )
        .order_by("-total_funded", "name")
    ):
        donor_rows.append(
            {
                "donor": donor,
                "project_count": donor.project_count or 0,
                "total_funded": donor.total_funded or Decimal("0"),
            }
        )

    # --- Comptes bancaires EVE ---
    bank_accounts = list(
        BankAccount.objects.filter(**ACTIVE_DOMAIN)
        .prefetch_related("projects")
        .order_by("name")
    )
    bank_total_opening = sum(
        (acc.opening_balance for acc in bank_accounts if acc.opening_balance is not None),
        Decimal("0"),
    )
    bank_accounts_with_balance = [acc for acc in bank_accounts if acc.opening_balance is not None]
    bank_accounts_missing_balance = [acc for acc in bank_accounts if acc.opening_balance is None]

    # --- Commitments / Disbursements globaux (lecture transversale) ---
    transaction_counts = {
        "commitments": Commitment.objects.filter(**ACTIVE_DOMAIN).count(),
        "disbursements": Disbursement.objects.filter(**ACTIVE_DOMAIN).count(),
    }

    context = {
        "portfolio_total_budget": portfolio_total_budget,
        "active_project_count": project_status_counts.get(Project.Status.ACTIVE, 0),
        "preparation_project_count": project_status_counts.get(Project.Status.PREPARATION, 0),
        "suspended_project_count": project_status_counts.get(Project.Status.SUSPENDED, 0),
        "total_project_count": projects.count(),
        "active_projects": active_projects,
        "preparation_projects": preparation_projects,
        "operating_planned": operating_planned,
        "operating_committed": operating_committed,
        "operating_disbursed": operating_disbursed,
        "operating_by_category": operating_by_category,
        "operating_lines_empty": operating_lines_empty,
        "operating_lines_detail": operating_lines_detail,
        "documented_contributions": documented_contributions,
        "pending_contributions": pending_contributions,
        "operating_revenue_total": operating_revenue_total,
        "operating_balance": operating_revenue_total - operating_planned,
        "bank_accounts": bank_accounts,
        "bank_total_opening": bank_total_opening,
        "bank_accounts_with_balance_count": len(bank_accounts_with_balance),
        "bank_accounts_missing_balance_count": len(bank_accounts_missing_balance),
        "donor_rows": donor_rows,
        "active_donor_count": len([d for d in donor_rows if d["project_count"] > 0]),
        "transaction_counts": transaction_counts,
    }
    return render(request, "finance/dashboard.html", context)
