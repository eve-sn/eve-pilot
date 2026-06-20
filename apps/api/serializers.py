from rest_framework import serializers

from apps.accounts.models import Role, User
from apps.activities.models import Activity, ActivityReport
from apps.finance.models import BudgetLine, Commitment, Disbursement
from apps.hr.models import Contract, Employee, Leave
from apps.projects.models import Donor, Indicator, Project
from apps.references.models import Commune
from apps.reporting.models import Report, ReportTemplate


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "public_uuid", "code", "name", "description", "is_active"]


class UserSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    def get_employee_name(self, obj):
        return str(obj.employee) if obj.employee else None

    class Meta:
        model = User
        fields = [
            "id",
            "public_uuid",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone",
            "employee",
            "employee_name",
            "is_active",
            "is_superuser",
            "two_factor_enabled",
            "created_at",
            "updated_at",
        ]
        # Champs sensibles JAMAIS modifiables via l'API (defense en profondeur,
        # meme si le ViewSet est desormais en lecture seule) : empeche toute
        # elevation de privilege ou (de)activation de compte par cette voie.
        read_only_fields = [
            "created_at", "updated_at",
            "is_superuser", "is_active", "two_factor_enabled",
        ]


class CommuneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Commune
        fields = ["id", "public_uuid", "code", "name", "department", "region", "is_intervention_zone", "is_active"]


class EmployeeSerializer(serializers.ModelSerializer):
    commune_name = serializers.CharField(source="commune.name", read_only=True)
    manager_name = serializers.SerializerMethodField()

    def get_manager_name(self, obj):
        return str(obj.manager) if obj.manager else None

    class Meta:
        model = Employee
        fields = [
            "id",
            "public_uuid",
            "matricule",
            "last_name",
            "first_name",
            "gender",
            "position",
            "department",
            "status",
            "hire_date",
            "end_date",
            "commune",
            "commune_name",
            "manager",
            "manager_name",
            "email_professional",
            "phone_primary",
            "is_active",
        ]


class ContractSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    project_title = serializers.CharField(source="project.title", read_only=True)

    def get_employee_name(self, obj):
        return str(obj.employee) if obj.employee else None

    class Meta:
        model = Contract
        fields = [
            "id",
            "public_uuid",
            "employee",
            "employee_name",
            "contract_type",
            "contract_number",
            "project",
            "project_title",
            "start_date",
            "end_date",
            "gross_salary",
            "net_salary",
            "currency",
            "status",
            "is_amendment",
            "parent_contract",
        ]


class LeaveSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    def get_employee_name(self, obj):
        return str(obj.employee) if obj.employee else None

    class Meta:
        model = Leave
        fields = [
            "id",
            "public_uuid",
            "employee",
            "employee_name",
            "leave_type",
            "start_date",
            "end_date",
            "days_count",
            "status",
            "approved_by",
            "approved_at",
            "reason",
        ]


class DonorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Donor
        fields = ["id", "public_uuid", "name", "short_name", "donor_type", "country", "email", "phone", "is_active"]


class ProjectSerializer(serializers.ModelSerializer):
    primary_donor_name = serializers.CharField(source="primary_donor.name", read_only=True)
    project_manager_name = serializers.SerializerMethodField()

    def get_project_manager_name(self, obj):
        return str(obj.project_manager) if obj.project_manager else None

    class Meta:
        model = Project
        fields = [
            "id",
            "public_uuid",
            "code",
            "title",
            "short_title",
            "primary_donor",
            "primary_donor_name",
            "total_budget",
            "currency",
            "start_date",
            "end_date",
            "project_manager",
            "project_manager_name",
            "status",
            "sector",
            "progress_percentage",
            "target_beneficiaries",
            "is_active",
        ]


class IndicatorSerializer(serializers.ModelSerializer):
    project_code = serializers.CharField(source="project.code", read_only=True)

    class Meta:
        model = Indicator
        fields = [
            "id",
            "public_uuid",
            "project",
            "project_code",
            "code",
            "name",
            "indicator_type",
            "baseline_value",
            "target_value",
            "current_value",
            "achievement_rate",
            "frequency",
        ]


class ActivitySerializer(serializers.ModelSerializer):
    project_code = serializers.CharField(source="project.code", read_only=True)
    responsible_name = serializers.SerializerMethodField()

    def get_responsible_name(self, obj):
        return str(obj.responsible) if obj.responsible else None

    class Meta:
        model = Activity
        fields = [
            "id",
            "public_uuid",
            "project",
            "project_code",
            "code",
            "title",
            "activity_type",
            "planned_start_date",
            "planned_end_date",
            "planned_budget",
            "responsible",
            "responsible_name",
            "status",
            "completion_rate",
            "is_active",
        ]


class ActivityReportSerializer(serializers.ModelSerializer):
    activity_title = serializers.CharField(source="activity.title", read_only=True)

    class Meta:
        model = ActivityReport
        fields = [
            "id",
            "public_uuid",
            "activity",
            "activity_title",
            "report_date",
            "actual_location",
            "participants_count",
            "male_count",
            "female_count",
            "children_count",
            "validation_status",
            "reported_by",
            "validated_by",
        ]


class BudgetLineSerializer(serializers.ModelSerializer):
    project_code = serializers.CharField(source="project.code", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = BudgetLine
        fields = [
            "id",
            "public_uuid",
            "project",
            "project_code",
            "category",
            "category_name",
            "activity",
            "donor",
            "code",
            "description",
            "planned_amount",
            "committed_amount",
            "disbursed_amount",
            "currency",
            "fiscal_year",
        ]


class CommitmentSerializer(serializers.ModelSerializer):
    budget_line_description = serializers.CharField(source="budget_line.description", read_only=True)

    class Meta:
        model = Commitment
        fields = [
            "id",
            "public_uuid",
            "budget_line",
            "budget_line_description",
            "commitment_number",
            "commitment_type",
            "supplier_name",
            "amount",
            "commitment_date",
            "status",
            "approved_by",
        ]


class DisbursementSerializer(serializers.ModelSerializer):
    budget_line_description = serializers.CharField(source="budget_line.description", read_only=True)

    class Meta:
        model = Disbursement
        fields = [
            "id",
            "public_uuid",
            "commitment",
            "budget_line",
            "budget_line_description",
            "payment_number",
            "payment_date",
            "amount",
            "currency",
            "payment_method",
            "beneficiary_name",
            "status",
            "validated_by",
        ]


class ReportTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportTemplate
        fields = ["id", "public_uuid", "name", "report_type", "donor", "template_file_url", "is_active"]


class ReportSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)
    project_code = serializers.CharField(source="project.code", read_only=True)

    class Meta:
        model = Report
        fields = [
            "id",
            "public_uuid",
            "template",
            "template_name",
            "project",
            "project_code",
            "title",
            "period_start",
            "period_end",
            "status",
            "generated_file_url",
            "generated_by",
            "generated_at",
            "validated_by",
            "validated_at",
        ]
