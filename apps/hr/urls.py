from django.urls import path

from apps.hr.views import employee_create, employee_detail, rh_dashboard


app_name = "hr"

urlpatterns = [
    path("", rh_dashboard, name="dashboard"),
    path("personnel/nouveau/", employee_create, name="employee_create"),
    path("personnel/<uuid:public_uuid>/", employee_detail, name="employee_detail"),
]
