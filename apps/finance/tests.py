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


class JournalPostingTests(TestCase):
    """Auto-generation des ecritures en partie double depuis BankMovement."""

    @classmethod
    def setUpTestData(cls):
        from datetime import date
        from apps.finance.models import BankAccount, ChartOfAccount

        cls.bank = BankAccount.objects.create(name="Banque test posting", bank_name="X")
        # Compte de tresorerie 512.x lie au compte bancaire
        cls.treasury = ChartOfAccount.objects.create(
            code="512.99", name="Banque test - tresorerie", class_number=5,
            linked_bank_account=cls.bank,
        )
        # Compte de charge contrepartie
        cls.charge = ChartOfAccount.objects.create(
            code="64.99", name="Charges de personnel test", class_number=6,
        )
        # Compte de produit contrepartie
        cls.produit = ChartOfAccount.objects.create(
            code="75.99", name="Subventions test", class_number=7,
        )

    def test_no_entry_without_contra_account(self):
        from datetime import date
        from apps.finance.models import BankMovement, JournalEntry

        m = BankMovement.objects.create(
            account=self.bank, date_operation=date(2026, 2, 1),
            reference="NOCONTRA", label="Sans imputation",
            debit=Decimal("50000"), credit=Decimal("0"),
        )
        self.assertFalse(JournalEntry.objects.filter(source_bank_movement=m).exists())

    def test_debit_movement_posts_debit_contra_credit_treasury(self):
        from datetime import date
        from apps.finance.models import BankMovement, JournalEntry

        m = BankMovement.objects.create(
            account=self.bank, date_operation=date(2026, 2, 2),
            reference="PAY-1", label="Paiement salaire",
            debit=Decimal("120000"), credit=Decimal("0"),
            contra_account=self.charge,
        )
        entry = JournalEntry.objects.get(source_bank_movement=m)
        self.assertTrue(entry.is_balanced)
        self.assertEqual(entry.total_debit, Decimal("120000"))
        charge_line = entry.lines.get(account=self.charge)
        treasury_line = entry.lines.get(account=self.treasury)
        self.assertEqual(charge_line.debit, Decimal("120000"))
        self.assertEqual(treasury_line.credit, Decimal("120000"))

    def test_credit_movement_posts_debit_treasury_credit_contra(self):
        from datetime import date
        from apps.finance.models import BankMovement, JournalEntry

        m = BankMovement.objects.create(
            account=self.bank, date_operation=date(2026, 2, 3),
            reference="SUBV-1", label="Subvention recue",
            debit=Decimal("0"), credit=Decimal("900000"),
            contra_account=self.produit,
        )
        entry = JournalEntry.objects.get(source_bank_movement=m)
        self.assertTrue(entry.is_balanced)
        treasury_line = entry.lines.get(account=self.treasury)
        produit_line = entry.lines.get(account=self.produit)
        self.assertEqual(treasury_line.debit, Decimal("900000"))
        self.assertEqual(produit_line.credit, Decimal("900000"))

    def test_changing_contra_account_regenerates_entry(self):
        from datetime import date
        from apps.finance.models import BankMovement, JournalEntry

        m = BankMovement.objects.create(
            account=self.bank, date_operation=date(2026, 2, 4),
            reference="REGEN-1", label="Mouvement a re-imputer",
            debit=Decimal("30000"), credit=Decimal("0"),
            contra_account=self.charge,
        )
        first = JournalEntry.objects.get(source_bank_movement=m)
        self.assertEqual(first.lines.get(account=self.charge).debit, Decimal("30000"))
        # Re-imputation
        m.contra_account = self.produit
        m.save()
        m.refresh_from_db()
        entry = JournalEntry.objects.get(source_bank_movement=m)
        # L'ancienne ligne sur self.charge a disparu, remplacee par self.produit
        self.assertFalse(entry.lines.filter(account=self.charge).exists())
        self.assertTrue(entry.lines.filter(account=self.produit).exists())
        self.assertTrue(entry.is_balanced)


class ExpensePublicUIPermissionsTests(TestCase):
    """L'UI expense /finance/demandes/ doit exiger un user connecte."""

    def test_anonymous_redirects_to_login(self):
        client = Client()
        response = client.get("/finance/demandes/")
        # @login_required redirect vers /connexion/?next=... (LOGIN_URL applicatif)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/connexion/", response.url)
        self.assertIn("next=/finance/demandes/", response.url)


class ExpenseRequestWorkflowTests(TestCase):
    """Workflow ExpenseRequest : SUBMITTED -> APPROVED si les 3 valideurs OK,
    REJECTED si un seul rejette."""

    @classmethod
    def setUpTestData(cls):
        from datetime import date
        from apps.accounts.models import Role
        from apps.finance.models import BudgetLine, ExpenseRequest, ExpenseValidation
        from apps.hr.models import Employee
        from apps.references.models import BudgetCategory

        cls.raf = Role.objects.create(code="RAF", name="RAF")
        cls.dp = Role.objects.create(code="DP", name="DP")
        cls.se = Role.objects.create(code="SE", name="SE")
        cls.category = BudgetCategory.objects.create(code="EX_CAT", name="Cat test")
        cls.budget_line = BudgetLine.objects.create(
            project=None,
            category=cls.category,
            code="EX-LINE-1",
            description="Ligne test",
            planned_amount=Decimal("0"),
            fiscal_year=2026,
        )
        cls.employee = Employee.objects.create(
            matricule="EX-001",
            first_name="Test",
            last_name="Requester",
            hire_date=date(2024, 1, 1),
            status=Employee.Status.ACTIVE,
        )

    def _make_submitted_request(self):
        from apps.finance.models import ExpenseRequest, ExpenseValidation

        req = ExpenseRequest.objects.create(
            project=None,
            budget_line=self.budget_line,
            requester=self.employee,
            title="Achat papier",
            motif="Reapprovisionnement papier bureau",
            requested_amount=Decimal("25000"),
            status=ExpenseRequest.Status.SUBMITTED,
        )
        # Cree les 3 validations PENDING
        for role in (self.raf, self.dp, self.se):
            ExpenseValidation.objects.create(
                request=req, role=role, decision=ExpenseValidation.Decision.PENDING
            )
        return req

    def test_request_becomes_approved_when_all_three_approve(self):
        from apps.finance.models import ExpenseRequest, ExpenseValidation

        req = self._make_submitted_request()
        for v in req.validations.all():
            v.decision = ExpenseValidation.Decision.APPROVED
            v.save()
        req.refresh_from_db()
        self.assertEqual(req.status, ExpenseRequest.Status.APPROVED)
        self.assertIsNotNone(req.decided_at)

    def test_request_becomes_rejected_on_first_rejection(self):
        from apps.finance.models import ExpenseRequest, ExpenseValidation

        req = self._make_submitted_request()
        first_validation = req.validations.first()
        first_validation.decision = ExpenseValidation.Decision.REJECTED
        first_validation.comment = "Motif insuffisant"
        first_validation.save()
        req.refresh_from_db()
        self.assertEqual(req.status, ExpenseRequest.Status.REJECTED)

    def test_request_stays_submitted_when_partial_approval(self):
        from apps.finance.models import ExpenseRequest, ExpenseValidation

        req = self._make_submitted_request()
        v = req.validations.first()
        v.decision = ExpenseValidation.Decision.APPROVED
        v.save()
        req.refresh_from_db()
        self.assertEqual(req.status, ExpenseRequest.Status.SUBMITTED)

    def test_unique_validation_per_role(self):
        from django.db import IntegrityError, transaction
        from apps.finance.models import ExpenseValidation

        req = self._make_submitted_request()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ExpenseValidation.objects.create(
                    request=req, role=self.raf, decision=ExpenseValidation.Decision.PENDING
                )


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
