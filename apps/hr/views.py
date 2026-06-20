from django.contrib import messages
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.access import can_see_everything, require_global_access
from apps.hr.forms import EmployeeForm
from apps.hr.models import Contract, Employee, Leave, WorkforceSnapshot
from apps.hr.reference_data import RH_REFERENCE_SOURCE


def employee_create(request):
    """Création manuelle d'une fiche du personnel. Réservée au responsable RH
    (rôles globaux RAF/DP/SE) et aux administrateurs."""
    if not can_see_everything(request.user):
        return render(
            request, "accounts/access_denied.html",
            {"message": "La création de fiches du personnel est réservée à la Direction / RH."},
            status=403,
        )
    if request.method == "POST":
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.created_by = request.user
            if not employee.reference_source:
                employee.reference_source = RH_REFERENCE_SOURCE
            employee.save()
            messages.success(request, f"Fiche créée : {employee.first_name} {employee.last_name}.")
            return redirect("hr:employee_detail", public_uuid=employee.public_uuid)
    else:
        form = EmployeeForm()
    return render(request, "hr/form.html", {"form": form, "mode": "create"})


@require_global_access
def rh_dashboard(request):
    # Donnees RH sensibles (salaires via contracts, congrs, documents) :
    # reservees a la Direction / RH (roles globaux), comme employee_create.
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    unit = request.GET.get("unit", "").strip()
    show = request.GET.get("show", "reference").strip()

    employees = Employee.objects.filter(is_active=True, deleted_at__isnull=True)
    if show != "all":
        employees = employees.filter(reference_source=RH_REFERENCE_SOURCE)

    employees = employees.select_related("commune", "manager").prefetch_related(
        Prefetch(
            "contracts",
            queryset=Contract.objects.select_related("project", "contract_type").order_by("-start_date"),
        ),
        "project_assignments__project",
        "documents__document_type",
        "evaluations",
    )

    if q:
        employees = employees.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(matricule__icontains=q)
            | Q(position__icontains=q)
            | Q(assignment_label__icontains=q)
            | Q(organizational_unit__icontains=q)
        )

    if category:
        employees = employees.filter(workforce_category=category)

    if unit:
        employees = employees.filter(organizational_unit=unit)

    employees = employees.order_by("organizational_unit", "last_name", "first_name").distinct()

    for employee in employees:
        employee.primary_contract = employee.contracts.first()
        employee.project_links = [assignment.project for assignment in employee.project_assignments.all() if assignment.project]

    summary_queryset = Employee.objects.filter(is_active=True, deleted_at__isnull=True, reference_source=RH_REFERENCE_SOURCE)
    category_counts = {
        item["workforce_category"]: item["total"]
        for item in summary_queryset.values("workforce_category").annotate(total=Count("id"))
    }
    units = (
        summary_queryset.exclude(organizational_unit="")
        .order_by("organizational_unit")
        .values_list("organizational_unit", flat=True)
        .distinct()
    )

    latest_snapshot = (
        WorkforceSnapshot.objects.filter(is_active=True, deleted_at__isnull=True)
        .prefetch_related("geographies")
        .order_by("-source_date")
        .first()
    )

    context = {
        "employees": employees,
        "filters": {
            "q": q,
            "category": category,
            "unit": unit,
            "show": show,
        },
        "latest_snapshot": latest_snapshot,
        "total_people": summary_queryset.count(),
        "salaried_count": category_counts.get(Employee.WorkforceCategory.SALARIED, 0),
        "service_provider_count": category_counts.get(Employee.WorkforceCategory.SERVICE_PROVIDER, 0),
        "consultant_count": category_counts.get(Employee.WorkforceCategory.CONSULTANT, 0),
        "pending_leave_count": Leave.objects.filter(
            is_active=True,
            deleted_at__isnull=True,
            employee__reference_source=RH_REFERENCE_SOURCE,
            status=Leave.Status.PENDING,
        ).count(),
        "units": units,
        "category_choices": Employee.WorkforceCategory.choices,
        "can_create_employee": can_see_everything(request.user),
    }
    return render(request, "hr/dashboard.html", context)


@require_global_access
def employee_detail(request, public_uuid):
    employee = get_object_or_404(
        Employee.objects.select_related("commune", "manager").prefetch_related(
            Prefetch(
                "contracts",
                queryset=Contract.objects.select_related("project", "contract_type").order_by("-start_date"),
            ),
            "project_assignments__project",
            "documents__document_type",
            "leaves",
            "evaluations__evaluator",
        ),
        public_uuid=public_uuid,
        is_active=True,
        deleted_at__isnull=True,
    )

    related_projects = []
    seen_project_ids = set()
    for contract in employee.contracts.all():
        if contract.project and contract.project_id not in seen_project_ids:
            related_projects.append(contract.project)
            seen_project_ids.add(contract.project_id)
    for assignment in employee.project_assignments.all():
        if assignment.project and assignment.project_id not in seen_project_ids:
            related_projects.append(assignment.project)
            seen_project_ids.add(assignment.project_id)

    context = {
        "employee": employee,
        "contracts": employee.contracts.all(),
        "documents": employee.documents.all(),
        "leaves": employee.leaves.all()[:6],
        "evaluations": employee.evaluations.all()[:4],
        "project_assignments": employee.project_assignments.all(),
        "related_projects": related_projects,
    }
    return render(request, "hr/employee_detail.html", context)
