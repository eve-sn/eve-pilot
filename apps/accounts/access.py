"""Politique d'acces par projet pour les vues applicatives.

Regles, de la plus permissive a la plus restrictive :

1. Superuser Django           -> acces a TOUS les projets + lignes BG.
2. UserRole(role.code in {RAF, DP, SE}, project=None)
   = role applicatif global   -> acces a TOUS les projets + lignes BG.
3. UserRole(role.code in {RAF, DP, SE}, project=<X>)
   = role applicatif scope    -> acces aux projets X uniquement (rare en pratique).
4. Employee membre actif d'un ProjectTeam
                              -> acces aux projets ou il est membre.
5. Tout autre cas (utilisateur sans Employee ni role)
                              -> AUCUN acces aux donnees projet.

Les "lignes BG" (BudgetLine.project=None, CashflowEntry.project=None,
ExpenseRequest.project=None) ne sont visibles qu'aux utilisateurs ayant
acces a TOUS les projets (cas 1 ou 2). C'est volontaire : le Budget
General est une donnee de direction.
"""

from __future__ import annotations

from django.db.models import Q

GLOBAL_ROLES = {"RAF", "DP", "SE"}
# Roles qui peuvent ouvrir les ecrans comptables techniques (plan comptable,
# balance, compte de resultat, bilan, grand livre). Le Secretaire Executif (SE)
# en est exclu : il voit la finance de pilotage mais pas la comptabilite pure.
ACCOUNTING_ROLES = {"RAF", "DP"}
# Roles qui peuvent acceder au Budget General et a la petite caisse sans avoir
# la vue globale projets. L'Assistante RAF gere les depenses de fonctionnement
# (femme de charge, stagiaires, restauration, hospitalites) sans voir les
# projets sur lesquels elle n'est pas affectee.
BG_ROLES = {"RAF", "DP", "SE", "ARAF"}


def _has_global_role(user) -> bool:
    """L'utilisateur porte-t-il un role global RAF/DP/SE non scope a un projet ?"""
    return user.user_roles.filter(
        role__code__in=GLOBAL_ROLES, project__isnull=True
    ).exists()


def can_see_everything(user) -> bool:
    """L'utilisateur a-t-il une vue globale (tous projets + BG) ?

    True pour : superuser, RAF/DP/SE en portee globale. Determine le filtre
    par perimetre projet (dashboard finance, demandes, activites, etc.).
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return _has_global_role(user)


def can_see_accounting(user) -> bool:
    """L'utilisateur peut-il acceder aux ecrans comptables techniques ?

    Plus restrictif que can_see_everything : exclut le Secretaire Executif.
    Couvre plan comptable, balance generale, compte de resultat, bilan,
    grand livre. Reserve RAF, DP et superuser.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.user_roles.filter(
        role__code__in=ACCOUNTING_ROLES, project__isnull=True
    ).exists()


def accessible_project_ids(user) -> set[int] | None:
    """Renvoie l'ensemble des IDs de projets visibles par l'utilisateur.

    Retour `None` = vue globale (tous projets accessibles, sans restriction).
    Retour set vide = aucun projet accessible.
    """
    if not user.is_authenticated:
        return set()
    if can_see_everything(user):
        return None

    from apps.projects.models import ProjectTeam

    ids: set[int] = set()

    # Cas 3 : roles applicatifs scope a des projets (rare mais on le supporte).
    scoped = user.user_roles.filter(
        role__code__in=GLOBAL_ROLES, project__isnull=False
    ).values_list("project_id", flat=True)
    ids.update(scoped)

    # Cas 4 : appartenance ProjectTeam via l'Employee lie au User.
    if user.employee_id:
        team_ids = ProjectTeam.objects.filter(
            employee_id=user.employee_id,
            is_active=True,
            deleted_at__isnull=True,
        ).values_list("project_id", flat=True)
        ids.update(team_ids)

    return ids


def can_see_bg(user) -> bool:
    """Acces aux lignes Budget General (project=None) et a la petite caisse.

    Plus large que can_see_everything : inclut l'Assistante RAF qui gere
    uniquement les depenses BG, sans avoir une vue globale sur les projets.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.user_roles.filter(
        role__code__in=BG_ROLES, project__isnull=True
    ).exists()


def project_filter(user, project_field: str = "project") -> Q:
    """Construit un Q() a appliquer sur un queryset pour filtrer selon l'acces.

    Usage :
        qs = BudgetLine.objects.filter(project_filter(request.user))

    Si l'utilisateur voit tout -> Q() neutre (matche tout).
    Si l'utilisateur voit BG + N projets -> Q(project=None) | Q(project_id__in=ids).
    Si l'utilisateur voit N projets sans BG -> Q(project_id__in=ids).
    Si l'utilisateur ne voit rien -> Q(pk__in=[]) (matche rien).
    """
    ids = accessible_project_ids(user)
    if ids is None:
        return Q()  # vue globale, pas de filtre
    if not ids:
        return Q(pk__in=[])  # rien accessible
    return Q(**{f"{project_field}_id__in": ids})


def user_can_access_project(user, project) -> bool:
    """Predicat unitaire : l'utilisateur a-t-il acces a ce projet ?"""
    if can_see_everything(user):
        return True
    ids = accessible_project_ids(user) or set()
    return project.id in ids


def user_can_record_bank_movements(user) -> bool:
    """L'utilisateur peut-il saisir directement un mouvement bancaire ?

    Sont autorises :
      - comptes a vue globale (RAF, DP, SE, superuser)
      - tout membre actif d'un ProjectTeam dont le role contient "comptable"
        (cas SAKHO : il gere ses 10 projets)
    """
    if not user.is_authenticated:
        return False
    if can_see_everything(user):
        return True
    if not user.employee_id:
        return False
    from apps.projects.models import ProjectTeam
    return ProjectTeam.objects.filter(
        employee_id=user.employee_id,
        is_active=True,
        deleted_at__isnull=True,
        role__icontains="comptable",
    ).exists()


def accessible_bank_account_ids(user) -> set[int] | None:
    """Comptes bancaires accessibles a l'utilisateur (saisie directe).

    Retour `None` = tous accessibles. Sinon set des IDs.
    """
    if can_see_everything(user):
        return None
    acc_proj_ids = accessible_project_ids(user)
    if acc_proj_ids is None:
        return None
    if not acc_proj_ids:
        return set()
    from apps.finance.models import BankAccount
    return set(
        BankAccount.objects.filter(
            is_active=True, deleted_at__isnull=True,
            projects__id__in=acc_proj_ids,
        ).values_list("id", flat=True).distinct()
    )


def user_can_execute_expense(user, expense) -> bool:
    """L'utilisateur peut-il marquer la demande comme executee (saisir le paiement) ?

    Sont autorises :
      - les comptes a vue globale (RAF/DP/SE/superuser)
      - le demandeur (sur sa propre demande)
      - tout membre actif de l'equipe projet dont le role libelle contient
        "comptable" (cas SAKHO sur ses 5 projets)
    """
    if not user.is_authenticated:
        return False
    if can_see_everything(user):
        return True
    if user.employee_id and user.employee_id == expense.requester_id:
        return True
    if expense.project_id is None:
        # Demande BG : executable par les comptes a vue globale OU par les
        # utilisateurs avec acces BG (Assistante RAF notamment).
        return can_see_bg(user)
    if not user.employee_id:
        return False
    from apps.projects.models import ProjectTeam
    return ProjectTeam.objects.filter(
        project_id=expense.project_id,
        employee_id=user.employee_id,
        is_active=True,
        deleted_at__isnull=True,
        role__icontains="comptable",
    ).exists()


def require_global_access(view_func):
    """Decorateur : reserve une vue aux comptes a acces global (RAF/DP/SE/superuser).

    Pour les ecrans de pilotage transverses qui ne sont pas comptables au
    sens strict (ex: vue consolidee par projet).
    """
    from functools import wraps
    from django.contrib.auth.decorators import login_required
    from django.shortcuts import render

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not can_see_everything(request.user):
            return render(
                request,
                "accounts/access_denied.html",
                {
                    "message": (
                        "Cet ecran est reserve a la Direction (RAF, DP, SE) "
                        "et a l'administration."
                    ),
                },
                status=403,
            )
        return view_func(request, *args, **kwargs)

    return wrapper


def require_accounting_access(view_func):
    """Decorateur : reserve une vue aux ecrans comptables techniques.

    Plus restrictif que require_global_access : exclut le Secretaire Executif.
    Plan comptable, balance, compte de resultat, bilan, grand livre.
    """
    from functools import wraps
    from django.contrib.auth.decorators import login_required
    from django.shortcuts import render

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not can_see_accounting(request.user):
            return render(
                request,
                "accounts/access_denied.html",
                {
                    "message": (
                        "Cet ecran est reserve au RAF, a la DP et a "
                        "l'administration technique. Le Secretaire Executif et "
                        "les utilisateurs project-scopes n'y ont pas acces."
                    ),
                },
                status=403,
            )
        return view_func(request, *args, **kwargs)

    return wrapper
