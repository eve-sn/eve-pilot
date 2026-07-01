"""
Smoke tests for the public Projects UI.

Each test creates its own fixtures (no reliance on imported real data).
Covers regressions surfaced previously:
 - /projets/ list renders project cards
 - /projets/<uuid>/ detail renders the project header
 - Progress bar CSS width is written with a dot (not the French comma),
   to keep the rule valid for the browser (regression on commit 200eb1b).
"""

from datetime import date
from decimal import Decimal

from django.test import Client, TestCase

from apps.accounts.models import User
from apps.projects.models import Donor, Project


class ProjectViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.donor = Donor.objects.create(
            name="Test Donor",
            short_name="TD",
            donor_type=Donor.DonorType.FOUNDATION,
        )
        cls.project = Project.objects.create(
            code="TEST-PROJECT-2026",
            title="Projet de test",
            short_title="Test",
            description="Projet pour tests automatises.",
            primary_donor=cls.donor,
            total_budget=Decimal("10000000.00"),
            currency="XOF",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status=Project.Status.ACTIVE,
            sector="NUTRITION",
            progress_percentage=Decimal("50.00"),
        )

    def setUp(self):
        # Le site est en deny-by-default (LoginRequiredMiddleware) : il faut un
        # utilisateur authentifie. Superuser -> voit tous les projets.
        self.client = Client()
        admin = User(
            username=f"proj_admin_{id(self)}",
            email=f"proj_admin_{id(self)}@test.local",
            first_name="T", last_name="Admin",
            is_superuser=True, is_active=True,
        )
        admin.set_password("x")
        admin.save()
        self.client.force_login(admin)

    def test_project_list_returns_200_and_shows_code(self):
        response = self.client.get("/projets/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TEST-PROJECT-2026")

    def test_project_list_shows_active_counter(self):
        response = self.client.get("/projets/")
        self.assertEqual(response.status_code, 200)
        # The hero displays the active project count; at least our test project.
        self.assertContains(response, "Projets en base")

    def test_project_detail_returns_200_and_shows_title(self):
        response = self.client.get(f"/projets/{self.project.public_uuid}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Projet de test")
        self.assertContains(response, "Test Donor")

    def test_project_detail_progress_css_uses_dot_decimal(self):
        """Regression: CSS width must use a dot, not the French comma
        (Django locale renders Decimal with comma by default; |unlocalize
        in the template forces ASCII format on the CSS attribute)."""
        response = self.client.get(f"/projets/{self.project.public_uuid}/")
        content = response.content.decode("utf-8")
        self.assertIn('width: 50.00%', content)
        self.assertNotIn('width: 50,00%', content)

    def test_project_detail_404_for_unknown_uuid(self):
        response = self.client.get("/projets/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(response.status_code, 404)

    def test_project_detail_shows_budget_lines(self):
        """Regression : les lignes budgetaires doivent s'afficher (et non le
        placeholder 'Section a venir')."""
        from apps.finance.models import BudgetLine
        from apps.references.models import BudgetCategory

        cat = BudgetCategory.objects.create(code="DETAIL_CAT", name="Cat detail")
        BudgetLine.objects.create(
            project=self.project,
            category=cat,
            code="BL-DETAIL",
            description="Ligne budgetaire visible",
            planned_amount=Decimal("500000.00"),
            committed_amount=Decimal("200000.00"),
            disbursed_amount=Decimal("100000.00"),
            currency="XOF",
            fiscal_year=2026,
        )
        response = self.client.get(f"/projets/{self.project.public_uuid}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ligne budgetaire visible")
        self.assertContains(response, "BL-DETAIL")
        # Les placeholders "Section a venir" doivent avoir disparu.
        self.assertNotContains(response, "Section a venir")


class ProjectModelTests(TestCase):
    def test_project_has_public_uuid_and_soft_delete_fields(self):
        donor = Donor.objects.create(name="Donor X")
        project = Project.objects.create(
            code="P1",
            title="P1",
            primary_donor=donor,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.assertIsNotNone(project.public_uuid)
        self.assertTrue(project.is_active)
        self.assertIsNone(project.deleted_at)

    def test_operating_contribution_fields_are_nullable(self):
        donor = Donor.objects.create(name="Donor Y")
        project = Project.objects.create(
            code="P2",
            title="P2",
            primary_donor=donor,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.assertIsNone(project.operating_contribution_amount)
        self.assertIsNone(project.operating_contribution_pct)
        self.assertEqual(project.operating_contribution_note, "")


class ProjectSplitKeyTests(TestCase):
    """La cle de repartition SYCEBNL (162 invest / 462 admin) doit totaliser
    100 % : controle au niveau formulaire (clean) ET base (CheckConstraint)."""

    @classmethod
    def setUpTestData(cls):
        cls.donor = Donor.objects.create(name="Donor split")

    def _project(self, code, inv, adm):
        from decimal import Decimal
        return Project(
            code=code, title=code, primary_donor=self.donor,
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
            investment_split_pct=Decimal(inv),
            administration_split_pct=Decimal(adm),
        )

    def test_default_split_is_valid(self):
        # Defaut 0/100 -> conforme.
        p = Project.objects.create(
            code="SPLIT-DEF", title="Def", primary_donor=self.donor,
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        p.full_clean()  # ne leve pas

    def test_valid_split_80_20(self):
        p = self._project("SPLIT-OK", "80.00", "20.00")
        p.full_clean()
        p.save()  # ne leve pas

    def test_clean_rejects_sum_not_100(self):
        from django.core.exceptions import ValidationError
        p = self._project("SPLIT-BAD", "50.00", "30.00")  # somme 80
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_db_constraint_rejects_sum_not_100(self):
        # Contournement de clean() (save direct) : la base doit refuser.
        from django.db import IntegrityError
        p = self._project("SPLIT-DBBAD", "70.00", "20.00")  # somme 90
        with self.assertRaises(IntegrityError):
            p.save()
