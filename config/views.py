import os
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import SuspiciousOperation
from django.db.models import Count, Sum
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import render
from django.utils._os import safe_join

from apps.accounts.access import accessible_project_ids, can_see_everything
from apps.accounts.models import UserRole
from apps.common.reference_snapshots import RH_REFERENCE_SNAPSHOT
from apps.hr.models import Employee, Leave
from apps.hr.models import WorkforceSnapshot
from apps.projects.models import Project, ProjectTeam
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
        # Aucune donnee RH en base : on affiche un tableau vide (zeros) plutot
        # que des chiffres codes en dur. Les vrais chiffres apparaitront quand
        # un WorkforceSnapshot sera seede (ex: import_rh_reference_2026).
        rh_reference = {
            "title": "Tableau de bord RH",
            "scope": "",
            "source_date": None,
            "staff": {
                "salaried_and_contractual": 0,
                "service_providers": 0,
                "consultants": 0,
                "detailed_total_listed": 0,
                "reported_summary_total": 0,
                "has_total_discrepancy": False,
            },
            "community": {
                "relay_workers": 0,
                "icp": 0,
                "health_posts": 0,
                "companions": 0,
                "community_supervisors": 0,
                "regions": 0,
                "total_actors": 0,
            },
            "geographies": [],
        }

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


# Cartographie des roles applicatifs -> identifiant de section dans l'aide.
# L'utilisateur connecte voit l'ancre "votre role" mise en avant.
ROLE_SECTION_KEY = {
    "RAF": "raf",
    "DP": "dp",
    "SE": "se",
    "ARAF": "araf",
}


@login_required
def protected_media(request, path):
    """Sert les fichiers de MEDIA_ROOT UNIQUEMENT aux utilisateurs connectes.

    Les medias (justificatifs bancaires, pieces RH, factures) contiennent des
    donnees personnelles et financieres : ils ne doivent jamais etre servis en
    clair par nginx. En production, on delegue le streaming a nginx via
    l'en-tete X-Accel-Redirect (efficace, pas de streaming Python) vers une
    location `internal`. En dev (ou si X-Accel desactive), on streame via
    Django.
    """
    try:
        full_path = safe_join(settings.MEDIA_ROOT, path)
    except (SuspiciousOperation, ValueError):
        raise Http404("Chemin invalide.")

    if getattr(settings, "USE_X_ACCEL_REDIRECT", False):
        response = HttpResponse(status=200)
        # Prefixe correspondant a la location `internal` de nginx.
        response["X-Accel-Redirect"] = "/__protected_media__/" + path
        del response["Content-Type"]  # nginx determine le type
        return response

    if not os.path.exists(full_path):
        raise Http404("Fichier introuvable.")
    return FileResponse(open(full_path, "rb"))


@login_required
def help_view(request):
    """Page d'aide integree : mode d'emploi par role.

    Detecte les roles applicatifs de l'utilisateur connecte et les projets
    auxquels il est affecte via ProjectTeam, puis surligne sa section dans
    le sommaire. Toutes les sections restent visibles pour que chacun
    comprenne ce que font les autres.
    """
    user = request.user

    # Roles applicatifs (RAF, DP, SE).
    user_role_codes = list(
        UserRole.objects.filter(user=user)
        .values_list("role__code", flat=True)
        .distinct()
    )

    # Affectations projet (chargee de suivi, comptable, etc.).
    project_assignments = []
    if user.employee_id:
        project_assignments = list(
            ProjectTeam.objects.filter(
                employee_id=user.employee_id,
                is_active=True,
                deleted_at__isnull=True,
            )
            .select_related("project")
            .values_list("project__code", "role")
        )

    # Determine la (ou les) section(s) a mettre en avant.
    primary_sections = set()
    for code in user_role_codes:
        if code in ROLE_SECTION_KEY:
            primary_sections.add(ROLE_SECTION_KEY[code])
    # Heuristique : si l'utilisateur n'a pas de role global mais est dans
    # une ProjectTeam comme "Comptable", on met en avant la section comptable.
    if not primary_sections and project_assignments:
        roles = [r for _, r in project_assignments]
        if any("comptable" in (r or "").lower() for r in roles):
            primary_sections.add("comptable")
        elif any("suivi" in (r or "").lower() for r in roles):
            primary_sections.add("chargee_suivi")
        else:
            primary_sections.add("chargee_suivi")
    if user.is_superuser:
        primary_sections.add("admin")

    context = {
        "user_role_codes": user_role_codes,
        "project_assignments": project_assignments,
        "primary_sections": primary_sections,
        "site_base_url": getattr(settings, "SITE_BASE_URL", ""),
    }
    return render(request, "help.html", context)
