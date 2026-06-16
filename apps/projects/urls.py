from django.urls import path

from apps.projects.views import project_create, project_detail, project_list


app_name = "projects"

urlpatterns = [
    path("", project_list, name="list"),
    path("nouveau/", project_create, name="create"),
    path("<uuid:public_uuid>/", project_detail, name="detail"),
]
