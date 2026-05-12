from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, render

from apps.projects.models import (
    Donor,
    Indicator,
    Project,
    ProjectDonor,
    ProjectLocation,
    ProjectTeam,
)


ACTIVE_DOMAIN = {"is_active": True, "deleted_at__isnull": True}


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

    context = {
        "project": project,
        "co_funders": project.co_funders.all(),
        "team_assignments": project.team_assignments.all(),
        "locations": project.locations.all(),
        "indicators": project.indicators.all(),
    }
    return render(request, "projects/detail.html", context)
