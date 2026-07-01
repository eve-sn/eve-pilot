# -*- coding: utf-8 -*-
from django.contrib import admin

from apps.common.models import Feedback


# --- Protection globale du champ soft-delete `deleted_at` dans l'admin --------
# `deleted_at` ne doit JAMAIS etre saisi a la main : le soft-delete passe par
# SoftDeleteModel.soft_delete(). Expose en champ editable dans l'admin, il etait
# rempli par l'autofill du navigateur a la creation -> enregistrement
# is_active=True mais deleted_at != NULL -> exclu de .active() -> invisible
# partout (ex. le dropdown des lignes budgetaires).
#
# On rend donc `deleted_at` READONLY sur TOUS les admins dont le modele porte ce
# champ, en enveloppant `ModelAdmin.get_readonly_fields` (appele a chaque
# requete) plutot qu'en le declarant admin par admin : les futurs admins sont
# couverts automatiquement. On ne touche pas a `editable` cote modele (evite une
# migration sur chaque modele heritant de TrackedModel) : la restauration d'un
# enregistrement soft-delete reste possible via le shell.
_orig_get_readonly_fields = admin.ModelAdmin.get_readonly_fields


def _get_readonly_fields_with_soft_delete(self, request, obj=None):
    readonly = tuple(_orig_get_readonly_fields(self, request, obj))
    try:
        field_names = {f.name for f in self.model._meta.get_fields()}
    except Exception:  # pragma: no cover - securite defensive
        field_names = set()
    if "deleted_at" in field_names and "deleted_at" not in readonly:
        readonly = readonly + ("deleted_at",)
    return readonly


admin.ModelAdmin.get_readonly_fields = _get_readonly_fields_with_soft_delete


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("created_at", "category", "status", "rating", "created_by", "page", "short_message")
    list_filter = ("category", "status", "created_at")
    search_fields = ("message", "page", "created_by__username")
    list_editable = ("status",)
    readonly_fields = ("created_at", "updated_at", "created_by", "page", "category", "rating", "message")
    ordering = ("-id",)

    @admin.display(description="Message")
    def short_message(self, obj):
        return (obj.message or "")[:80]
