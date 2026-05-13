from collections import OrderedDict
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, render

from apps.finance.models import (
    BankAccount,
    BankAccountSnapshot,
    BankMovement,
    BudgetLine,
    CashMovement,
    CashflowEntry,
    ChartOfAccount,
    Commitment,
    Disbursement,
)
from apps.projects.models import Donor, Project
from apps.references.models import BudgetCategory


ACTIVE_DOMAIN = {"is_active": True, "deleted_at__isnull": True}

MONTHS_FR = ["Jan", "Fév", "Mars", "Avr", "Mai", "Juin", "Juil", "Août", "Sept", "Oct", "Nov", "Déc"]


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


def cashflow_dashboard(request):
    """Plan de tresorerie mensuel 2026, reconstruit depuis les CashflowEntry."""

    year = 2026
    entries = (
        CashflowEntry.objects.filter(period_year=year, **ACTIVE_DOMAIN)
        .select_related("project", "category")
        .order_by("direction", "label", "period_month")
    )

    def _empty_row(label):
        return {
            "label": label,
            "project": None,
            "category": None,
            "monthly": [Decimal("0")] * 12,
            "total_year": Decimal("0"),
        }

    in_rows = OrderedDict()
    out_rows = OrderedDict()

    for entry in entries:
        bucket = in_rows if entry.direction == CashflowEntry.Direction.INCOMING else out_rows
        row = bucket.setdefault(entry.label, _empty_row(entry.label))
        if entry.project is not None and row["project"] is None:
            row["project"] = entry.project
        if entry.category is not None and row["category"] is None:
            row["category"] = entry.category
        row["monthly"][entry.period_month - 1] = entry.planned_amount

    for row in list(in_rows.values()) + list(out_rows.values()):
        row["total_year"] = sum(row["monthly"], Decimal("0"))

    in_rows_list = sorted(in_rows.values(), key=lambda r: r["label"])
    out_rows_list = sorted(out_rows.values(), key=lambda r: r["label"])

    total_in_by_month = [
        sum((row["monthly"][i] for row in in_rows_list), Decimal("0")) for i in range(12)
    ]
    total_out_by_month = [
        sum((row["monthly"][i] for row in out_rows_list), Decimal("0")) for i in range(12)
    ]
    solde_net = [total_in_by_month[i] - total_out_by_month[i] for i in range(12)]
    cumul = []
    running = Decimal("0")
    for value in solde_net:
        running += value
        cumul.append(running)

    # Position de depart utile pour comparer le cumul a une trajectoire de
    # tresorerie reelle (solde bancaire d'ouverture au 01/01/2026).
    bank_total_opening = (
        BankAccount.objects.filter(**ACTIVE_DOMAIN)
        .aggregate(total=Sum("opening_balance"))["total"]
        or Decimal("0")
    )

    cumul_with_opening = [bank_total_opening + value for value in cumul]

    context = {
        "year": year,
        "months": MONTHS_FR,
        "in_rows": in_rows_list,
        "out_rows": out_rows_list,
        "total_in_by_month": total_in_by_month,
        "total_out_by_month": total_out_by_month,
        "solde_net": solde_net,
        "cumul": cumul,
        "cumul_with_opening": cumul_with_opening,
        "bank_total_opening": bank_total_opening,
        "total_in_year": sum(total_in_by_month, Decimal("0")),
        "total_out_year": sum(total_out_by_month, Decimal("0")),
        "solde_net_year": sum(solde_net, Decimal("0")),
    }
    return render(request, "finance/cashflow.html", context)


def chart_of_accounts_view(request):
    """Vue plan comptable SYCEBNL.

    Affiche tous les comptes regroupes par classe, avec le solde de chaque
    compte ayant des mouvements imputes (BankMovement.contra_account ou
    CashMovement.contra_account).
    """

    accounts = (
        ChartOfAccount.objects.filter(**ACTIVE_DOMAIN)
        .select_related("parent", "linked_project", "linked_bank_account", "linked_cash_register")
        .order_by("class_number", "code")
    )

    # Calcul du solde par compte (mouvements bancaires + caisse)
    bank_totals = (
        BankMovement.objects.filter(**ACTIVE_DOMAIN, contra_account__isnull=False)
        .values("contra_account_id")
        .annotate(total_credit=Sum("credit"), total_debit=Sum("debit"))
    )
    cash_totals = (
        CashMovement.objects.filter(**ACTIVE_DOMAIN, contra_account__isnull=False)
        .values("contra_account_id")
        .annotate(total_credit=Sum("credit"), total_debit=Sum("debit"))
    )

    balances = {}
    for row in list(bank_totals) + list(cash_totals):
        acc_id = row["contra_account_id"]
        cur = balances.setdefault(acc_id, {"credit": Decimal("0"), "debit": Decimal("0")})
        cur["credit"] += row["total_credit"] or Decimal("0")
        cur["debit"] += row["total_debit"] or Decimal("0")

    # Regroupement par classe
    classes = OrderedDict()
    for cls_value, cls_label in ChartOfAccount.AccountClass.choices:
        classes[cls_value] = {"label": cls_label, "accounts": []}

    for account in accounts:
        b = balances.get(account.id, {"credit": Decimal("0"), "debit": Decimal("0")})
        # Solde brut = credit - debit (positif = solde crediteur)
        net = b["credit"] - b["debit"]
        movement_count = (
            BankMovement.objects.filter(**ACTIVE_DOMAIN, contra_account=account).count()
            + CashMovement.objects.filter(**ACTIVE_DOMAIN, contra_account=account).count()
        )
        classes[account.class_number]["accounts"].append(
            {
                "account": account,
                "total_credit": b["credit"],
                "total_debit": b["debit"],
                "balance_net": net,
                "movement_count": movement_count,
            }
        )

    total_bank_movements = BankMovement.objects.filter(**ACTIVE_DOMAIN).count()
    imputed_bank_movements = BankMovement.objects.filter(
        **ACTIVE_DOMAIN, contra_account__isnull=False
    ).count()

    context = {
        "classes": classes,
        "total_bank_movements": total_bank_movements,
        "imputed_bank_movements": imputed_bank_movements,
        "unimputed_bank_movements": total_bank_movements - imputed_bank_movements,
    }
    return render(request, "finance/chart_of_accounts.html", context)


def bank_account_detail(request, public_uuid):
    """Detail d'un compte bancaire : projets rattaches, snapshots de solde,
    mouvements bancaires (BankMovement) saisis pour ce compte."""

    account = get_object_or_404(
        BankAccount.objects.prefetch_related("projects", "snapshots", "movements"),
        public_uuid=public_uuid,
        **ACTIVE_DOMAIN,
    )

    snapshots = account.snapshots.filter(**ACTIVE_DOMAIN).order_by("-date")
    movements = (
        account.movements.filter(**ACTIVE_DOMAIN)
        .select_related("project", "cashflow_entry")
        .order_by("-date_operation", "-id")
    )
    movement_totals = movements.aggregate(
        total_debit=Sum("debit"),
        total_credit=Sum("credit"),
    )
    total_debit = movement_totals["total_debit"] or Decimal("0")
    total_credit = movement_totals["total_credit"] or Decimal("0")

    projects = account.projects.filter(**ACTIVE_DOMAIN).order_by("code")

    context = {
        "account": account,
        "projects": projects,
        "snapshots": snapshots,
        "movements": movements,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "net_movement": total_credit - total_debit,
    }
    return render(request, "finance/bank_account_detail.html", context)
