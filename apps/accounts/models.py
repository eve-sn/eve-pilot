from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

from apps.accounts.managers import UserManager
from apps.common.models import TimeStampedModel, TrackedModel


phone_validator = RegexValidator(
    regex=r"^[0-9+\-\s]{7,20}$",
    message="Phone numbers must contain only digits, spaces, + or -.",
)


class Role(TrackedModel):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "roles"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Permission(TrackedModel):
    code = models.CharField(max_length=60, unique=True)
    module = models.CharField(max_length=30)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "permissions"
        ordering = ["module", "code"]

    def __str__(self):
        return self.code


class User(AbstractBaseUser, PermissionsMixin, TrackedModel):
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(max_length=120, unique=True)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    employee = models.ForeignKey(
        "hr.Employee",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="user_accounts",
    )
    is_superuser = models.BooleanField(default=False)
    two_factor_enabled = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email", "first_name", "last_name"]

    class Meta:
        db_table = "users"
        ordering = ["last_name", "first_name"]

    @property
    def is_staff(self):
        return self.is_superuser

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username


class RolePermission(TimeStampedModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="permission_roles")
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="granted_role_permissions",
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "role_permissions"
        unique_together = ("role", "permission")

    def __str__(self):
        return f"{self.role.code} -> {self.permission.code}"


class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_users")
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="scoped_user_roles",
    )
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="granted_user_roles",
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_roles"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role"],
                condition=Q(project__isnull=True),
                name="uq_user_roles_global_scope",
            ),
            models.UniqueConstraint(
                fields=["user", "role", "project"],
                condition=Q(project__isnull=False),
                name="uq_user_roles_project_scope",
            ),
        ]

    def __str__(self):
        if self.project_id:
            return f"{self.user} / {self.role.code} / {self.project.code}"
        return f"{self.user} / {self.role.code}"


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "CREATE", "Create"
        UPDATE = "UPDATE", "Update"
        DELETE = "DELETE", "Delete"
        LOGIN = "LOGIN", "Login"
        LOGOUT = "LOGOUT", "Logout"
        EXPORT = "EXPORT", "Export"
        APPROVE = "APPROVE", "Approve"
        REJECT = "REJECT", "Reject"
        RESET_PASSWORD = "RESET_PASSWORD", "Reset password"

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    entity_type = models.CharField(max_length=50)
    entity_id = models.BigIntegerField(blank=True, null=True)
    changes = models.JSONField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=255, blank=True)
    event_timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_log"
        ordering = ["-event_timestamp"]

    def __str__(self):
        return f"{self.action} {self.entity_type} ({self.entity_id})"
