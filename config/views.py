from decimal import Decimal

from django.db.models import Count, Sum
from django.shortcuts import render

from apps.common.reference_snapshots import RH_REFERENCE_SNAPSHOT
from apps.hr.models import Employee, Leave
from apps.hr.models import WorkforceSnapshot
from apps.projects.models import Project
from apps.activities.models import Activity
from apps.finance.models import BudgetLine
from apps.reporting.models import Report


def home(request):
    employees = Employee.objects.filter(is_active=True, deleted_at__isnull=True)
    projects = Project.objects.filter(is_active=True, deleted_at__isnull=True).select_related("primary_donor", "project_manager")
    activities = Activity.objects.filter(is_active=True, deleted_at__isnull=True).select_related("project", "responsible")
    budget_lines = BudgetLine.objects.filter(is_active=True, deleted_at__isnull=True).select_related("project", "category")
    reports = Report.objects.filter(is_active=True, deleted_at__isnull=True).select_related("template", "project")

    total_budget = budget_lines.aggregate(total=Sum("planned_amount"))["total"] or Decimal("0")
    total_committed = budget_lines.aggregate(total=Sum("committed_amount"))["total"] or Decimal("0")
    total_disbursed = budget_lines.aggregate(total=Sum("disbursed_amount"))["total"] or Decimal("0")

    status_counts = projects.values("status").annotate(total=Count("id"))
    project_status_map = {item["status"]: item["total"] for item in status_counts}

    priority_projects = projects.order_by("-progress_percentage", "code")[:3]
    recent_activities = activities.order_by("-planned_start_date", "-created_at")[:4]
    latest_reports = reports.order_by("-created_at")[:3]
    top_budget_lines = budget_lines.order_by("-planned_amount")[:4]
    latest_snapshot = (
        WorkforceSnapshot.objects.filter(is_active=True, deleted_at__isnull=True)
        .prefetch_related("geographies")
        .order_by("-source_date")
        .first()
    )

    if latest_snapshot:
        rh_reference = {
            "title": latest_snapshot.title,
            "scope": latest_snapshot.scope,
            "source_date": latest_snapshot.source_date,
            "staff": {
                "salaried_and_contractual": latest_snapshot.salaried_and_contractual_count,
                "service_providers": latest_snapshot.service_provider_count,
                "consultants": latest_snapshot.consultant_count,
                "detailed_total_listed": latest_snapshot.detailed_total_staff,
                "reported_summary_total": latest_snapshot.reported_total_staff,
                "has_total_discrepancy": latest_snapshot.reported_total_staff != latest_snapshot.detailed_total_staff,
            },
            "community": {
                "relay_workers": latest_snapshot.relay_worker_count,
                "icp": latest_snapshot.icp_count,
                "health_posts": latest_snapshot.health_post_count,
                "companions": latest_snapshot.companion_count,
                "community_supervisors": latest_snapshot.community_supervisor_count,
                "regions": latest_snapshot.covered_regions_count,
                "total_actors": (
                    latest_snapshot.relay_worker_count
                    + latest_snapshot.icp_count
                    + latest_snapshot.health_post_count
                    + latest_snapshot.companion_count
                    + latest_snapshot.community_supervisor_count
                ),
            },
            "geographies": [
                {
                    "label": geography.label,
                    "relay_workers": geography.relay_worker_count,
                    "support_structures": geography.support_structures,
                    "beneficiaries": geography.beneficiary_scope,
                }
                for geography in latest_snapshot.geographies.all()
            ],
        }
    else:
        rh_reference = RH_REFERENCE_SNAPSHOT

    rh_reference_staff = rh_reference["staff"]
    rh_reference_community = rh_reference["community"]

    context = {
        "employee_count": employees.count(),
        "project_count": projects.count(),
        "activity_count": activities.count(),
        "budget_line_count": budget_lines.count(),
        "report_count": reports.count(),
        "total_budget": total_budget,
        "total_committed": total_committed,
        "total_disbursed": total_disbursed,
        "project_status_map": project_status_map,
        "priority_projects": priority_projects,
        "recent_activities": recent_activities,
        "latest_reports": latest_reports,
        "top_budget_lines": top_budget_lines,
        "rh_reference": rh_reference,
        "rh_reference_staff_cards": [
            {
                "label": "Salaries / contractuels listes",
                "value": rh_reference_staff["salaried_and_contractual"],
                "note": "Effectif nominatif present dans la section personnel EVE.",
                "tone": "soft-green",
            },
            {
                "label": "Prestataires terrain listes",
                "value": rh_reference_staff["service_providers"],
                "note": "Supervision, logistique et animation terrain.",
                "tone": "soft-blue",
            },
            {
                "label": "Consultants / experts",
                "value": rh_reference_staff["consultants"],
                "note": "Experts multi-projets presents dans le tableau RH.",
                "tone": "soft-amber",
            },
            {
                "label": "Acteurs communautaires",
                "value": rh_reference_community["total_actors"],
                "note": "Relais, ICP, postes, accompagnateurs et superviseurs.",
                "tone": "",
            },
        ],
        "pending_leaves_count": Leave.objects.filter(
            is_active=True,
            deleted_at__isnull=True,
            status="EN_ATTENTE",
        ).count(),
    }
    return render(request, "home.html", context)
