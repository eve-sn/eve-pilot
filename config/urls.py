from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import JsonResponse
from django.urls import include, path

from config.views import home, help_view, protected_media


def healthcheck(_request):
    return JsonResponse({"status": "ok", "service": "eve_pilot_backend"})


urlpatterns = [
    path("", home, name="home"),
    path(
        "connexion/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
    path("aide/", help_view, name="help"),
    path("admin/", admin.site.urls),
    path("api/", include("apps.api.urls")),
    path("rh/", include("apps.hr.urls")),
    path("projets/", include("apps.projects.urls")),
    path("activites/", include("apps.activities.urls")),
    path("finance/", include("apps.finance.urls")),
    path("health/", healthcheck, name="healthcheck"),
    # Medias servis UNIQUEMENT aux utilisateurs connectes (donnees sensibles).
    # Jamais via le service statique public de Django/nginx. Cf. protected_media.
    path("media/<path:path>", protected_media, name="protected_media"),
]
