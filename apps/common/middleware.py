"""Middlewares transverses EVE Pilot."""

from django.conf import settings
from django.shortcuts import redirect
from urllib.parse import quote


class LoginRequiredMiddleware:
    """Exige une session authentifiee pour TOUTES les pages, sauf une liste
    blanche. Securite « deny-by-default » : meme si une vue oublie son
    decorateur @login_required, elle reste protegee.

    Exemptions :
      - la page de connexion / deconnexion (sinon boucle) ;
      - /health/ (sonde de disponibilite) ;
      - /static/ (CSS/JS/logo publics, aucune donnee sensible) ;
      - /admin/ (l'admin Django gere sa propre authentification) ;
      - /api/ (DRF applique IsAuthenticated et renvoie 401/403, pas une
        redirection HTML).

    A placer APRES AuthenticationMiddleware dans MIDDLEWARE (request.user doit
    etre disponible).
    """

    EXEMPT_PREFIXES = (
        "/connexion/",
        "/deconnexion/",
        "/health/",
        "/static/",
        "/admin/",
        "/api/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            path = request.path
            if not any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
                login_url = getattr(settings, "LOGIN_URL", "/connexion/")
                return redirect(f"{login_url}?next={quote(path)}")
        return self.get_response(request)
