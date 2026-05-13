from django.conf import settings
from django.conf.urls.static import static
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
    path("projets/", include("apps.projects.urls")),
    path("finance/", include("apps.finance.urls")),
    path("health/", healthcheck, name="healthcheck"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
