"""Context processors EVE Pilot."""

from apps.accounts.access import can_see_accounting, can_see_bg, can_see_everything

# Libelle affiche dans la pastille utilisateur, par ordre de priorite.
ROLE_DISPLAY = {
    "RAF": "RAF",
    "DP": "Direction Programmes",
    "SE": "Sec. Executif",
    "ARAF": "Assistante RAF",
}


def _user_display_role(user) -> str:
    """Retourne le libelle court du role principal de l'utilisateur connecte."""
    if user.is_superuser:
        return "Superuser"
    codes = list(user.user_roles.filter(project__isnull=True).values_list("role__code", flat=True))
    for code in ("RAF", "DP", "SE", "ARAF"):
        if code in codes:
            return ROLE_DISPLAY[code]
    if user.employee_id:
        return user.employee.position[:24]
    return "Utilisateur"


def _user_initials(user) -> str:
    first = (user.first_name or "").strip()
    last = (user.last_name or "").strip()
    if first and last:
        return (first[0] + last[0]).upper()
    if user.username:
        return user.username[:2].upper()
    return "?"


def user_access(request):
    """Injecte des flags d'acces dans tous les templates.

    user_can_see_everything : pilote l'affichage des elements transverses
        (vue globale projets, BG, etc.).
    user_can_see_accounting : pilote l'affichage des ecrans comptables
        techniques (plan comptable, balance, bilan, compte de resultat).
        Exclut le Secretaire Executif.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {
            "user_can_see_everything": False,
            "user_can_see_accounting": False,
            "user_can_see_bg": False,
            "user_initials": "",
            "user_display_role": "",
            "user_display_name": "",
        }
    full_name = f"{user.first_name} {user.last_name}".strip() or user.username
    return {
        "user_can_see_everything": can_see_everything(user),
        "user_can_see_accounting": can_see_accounting(user),
        "user_can_see_bg": can_see_bg(user),
        "user_initials": _user_initials(user),
        "user_display_role": _user_display_role(user),
        "user_display_name": full_name,
    }
