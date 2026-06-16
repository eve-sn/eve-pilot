"""Vues de la couche publique du module Activites.

Iteration 1 (perimetre A + B) :
  A. CRUD Activity : planification des activites projet.
  B. Rapports terrain : soumission d'ActivityReport (participants,
     beneficiaires, preuves) + workflow de validation Secretaire Executif
     (SOUMIS -> VALIDE / REJETE).
"""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.access import (
    accessible_project_ids,
    can_see_everything,
)
from apps.accounts.models import UserRole
from apps.activities.forms import (
    ActivityEvidenceForm,
    ActivityForm,
    ActivityReportDecisionForm,
    ActivityReportForm,
    BeneficiaryForm,
)
from apps.activities.models import Activity, ActivityReport
from apps.finance.models import BudgetLine
from apps.projects.models import Project

ACTIVE_DOMAIN = {"is_active": True, "deleted_at__isnull": True}

# Role habilite a valider les rapports d'activite terrain.
VALIDATOR_ROLE_CODE = "SE"


def _user_role_codes(user):
    return set(
        UserRole.objects.filter(user=user).values_list("role__code", flat=True)
    )


@login_required
def activity_list(request):
    """Liste des activites, filtrable par projet, statut et texte libre."""

    qs = Activity.objects.filter(**ACTIVE_DOMAIN).select_related(
        "project", "responsible"
    )

    # Filtre par perimetre projet (chargee de suivi, comptable scope).
    acc_ids = accessible_project_ids(request.user)
    if acc_ids is not None:
        qs = qs.filter(project_id__in=acc_ids)

    q = request.GET.get("q", "").strip()
    project_id = request.GET.get("project", "").strip()
    status = request.GET.get("status", "").strip()

    if q:
        qs = qs.filter(
            Q(title__icontains=q) | Q(code__icontains=q) | Q(description__icontains=q)
        )
    if project_id:
        qs = qs.filter(project_id=project_id)
    if status:
        qs = qs.filter(status=status)

    qs = qs.annotate(report_count=Count("reports", filter=Q(reports__is_active=True)))
    qs = qs.order_by("project__code", "planned_start_date", "title")

    summary = Activity.objects.filter(**ACTIVE_DOMAIN)
    if acc_ids is not None:
        summary = summary.filter(project_id__in=acc_ids)
    status_counts = {
        item["status"]: item["total"]
        for item in summary.values("status").annotate(total=Count("id"))
    }

    proj_qs = Project.objects.filter(**ACTIVE_DOMAIN)
    if acc_ids is not None:
        proj_qs = proj_qs.filter(id__in=acc_ids)

    context = {
        "activities": qs[:300],
        "filters": {"q": q, "project": project_id, "status": status},
        "status_choices": Activity.Status.choices,
        "projects": proj_qs.order_by("code"),
        "total_activities": summary.count(),
        "planned_count": status_counts.get(Activity.Status.PLANNED, 0),
        "in_progress_count": status_counts.get(Activity.Status.IN_PROGRESS, 0),
        "completed_count": status_counts.get(Activity.Status.COMPLETED, 0),
        "canceled_count": status_counts.get(Activity.Status.CANCELED, 0),
    }
    return render(request, "activities/list.html", context)


@login_required
def activity_create(request):
    """Creation d'une activite."""

    if request.method == "POST":
        form = ActivityForm(request.POST, user=request.user)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.created_by = request.user
            activity.save()
            messages.success(request, f"Activite '{activity.title}' creee.")
            return redirect("activities:detail", public_uuid=activity.public_uuid)
    else:
        form = ActivityForm(user=request.user)
    return render(request, "activities/form.html", {"form": form, "mode": "create"})


@login_required
def activity_edit(request, public_uuid):
    """Edition d'une activite existante."""

    activity = get_object_or_404(Activity, public_uuid=public_uuid, **ACTIVE_DOMAIN)

    # Acces : 404 si activite hors perimetre.
    if not can_see_everything(request.user):
        acc_ids = accessible_project_ids(request.user) or set()
        if activity.project_id not in acc_ids:
            raise Http404("Activite non accessible.")

    if request.method == "POST":
        form = ActivityForm(request.POST, instance=activity, user=request.user)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.updated_by = request.user
            activity.save()
            messages.success(request, "Activite mise a jour.")
            return redirect("activities:detail", public_uuid=activity.public_uuid)
    else:
        form = ActivityForm(instance=activity, user=request.user)
    return render(
        request,
        "activities/form.html",
        {"form": form, "mode": "edit", "activity": activity},
    )


@login_required
def activity_detail(request, public_uuid):
    """Detail d'une activite : informations + liste de ses rapports terrain."""

    activity = get_object_or_404(
        Activity.objects.select_related("project", "responsible").prefetch_related(
            "locations__commune"
        ),
        public_uuid=public_uuid,
        **ACTIVE_DOMAIN,
    )

    # Controle d'acces : 404 si activite hors perimetre utilisateur.
    if not can_see_everything(request.user):
        acc_ids = accessible_project_ids(request.user) or set()
        if activity.project_id not in acc_ids:
            raise Http404("Activite non accessible.")

    reports = (
        activity.reports.filter(**ACTIVE_DOMAIN)
        .select_related("reported_by", "validated_by", "commune")
        .annotate(
            beneficiary_count=Count(
                "beneficiaries", filter=Q(beneficiaries__is_active=True)
            ),
            evidence_count=Count(
                "evidences", filter=Q(evidences__is_active=True)
            ),
        )
        .order_by("-report_date", "-created_at")
    )
    budget_lines = (
        BudgetLine.objects.filter(activity=activity, **ACTIVE_DOMAIN)
        .select_related("category")
        .order_by("code")
    )
    budget_totals = budget_lines.aggregate(
        planned=Sum("planned_amount"),
        committed=Sum("committed_amount"),
        disbursed=Sum("disbursed_amount"),
    )
    context = {
        "activity": activity,
        "reports": reports,
        "locations": activity.locations.all(),
        "budget_lines": budget_lines,
        "budget_planned": budget_totals["planned"] or Decimal("0"),
        "budget_committed": budget_totals["committed"] or Decimal("0"),
        "budget_disbursed": budget_totals["disbursed"] or Decimal("0"),
    }
    return render(request, "activities/detail.html", context)


@login_required
def activity_report_create(request, public_uuid):
    """Soumission d'un rapport terrain rattache a une activite."""

    activity = get_object_or_404(Activity, public_uuid=public_uuid, **ACTIVE_DOMAIN)

    # Acces : 404 si activite hors perimetre.
    if not can_see_everything(request.user):
        acc_ids = accessible_project_ids(request.user) or set()
        if activity.project_id not in acc_ids:
            raise Http404("Activite non accessible.")

    if request.method == "POST":
        form = ActivityReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.activity = activity
            report.reported_by = request.user
            report.validation_status = ActivityReport.ValidationStatus.SUBMITTED
            report.created_by = request.user
            report.save()
            messages.success(
                request,
                "Rapport soumis. Il attend la validation du Secretaire Executif.",
            )
            return redirect(
                "activities:report_detail", public_uuid=report.public_uuid
            )
    else:
        form = ActivityReportForm(initial={"report_date": timezone.now().date()})
    return render(
        request,
        "activities/report_form.html",
        {"form": form, "activity": activity},
    )


@login_required
def activity_report_detail(request, public_uuid):
    """Detail d'un rapport : participants, beneficiaires, preuves, validation.

    Actions POST :
      add_beneficiary : ajoute un beneficiaire nominatif.
      add_evidence    : televerse une piece de preuve.
      decide          : valideur SE -> VALIDE / REJETE (rapport SOUMIS).
    """

    # Charge d'abord pour pouvoir verifier le projet.
    report = get_object_or_404(
        ActivityReport.objects.select_related(
            "activity", "activity__project", "reported_by", "validated_by", "commune"
        ).prefetch_related("beneficiaries", "evidences"),
        public_uuid=public_uuid,
        **ACTIVE_DOMAIN,
    )

    # Acces : 404 si rapport hors perimetre projet utilisateur.
    if not can_see_everything(request.user):
        acc_ids = accessible_project_ids(request.user) or set()
        if report.activity.project_id not in acc_ids:
            raise Http404("Rapport non accessible.")

    role_codes = _user_role_codes(request.user)
    can_validate = VALIDATOR_ROLE_CODE in role_codes
    is_pending = report.validation_status == ActivityReport.ValidationStatus.SUBMITTED

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "add_beneficiary":
            bform = BeneficiaryForm(request.POST)
            if bform.is_valid():
                beneficiary = bform.save(commit=False)
                beneficiary.activity_report = report
                beneficiary.created_by = request.user
                beneficiary.save()
                messages.success(request, "Beneficiaire ajoute.")
            else:
                messages.error(request, "Beneficiaire invalide : verifier les champs.")
            return redirect("activities:report_detail", public_uuid=public_uuid)

        if action == "add_evidence":
            eform = ActivityEvidenceForm(request.POST, request.FILES)
            if eform.is_valid():
                evidence = eform.save(commit=False)
                evidence.activity_report = report
                evidence.created_by = request.user
                evidence.save()
                messages.success(request, "Preuve televersee.")
            else:
                messages.error(request, "Preuve invalide : verifier le fichier et le type.")
            return redirect("activities:report_detail", public_uuid=public_uuid)

        if action == "decide":
            if not can_validate:
                messages.error(
                    request,
                    "Seul le Secretaire Executif (SE) peut valider un rapport d'activite.",
                )
                return redirect("activities:report_detail", public_uuid=public_uuid)
            if not is_pending:
                messages.warning(request, "Ce rapport a deja ete traite.")
                return redirect("activities:report_detail", public_uuid=public_uuid)
            dform = ActivityReportDecisionForm(request.POST)
            if dform.is_valid():
                report.validation_status = dform.cleaned_data["decision"]
                report.validation_comment = dform.cleaned_data["comment"]
                report.validated_by = request.user
                report.validated_at = timezone.now()
                report.updated_by = request.user
                report.save(
                    update_fields=[
                        "validation_status",
                        "validation_comment",
                        "validated_by",
                        "validated_at",
                        "updated_by",
                        "updated_at",
                    ]
                )
                messages.success(
                    request,
                    f"Rapport {report.get_validation_status_display().lower()}.",
                )
            else:
                messages.error(request, "Decision invalide : un commentaire est requis pour rejeter.")
            return redirect("activities:report_detail", public_uuid=public_uuid)

    context = {
        "report": report,
        "beneficiaries": report.beneficiaries.filter(**ACTIVE_DOMAIN).order_by(
            "last_name", "first_name"
        ),
        "evidences": report.evidences.filter(**ACTIVE_DOMAIN).order_by("-uploaded_at"),
        "beneficiary_form": BeneficiaryForm(),
        "evidence_form": ActivityEvidenceForm(),
        "decision_form": ActivityReportDecisionForm() if (can_validate and is_pending) else None,
        "can_validate": can_validate,
        "is_pending": is_pending,
    }
    return render(request, "activities/report_detail.html", context)
