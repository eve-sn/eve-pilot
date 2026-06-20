"""Tests du socle commun : manager soft-delete des TrackedModel."""

from datetime import date

from django.test import TestCase

from apps.projects.models import Donor, Project


class SoftDeleteManagerTests(TestCase):
    """Le manager des TrackedModel garde le comportement Django par defaut
    (tous les enregistrements) et ajoute .active()/.deleted()."""

    @classmethod
    def setUpTestData(cls):
        cls.donor = Donor.objects.create(name="Donor SD")
        cls.alive = Project.objects.create(
            code="SD-ALIVE", title="Vivant", primary_donor=cls.donor,
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        cls.gone = Project.objects.create(
            code="SD-GONE", title="Supprime", primary_donor=cls.donor,
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        cls.gone.soft_delete()

    def test_objects_returns_all_including_soft_deleted(self):
        # Comportement par defaut INCHANGE : objects voit tout (non-regression).
        codes = set(Project.objects.values_list("code", flat=True))
        self.assertEqual(codes, {"SD-ALIVE", "SD-GONE"})

    def test_active_excludes_soft_deleted(self):
        actifs = list(Project.objects.active())
        self.assertIn(self.alive, actifs)
        self.assertNotIn(self.gone, actifs)

    def test_active_matches_manual_filter(self):
        # .active() == l'ancien filtre ACTIVE_DOMAIN, a l'identique.
        manuel = set(
            Project.objects.filter(is_active=True, deleted_at__isnull=True)
            .values_list("pk", flat=True)
        )
        via_active = set(Project.objects.active().values_list("pk", flat=True))
        self.assertEqual(manuel, via_active)

    def test_deleted_returns_only_soft_deleted(self):
        supprimes = list(Project.objects.deleted())
        self.assertEqual(supprimes, [self.gone])

    def test_active_is_chainable(self):
        # .active() reste chainable apres un filtre.
        qs = Project.objects.filter(code__startswith="SD-").active()
        self.assertEqual(list(qs), [self.alive])


class UserManagerPreservedTests(TestCase):
    """Garde-fou : ajouter un manager sur le socle ne doit PAS detourner le
    default manager de User (sinon createsuperuser / auth cassent)."""

    def test_user_default_manager_is_user_manager(self):
        from apps.accounts.models import User
        from apps.accounts.managers import UserManager

        self.assertIsInstance(User.objects, UserManager)
        self.assertIsInstance(User._default_manager, UserManager)

    def test_create_superuser_still_works(self):
        from apps.accounts.models import User

        u = User.objects.create_superuser(
            username="root_sd", email="root_sd@test.local", password="x",
        )
        self.assertTrue(u.is_superuser)
        self.assertTrue(u.is_staff)
