from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.models import TrackedModel


class Employee(TrackedModel):
    class WorkforceCategory(models.TextChoices):
        SALARIED = "SALARIE", "Salarie / Contractuel"
        SERVICE_PROVIDER = "PRESTATAIRE", "Prestataire terrain"
        CONSULTANT = "CONSULTANT", "Consultant / Expert"

    class Gender(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"

    class Status(models.TextChoices):
        ACTIVE = "ACTIF", "Actif"
        SUSPENDED = "SUSPENDU", "Suspendu"
        TERMINATED = "TERMINE", "Termine"

    matricule = models.CharField(max_length=20, unique=True)
    last_name = models.CharField(max_length=80)
    first_name = models.CharField(max_length=80)
    birth_date = models.DateField(blank=True, null=True)
    birth_place = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=1, choices=Gender.choices, blank=True)
    nationality = models.CharField(max_length=50, default="Senegalaise")
    id_card_number = models.CharField(max_length=30, blank=True)
    id_card_expiry = models.DateField(blank=True, null=True)
    marital_status = models.CharField(max_length=20, blank=True)
    children_count = models.PositiveIntegerField(default=0)
    address = models.TextField(blank=True)
    commune = models.ForeignKey(
        "references.Commune",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="employees",
    )
    phone_primary = models.CharField(max_length=20, blank=True)
    phone_secondary = models.CharField(max_length=20, blank=True)
    email_personal = models.EmailField(max_length=120, blank=True)
    email_professional = models.EmailField(max_length=120, blank=True)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    photo_url = models.CharField(max_length=255, blank=True)
    position = models.CharField(max_length=120)
    department = models.CharField(max_length=80, blank=True)
    workforce_category = models.CharField(
        max_length=20,
        choices=WorkforceCategory.choices,
        default=WorkforceCategory.SALARIED,
    )
    organizational_unit = models.CharField(max_length=120, blank=True)
    assignment_label = models.CharField(max_length=150, blank=True)
    reference_source = models.CharField(max_length=60, blank=True)
    manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="managed_employees",
    )
    hire_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    ipres_number = models.CharField(max_length=30, blank=True)
    css_number = models.CharField(max_length=30, blank=True)
    tax_number = models.CharField(max_length=30, blank=True)
    bank_name = models.CharField(max_length=80, blank=True)
    bank_account = models.CharField(max_length=30, blank=True)

    class Meta:
        db_table = "employees"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.matricule} - {self.first_name} {self.last_name}"


class WorkforceSnapshot(TrackedModel):
    reference_code = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=180)
    scope = models.CharField(max_length=180, blank=True)
    source_date = models.DateField()
    reported_total_staff = models.PositiveIntegerField(default=0)
    detailed_total_staff = models.PositiveIntegerField(default=0)
    salaried_and_contractual_count = models.PositiveIntegerField(default=0)
    service_provider_count = models.PositiveIntegerField(default=0)
    consultant_count = models.PositiveIntegerField(default=0)
    relay_worker_count = models.PositiveIntegerField(default=0)
    icp_count = models.PositiveIntegerField(default=0)
    health_post_count = models.PositiveIntegerField(default=0)
    companion_count = models.PositiveIntegerField(default=0)
    community_supervisor_count = models.PositiveIntegerField(default=0)
    covered_regions_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "workforce_snapshots"
        ordering = ["-source_date", "reference_code"]

    def __str__(self):
        return f"{self.reference_code} - {self.title}"


class WorkforceGeography(TrackedModel):
    snapshot = models.ForeignKey(
        WorkforceSnapshot,
        on_delete=models.CASCADE,
        related_name="geographies",
    )
    sort_order = models.PositiveIntegerField(default=0)
    label = models.CharField(max_length=150)
    relay_worker_count = models.PositiveIntegerField(default=0)
    support_structures = models.CharField(max_length=180, blank=True)
    beneficiary_scope = models.CharField(max_length=180, blank=True)

    class Meta:
        db_table = "workforce_geographies"
        ordering = ["sort_order", "label"]

    def __str__(self):
        return self.label


class Contract(TrackedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIF", "Actif"
        SUSPENDED = "SUSPENDU", "Suspendu"
        TERMINATED = "TERMINE", "Termine"
        RESCINDED = "RESILIE", "Resilie"

    employee = models.ForeignKey(Employee, on_delete=models.RESTRICT, related_name="contracts")
    contract_type = models.ForeignKey(
        "references.ContractType",
        on_delete=models.RESTRICT,
        related_name="contracts",
    )
    contract_number = models.CharField(max_length=30, unique=True, blank=True, null=True)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="contracts",
    )
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    gross_salary = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=3, default="XOF")
    working_hours = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    probation_period_months = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    document_url = models.CharField(max_length=255, blank=True)
    is_amendment = models.BooleanField(default=False)
    parent_contract = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="amendments",
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "contracts"
        ordering = ["-start_date"]

    def __str__(self):
        return self.contract_number or f"Contract {self.pk}"


class Leave(TrackedModel):
    class LeaveType(models.TextChoices):
        ANNUAL = "ANNUEL", "Annuel"
        SICK = "MALADIE", "Maladie"
        MATERNITY = "MATERNITE", "Maternite"
        PATERNITY = "PATERNITE", "Paternite"
        EXCEPTIONAL = "EXCEPTIONNEL", "Exceptionnel"
        UNPAID = "SANS_SOLDE", "Sans solde"
        MISSION = "MISSION", "Mission"

    class Status(models.TextChoices):
        PENDING = "EN_ATTENTE", "En attente"
        APPROVED = "APPROUVE", "Approuve"
        REJECTED = "REFUSE", "Refuse"
        CANCELED = "ANNULE", "Annule"

    employee = models.ForeignKey(Employee, on_delete=models.RESTRICT, related_name="leaves")
    leave_type = models.CharField(max_length=30, choices=LeaveType.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    days_count = models.DecimalField(max_digits=5, decimal_places=2)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="approved_leaves",
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True)
    medical_certificate_url = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "leaves"
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.employee} / {self.leave_type}"


class Payslip(TrackedModel):
    class Status(models.TextChoices):
        DRAFT = "BROUILLON", "Brouillon"
        VALIDATED = "VALIDE", "Valide"
        PAID = "PAYE", "Paye"

    class PaymentMethod(models.TextChoices):
        TRANSFER = "VIREMENT", "Virement"
        CASH = "ESPECES", "Especes"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile money"
        CHEQUE = "CHEQUE", "Cheque"

    employee = models.ForeignKey(Employee, on_delete=models.RESTRICT, related_name="payslips")
    contract = models.ForeignKey(
        Contract,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="payslips",
    )
    period_year = models.PositiveIntegerField()
    period_month = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    gross_salary = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    ipres_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    css_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    ir_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    trimf_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonuses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField(blank=True, null=True)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, blank=True)
    pdf_url = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        db_table = "payslips"
        ordering = ["-period_year", "-period_month", "employee__last_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "period_year", "period_month"],
                name="uq_payslips_employee_period",
            )
        ]

    def __str__(self):
        return f"{self.employee} / {self.period_month:02d}-{self.period_year}"


class Evaluation(TrackedModel):
    class Status(models.TextChoices):
        DRAFT = "BROUILLON", "Brouillon"
        FINALIZED = "FINALISE", "Finalise"

    employee = models.ForeignKey(Employee, on_delete=models.RESTRICT, related_name="evaluations")
    evaluator = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="performed_evaluations",
    )
    evaluation_year = models.PositiveIntegerField()
    interview_date = models.DateField(blank=True, null=True)
    overall_score = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    strengths = models.TextField(blank=True)
    areas_for_improvement = models.TextField(blank=True)
    objectives_next_year = models.TextField(blank=True)
    employee_comments = models.TextField(blank=True)
    manager_comments = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    document_url = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "evaluations"
        ordering = ["-evaluation_year", "employee__last_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "evaluation_year"],
                name="uq_evaluations_employee_year",
            )
        ]

    def __str__(self):
        return f"{self.employee} / {self.evaluation_year}"


class EmployeeDocument(TrackedModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="documents")
    document_type = models.ForeignKey(
        "references.DocumentType",
        on_delete=models.RESTRICT,
        related_name="employee_documents",
    )
    title = models.CharField(max_length=150, blank=True)
    file_url = models.CharField(max_length=255)
    file_size_kb = models.PositiveIntegerField(blank=True, null=True)
    mime_type = models.CharField(max_length=50, blank=True)
    expiry_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "employee_documents"
        ordering = ["employee__last_name", "document_type__name"]

    def __str__(self):
        return self.title or self.document_type.name
