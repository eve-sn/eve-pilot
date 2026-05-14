from django.urls import path

from apps.activities.views import (
    activity_create,
    activity_detail,
    activity_edit,
    activity_list,
    activity_report_create,
    activity_report_detail,
)

app_name = "activities"

urlpatterns = [
    path("", activity_list, name="list"),
    path("nouvelle/", activity_create, name="create"),
    path("<uuid:public_uuid>/", activity_detail, name="detail"),
    path("<uuid:public_uuid>/modifier/", activity_edit, name="edit"),
    path("<uuid:public_uuid>/rapport/", activity_report_create, name="report_create"),
    path("rapports/<uuid:public_uuid>/", activity_report_detail, name="report_detail"),
]
