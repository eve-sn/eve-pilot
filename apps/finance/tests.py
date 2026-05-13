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
