from rest_framework.routers import DefaultRouter
from django.urls import include, path

from apps.api.views import (
    ActivityReportViewSet,
    ActivityViewSet,
    BudgetLineViewSet,
    CommitmentViewSet,
    CommuneViewSet,
    ContractViewSet,
    DisbursementViewSet,
    DonorViewSet,
    EmployeeViewSet,
    IndicatorViewSet,
    LeaveViewSet,
    ProjectViewSet,
    ReportTemplateViewSet,
    ReportViewSet,
    RoleViewSet,
    UserViewSet,
)

router = DefaultRouter()
router.register("roles", RoleViewSet)
router.register("users", UserViewSet)
router.register("communes", CommuneViewSet)
router.register("employees", EmployeeViewSet)
router.register("contracts", ContractViewSet)
router.register("leaves", LeaveViewSet)
router.register("donors", DonorViewSet)
router.register("projects", ProjectViewSet)
router.register("indicators", IndicatorViewSet)
router.register("activities", ActivityViewSet)
router.register("activity-reports", ActivityReportViewSet)
router.register("budget-lines", BudgetLineViewSet)
router.register("commitments", CommitmentViewSet)
router.register("disbursements", DisbursementViewSet)
router.register("report-templates", ReportTemplateViewSet)
router.register("reports", ReportViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
