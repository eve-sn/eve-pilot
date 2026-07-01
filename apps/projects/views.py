from django.contrib import messages
from django.db.models import Count, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from apps.activities.models import ActivityReport
from apps.finance.models import BudgetLine

from apps.accounts.access import can_see_everything
from apps.projects.forms import ProjectForm
from apps.projects.models import (
    Donor,
    Indicator,
    Project,
    ProjectDonor,
    ProjectLocation,
    ProjectTeam,
)


ACTIVE_DOMAIN = {"is_active": True, "deleted_at__isnull": True}


def project_create(request):
    """Création manuelle d'un projet. Réservé aux rôles globaux (RAF/DP/SE)
    et aux administrateurs."""
    if not can_see_everything(request.user):
        return render(
            request, "accounts/access_denied.html",
            {"message": "La création de projets est réservée à la Direction (RAF, DP, SE)."},
            status=403,
        )
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()
            form.save_m2m()
            messages.success(request, f"Projet « {project.title} » créé.")
            return redirect("projects:detail", public_uuid=project.public_uuid)
    else:
        form = ProjectForm()
    return render(request, "projects/form.html", {"form": form, "mode": "create"})


def project_list(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    sector = request.GET.get("sector", "").strip()
    donor = request.GET.get("donor", "").strip()

    projects = (
        Project.objects.filter(**ACTIVE_DOMAIN)
        .select_related("primary_donor", "project_manager")
    )

    if q:
        projects = projects.filter(
            Q(code__icontains=q)
            | Q(title__icontains=q)
            | Q(short_title__icontains=q)
        )
    if status:
        projects = projects.filter(status=status)
    if sector:
        projects = projects.filter(sector=sector)
    if donor:
        projects = projects.filter(primary_donor_id=donor)

    projects = projects.order_by("code")

    summary_qs = Project.objects.filter(**ACTIVE_DOMAIN)
    status_counts = {
        item["status"]: item["total"]
        for item in summary_qs.values("status").annotate(total=Count("id"))
    }

    sectors = (
        summary_qs.exclude(sector="")
        .order_by("sector")
        .values_list("sector", flat=True)
        .distinct()
    )

    donors = Donor.objects.filter(**ACTIVE_DOMAIN).order_by("name")

    context = {
        "projects": projects,
        "filters": {"q": q, "status": status, "sector": sector, "donor": donor},
        "status_choices": Project.Status.choices,
        "sectors": sectors,
        "donors": donors,
        "total_projects": summary_qs.count(),
        "active_count": status_counts.get(Project.Status.ACTIVE, 0),
        "preparation_count": status_counts.get(Project.Status.PREPARATION, 0),
        "suspended_count": status_counts.get(Project.Status.SUSPENDED, 0),
        "closed_count": status_counts.get(Project.Status.CLOSED, 0),
        "can_create_project": can_see_everything(request.user),
    }
    return render(request, "projects/list.html", context)


def project_detail(request, public_uuid):
    project = get_object_or_404(
        Project.objects.select_related("primary_donor", "project_manager").prefetch_related(
            Prefetch(
                "co_funders",
                queryset=ProjectDonor.objects.select_related("donor"),
            ),
            Prefetch(
                "team_assignments",
                queryset=ProjectTeam.objects.filter(**ACTIVE_DOMAIN).select_related("employee"),
            ),
            Prefetch(
                "locations",
                queryset=ProjectLocation.objects.select_related("commune"),
            ),
            Prefetch(
                "indicators",
                queryset=Indicator.objects.filter(**ACTIVE_DOMAIN).order_by("code", "name"),
            ),
        ),
        public_uuid=public_uuid,
        **ACTIVE_DOMAIN,
    )

    budget_lines = (
        BudgetLine.objects.filter(project=project, **ACTIVE_DOMAIN)
        .select_related("category")
        .order_by("category__code", "code", "description")
    )
    budget_totals = budget_lines.aggregate(
        planned=Sum("planned_amount"),
        committed=Sum("committed_amount"),
        disbursed=Sum("disbursed_amount"),
    )
    activities = (
        project.activities.filter(**ACTIVE_DOMAIN)
        .order_by("planned_start_date", "title")
    )
    reports = (
        ActivityReport.objects.filter(activity__project=project, **ACTIVE_DOMAIN)
        .select_related("activity", "reported_by")
        .order_by("-report_date")[:10]
    )

    context = {
        "project": project,
        "co_funders": project.co_funders.all(),
        "team_assignments": project.team_assignments.all(),
        "locations": project.locations.all(),
        "indicators": project.indicators.all(),
        "budget_lines": budget_lines,
        "budget_totals": budget_totals,
        "activities": activities,
        "reports": reports,
    }
    return render(request, "projects/detail.html", context)
