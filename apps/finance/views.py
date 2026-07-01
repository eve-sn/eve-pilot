from collections import OrderedDict
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.access import (
    accessible_bank_account_ids,
    accessible_project_ids,
    can_see_accounting,
    can_see_bg,
    can_see_everything,
    project_filter,
    require_accounting_access,
    require_global_access,
    user_can_access_project,
    user_can_execute_expense,
    user_can_record_bank_movements,
)
from apps.accounts.models import Role, UserRole
from apps.finance.forms import (
    BankMovementQuickForm,
    CashMovementQuickForm,
    ExpenseDocumentForm,
    ExpenseEngageForm,
    ExpenseExecuteForm,
    ExpenseRequestForm,
    ExpenseValidationDecisionForm,
    RecordPaymentForm,
)
from apps.finance.notifications import (
    notify_after_signature,
    notify_requester_on_decision,
    notify_validators_on_submit,
)
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
    ExpenseDocument,
    ExpenseRequest,
    ExpenseValidation,
    JournalLine,
)
from apps.projects.models import Donor, Project
from apps.references.models import BudgetCategory


ACTIVE_DOMAIN = {"is_active": True, "deleted_at__isnull": True}

MONTHS_FR = ["Jan", "Fév", "Mars", "Avr", "Mai", "Juin", "Juil", "Août", "Sept", "Oct", "Nov", "Déc"]


@login_required
def finance_dashboard(request):
    """Tableau de bord financier.

    Trois lectures cote a cote:
    1. Portefeuille projets: somme des budgets et avancement (donnees alimentees
       depuis Budget_Previsionnel_EVE_2026.xlsx onglet 6).
    2. Budget General EVE: charges fixes + masse salariale, finances par les
       contributions de fonctionnement des projets. Personnel jamais paye
       directement sur un compte projet. Donnees a importer separement.
    3. Vue bailleurs: agregation par donor (volume finance, projets actifs).

    Acces : filtre par periemtre projet de l'utilisateur (cf. accounts.access).
    Les utilisateurs project-scopes (chargee de suivi, comptable projet) ne
    voient que leurs projets ; les lignes BG restent reservees aux RAF/DP/SE.
    """

    see_all = can_see_everything(request.user)
    show_bg = can_see_bg(request.user)
    acc_ids = accessible_project_ids(request.user)  # None = tous

    # --- Portefeuille projets (restreint au perimetre utilisateur) ---
    projects = Project.objects.filter(**ACTIVE_DOMAIN).select_related("primary_donor")
    if acc_ids is not None:
        projects = projects.filter(id__in=acc_ids)
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

    # --- Budget General EVE (lignes sans projet) -- visible direction seulement ---
    if show_bg:
        operating_lines = BudgetLine.objects.filter(project__isnull=True, **ACTIVE_DOMAIN).select_related("category")
    else:
        operating_lines = BudgetLine.objects.none()
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

    # --- Bailleurs (restreint au perimetre utilisateur) ---
    donor_rows = []
    donor_proj_filter = Q(primary_projects__is_active=True, primary_projects__deleted_at__isnull=True)
    if acc_ids is not None:
        donor_proj_filter &= Q(primary_projects__id__in=acc_ids)
    donor_qs = (
        Donor.objects.filter(**ACTIVE_DOMAIN)
        .annotate(
            project_count=Count("primary_projects", filter=donor_proj_filter),
            total_funded=Sum("primary_projects__total_budget", filter=donor_proj_filter),
        )
        .order_by("-total_funded", "name")
    )
    # Cache les bailleurs sans projet accessible.
    if acc_ids is not None:
        donor_qs = donor_qs.filter(primary_projects__id__in=acc_ids).distinct()
    for donor in donor_qs:
        donor_rows.append(
            {
                "donor": donor,
                "project_count": donor.project_count or 0,
                "total_funded": donor.total_funded or Decimal("0"),
            }
        )

    # --- Comptes bancaires EVE (restreint aux projets de l'utilisateur) ---
    # Inclut aussi les comptes BG (sans projet rattache) si l'utilisateur a
    # acces BG (cas Assistante RAF).
    bank_qs = (
        BankAccount.objects.filter(**ACTIVE_DOMAIN)
        .prefetch_related("projects")
        .annotate(_proj_count=Count("projects"))
    )
    if acc_ids is not None:
        bank_filter = Q(projects__id__in=acc_ids) if acc_ids else Q(pk__in=[])
        if show_bg:
            bank_filter |= Q(_proj_count=0)
        bank_qs = bank_qs.filter(bank_filter).distinct()
    bank_accounts = list(bank_qs.order_by("name"))
    bank_total_opening = sum(
        (acc.opening_balance for acc in bank_accounts if acc.opening_balance is not None),
        Decimal("0"),
    )
    bank_accounts_with_balance = [acc for acc in bank_accounts if acc.opening_balance is not None]
    bank_accounts_missing_balance = [acc for acc in bank_accounts if acc.opening_balance is None]

    # --- Commitments / Disbursements (restreints aux projets accessibles) ---
    commit_qs = Commitment.objects.filter(**ACTIVE_DOMAIN)
    disb_qs = Disbursement.objects.filter(**ACTIVE_DOMAIN)
    if acc_ids is not None:
        # Commitment et Disbursement transitent par budget_line qui porte project.
        commit_qs = commit_qs.filter(budget_line__project_id__in=acc_ids)
        disb_qs = disb_qs.filter(budget_line__project_id__in=acc_ids)
    transaction_counts = {
        "commitments": commit_qs.count(),
        "disbursements": disb_qs.count(),
    }

    # --- Petite caisse (visible aux utilisateurs avec acces BG) ---
    cash_summary = []
    if show_bg:
        from apps.finance.models import CashRegister, CashMovement
        today = timezone.now().date()
        month_start = today.replace(day=1)
        for r in CashRegister.objects.filter(**ACTIVE_DOMAIN).order_by("name"):
            mvs = CashMovement.objects.filter(register=r, **ACTIVE_DOMAIN)
            agg_all = mvs.aggregate(d=Sum("debit"), c=Sum("credit"))
            mvs_month = mvs.filter(date_operation__gte=month_start)
            agg_month = mvs_month.aggregate(d=Sum("debit"), c=Sum("credit"))
            recent = list(
                mvs.select_related("contra_account", "project", "budget_line")
                .order_by("-date_operation", "-id")[:5]
            )
            cash_summary.append({
                "register": r,
                "debit_total": agg_all["d"] or Decimal("0"),
                "credit_total": agg_all["c"] or Decimal("0"),
                "solde": (agg_all["c"] or Decimal("0")) - (agg_all["d"] or Decimal("0")),
                "mvt_total": mvs.count(),
                "month_debit": agg_month["d"] or Decimal("0"),
                "month_credit": agg_month["c"] or Decimal("0"),
                "month_count": mvs_month.count(),
                "unit_limit": r.UNIT_LIMIT,
                "weekly_limit": r.WEEKLY_LIMIT,
                "recent": recent,
            })

    # --- Indicateurs operationnels scopes au perimetre utilisateur ---
    # Activites (planning + execution terrain) + rapports + beneficiaires.
    from apps.activities.models import Activity as _Activity, ActivityReport, Beneficiary
    act_qs = _Activity.objects.filter(**ACTIVE_DOMAIN)
    if acc_ids is not None:
        act_qs = act_qs.filter(project_id__in=acc_ids)
    rpt_qs = ActivityReport.objects.filter(**ACTIVE_DOMAIN, activity__in=act_qs)
    bnf_qs = Beneficiary.objects.filter(**ACTIVE_DOMAIN, activity_report__in=rpt_qs)

    activity_stats = {
        "total": act_qs.count(),
        "planned": act_qs.filter(status=_Activity.Status.PLANNED).count(),
        "in_progress": act_qs.filter(status=_Activity.Status.IN_PROGRESS).count(),
        "completed": act_qs.filter(status=_Activity.Status.COMPLETED).count(),
        "canceled": act_qs.filter(status=_Activity.Status.CANCELED).count(),
    }
    report_stats = {
        "total": rpt_qs.count(),
        "submitted": rpt_qs.filter(validation_status=ActivityReport.ValidationStatus.SUBMITTED).count(),
        "validated": rpt_qs.filter(validation_status=ActivityReport.ValidationStatus.VALIDATED).count(),
        "rejected": rpt_qs.filter(validation_status=ActivityReport.ValidationStatus.REJECTED).count(),
    }
    beneficiary_stats = {
        "total": bnf_qs.count(),
        "male": bnf_qs.filter(gender=Beneficiary.Gender.MALE).count(),
        "female": bnf_qs.filter(gender=Beneficiary.Gender.FEMALE).count(),
    }
    # Repartition activites par projet (top 5 par nombre d'activites).
    activities_by_project = list(
        act_qs.values("project__code", "project__title")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    # --- Notifications de l'utilisateur connecte ---
    user = request.user
    user_role_codes = set(
        UserRole.objects.filter(user=user).values_list("role__code", flat=True)
    )

    # Demandes accessibles par l'utilisateur (meme regle que expense_list).
    user_expenses = ExpenseRequest.objects.filter(**ACTIVE_DOMAIN)
    if acc_ids is not None:
        scope = Q(project_id__in=acc_ids)
        if show_bg:
            scope |= Q(project__isnull=True)
        user_expenses = user_expenses.filter(scope)

    # Validateur : combien de lignes PENDING attendent ma signature ?
    pending_signatures_count = 0
    validator_codes = user_role_codes & {"RAF", "DP", "SE"}
    if validator_codes:
        pending_signatures_count = ExpenseValidation.objects.filter(
            is_active=True,
            deleted_at__isnull=True,
            decision=ExpenseValidation.Decision.PENDING,
            role__code__in=validator_codes,
            request__status=ExpenseRequest.Status.SUBMITTED,
            request__in=user_expenses,
        ).count()

    # Comptable / RAF : demandes APPROUVEES en attente d'execution.
    awaiting_execution_count = user_expenses.filter(
        status=ExpenseRequest.Status.APPROVED
    ).count()

    # Demandeur : mes propres brouillons + mes rejetees a retravailler.
    my_drafts_count = 0
    my_rejected_count = 0
    if user.employee_id:
        my_drafts_count = ExpenseRequest.objects.filter(
            requester=user.employee,
            status=ExpenseRequest.Status.DRAFT,
            **ACTIVE_DOMAIN,
        ).count()
        my_rejected_count = ExpenseRequest.objects.filter(
            requester=user.employee,
            status=ExpenseRequest.Status.REJECTED,
            **ACTIVE_DOMAIN,
        ).count()

    notifications = {
        "pending_signatures": pending_signatures_count,
        "awaiting_execution": awaiting_execution_count,
        "my_drafts": my_drafts_count,
        "my_rejected": my_rejected_count,
        "is_validator": bool(validator_codes),
        "validator_codes": sorted(validator_codes),
        "total": (
            pending_signatures_count
            + awaiting_execution_count
            + my_drafts_count
            + my_rejected_count
        ),
    }

    # ----- GRAPHIQUES & ALERTES -----
    from datetime import timedelta
    from apps.finance.models import CashRegister, CashMovement

    # --- Graphique 1 : Consommation budget par projet (top 8 par planifie) ---
    bl_filter = ACTIVE_DOMAIN.copy()
    bl_qs = BudgetLine.objects.filter(**bl_filter, project__isnull=False)
    if acc_ids is not None:
        bl_qs = bl_qs.filter(project_id__in=acc_ids)
    budget_per_project = list(
        bl_qs.values("project_id", "project__code", "project__title")
        .annotate(
            planned=Sum("planned_amount"),
            committed=Sum("committed_amount"),
            disbursed=Sum("disbursed_amount"),
        )
        .order_by("-planned")[:8]
    )
    max_budget = max(
        [(row["planned"] or Decimal("0")) for row in budget_per_project],
        default=Decimal("1"),
    ) or Decimal("1")
    # Pre-calcule largeurs en % pour template
    for row in budget_per_project:
        p = row["planned"] or Decimal("0")
        c = row["committed"] or Decimal("0")
        d = row["disbursed"] or Decimal("0")
        row["bar_planned_pct"] = float(p * Decimal("100") / max_budget) if max_budget else 0
        row["bar_committed_pct"] = float(c * Decimal("100") / max_budget) if max_budget else 0
        row["bar_disbursed_pct"] = float(d * Decimal("100") / max_budget) if max_budget else 0
        row["taux_engagement"] = float(c * Decimal("100") / p) if p else 0

    # --- Graphique 2 : Tresorerie mensuelle 2026 (en/sorties) ---
    monthly_cashflow = []
    base_cf = CashflowEntry.objects.filter(period_year=2026, **ACTIVE_DOMAIN)
    if acc_ids is not None:
        cf_scope = Q(project_id__in=acc_ids)
        if show_bg:
            cf_scope |= Q(project__isnull=True)
        base_cf = base_cf.filter(cf_scope)
    for m in range(1, 13):
        agg = base_cf.filter(period_month=m).aggregate(
            entrees=Sum("planned_amount", filter=Q(direction=CashflowEntry.Direction.INCOMING)),
            sorties=Sum("planned_amount", filter=Q(direction=CashflowEntry.Direction.OUTGOING)),
        )
        monthly_cashflow.append({
            "month_idx": m,
            "month_label": MONTHS_FR[m - 1],
            "entrees": agg["entrees"] or Decimal("0"),
            "sorties": agg["sorties"] or Decimal("0"),
        })
    max_cashflow = max(
        max(row["entrees"], row["sorties"]) for row in monthly_cashflow
    ) or Decimal("1")
    for row in monthly_cashflow:
        row["entrees_h"] = float(row["entrees"] * 100 / max_cashflow) if max_cashflow else 0
        row["sorties_h"] = float(row["sorties"] * 100 / max_cashflow) if max_cashflow else 0

    # --- Graphique 3 : Donut activites par statut ---
    act_total = activity_stats["total"]
    donut_segments = []
    if act_total:
        # circonference d'un cercle de rayon 60
        C = 2 * 3.14159265 * 60
        offset = 0
        palette = [
            ("Planifie", activity_stats["planned"], "#8a5b1b"),
            ("En cours", activity_stats["in_progress"], "#1f5972"),
            ("Realise", activity_stats["completed"], "#0e4d36"),
            ("Annule", activity_stats["canceled"], "#8a2b2b"),
        ]
        for label, value, color in palette:
            if not value:
                continue
            pct = value / act_total
            length = C * pct
            donut_segments.append({
                "label": label, "value": value, "color": color,
                "dash": f"{length:.1f} {C - length:.1f}",
                "offset": offset,
                "pct": int(round(pct * 100)),
            })
            offset -= length  # SVG strokes start at 12 o'clock and go clockwise

    # ----- ALERTES -----
    alerts = []
    threshold_5d = timezone.now() - timedelta(days=5)
    # Alert 1 : demandes en retard de signature (RAF/DP/SE seulement)
    if validator_codes:
        late_q = user_expenses.filter(
            status=ExpenseRequest.Status.SUBMITTED,
            submitted_at__lt=threshold_5d,
        )
        late_count = late_q.count()
        if late_count:
            alerts.append({
                "level": "warn",
                "title": f"{late_count} demande{'s' if late_count > 1 else ''} en attente de signature depuis plus de 5 jours",
                "cta_label": "Ouvrir l'inbox",
                "cta_href": "/finance/demandes/?to_sign=1",
            })
    # Alert 2 : projet a engagement > 80% du planifie
    for row in budget_per_project:
        if row["taux_engagement"] >= 80:
            alerts.append({
                "level": "warn" if row["taux_engagement"] < 95 else "alert",
                "title": f"Projet {row['project__code']} : engagement a {row['taux_engagement']:.0f}% du budget planifie",
                "cta_label": "Voir le projet",
                "cta_href": f"/finance/demandes/?status=APPROVED",  # provisoire
            })
    # Alert 3 : caisse > 70% plafond hebdo
    if cash_summary:
        today_d = timezone.now().date()
        iso_week_start = today_d - timedelta(days=today_d.weekday())
        for c in cash_summary:
            weekly_debit = CashMovement.objects.filter(
                register=c["register"],
                date_operation__gte=iso_week_start,
                **ACTIVE_DOMAIN,
            ).aggregate(t=Sum("debit"))["t"] or Decimal("0")
            limit = CashRegister.WEEKLY_LIMIT
            ratio = float(weekly_debit * 100 / limit) if limit else 0
            if ratio >= 70:
                alerts.append({
                    "level": "warn" if ratio < 90 else "alert",
                    "title": f"Caisse {c['register'].name} : {ratio:.0f}% du plafond hebdomadaire utilise ({weekly_debit:.0f} / {limit:.0f} XOF)",
                    "cta_label": "Recharger la caisse",
                    "cta_href": "/finance/caisse/saisir/",
                })
    # Alert 4 : projets sans rapport ce mois (pour SE/DP/RAF)
    if see_all:
        today_d = timezone.now().date()
        month_start = today_d.replace(day=1)
        # Projets avec activites mais 0 rapport ce mois
        from django.db.models import Exists, OuterRef
        from apps.activities.models import ActivityReport as _AR
        projects_active = (
            act_qs.values("project_id", "project__code")
            .annotate(rpt_count=Count("reports", filter=Q(
                reports__report_date__gte=month_start,
                reports__is_active=True,
            )))
            .filter(rpt_count=0)
            .distinct()[:3]
        )
        for p in projects_active:
            alerts.append({
                "level": "info",
                "title": f"Projet {p['project__code']} : aucun rapport terrain depuis le 1er du mois",
                "cta_label": "Voir activites",
                "cta_href": f"/activites/?project={p['project_id']}",
            })
    # Limite a 6 alertes max pour ne pas saturer
    alerts = alerts[:6]


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
        "see_all": see_all,
        "show_bg": show_bg,
        "notifications": notifications,
        "cash_summary": cash_summary,
        "activity_stats": activity_stats,
        "report_stats": report_stats,
        "beneficiary_stats": beneficiary_stats,
        "activities_by_project": activities_by_project,
        "has_project_scope": acc_ids is None or bool(acc_ids),
        "can_record_bank": user_can_record_bank_movements(request.user),
        "budget_per_project": budget_per_project,
        "monthly_cashflow": monthly_cashflow,
        "donut_segments": donut_segments,
        "donut_total": act_total,
        "alerts": alerts,
    }
    return render(request, "finance/dashboard.html", context)


@login_required
def cashflow_dashboard(request):
    """Plan de tresorerie mensuel 2026, reconstruit depuis les CashflowEntry."""

    year = 2026
    acc_ids = accessible_project_ids(request.user)
    show_bg = can_see_bg(request.user)
    entries = (
        CashflowEntry.objects.filter(period_year=year, **ACTIVE_DOMAIN)
        .select_related("project", "category")
        .order_by("direction", "label", "period_month")
    )
    if acc_ids is not None:
        # Voir les entries des projets accessibles + entries BG ssi autorise.
        scope = Q(project_id__in=acc_ids)
        if show_bg:
            scope |= Q(project__isnull=True)
        entries = entries.filter(scope)

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


@require_accounting_access
def chart_of_accounts_view(request):
    """Vue plan comptable SYCEBNL avec filtres UX.

    Parametres GET :
      - q          : recherche libre sur code ou libelle (case-insensitive)
      - cls        : restreindre a une classe SYCEBNL (1..9)
      - all        : "1" pour afficher TOUS les comptes (sinon, par defaut, on
                     n'affiche que les comptes ayant au moins un mouvement
                     OU un objet metier lie - projet, banque, caisse).
    """
    from django.db.models import Q

    q = (request.GET.get("q") or "").strip()
    cls_filter = (request.GET.get("cls") or "").strip()
    show_all = request.GET.get("all") == "1"

    # Calcul des mouvements par compte (pour le toggle "avec mouvements"
    # et l'affichage des soldes)
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

    # JournalLine couvre aussi les comptes tresorerie (debit cote 5211 d'une
    # entree, etc.) qui ne sont pas en contra_account. On les inclut dans le
    # set "comptes avec mouvements" pour ne pas les masquer par defaut.
    journal_acc_ids = set(
        JournalLine.objects.filter(**ACTIVE_DOMAIN)
        .values_list("account_id", flat=True)
        .distinct()
    )
    accounts_with_movements = set(balances.keys()) | journal_acc_ids

    # Construction du queryset filtre
    qs = (
        ChartOfAccount.objects.filter(**ACTIVE_DOMAIN)
        .select_related("parent", "linked_project", "linked_bank_account", "linked_cash_register")
        .order_by("class_number", "code")
    )

    if q:
        qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))

    if cls_filter and cls_filter.isdigit():
        qs = qs.filter(class_number=int(cls_filter))

    if not show_all and not q:
        # Mode par defaut : on ne montre que les comptes ayant des mouvements
        # OU lies a un objet metier (project, banque, caisse) OU marques
        # comme comptes de liaison interne (qui sont des points de pivot
        # critiques meme sans mouvement).
        qs = qs.filter(
            Q(id__in=accounts_with_movements)
            | Q(linked_project__isnull=False)
            | Q(linked_bank_account__isnull=False)
            | Q(linked_cash_register__isnull=False)
            | Q(is_liaison=True)
        )

    accounts = list(qs)

    # Regroupement par classe
    classes = OrderedDict()
    for cls_value, cls_label in ChartOfAccount.AccountClass.choices:
        classes[cls_value] = {"label": cls_label, "accounts": []}

    for account in accounts:
        b = balances.get(account.id, {"credit": Decimal("0"), "debit": Decimal("0")})
        net = b["credit"] - b["debit"]
        movement_count = (
            BankMovement.objects.filter(**ACTIVE_DOMAIN, contra_account=account).count()
            + CashMovement.objects.filter(**ACTIVE_DOMAIN, contra_account=account).count()
        )
        # Defensif : classe absente du enum (cf. fix bug class 9).
        bucket = classes.setdefault(
            account.class_number,
            {"label": f"{account.class_number} - Classe inattendue", "accounts": []},
        )
        bucket["accounts"].append(
            {
                "account": account,
                "total_credit": b["credit"],
                "total_debit": b["debit"],
                "balance_net": net,
                "movement_count": movement_count,
            }
        )

    # Stats globales (non filtrees)
    total_bank_movements = BankMovement.objects.filter(**ACTIVE_DOMAIN).count()
    imputed_bank_movements = BankMovement.objects.filter(
        **ACTIVE_DOMAIN, contra_account__isnull=False
    ).count()
    total_accounts = ChartOfAccount.objects.filter(**ACTIVE_DOMAIN).count()
    displayed_accounts = sum(len(c["accounts"]) for c in classes.values())

    context = {
        "classes": classes,
        "total_bank_movements": total_bank_movements,
        "imputed_bank_movements": imputed_bank_movements,
        "unimputed_bank_movements": total_bank_movements - imputed_bank_movements,
        "total_accounts": total_accounts,
        "displayed_accounts": displayed_accounts,
        "q": q,
        "cls_filter": cls_filter,
        "show_all": show_all,
        "is_filtered": bool(q) or bool(cls_filter) or not show_all,
        "available_classes": list(ChartOfAccount.AccountClass.choices),
    }
    return render(request, "finance/chart_of_accounts.html", context)


@login_required
def expense_list(request):
    """Liste des demandes de depense.

    Filtres :
      ?status=SUBMITTED|APPROVED|...  : par statut
      ?mine=1                          : mes demandes uniquement
      ?to_sign=1                       : demandes ou j'ai un avis PENDING a rendre
    """

    qs = ExpenseRequest.objects.filter(**ACTIVE_DOMAIN).select_related(
        "project", "budget_line", "requester"
    )

    # Filtre par perimetre projet (chargee de suivi, comptable scope).
    acc_ids = accessible_project_ids(request.user)
    if acc_ids is not None:
        scope = Q(project_id__in=acc_ids)
        if can_see_bg(request.user):
            scope |= Q(project__isnull=True)
        qs = qs.filter(scope)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)
    mine = request.GET.get("mine") == "1"
    if mine and request.user.employee_id:
        qs = qs.filter(requester=request.user.employee)

    user_roles_codes = set(
        UserRole.objects.filter(user=request.user)
        .values_list("role__code", flat=True)
    )
    user_can_validate = bool(user_roles_codes & {"RAF", "DP", "SE"})

    # Inbox : compter les ExpenseValidation PENDING dont le role est dans
    # ceux de l'utilisateur connecte. Sert au badge + au filtre ?to_sign=1.
    inbox_validations = ExpenseValidation.objects.filter(
        is_active=True,
        deleted_at__isnull=True,
        decision=ExpenseValidation.Decision.PENDING,
        role__code__in=user_roles_codes,
        request__status=ExpenseRequest.Status.SUBMITTED,
    )
    inbox_count = inbox_validations.count()

    to_sign = request.GET.get("to_sign") == "1"
    if to_sign and user_can_validate:
        qs = qs.filter(id__in=inbox_validations.values_list("request_id", flat=True))

    qs = qs.order_by("-id")

    context = {
        "requests": qs[:200],
        "status_choices": ExpenseRequest.Status.choices,
        "filters": {"status": status, "mine": mine, "to_sign": to_sign},
        "user_roles_codes": user_roles_codes,
        "user_can_validate": user_can_validate,
        "user_has_employee": bool(request.user.employee_id),
        "inbox_count": inbox_count,
    }
    return render(request, "finance/expense_list.html", context)


@login_required
def expense_create(request):
    """Formulaire de creation d'une demande de depense (status DRAFT)."""

    if not request.user.employee_id:
        messages.error(
            request,
            "Ton compte utilisateur n'est pas rattache a un Employee. "
            "Demande au RAF de lier ton compte a un dossier RH avant de creer une demande.",
        )
        return redirect("finance:expense_list")

    if request.method == "POST":
        form = ExpenseRequestForm(request.POST, user=request.user)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.requester = request.user.employee
            expense.status = ExpenseRequest.Status.DRAFT
            expense.save()
            messages.success(request, f"Demande DD-{expense.id} creee en brouillon.")
            return redirect("finance:expense_detail", pk=expense.id)
    else:
        form = ExpenseRequestForm(user=request.user)

    context = {"form": form}
    return render(request, "finance/expense_create.html", context)


@login_required
def expense_detail(request, pk):
    """Detail d'une demande : informations, validations, documents.
    Gere les actions POST : submit (DRAFT->SUBMITTED), validate (RAF/DP/SE),
    upload_document, cancel."""

    expense = get_object_or_404(
        ExpenseRequest.objects.select_related("project", "budget_line", "requester").prefetch_related(
            "validations__role", "validations__validator", "documents__uploaded_by"
        ),
        pk=pk,
        **ACTIVE_DOMAIN,
    )

    # Controle d'acces par projet : valideurs RAF/DP/SE voient tout, les
    # autres ne voient que les demandes de leurs projets (ou BG si autorise).
    # Le demandeur peut toujours voir sa propre demande.
    is_requester_short = request.user.employee_id == expense.requester_id
    if not (is_requester_short or can_see_everything(request.user)):
        acc_ids = accessible_project_ids(request.user) or set()
        if expense.project_id is None:
            # Demande BG : reservee aux comptes a acces global.
            if not can_see_bg(request.user):
                raise Http404("Demande non accessible.")
        elif expense.project_id not in acc_ids:
            raise Http404("Demande non accessible.")

    user_role_codes = set(
        UserRole.objects.filter(user=request.user).values_list("role__code", flat=True)
    )
    is_requester = request.user.employee_id == expense.requester_id

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "submit" and is_requester and expense.status == ExpenseRequest.Status.DRAFT:
            roles = list(Role.objects.filter(code__in=["RAF", "DP", "SE"]))
            if len(roles) < 3:
                messages.error(request, "Roles RAF/DP/SE manquants. Lancer seed_expense_validation_roles.")
                return redirect("finance:expense_detail", pk=pk)
            expense.status = ExpenseRequest.Status.SUBMITTED
            expense.submitted_at = timezone.now()
            expense.save(update_fields=["status", "submitted_at", "updated_at"])
            for role in roles:
                ExpenseValidation.objects.get_or_create(
                    request=expense, role=role,
                    defaults={"decision": ExpenseValidation.Decision.PENDING},
                )
            notify_validators_on_submit(expense)
            messages.success(request, "Demande soumise. Les 3 valideurs RAF/DP/SE sont notifies.")
            return redirect("finance:expense_detail", pk=pk)

        if action == "cancel" and is_requester and expense.status in (
            ExpenseRequest.Status.DRAFT,
            ExpenseRequest.Status.SUBMITTED,
        ):
            expense.status = ExpenseRequest.Status.CANCELLED
            expense.save(update_fields=["status", "updated_at"])
            messages.info(request, "Demande annulee.")
            return redirect("finance:expense_detail", pk=pk)

        if action == "validate":
            form = ExpenseValidationDecisionForm(request.POST)
            if form.is_valid():
                v = ExpenseValidation.objects.filter(
                    pk=form.cleaned_data["validation_id"], request=expense
                ).first()
                if v is None:
                    messages.error(request, "Validation introuvable.")
                elif v.role.code not in user_role_codes:
                    messages.error(request, f"Tu n'as pas le role {v.role.code} pour valider cette ligne.")
                elif v.decision != ExpenseValidation.Decision.PENDING:
                    messages.warning(request, "Cette ligne a deja ete signee.")
                else:
                    v.decision = form.cleaned_data["decision"]
                    v.comment = form.cleaned_data["comment"]
                    v.validator = request.user
                    v.save()
                    messages.success(request, f"Decision {v.get_decision_display()} enregistree pour {v.role.code}.")
                    # v.save() a declenche recompute_status() sur une autre
                    # instance ; on relit l'etat reel depuis la base.
                    expense.refresh_from_db()
                    # Notification a chaque signature : demandeur + autres
                    # valideurs sont informes de la progression.
                    notify_after_signature(expense, v)
                    if expense.status in (
                        ExpenseRequest.Status.APPROVED,
                        ExpenseRequest.Status.REJECTED,
                    ):
                        # Mail de cloture explicite (resultat final) en plus.
                        notify_requester_on_decision(expense)
            return redirect("finance:expense_detail", pk=pk)

        if action == "upload_document":
            doc_form = ExpenseDocumentForm(request.POST, request.FILES)
            if doc_form.is_valid():
                doc = doc_form.save(commit=False)
                doc.request = expense
                doc.uploaded_by = request.user
                doc.save()
                messages.success(request, f"Document '{doc.get_document_type_display()}' ajoute.")
            else:
                messages.error(request, "Document invalide : verifier le fichier et le type.")
            return redirect("finance:expense_detail", pk=pk)

        if action == "execute" and expense.status == ExpenseRequest.Status.APPROVED:
            # Restriction : seuls les valideurs RAF ou un comptable (= le requester
            # par convention v1) peuvent marquer l'execution.
            allowed = ("RAF" in user_role_codes) or is_requester
            if not allowed:
                messages.error(request, "Seul un RAF ou le demandeur peut marquer l'execution.")
                return redirect("finance:expense_detail", pk=pk)
            exec_form = ExpenseExecuteForm(request.POST)
            if exec_form.is_valid():
                expense.executed_bank_movement = exec_form.cleaned_data.get("bank_movement")
                expense.executed_cash_movement = exec_form.cleaned_data.get("cash_movement")
                expense.status = ExpenseRequest.Status.EXECUTED
                expense.executed_at = timezone.now()
                expense.save(update_fields=[
                    "executed_bank_movement", "executed_cash_movement",
                    "status", "executed_at", "updated_at",
                ])
                messages.success(request, "Demande marquee comme executee, lien avec le mouvement enregistre.")
            else:
                messages.error(request, "Lien execution invalide : choisir UN mouvement (bancaire OU caisse).")
            return redirect("finance:expense_detail", pk=pk)

    decision_forms = []
    for v in expense.validations.filter(**ACTIVE_DOMAIN):
        if v.decision == ExpenseValidation.Decision.PENDING and v.role.code in user_role_codes:
            decision_forms.append(
                (v, ExpenseValidationDecisionForm(initial={"validation_id": v.id}))
            )
        else:
            decision_forms.append((v, None))

    engageable_statuses = {
        ExpenseRequest.Status.APPROVED,
        ExpenseRequest.Status.ENGAGED,
        ExpenseRequest.Status.LIQUIDATED,
    }
    context = {
        "expense": expense,
        "decision_forms": decision_forms,
        "document_form": ExpenseDocumentForm(),
        "is_requester": is_requester,
        "user_role_codes": user_role_codes,
        # Habilite a agir sur les etapes engagement -> liquidation -> paiement.
        "can_execute": (
            expense.status in engageable_statuses
            and user_can_execute_expense(request.user, expense)
        ),
        "has_facture": expense.documents.filter(
            document_type="FACTURE", is_active=True, deleted_at__isnull=True,
        ).exists(),
    }
    return render(request, "finance/expense_detail.html", context)


@login_required
def expense_record_payment(request, pk):
    """Saisie comptable du paiement effectif d'une demande approuvee.

    Cree un BankMovement (ou CashMovement) directement depuis la demande,
    le lie a la demande, et fait basculer le statut en EXECUTED. Le signal
    finance.posting.post_bank_movement genere automatiquement l'ecriture
    de journal SYCEBNL en partie double.

    Verrous metier :
      - demande au statut APPROUVEE
      - au moins une piece justificative de type FACTURE attachee
      - utilisateur RAF/DP/SE/superuser, demandeur, ou comptable membre
        de l'equipe projet (cf. user_can_execute_expense)
    """

    expense = get_object_or_404(
        ExpenseRequest.objects.select_related("project", "budget_line", "requester"),
        pk=pk, **ACTIVE_DOMAIN,
    )

    if not user_can_execute_expense(request.user, expense):
        messages.error(request, "Vous n'etes pas habilite a saisir le paiement de cette demande.")
        return redirect("finance:expense_detail", pk=pk)

    if expense.status != ExpenseRequest.Status.APPROVED:
        messages.error(
            request,
            f"Le paiement ne peut etre saisi qu'apres approbation (statut actuel : {expense.get_status_display()}).",
        )
        return redirect("finance:expense_detail", pk=pk)

    has_facture = expense.documents.filter(
        document_type="FACTURE", is_active=True, deleted_at__isnull=True,
    ).exists()
    if not has_facture:
        messages.error(
            request,
            "Impossible de saisir le paiement : aucune facture definitive n'est attachee. "
            "Joindre d'abord la piece (type 'Facture definitive') sur la fiche demande.",
        )
        return redirect("finance:expense_detail", pk=pk)

    if request.method == "POST":
        form = RecordPaymentForm(request.POST, expense=expense)
        if form.is_valid():
            cd = form.cleaned_data
            if cd["method"] == "BANK":
                movement = BankMovement.objects.create(
                    account=cd["bank_account"],
                    date_operation=cd["date_operation"],
                    reference=cd["reference"],
                    label=expense.title,
                    debit=cd["actual_amount"],
                    credit=Decimal("0"),
                    project=expense.project,
                    budget_line=expense.budget_line,
                    contra_account=cd["contra_account"],
                    commentary=cd.get("commentary", ""),
                )
                expense.executed_bank_movement = movement
            else:
                movement = CashMovement.objects.create(
                    register=cd["cash_register"],
                    date_operation=cd["date_operation"],
                    label=expense.title,
                    debit=cd["actual_amount"],
                    credit=Decimal("0"),
                    project=expense.project,
                    budget_line=expense.budget_line,
                    contra_account=cd["contra_account"],
                    commentary=cd.get("commentary", ""),
                )
                expense.executed_cash_movement = movement

            expense.status = ExpenseRequest.Status.EXECUTED
            expense.executed_at = timezone.now()
            expense.save(update_fields=[
                "executed_bank_movement", "executed_cash_movement",
                "status", "executed_at", "updated_at",
            ])
            messages.success(
                request,
                f"Paiement de DD-{expense.id} saisi : {cd['actual_amount']} XOF, ref {cd['reference']}. "
                f"L'ecriture comptable a ete generee automatiquement.",
            )
            return redirect("finance:expense_detail", pk=pk)
    else:
        form = RecordPaymentForm(
            expense=expense,
            initial={
                "actual_amount": expense.requested_amount,
                "date_operation": timezone.now().date(),
            },
        )

    return render(
        request,
        "finance/expense_record_payment.html",
        {"expense": expense, "form": form},
    )


@login_required
def expense_engage(request, pk):
    """Engage une demande APPROUVEE (Option L) : cree le Commitment (reservation
    budgetaire) et fixe le fournisseur. NE POSTE AUCUNE ecriture de journal : la
    charge Dr 6x / Cr 401 naitra a la liquidation (attachement de la facture)."""
    expense = get_object_or_404(
        ExpenseRequest.objects.select_related("project", "budget_line"),
        pk=pk, **ACTIVE_DOMAIN,
    )
    if not user_can_execute_expense(request.user, expense):
        messages.error(request, "Vous n'etes pas habilite a engager cette demande.")
        return redirect("finance:expense_detail", pk=pk)
    if expense.status != ExpenseRequest.Status.APPROVED:
        messages.error(
            request,
            f"L'engagement n'est possible qu'apres approbation "
            f"(statut actuel : {expense.get_status_display()}).",
        )
        return redirect("finance:expense_detail", pk=pk)
    if expense.commitment_id:
        messages.info(request, "Cette demande est deja engagee.")
        return redirect("finance:expense_detail", pk=pk)

    if request.method == "POST":
        form = ExpenseEngageForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            with transaction.atomic():
                commitment = Commitment.objects.create(
                    budget_line=expense.budget_line,
                    commitment_number=f"ENG-DD{expense.id}",
                    commitment_type=Commitment.CommitmentType.DIRECT_PURCHASE,
                    supplier=cd["supplier"],
                    charge_account=cd.get("charge_account"),
                    amount=expense.requested_amount,
                    commitment_date=cd["commitment_date"],
                    description=expense.title,
                )
                expense.commitment = commitment
                expense.status = ExpenseRequest.Status.ENGAGED
                expense.save(update_fields=["commitment", "status", "updated_at"])
                # Reservation budgetaire (Engage). Aucune ecriture GL a ce stade.
                bl = expense.budget_line
                bl.committed_amount = (bl.committed_amount or Decimal("0")) + expense.requested_amount
                bl.save(update_fields=["committed_amount", "updated_at"])
            messages.success(
                request,
                f"Demande DD-{expense.id} engagee : budget reserve, fournisseur {cd['supplier']}. "
                "La charge sera constatee a l'attachement de la facture definitive.",
            )
            return redirect("finance:expense_detail", pk=pk)
    else:
        form = ExpenseEngageForm(initial={"commitment_date": timezone.now().date()})

    return render(request, "finance/expense_engage.html", {"expense": expense, "form": form})


@require_accounting_access
def general_ledger(request, code):
    """Grand livre d'un compte SYCEBNL : toutes ses ecritures, solde progressif."""

    account = get_object_or_404(ChartOfAccount, code=code, **ACTIVE_DOMAIN)

    lines = (
        JournalLine.objects.filter(account=account, **ACTIVE_DOMAIN)
        .select_related("entry", "entry__source_bank_movement", "entry__source_cash_movement")
        .order_by("entry__entry_date", "entry_id", "id")
    )

    rows = []
    running = Decimal("0")
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for line in lines:
        running += (line.debit or Decimal("0")) - (line.credit or Decimal("0"))
        total_debit += line.debit or Decimal("0")
        total_credit += line.credit or Decimal("0")
        rows.append({"line": line, "running_balance": running})

    context = {
        "account": account,
        "rows": rows,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "final_balance": running,
        "movement_count": len(rows),
    }
    return render(request, "finance/general_ledger.html", context)


@require_accounting_access
def trial_balance(request):
    """Balance generale SYCEBNL : par compte, total debit / credit / solde,
    groupee par classe."""

    aggregates = (
        JournalLine.objects.filter(**ACTIVE_DOMAIN)
        .values("account_id")
        .annotate(total_debit=Sum("debit"), total_credit=Sum("credit"))
    )
    agg_by_account = {
        row["account_id"]: (row["total_debit"] or Decimal("0"), row["total_credit"] or Decimal("0"))
        for row in aggregates
    }

    accounts = (
        ChartOfAccount.objects.filter(**ACTIVE_DOMAIN, id__in=agg_by_account.keys())
        .order_by("class_number", "code")
    )

    classes = OrderedDict()
    for cls_value, cls_label in ChartOfAccount.AccountClass.choices:
        classes[cls_value] = {"label": cls_label, "accounts": [], "total_debit": Decimal("0"), "total_credit": Decimal("0")}

    grand_debit = Decimal("0")
    grand_credit = Decimal("0")
    for account in accounts:
        td, tc = agg_by_account.get(account.id, (Decimal("0"), Decimal("0")))
        balance = td - tc
        # Defensif (cf. fix chart_of_accounts_view) : un compte avec une
        # class_number absente du enum (ex. nouvelle classe ajoutee plus tard)
        # ne doit pas crasher la balance generale.
        bucket = classes.setdefault(
            account.class_number,
            {
                "label": f"{account.class_number} - Classe inattendue",
                "accounts": [], "total_debit": Decimal("0"),
                "total_credit": Decimal("0"),
            },
        )
        bucket["accounts"].append(
            {
                "account": account,
                "total_debit": td,
                "total_credit": tc,
                "balance": balance,
                "balance_debit": balance if balance > 0 else Decimal("0"),
                "balance_credit": -balance if balance < 0 else Decimal("0"),
            }
        )
        bucket["total_debit"] += td
        bucket["total_credit"] += tc
        grand_debit += td
        grand_credit += tc

    context = {
        "classes": classes,
        "grand_debit": grand_debit,
        "grand_credit": grand_credit,
        "is_balanced": grand_debit == grand_credit,
    }
    return render(request, "finance/trial_balance.html", context)


def _account_balances():
    """Retourne {ChartOfAccount: solde_net} pour tous les comptes ayant des
    JournalLine. solde_net = total_debit - total_credit (positif = debiteur)."""
    rows = (
        JournalLine.objects.filter(**ACTIVE_DOMAIN)
        .values("account_id")
        .annotate(total_debit=Sum("debit"), total_credit=Sum("credit"))
    )
    balances = {}
    account_ids = [r["account_id"] for r in rows]
    accounts = {
        a.id: a
        for a in ChartOfAccount.objects.filter(id__in=account_ids).order_by("code")
    }
    for r in rows:
        acc = accounts.get(r["account_id"])
        if acc is None:
            continue
        net = (r["total_debit"] or Decimal("0")) - (r["total_credit"] or Decimal("0"))
        balances[acc] = {
            "debit": r["total_debit"] or Decimal("0"),
            "credit": r["total_credit"] or Decimal("0"),
            "net": net,
        }
    return balances


@require_accounting_access
def income_statement(request):
    """Compte d'exploitation SYCEBNL EVE (modele officiel REF RA -> XE)."""
    from apps.finance.financial_statements_sycebnl import (
        compute_income_statement,
    )

    lines = compute_income_statement()

    # Indicateurs synthese pour le hero
    def _amt(ref):
        for line in lines:
            if line["ref"] == ref:
                return line["amount"]
        return Decimal("0")

    total_produits = _amt("XA")
    total_charges = _amt("XB")
    result_activities = _amt("XC")
    result_hao = _amt("XD")
    result_exercise = _amt("XE")

    context = {
        "lines": lines,
        "total_produits": total_produits,
        "total_charges": total_charges,
        "result_activities": result_activities,
        "result_hao": result_hao,
        "result_exercise": result_exercise,
        "is_profit": result_exercise >= 0,
        "has_data": any(line["amount"] != Decimal("0") for line in lines),
    }
    return render(request, "finance/income_statement.html", context)


@require_accounting_access
def balance_sheet(request):
    """Bilan SYCEBNL EVE (modele officiel REF AA -> DZ).

    Affiche cote a cote l'Actif (REF AA -> BZ) et le Passif (REF CA -> DZ)
    conformes au modele XLSX livre par EVE.
    """
    from apps.finance.financial_statements_sycebnl import (
        compute_balance_sheet_asset,
        compute_balance_sheet_liability,
    )

    actif_lines = compute_balance_sheet_asset()
    passif_lines = compute_balance_sheet_liability()

    def _amt(lines, ref):
        for line in lines:
            if line["ref"] == ref:
                return line["amount"]
        return Decimal("0")

    total_actif = _amt(actif_lines, "BZ")
    total_passif = _amt(passif_lines, "DZ")
    result_exercise = _amt(passif_lines, "CH")
    is_balanced = total_actif == total_passif

    context = {
        "actif_lines": actif_lines,
        "passif_lines": passif_lines,
        "total_actif": total_actif,
        "total_passif": total_passif,
        "result_exercise": result_exercise,
        "is_profit": result_exercise >= 0,
        "is_balanced": is_balanced,
        "imbalance": total_actif - total_passif,
        "has_data": any(line["amount"] != Decimal("0") for line in actif_lines + passif_lines),
    }
    return render(request, "finance/balance_sheet.html", context)


@require_accounting_access
def cash_flow_statement(request):
    """Tableau des Flux de Tresorerie SYCEBNL EVE (REF FA -> ZH).

    Calcul approximatif : sans separation explicite des mouvements de la
    periode, le TFT est base sur les soldes debit/credit cumules. Pour un
    TFT annuel precis, filtrer JournalLine par exercice fiscal.
    """
    from apps.finance.financial_statements_sycebnl import (
        compute_cash_flow_statement,
        account_balances,
    )

    balances = account_balances()
    # Tresorerie d'ouverture = solde des comptes 5x debiteurs au 1er janvier
    # Approximation : on prend 0 pour l'instant (a affiner avec un parametre
    # exercice et la lecture des a-nouveaux).
    opening = Decimal("0")
    for code, data in balances.items():
        if code.startswith("1101") or code.startswith("1211"):
            # Report a nouveau : approximation du solde anterieur
            pass  # TODO affiner

    tft = compute_cash_flow_statement(opening_treasury=opening)

    context = {
        "tft": tft,
        "opening_treasury": tft["opening_treasury"],
        "closing_treasury": tft["ZH"],
        "variation": tft["variation"],
        "has_data": any(line["amount"] != Decimal("0") for line in tft["lines"]),
    }
    return render(request, "finance/cash_flow_statement.html", context)


@login_required
def cash_movement_create(request):
    """Saisie rapide d'une operation de caisse avec piece justificative.

    Acces : utilisateurs ayant acces BG (Assistante RAF, RAF, DP, SE,
    superuser). L'ARAF (Amy) utilise cette vue au quotidien pour saisir
    les petites depenses (transport, carburant, restauration, etc.) et
    les recharges de caisse provenant des comptes bancaires (BG ou projet).
    """
    if not can_see_bg(request.user):
        return render(
            request, "accounts/access_denied.html",
            {"message": "Acces reserve aux gestionnaires de caisse (Assistante RAF, RAF, DP, SE)."},
            status=403,
        )

    from apps.finance.models import CashMovement
    from django.core.exceptions import ValidationError

    if request.method == "POST":
        form = CashMovementQuickForm(request.POST, request.FILES)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                m = CashMovement(
                    register=cd["register"],
                    date_operation=cd["date_operation"],
                    label=cd["label"],
                    debit=cd["amount"] if cd["operation"] == "DEBIT" else Decimal("0"),
                    credit=cd["amount"] if cd["operation"] == "CREDIT" else Decimal("0"),
                    budget_line=cd.get("budget_line"),
                    project=cd.get("project"),
                    contra_account=cd["contra_account"],
                    recipient=cd.get("recipient", ""),
                    commentary=cd.get("commentary", ""),
                    created_by=request.user,
                )
                if cd.get("justification"):
                    m.justification = cd["justification"]
                # Plafonds caisse SYCEBNL : la validation full_clean() applique
                # 40 000 par operation, 200 000 par semaine ISO.
                m.full_clean()
                m.save()
                messages.success(
                    request,
                    f"Operation caisse enregistree : {cd['operation']} {cd['amount']} XOF sur {cd['register'].name}. "
                    f"L'ecriture comptable est generee automatiquement.",
                )
                return redirect("finance:dashboard")
            except ValidationError as ve:
                # Plafond depasse ou autre regle metier.
                for field, errs in ve.message_dict.items() if hasattr(ve, "message_dict") else [("__all__", ve.messages)]:
                    for e in errs:
                        form.add_error(None, e)
    else:
        form = CashMovementQuickForm(initial={
            "date_operation": timezone.now().date(),
        })

    return render(request, "finance/cash_movement_create.html", {"form": form})


@login_required
def bank_movement_create(request):
    """Saisie directe d'un mouvement bancaire par le comptable projet.

    Acces : superuser, RAF/DP/SE OU comptable d'un ProjectTeam (cas SAKHO).
    Le mouvement saisi est aussitot post-traité par le signal de finance.posting,
    qui genere automatiquement l'ecriture en partie double SYCEBNL.

    Permet la saisie back-datee a partir du 1er janvier 2026 pour le
    rattrapage des releves bancaires.
    """
    if not user_can_record_bank_movements(request.user):
        return render(
            request, "accounts/access_denied.html",
            {"message": "Acces reserve aux comptables (membres ProjectTeam rôle Comptable) et a la Direction."},
            status=403,
        )

    from apps.finance.models import BankMovement
    from django.core.exceptions import ValidationError

    if request.method == "POST":
        form = BankMovementQuickForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                # Parse les allocations multi-lignes envoyees par le formulaire :
                # POST contient alloc_contra_0, alloc_amount_0, alloc_project_0,
                # alloc_budget_line_0, alloc_desc_0 ... pour chaque ligne.
                from apps.finance.models import (
                    BankMovementAllocation, BankMovementDocument, ChartOfAccount,
                    BudgetLine,
                )
                from apps.projects.models import Project as _Project

                allocations_data = []
                idx = 0
                while True:
                    contra_code = request.POST.get(f"alloc_contra_{idx}", "").strip()
                    amount_s = request.POST.get(f"alloc_amount_{idx}", "").strip().replace(" ", "").replace(",", ".")
                    if not contra_code and not amount_s:
                        break  # plus de ligne suivante
                    if contra_code and amount_s:
                        contra = ChartOfAccount.objects.filter(code=contra_code, is_active=True, deleted_at__isnull=True).first()
                        try:
                            amount = Decimal(amount_s)
                        except Exception:
                            amount = None
                        if contra and amount and amount > 0:
                            project_id = request.POST.get(f"alloc_project_{idx}", "").strip() or None
                            budget_line_id = request.POST.get(f"alloc_budget_line_{idx}", "").strip() or None
                            desc = request.POST.get(f"alloc_desc_{idx}", "").strip()
                            allocations_data.append({
                                "contra": contra, "amount": amount,
                                "project_id": int(project_id) if project_id else None,
                                "budget_line_id": int(budget_line_id) if budget_line_id else None,
                                "desc": desc,
                            })
                    idx += 1
                    if idx > 50:  # garde-fou
                        break

                # Verifie la coherence si on a des allocations
                if allocations_data:
                    alloc_total = sum(a["amount"] for a in allocations_data)
                    if alloc_total != cd["amount"]:
                        form.add_error(None,
                            f"La somme des ventilations ({alloc_total}) doit egaler le montant total ({cd['amount']})."
                        )
                        raise ValidationError("ventilation incoherente")

                m = BankMovement(
                    account=cd["account"],
                    date_operation=cd["date_operation"],
                    reference=cd.get("reference", "") or "",
                    label=cd["label"],
                    debit=cd["amount"] if cd["operation"] == "DEBIT" else Decimal("0"),
                    credit=cd["amount"] if cd["operation"] == "CREDIT" else Decimal("0"),
                    project=cd.get("project"),
                    budget_line=cd.get("budget_line"),
                    # Si pas d'allocations : on garde le contra_account du form
                    contra_account=cd["contra_account"] if not allocations_data else None,
                    recipient=cd.get("recipient", ""),
                    commentary=cd.get("commentary", ""),
                    created_by=request.user,
                )
                if cd.get("justification"):
                    m.justification = cd["justification"]
                m.full_clean()
                m.save()

                # Cree les allocations
                for a in allocations_data:
                    BankMovementAllocation.objects.create(
                        movement=m,
                        project_id=a["project_id"],
                        budget_line_id=a["budget_line_id"],
                        contra_account=a["contra"],
                        amount=a["amount"],
                        description=a["desc"],
                        created_by=request.user,
                    )

                # Cree les documents multi-fichiers (input names: docs_files / docs_types / docs_labels en liste)
                files_list = request.FILES.getlist("docs_files")
                types_list = request.POST.getlist("docs_types")
                labels_list = request.POST.getlist("docs_labels")
                for i, f in enumerate(files_list):
                    if not f:
                        continue
                    doc_type = types_list[i] if i < len(types_list) else "AUTRE"
                    doc_label = labels_list[i] if i < len(labels_list) else ""
                    BankMovementDocument.objects.create(
                        movement=m, document_type=doc_type, file=f,
                        label=doc_label, created_by=request.user,
                    )

                # Si on a cree des allocations apres le save (le signal n'a pas
                # vu les allocations a son passage), regenerate l'ecriture comptable.
                if allocations_data:
                    from apps.finance.posting import post_bank_movement
                    post_bank_movement(m, regenerate=True)

                op_label = "Depense" if cd["operation"] == "DEBIT" else "Recette"
                ventilation_msg = ""
                if allocations_data:
                    ventilation_msg = f" Ventilation sur {len(allocations_data)} lignes comptables."
                docs_msg = ""
                if files_list:
                    docs_msg = f" {len([f for f in files_list if f])} piece(s) jointe(s)."
                messages.success(
                    request,
                    f"{op_label} bancaire enregistree : {cd['amount']} XOF sur {cd['account'].name} le {cd['date_operation']}.{ventilation_msg}{docs_msg}",
                )
                return redirect("finance:dashboard")
            except ValidationError as ve:
                msg_dict = getattr(ve, "message_dict", None)
                if msg_dict:
                    for field, errs in msg_dict.items():
                        for e in errs:
                            form.add_error(None, e)
                else:
                    for e in getattr(ve, "messages", []):
                        form.add_error(None, e)
    else:
        form = BankMovementQuickForm(
            user=request.user,
            initial={"date_operation": timezone.now().date()},
        )

    # Liste des comptes SYCEBNL classes 6 et 7 pour le selecteur de ventilation
    from apps.finance.models import ChartOfAccount as _Chart, BudgetLine as _BL
    chart_accounts_for_split = list(
        _Chart.objects.filter(
            is_active=True, deleted_at__isnull=True, class_number__in=[6, 7]
        ).order_by("code").values("code", "name")
    )

    # Donnees pre-rendues pour filtrage JS Rubrique/Ligne par projet :
    # - chaque rubrique connait les projets ou elle a au moins une BudgetLine
    # - chaque BudgetLine connait son project_id et son category_id
    acc_proj_ids = accessible_project_ids(request.user)
    bl_filter = Q(is_active=True, deleted_at__isnull=True)
    if acc_proj_ids is not None:
        bl_scope = Q(project_id__in=acc_proj_ids)
        if can_see_bg(request.user):
            bl_scope |= Q(project__isnull=True)
        bl_filter &= bl_scope

    bl_rows = list(
        _BL.objects.filter(bl_filter)
        .select_related("project", "category")
        .order_by("project__code", "category__code", "code")
        .values("id", "code", "description", "project_id", "category_id", "planned_amount")
    )
    # Pour chaque category, set des project_ids ou elle a une BudgetLine
    from collections import defaultdict
    cat_to_projects = defaultdict(set)
    for r in bl_rows:
        cat_to_projects[r["category_id"]].add(r["project_id"] or 0)  # 0 = BG (project null)
    rubriques_data = [
        {
            "id": c.id, "code": c.code, "name": c.name,
            "projects": ",".join(str(p) for p in sorted(cat_to_projects.get(c.id, set()))),
        }
        for c in form.fields["budget_category"].queryset.order_by("code")
    ]
    budget_lines_data = [
        {
            "id": r["id"], "code": r["code"], "description": r["description"][:60],
            "project_id": r["project_id"] or 0,
            "category_id": r["category_id"],
            "amount": str(r["planned_amount"]),
        }
        for r in bl_rows
    ]

    return render(request, "finance/bank_movement_create.html", {
        "form": form,
        "chart_accounts_for_split": chart_accounts_for_split,
        "rubriques_data": rubriques_data,
        "budget_lines_data": budget_lines_data,
    })


@login_required
def bank_statement_upload(request):
    """Etape 1 : upload d'un PDF de releve bancaire + selection du compte."""
    if not user_can_record_bank_movements(request.user):
        return render(
            request, "accounts/access_denied.html",
            {"message": "Acces reserve aux comptables et a la Direction."},
            status=403,
        )

    from apps.finance.models import BankStatementImport
    from apps.finance.statement_parser import parse_statement
    from apps.finance.imputation_rules import suggest_contra_account

    # Comptes bancaires accessibles
    bank_qs = BankAccount.objects.filter(**ACTIVE_DOMAIN).order_by("name")
    bank_ids = accessible_bank_account_ids(request.user)
    if bank_ids is not None:
        bank_qs = bank_qs.filter(id__in=bank_ids)

    if request.method == "POST":
        account_id = request.POST.get("account")
        pdf_file = request.FILES.get("pdf_file")
        if not account_id or not pdf_file:
            messages.error(request, "Compte bancaire et fichier PDF sont obligatoires.")
            return redirect("finance:bank_statement_upload")
        try:
            account = bank_qs.get(id=account_id)
        except BankAccount.DoesNotExist:
            messages.error(request, "Compte bancaire non accessible.")
            return redirect("finance:bank_statement_upload")

        from apps.finance.statement_parser import ScannedPDFError
        try:
            parsed = parse_statement(pdf_file)
        except ScannedPDFError as e:
            # PDF scanne : message detaille, pas de brouillon cree
            messages.error(request, str(e))
            return redirect("finance:bank_statement_upload")
        except Exception as e:
            messages.error(request, f"Echec de l'extraction PDF : {type(e).__name__}: {e}.")
            return redirect("finance:bank_statement_upload")

        # Si parsing reussi mais 0 ligne extraite, on previent aussi
        if not parsed:
            messages.warning(
                request,
                "PDF analyse mais aucune ligne de mouvement detectee. "
                "Le format de ce releve n'est peut-etre pas reconnu par notre parser. "
                "Saisissez les mouvements manuellement via 'Saisir un mouvement bancaire'."
            )
            return redirect("finance:bank_statement_upload")

        # Enrichissement : ajoute suggestions de compte contrepartie
        for line in parsed:
            code, hint = suggest_contra_account(line.get("label", ""))
            line["suggested_contra_code"] = code or ""
            line["suggested_contra_hint"] = hint
            line["keep"] = True  # par defaut conserve

        pdf_file.seek(0)
        draft = BankStatementImport.objects.create(
            account=account,
            source_file=pdf_file,
            status=BankStatementImport.Status.DRAFT,
            parsed_lines=parsed,
            nb_lines_parsed=len(parsed),
            submitted_by=request.user,
            created_by=request.user,
        )
        messages.success(
            request,
            f"PDF analyse : {len(parsed)} ligne(s) extraite(s). Revoir les imputations ci-dessous avant validation.",
        )
        return redirect("finance:bank_statement_review", pk=draft.id)

    # Liste des derniers brouillons en cours
    recent_drafts = (
        BankStatementImport.objects.filter(**ACTIVE_DOMAIN)
        .select_related("account", "submitted_by")
        .order_by("-created_at")
    )
    if bank_ids is not None:
        recent_drafts = recent_drafts.filter(account_id__in=bank_ids)
    recent_drafts = recent_drafts[:10]

    return render(request, "finance/bank_statement_upload.html", {
        "bank_accounts": bank_qs,
        "recent_drafts": recent_drafts,
    })


@login_required
def bank_statement_review(request, pk):
    """Etape 2 : revue + edition des lignes auto-suggerees + validation finale."""
    if not user_can_record_bank_movements(request.user):
        return render(
            request, "accounts/access_denied.html",
            {"message": "Acces reserve aux comptables et a la Direction."},
            status=403,
        )

    from apps.finance.models import BankMovement, BankStatementImport, ChartOfAccount

    draft = get_object_or_404(BankStatementImport, pk=pk, **ACTIVE_DOMAIN)
    # Verifie acces au compte
    bank_ids = accessible_bank_account_ids(request.user)
    if bank_ids is not None and draft.account_id not in bank_ids:
        raise Http404("Brouillon non accessible.")

    # Tous les comptes SYCEBNL actifs pour le selecteur de contrepartie
    chart_accounts = list(
        ChartOfAccount.objects.filter(**ACTIVE_DOMAIN).order_by("code")
        .values("code", "name")
    )

    if request.method == "POST":
        if draft.status != BankStatementImport.Status.DRAFT:
            messages.error(request, "Ce brouillon a deja ete traite.")
            return redirect("finance:bank_statement_review", pk=pk)

        # Lecture des modifications par ligne. Index forme par parsed_lines order.
        from decimal import Decimal as _Dec
        from datetime import datetime

        created, skipped, errors = 0, 0, 0
        for i, line in enumerate(draft.parsed_lines):
            if request.POST.get(f"keep_{i}") != "on":
                skipped += 1
                continue
            contra_code = request.POST.get(f"contra_{i}", "").strip()
            label = request.POST.get(f"label_{i}", "").strip()
            date_s = request.POST.get(f"date_{i}", "").strip()
            debit_s = request.POST.get(f"debit_{i}", "").strip().replace(" ", "").replace(",", ".")
            credit_s = request.POST.get(f"credit_{i}", "").strip().replace(" ", "").replace(",", ".")
            ref = request.POST.get(f"ref_{i}", "").strip()

            if not contra_code or not label or not date_s:
                errors += 1
                continue
            try:
                date_op = datetime.strptime(date_s, "%Y-%m-%d").date()
            except ValueError:
                errors += 1
                continue
            try:
                debit = _Dec(debit_s) if debit_s else _Dec("0")
                credit = _Dec(credit_s) if credit_s else _Dec("0")
            except Exception:
                errors += 1
                continue
            if debit == 0 and credit == 0:
                errors += 1
                continue

            contra = ChartOfAccount.objects.filter(code=contra_code, **ACTIVE_DOMAIN).first()
            if not contra:
                errors += 1
                continue

            try:
                m = BankMovement(
                    account=draft.account,
                    date_operation=date_op,
                    reference=ref or "",
                    label=label[:300],
                    debit=debit, credit=credit,
                    contra_account=contra,
                    commentary=f"Import en lot via assistant (brouillon #{draft.id} ligne #{i+1})",
                    created_by=request.user,
                )
                m.save()
                created += 1
            except Exception:
                errors += 1

        draft.status = BankStatementImport.Status.IMPORTED
        draft.nb_lines_imported = created
        draft.imported_at = timezone.now()
        draft.save(update_fields=["status", "nb_lines_imported", "imported_at", "updated_at"])

        msg = f"Import termine : {created} mouvement(s) cree(s), {skipped} ignore(s), {errors} erreur(s)."
        if errors:
            messages.warning(request, msg)
        else:
            messages.success(request, msg)
        return redirect("finance:bank_account", public_uuid=draft.account.public_uuid)

    return render(request, "finance/bank_statement_review.html", {
        "draft": draft,
        "chart_accounts": chart_accounts,
    })


@login_required
def bank_movement_delete(request, pk):
    """Annule (soft-delete) un mouvement bancaire saisi par erreur.

    Soft-delete le BankMovement, ses allocations, ses documents et son
    JournalEntry. Les lignes n'apparaissent plus ni dans le grand livre,
    ni dans la balance, ni dans le bilan ou le compte de resultat.

    Le mouvement reste en base avec is_active=False et deleted_at=now pour
    la piste d'audit (administrateur peut le restaurer via /admin/ si
    necessaire).

    Reservation : utilisateurs habilites a saisir des mouvements bancaires
    (RAF, DP, SE, ARAF, comptables ProjectTeam).
    """
    if not user_can_record_bank_movements(request.user):
        return render(
            request, "accounts/access_denied.html",
            {"message": "Acces reserve aux comptables et a la Direction."},
            status=403,
        )

    from apps.finance.models import BankMovement, JournalEntry, JournalLine

    movement = get_object_or_404(BankMovement, pk=pk, **ACTIVE_DOMAIN)
    bank_ids = accessible_bank_account_ids(request.user)
    if bank_ids is not None and movement.account_id not in bank_ids:
        raise Http404("Mouvement non accessible.")

    if request.method != "POST":
        return redirect("finance:bank_account", public_uuid=movement.account.public_uuid)

    # Soft-delete cascade : JournalEntry, JournalLines, allocations, documents
    now = timezone.now()
    entry = JournalEntry.objects.filter(source_bank_movement=movement).first()
    if entry:
        JournalLine.objects.filter(entry=entry).update(is_active=False, deleted_at=now)
        entry.soft_delete()

    movement.allocations.all().update(is_active=False, deleted_at=now)
    movement.documents.all().update(is_active=False, deleted_at=now)
    movement.soft_delete()

    amount = movement.credit if movement.credit else movement.debit
    messages.success(
        request,
        f"Mouvement annule : {movement.label[:60]} ({amount} XOF). "
        f"L'ecriture comptable a ete retiree de la balance et du bilan. "
        f"Vous pouvez maintenant ressaisir la valeur correcte si besoin.",
    )
    return redirect("finance:bank_account", public_uuid=movement.account.public_uuid)


def _user_can_view_bank_account(user, account):
    """Regle d'acces a un compte bancaire (lecture) : vue globale OU lien a
    un projet accessible OU compte BG avec droit BG. Identique a la logique
    de bank_account_detail."""
    if can_see_everything(user):
        return True
    acc_ids = accessible_project_ids(user) or set()
    linked_ids = set(account.projects.values_list("id", flat=True))
    is_bg_account = not linked_ids
    has_overlap = bool(linked_ids & acc_ids)
    has_bg_pass = is_bg_account and can_see_bg(user)
    return has_overlap or has_bg_pass


def _voucher_data(request, pk):
    """Charge un BankMovement et tout ce qu'il faut pour rendre sa piece
    comptable (ecriture partie double, ventilations, pieces). Applique le
    controle d'acces lecture. Leve Http404 si non accessible."""
    from apps.finance.models import BankMovement, JournalEntry

    movement = get_object_or_404(
        BankMovement.objects.select_related(
            "account", "project", "budget_line", "contra_account", "cashflow_entry",
        ),
        pk=pk, **ACTIVE_DOMAIN,
    )
    if not _user_can_view_bank_account(request.user, movement.account):
        raise Http404("Mouvement non accessible.")

    entry = (
        JournalEntry.objects.filter(source_bank_movement=movement, **ACTIVE_DOMAIN)
        .prefetch_related("lines__account")
        .first()
    )
    journal_lines = (
        list(entry.lines.filter(**ACTIVE_DOMAIN).select_related("account"))
        if entry else []
    )
    allocations = list(
        movement.allocations.filter(**ACTIVE_DOMAIN)
        .select_related("project", "budget_line", "contra_account")
    )
    documents = list(movement.documents.filter(**ACTIVE_DOMAIN))

    total_debit = sum((l.debit or Decimal("0")) for l in journal_lines)
    total_credit = sum((l.credit or Decimal("0")) for l in journal_lines)

    return {
        "movement": movement,
        "account": movement.account,
        "entry": entry,
        "journal_lines": journal_lines,
        "allocations": allocations,
        "documents": documents,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "amount": movement.credit if movement.credit else movement.debit,
        "is_credit": bool(movement.credit),
        "piece_ref": entry.reference if entry else f"BM-{movement.id}",
    }


@login_required
def bank_movement_detail(request, pk):
    """Fiche detaillee d'un mouvement bancaire : imputation comptable (partie
    double), ventilations, pieces justificatives, et EDITION CONTROLEE.

    Edition controlee (conformite piste d'audit SYCEBNL) : seuls les champs
    non financiers (libelle, beneficiaire, reference, commentaire) sont
    modifiables, et les pieces peuvent etre ajoutees apres coup. Toute
    correction de montant / date / sens / imputation passe par l'annulation
    (extourne) puis une nouvelle saisie.
    """
    from apps.finance.forms import BankMovementDocumentForm, BankMovementEditForm
    from apps.finance.models import BankMovement

    movement = get_object_or_404(
        BankMovement.objects.select_related(
            "account", "project", "budget_line", "contra_account", "cashflow_entry",
        ),
        pk=pk, **ACTIVE_DOMAIN,
    )
    if not _user_can_view_bank_account(request.user, movement.account):
        raise Http404("Mouvement non accessible.")

    can_edit = user_can_record_bank_movements(request.user)
    if can_edit:
        bank_ids = accessible_bank_account_ids(request.user)
        if bank_ids is not None and movement.account_id not in bank_ids:
            can_edit = False

    edit_form = None
    doc_form = None

    if request.method == "POST":
        if not can_edit:
            return render(
                request, "accounts/access_denied.html",
                {"message": "Acces reserve aux comptables et a la Direction."},
                status=403,
            )
        action = request.POST.get("action")
        if action == "edit_meta":
            edit_form = BankMovementEditForm(request.POST, instance=movement)
            if edit_form.is_valid():
                m = edit_form.save(commit=False)
                m.updated_by = request.user
                m.save(update_fields=[
                    "label", "recipient", "reference", "commentary",
                    "updated_by", "updated_at",
                ])
                # Resynchronise l'ecriture comptable (libelle/reference) sans
                # toucher aux montants : regeneration deterministe a partir des
                # memes donnees financieres (inchangees).
                from apps.finance.posting import post_bank_movement
                post_bank_movement(m, regenerate=True)
                messages.success(
                    request,
                    "Mouvement mis a jour (champs non financiers). Montant, "
                    "date et imputation inchanges.",
                )
                return redirect("finance:bank_movement_detail", pk=movement.pk)
        elif action == "add_document":
            doc_form = BankMovementDocumentForm(request.POST, request.FILES)
            if doc_form.is_valid():
                doc = doc_form.save(commit=False)
                doc.movement = movement
                doc.created_by = request.user
                doc.save()
                messages.success(request, "Piece justificative ajoutee.")
                return redirect("finance:bank_movement_detail", pk=movement.pk)

    if edit_form is None:
        edit_form = BankMovementEditForm(instance=movement)
    if doc_form is None:
        doc_form = BankMovementDocumentForm()

    context = _voucher_data(request, pk)
    context.update({
        "edit_form": edit_form,
        "doc_form": doc_form,
        "can_edit": can_edit,
    })
    return render(request, "finance/bank_movement_detail.html", context)


@login_required
def bank_movement_voucher(request, pk):
    """Piece comptable imprimable (HTML) d'un mouvement bancaire, avec la
    liste de ses annexes. Impression vers PDF via le navigateur (Ctrl+P)."""
    context = _voucher_data(request, pk)
    return render(request, "finance/bank_movement_voucher.html", context)


@login_required
def bank_movement_voucher_pdf(request, pk):
    """Genere un PDF unique : la piece comptable suivie de ses annexes
    (justificatifs PDF concatenes, images converties en pages). Les annexes
    non fusionnables (ex: .docx) sont signalees sur une page recapitulative."""
    from django.http import HttpResponse
    from apps.finance.voucher_pdf import build_voucher_pdf

    context = _voucher_data(request, pk)
    pdf_bytes = build_voucher_pdf(context)
    filename = f"piece_{context['piece_ref']}.pdf".replace("/", "-").replace(" ", "_")
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@login_required
def bank_statement_delete(request, pk):
    """Soft-delete d'un brouillon d'import de releve.

    Reserve aux utilisateurs habilites a saisir des mouvements bancaires
    (RAF, DP, SE, ARAF, comptables). Un brouillon deja importe peut etre
    supprime (les BankMovement crees restent intacts) - cela ne fait que
    cacher le brouillon de la liste 'Imports recents'.
    """
    if not user_can_record_bank_movements(request.user):
        return render(
            request, "accounts/access_denied.html",
            {"message": "Acces reserve aux comptables et a la Direction."},
            status=403,
        )

    from apps.finance.models import BankStatementImport
    draft = get_object_or_404(BankStatementImport, pk=pk, **ACTIVE_DOMAIN)
    bank_ids = accessible_bank_account_ids(request.user)
    if bank_ids is not None and draft.account_id not in bank_ids:
        raise Http404("Brouillon non accessible.")

    if request.method != "POST":
        return redirect("finance:bank_statement_upload")

    draft.soft_delete()
    messages.success(
        request,
        f"Brouillon supprime ({draft.account.name}, {draft.created_at:%d/%m/%Y %H:%M}).",
    )
    return redirect("finance:bank_statement_upload")


@login_required
def bank_account_detail(request, public_uuid):
    """Detail d'un compte bancaire : projets rattaches, snapshots de solde,
    mouvements bancaires (BankMovement) saisis pour ce compte."""

    account = get_object_or_404(
        BankAccount.objects.prefetch_related("projects", "snapshots", "movements"),
        public_uuid=public_uuid,
        **ACTIVE_DOMAIN,
    )

    # Acces : un compte bancaire est accessible si l'utilisateur a un acces
    # global OU s'il est lie a au moins un de ses projets OU si c'est un
    # compte BG (sans projet) et l'utilisateur a acces BG.
    if not can_see_everything(request.user):
        acc_ids = accessible_project_ids(request.user) or set()
        linked_ids = set(account.projects.values_list("id", flat=True))
        is_bg_account = not linked_ids
        has_overlap = bool(linked_ids & acc_ids)
        has_bg_pass = is_bg_account and can_see_bg(request.user)
        if not (has_overlap or has_bg_pass):
            raise Http404("Compte bancaire non accessible.")

    snapshots = account.snapshots.filter(**ACTIVE_DOMAIN).order_by("-date")
    # Mouvements ordonnes chronologiquement croissants pour calculer le solde
    # progressif puis inverses pour l'affichage.
    movements_asc = list(
        account.movements.filter(**ACTIVE_DOMAIN)
        .select_related("project", "cashflow_entry")
        .annotate(doc_count=Count(
            "documents",
            filter=Q(documents__is_active=True, documents__deleted_at__isnull=True),
        ))
        .order_by("date_operation", "id")
    )
    opening = account.opening_balance or Decimal("0")
    running = opening
    for m in movements_asc:
        running += (m.credit or Decimal("0")) - (m.debit or Decimal("0"))
        m.computed_balance = running  # attribut Python ad-hoc
    final_balance = running

    movements = list(reversed(movements_asc))  # plus recent d'abord pour affichage
    total_debit = sum((m.debit or Decimal("0")) for m in movements_asc)
    total_credit = sum((m.credit or Decimal("0")) for m in movements_asc)

    projects = account.projects.filter(**ACTIVE_DOMAIN).order_by("code")

    context = {
        "account": account,
        "projects": projects,
        "snapshots": snapshots,
        "movements": movements,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "net_movement": total_credit - total_debit,
        "opening_balance": opening,
        "computed_balance": final_balance,
        "can_record_bank": user_can_record_bank_movements(request.user),
    }
    return render(request, "finance/bank_account_detail.html", context)
