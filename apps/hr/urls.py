from django.urls import path

from apps.hr.views import employee_detail, rh_dashboard


app_name = "hr"

urlpatterns = [
    path("", rh_dashboard, name="dashboard"),
    path("personnel/<uuid:public_uuid>/", employee_detail, name="employee_detail"),
]
