from rest_framework import filters, viewsets
from rest_framework.permissions import IsAdminUser

from apps.accounts.models import Role, User
from apps.activities.models import Activity, ActivityReport
from apps.api.serializers import (
    ActivityReportSerializer,
    ActivitySerializer,
    BudgetLineSerializer,
    CommitmentSerializer,
    CommuneSerializer,
    ContractSerializer,
    DisbursementSerializer,
    DonorSerializer,
    EmployeeSerializer,
    IndicatorSerializer,
    LeaveSerializer,
    ProjectSerializer,
    ReportSerializer,
    ReportTemplateSerializer,
    RoleSerializer,
    UserSerializer,
)
from apps.finance.models import BudgetLine, Commitment, Disbursement
from apps.hr.models import Contract, Employee, Leave
from apps.projects.models import Donor, Indicator, Project
from apps.references.models import Commune
from apps.reporting.models import Report, ReportTemplate


class BaseModelViewSet(viewsets.ReadOnlyModelViewSet):
    """Lecture seule, reservee aux administrateurs.

    AVANT : viewsets.ModelViewSet avec la seule permission par defaut
    (IsAuthenticated). Tout utilisateur connecte pouvait, via /api/ :
      - s'auto-promouvoir superadmin (PATCH /api/users/<id>/ is_superuser=true,
        champ inscriptible dans UserSerializer) ;
      - lire les salaires (contracts), les finances et le personnel de TOUS les
        projets, en ignorant le cloisonnement par perimetre de la couche web ;
      - hard-delete en cascade des donnees comptables/terrain (DELETE non
        surcharge -> suppression reelle malgre le soft-delete).
    Aucun client ne consomme cette API (verifie : aucun fetch/JS, seul un lien
    vers l'API navigable). On la verrouille donc en lecture seule + IsAdminUser.

    Pour rouvrir un endpoint a des utilisateurs operationnels, il faut d'abord y
    reimplanter le filtrage par perimetre (cf. apps.accounts.access.project_filter)
    et le soft-delete AVANT de readmettre l'ecriture.
    """

    permission_classes = [IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering = ["-id"]


class RoleViewSet(BaseModelViewSet):
    queryset = Role.objects.filter(deleted_at__isnull=True)
    serializer_class = RoleSerializer
    search_fields = ["code", "name"]
    ordering = ["name"]


class UserViewSet(BaseModelViewSet):
    queryset = User.objects.filter(deleted_at__isnull=True).select_related("employee")
    serializer_class = UserSerializer
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering = ["last_name", "first_name"]


class CommuneViewSet(BaseModelViewSet):
    queryset = Commune.objects.filter(deleted_at__isnull=True)
    serializer_class = CommuneSerializer
    search_fields = ["code", "name", "department", "region"]
    ordering = ["region", "department", "name"]


class EmployeeViewSet(BaseModelViewSet):
    queryset = Employee.objects.filter(deleted_at__isnull=True).select_related("commune", "manager")
    serializer_class = EmployeeSerializer
    search_fields = ["matricule", "first_name", "last_name", "position", "department"]
    ordering = ["last_name", "first_name"]


class ContractViewSet(BaseModelViewSet):
    queryset = Contract.objects.filter(deleted_at__isnull=True).select_related("employee", "project", "contract_type")
    serializer_class = ContractSerializer
    search_fields = ["contract_number", "employee__first_name", "employee__last_name"]


class LeaveViewSet(BaseModelViewSet):
    queryset = Leave.objects.filter(deleted_at__isnull=True).select_related("employee", "approved_by")
    serializer_class = LeaveSerializer
    search_fields = ["employee__first_name", "employee__last_name", "leave_type", "status"]


class DonorViewSet(BaseModelViewSet):
    queryset = Donor.objects.filter(deleted_at__isnull=True)
    serializer_class = DonorSerializer
    search_fields = ["name", "short_name", "country"]
    ordering = ["name"]


class ProjectViewSet(BaseModelViewSet):
    queryset = Project.objects.filter(deleted_at__isnull=True).select_related("primary_donor", "project_manager")
    serializer_class = ProjectSerializer
    search_fields = ["code", "title", "short_title", "sector", "status"]


class IndicatorViewSet(BaseModelViewSet):
    queryset = Indicator.objects.filter(deleted_at__isnull=True).select_related("project")
    serializer_class = IndicatorSerializer
    search_fields = ["code", "name", "project__code", "project__title"]


class ActivityViewSet(BaseModelViewSet):
    queryset = Activity.objects.filter(deleted_at__isnull=True).select_related("project", "responsible")
    serializer_class = ActivitySerializer
    search_fields = ["code", "title", "project__code", "project__title", "status"]


class ActivityReportViewSet(BaseModelViewSet):
    queryset = ActivityReport.objects.filter(deleted_at__isnull=True).select_related("activity", "reported_by", "validated_by")
    serializer_class = ActivityReportSerializer
    search_fields = ["activity__title", "validation_status", "actual_location"]


class BudgetLineViewSet(BaseModelViewSet):
    queryset = BudgetLine.objects.filter(deleted_at__isnull=True).select_related("project", "category", "activity", "donor")
    serializer_class = BudgetLineSerializer
    search_fields = ["code", "description", "project__code", "project__title"]


class CommitmentViewSet(BaseModelViewSet):
    queryset = Commitment.objects.filter(deleted_at__isnull=True).select_related("budget_line", "approved_by")
    serializer_class = CommitmentSerializer
    search_fields = ["commitment_number", "supplier_name", "status"]


class DisbursementViewSet(BaseModelViewSet):
    queryset = Disbursement.objects.filter(deleted_at__isnull=True).select_related("budget_line", "commitment", "validated_by")
    serializer_class = DisbursementSerializer
    search_fields = ["payment_number", "beneficiary_name", "status"]


class ReportTemplateViewSet(BaseModelViewSet):
    queryset = ReportTemplate.objects.filter(deleted_at__isnull=True).select_related("donor")
    serializer_class = ReportTemplateSerializer
    search_fields = ["name", "report_type"]


class ReportViewSet(BaseModelViewSet):
    queryset = Report.objects.filter(deleted_at__isnull=True).select_related("template", "project", "generated_by", "validated_by")
    serializer_class = ReportSerializer
    search_fields = ["title", "status", "project__code", "project__title"]
