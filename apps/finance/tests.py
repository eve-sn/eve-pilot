"""
Smoke tests for the Finance module : dashboard, cash-flow plan, bank accounts.
"""

from datetime import date
from decimal import Decimal

from django.test import Client, TestCase

from apps.finance.models import BankAccount, BudgetLine, CashflowEntry
from apps.projects.models import Donor, Project
from apps.references.models import BudgetCategory


class FinanceDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.donor = Donor.objects.create(name="Donor F", donor_type=Donor.DonorType.MULTILATERAL)
        cls.project = Project.objects.create(
            code="F-001",
            title="Projet finance",
            primary_donor=cls.donor,
            total_budget=Decimal("50000000.00"),
            currency="XOF",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status=Project.Status.ACTIVE,
            sector="NUTRITION",
            operating_contribution_amount=Decimal("5000000.00"),
            operating_contribution_pct=Decimal("10.00"),
        )
        cls.category = BudgetCategory.objects.create(
            code="CHARGES_TEST", name="Charges test"
        )
        cls.budget_line = BudgetLine.objects.create(
            project=None,  # Budget General
            category=cls.category,
            code="TEST-PAYROLL",
            description="Charges personnel test",
            planned_amount=Decimal("3000000.00"),
            currency="XOF",
            fiscal_year=2026,
        )
        cls.bank = BankAccount.objects.create(
            name="Test Bank",
            bank_name="Test SA",
            opening_balance=Decimal("100000.00"),
            opening_date=date(2026, 1, 1),
        )

    def setUp(self):
        self.client = Client()

    def test_dashboard_returns_200(self):
        response = self.client.get("/finance/")
        self.assertEqual(response.status_code, 200)

    def test_dashboard_shows_portfolio_and_revenue(self):
        response = self.client.get("/finance/")
        content = response.content.decode("utf-8")
        self.assertIn("Portefeuille projets", content)
        self.assertIn("Recettes du Budget General", content)
        # Operating contribution from cls.project should be summed.
        self.assertIn("5000000", content.replace(" ", ""))

    def test_dashboard_shows_bank_section(self):
        response = self.client.get("/finance/")
        content = response.content.decode("utf-8")
        self.assertIn("Comptes bancaires EVE", content)
        self.assertIn("Test Bank", content)

    def test_dashboard_shows_operating_line_detail(self):
        response = self.client.get("/finance/")
        self.assertContains(response, "TEST-PAYROLL")


class CashflowDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.donor = Donor.objects.create(name="Donor C")
        cls.project = Project.objects.create(
            code="C-001",
            title="Cashflow project",
            primary_donor=cls.donor,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status=Project.Status.ACTIVE,
        )
        cls.category = BudgetCategory.objects.create(code="CFLOW_TEST", name="Test")
        # Two months of receipts and one month of spend.
        CashflowEntry.objects.create(
            period_year=2026, period_month=1, label="Test receipt",
            direction=CashflowEntry.Direction.INCOMING,
            project=cls.project, planned_amount=Decimal("10000000.00"),
        )
        CashflowEntry.objects.create(
            period_year=2026, period_month=2, label="Test receipt",
            direction=CashflowEntry.Direction.INCOMING,
            project=cls.project, planned_amount=Decimal("5000000.00"),
        )
        CashflowEntry.objects.create(
            period_year=2026, period_month=1, label="Test spend",
            direction=CashflowEntry.Direction.OUTGOING,
            category=cls.category, planned_amount=Decimal("3000000.00"),
        )

    def setUp(self):
        self.client = Client()

    def test_cashflow_returns_200(self):
        response = self.client.get("/finance/tresorerie/")
        self.assertEqual(response.status_code, 200)

    def test_cashflow_shows_yearly_totals(self):
        response = self.client.get("/finance/tresorerie/")
        content = response.content.decode("utf-8")
        # Receipts: 10M + 5M = 15M; spend: 3M; net: 12M
        self.assertIn("15000000", content.replace(" ", ""))
        self.assertIn("3000000", content.replace(" ", ""))
        self.assertIn("12000000", content.replace(" ", ""))

    def test_cashflow_shows_section_headers(self):
        response = self.client.get("/finance/tresorerie/")
        self.assertContains(response, "Encaissements")
        self.assertContains(response, "Decaissements")
        self.assertContains(response, "Solde net mensuel")


class CashflowEntryConstraintTests(TestCase):
    def test_unique_per_period_label_direction(self):
        """The (year, month, label, direction) tuple is unique."""
        CashflowEntry.objects.create(
            period_year=2026, period_month=3, label="Same",
            direction=CashflowEntry.Direction.INCOMING,
            planned_amount=Decimal("1000.00"),
        )
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CashflowEntry.objects.create(
                    period_year=2026, period_month=3, label="Same",
                    direction=CashflowEntry.Direction.INCOMING,
                    planned_amount=Decimal("2000.00"),
                )


class BudgetLineNullableProjectTests(TestCase):
    def test_budget_line_can_have_no_project(self):
        cat = BudgetCategory.objects.create(code="X", name="X")
        line = BudgetLine.objects.create(
            project=None,
            category=cat,
            code="BG-LINE",
            description="Budget General line",
            planned_amount=Decimal("1.00"),
            fiscal_year=2026,
        )
        self.assertIsNone(line.project)


class CashRegisterValidationTests(TestCase):
    """Plafonds caisse : 40 000 par operation, 100 000 par semaine ISO."""

    @classmethod
    def setUpTestData(cls):
        from apps.finance.models import CashRegister

        cls.register = CashRegister.objects.create(name="Caisse test")

    def _make_movement(self, debit, day):
        from apps.finance.models import CashMovement
        from datetime import date

        return CashMovement(
            register=self.register,
            date_operation=date(2026, 5, day),
            label="Test op",
            debit=Decimal(str(debit)),
            credit=Decimal("0"),
        )

    def test_unit_cap_rejects_more_than_40000(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self._make_movement(45000, 5).save()

    def test_unit_cap_accepts_exactly_40000(self):
        movement = self._make_movement(40000, 5)
        movement.save()
        self.assertIsNotNone(movement.pk)

    def test_weekly_cap_rejects_cumulative_over_100000(self):
        from django.core.exceptions import ValidationError

        # All four days are within the same ISO week (W19 of 2026 :
        # Monday 4 May -> Sunday 10 May).
        self._make_movement(40000, 4).save()
        self._make_movement(40000, 5).save()
        self._make_movement(20000, 6).save()  # cumul = 100 000 pile, OK
        with self.assertRaises(ValidationError):
            # 5e operation 1 FCFA -> cumul 100 001 -> rejet
            self._make_movement(1, 7).save()

    def test_weekly_cap_resets_across_iso_weeks(self):
        # 5 mai (W19) cumul 40k, puis 12 mai (W20) doit recommencer a 0
        self._make_movement(40000, 5).save()
        self._make_movement(40000, 12).save()  # autre semaine ISO -> OK


class ChartOfAccountsViewTests(TestCase):
    """Smoke test plan comptable SYCEBNL : route 200 + comptes de liaison rendus."""

    @classmethod
    def setUpTestData(cls):
        from apps.finance.models import ChartOfAccount

        cls.parent = ChartOfAccount.objects.create(
            code="181",
            name="Comptes de liaison projets EVE",
            class_number=1,
        )
        cls.liaison = ChartOfAccount.objects.create(
            code="181.10",
            name="Liaison Test Project",
            class_number=1,
            parent=cls.parent,
            is_liaison=True,
        )
        cls.account_bank = ChartOfAccount.objects.create(
            code="512.10",
            name="Banque test",
            class_number=5,
        )

    def setUp(self):
        self.client = Client()

    def test_chart_of_accounts_returns_200(self):
        response = self.client.get("/finance/plan-comptable/")
        self.assertEqual(response.status_code, 200)

    def test_chart_of_accounts_lists_liaison_account(self):
        response = self.client.get("/finance/plan-comptable/")
        self.assertContains(response, "181.10")
        self.assertContains(response, "Liaison Test Project")
        self.assertContains(response, "LIAISON")


class BankMovementUniqueConstraintTests(TestCase):
    def test_duplicate_movement_is_rejected(self):
        from datetime import date
        from django.db import IntegrityError, transaction
        from apps.finance.models import BankAccount, BankMovement

        account = BankAccount.objects.create(name="Test BA", bank_name="X")
        BankMovement.objects.create(
            account=account,
            date_operation=date(2026, 1, 15),
            reference="REF-1",
            label="Mouvement test",
            debit=Decimal("100.00"),
            credit=Decimal("0"),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BankMovement.objects.create(
                    account=account,
                    date_operation=date(2026, 1, 15),
                    reference="REF-1",
                    label="Mouvement test (doublon)",
                    debit=Decimal("100.00"),
                    credit=Decimal("0"),
                )
