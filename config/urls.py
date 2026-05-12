from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from config.views import home


def healthcheck(_request):
    return JsonResponse({"status": "ok", "service": "eve_pilot_backend"})


urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("api/", include("apps.api.urls")),
    path("rh/", include("apps.hr.urls")),
    path("health/", healthcheck, name="healthcheck"),
]
