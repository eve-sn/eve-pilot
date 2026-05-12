from django.contrib import admin

from apps.accounts.models import AuditLog, Permission, Role, RolePermission, User, UserRole


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "first_name", "last_name", "employee", "is_active", "is_superuser")
    search_fields = ("username", "email", "first_name", "last_name")
    list_filter = ("is_active", "is_superuser", "two_factor_enabled")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "updated_at")
    search_fields = ("code", "name")
    list_filter = ("is_active",)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "module", "is_active")
    search_fields = ("code", "module")
    list_filter = ("module", "is_active")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission", "granted_by", "granted_at")
    search_fields = ("role__code", "permission__code")


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "project", "granted_by", "granted_at")
    search_fields = ("user__username", "role__code", "project__code")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "entity_type", "entity_id", "user", "event_timestamp")
    search_fields = ("entity_type", "entity_id", "user__username")
    list_filter = ("action", "entity_type")
