from django.urls import path

from apps.projects.views import project_detail, project_list


app_name = "projects"

urlpatterns = [
    path("", project_list, name="list"),
    path("<uuid:public_uuid>/", project_detail, name="detail"),
]
