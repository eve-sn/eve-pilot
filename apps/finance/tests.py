"""
Smoke tests for the Finance module : dashboard, cash-flow plan, bank accounts.
"""

from datetime import date
from decimal import Decimal

from django.core import mail
from django.test import Client, SimpleTestCase, TestCase, override_settings

from apps.finance.models import BankAccount, BudgetLine, CashflowEntry
from apps.projects.models import Donor, Project
from apps.references.models import BudgetCategory


class StatementParserAmountTests(SimpleTestCase):
    """Parsing des montants de releves bancaires (fonction pure, sans DB).

    Couvre la regression : "1.234.567" (milliers FCFA sans decimale) etait
    perdu (-> None) par l'ancienne implementation, faisant disparaitre des
    mouvements entiers du releve.
    """

    def test_parse_amount_formats(self):
        from apps.finance.statement_parser import _parse_amount

        cases = {
            # format -> Decimal attendu
            "1.234.567": Decimal("1234567"),      # FCFA milliers sans decimale (BUG)
            "1 234 567": Decimal("1234567"),      # milliers separes par espace
            "1 234 567,89": Decimal("1234567.89"),  # FR avec decimale
            "1.234.567,89": Decimal("1234567.89"),  # FR points milliers + virgule
            "1,234,567.89": Decimal("1234567.89"),  # US virgules milliers + point
            "1,234,567": Decimal("1234567"),      # US milliers sans decimale
            "1234567": Decimal("1234567"),        # brut
            "1234,50": Decimal("1234.50"),        # FR decimale simple
            "1234.50": Decimal("1234.50"),        # US decimale simple
            "1.234": Decimal("1234"),             # FCFA : 1234, pas 1.234
            "1,234": Decimal("1234"),
            "-1.234.567": Decimal("-1234567"),    # signe negatif preserve
            "-1 234,56": Decimal("-1234.56"),
        }
        for raw, expected in cases.items():
            self.assertEqual(
                _parse_amount(raw), expected,
                msg=f"_parse_amount({raw!r}) attendu {expected}",
            )

    def test_parse_amount_invalid_returns_none(self):
        from apps.finance.statement_parser import _parse_amount

        for raw in ("", "   ", "abc", "0", "0,00", "..", "-", None):
            self.assertIsNone(_parse_amount(raw), msg=f"{raw!r} devrait donner None")

    def test_attribute_direction(self):
        from apps.finance.statement_parser import _attribute_direction

        amt = Decimal("500000")
        # Sens detecte au libelle : attribution ferme.
        self.assertEqual(_attribute_direction("DEBIT", amt), (amt, None, False))
        self.assertEqual(_attribute_direction("CREDIT", amt), (None, amt, False))
        # Montant signe negatif, sens non detecte -> debit (signe fiable).
        self.assertEqual(
            _attribute_direction(None, Decimal("-500000")), (amt, None, False)
        )
        # Indecis ET non signe -> AMBIGU, on ne devine pas (avant : credit).
        self.assertEqual(_attribute_direction(None, amt), (None, None, True))


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
        from apps.accounts.models import User
        self.client = Client()
        admin = User(
            username=f"admin_{id(self)}",
            email=f"admin_{id(self)}@test.local",
            first_name="T", last_name="Admin",
            is_superuser=True, is_active=True,
        )
        admin.set_password("x")
        admin.save()
        self.client.force_login(admin)

    def test_dashboard_returns_200(self):
        response = self.client.get("/finance/")
        self.assertEqual(response.status_code, 200)

    def test_dashboard_shows_portfolio_and_revenue(self):
        response = self.client.get("/finance/")
        content = response.content.decode("utf-8")
        self.assertIn("Portefeuille projets", content)
        self.assertIn("Recettes du Budget Général", content)
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
        from apps.accounts.models import User
        self.client = Client()
        admin = User(
            username=f"admin_{id(self)}",
            email=f"admin_{id(self)}@test.local",
            first_name="T", last_name="Admin",
            is_superuser=True, is_active=True,
        )
        admin.set_password("x")
        admin.save()
        self.client.force_login(admin)

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
        self.assertContains(response, "Décaissements")
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
    """Plafonds caisse : 40 000 par operation, 200 000 par semaine ISO."""

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

    def test_weekly_cap_rejects_cumulative_over_200000(self):
        from django.core.exceptions import ValidationError

        # All five days are within the same ISO week (W19 of 2026 :
        # Monday 4 May -> Sunday 10 May).
        self._make_movement(40000, 4).save()
        self._make_movement(40000, 5).save()
        self._make_movement(40000, 6).save()
        self._make_movement(40000, 7).save()
        self._make_movement(40000, 8).save()  # cumul = 200 000 pile, OK
        with self.assertRaises(ValidationError):
            # operation suivante 1 FCFA -> cumul 200 001 -> rejet
            self._make_movement(1, 9).save()

    def test_weekly_cap_resets_across_iso_weeks(self):
        # 5 mai (W19) cumul 40k, puis 12 mai (W20) doit recommencer a 0
        self._make_movement(40000, 5).save()
        self._make_movement(40000, 12).save()  # autre semaine ISO -> OK


class FinancialStatementsTests(TestCase):
    """Compte de resultat + bilan : routes 200 et coherence comptable."""

    @classmethod
    def setUpTestData(cls):
        from datetime import date
        from apps.finance.models import (
            BankAccount, ChartOfAccount, JournalEntry, JournalLine,
        )

        bank = BankAccount.objects.create(name="Banque stmt test", bank_name="X")
        cls.treasury = ChartOfAccount.objects.create(
            code="5211.STMT", name="Tresorerie test", class_number=5,
            linked_bank_account=bank,
        )
        cls.charge = ChartOfAccount.objects.create(
            code="66.STMT", name="Charges personnel test (SYCEBNL classe 66)", class_number=6,
        )
        cls.produit = ChartOfAccount.objects.create(
            code="75.STMT", name="Subventions test", class_number=7,
        )
        # Ecriture 1 : charge 200 000 (debit charge / credit tresorerie)
        e1 = JournalEntry.objects.create(entry_date=date(2026, 1, 10), label="Charge test")
        JournalLine.objects.create(entry=e1, account=cls.charge, debit=Decimal("200000"), credit=Decimal("0"))
        JournalLine.objects.create(entry=e1, account=cls.treasury, debit=Decimal("0"), credit=Decimal("200000"))
        # Ecriture 2 : produit 500 000 (debit tresorerie / credit produit)
        e2 = JournalEntry.objects.create(entry_date=date(2026, 1, 11), label="Produit test")
        JournalLine.objects.create(entry=e2, account=cls.treasury, debit=Decimal("500000"), credit=Decimal("0"))
        JournalLine.objects.create(entry=e2, account=cls.produit, debit=Decimal("0"), credit=Decimal("500000"))

    def setUp(self):
        from apps.accounts.models import User
        self.client = Client()
        admin = User(
            username=f"admin_{id(self)}",
            email=f"admin_{id(self)}@test.local",
            first_name="T", last_name="Admin",
            is_superuser=True, is_active=True,
        )
        admin.set_password("x")
        admin.save()
        self.client.force_login(admin)

    def test_income_statement_returns_200_and_computes_result(self):
        response = self.client.get("/finance/compte-resultat/")
        self.assertEqual(response.status_code, 200)
        # produits 500 000 - charges 200 000 = resultat 300 000 (excedent)
        content = response.content.decode("utf-8")
        self.assertIn("300000", content.replace(" ", ""))
        self.assertIn("Excedent", content)

    def test_balance_sheet_returns_200_and_is_balanced(self):
        response = self.client.get("/finance/bilan/")
        self.assertEqual(response.status_code, 200)
        # tresorerie nette = -200000 + 500000 = +300000 -> actif
        # resultat +300000 -> passif. Bilan equilibre.
        self.assertContains(response, "OK")

    def test_balance_sheet_balances_actif_equals_passif(self):
        response = self.client.get("/finance/bilan/")
        self.assertTrue(response.context["is_balanced"])
        # Nouveau modele SYCEBNL : on compare total_actif (BZ) vs total_passif (DZ).
        self.assertEqual(
            response.context["total_actif"],
            response.context["total_passif"],
        )


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
        from apps.accounts.models import User
        self.client = Client()
        admin = User(
            username=f"admin_{id(self)}",
            email=f"admin_{id(self)}@test.local",
            first_name="T", last_name="Admin",
            is_superuser=True, is_active=True,
        )
        admin.set_password("x")
        admin.save()
        self.client.force_login(admin)

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
            code="5211.99", name="Banque test - tresorerie", class_number=5,
            linked_bank_account=cls.bank,
        )
        # Compte de charge contrepartie (SYCEBNL classe 66 = charges de personnel)
        cls.charge = ChartOfAccount.objects.create(
            code="66.99", name="Charges de personnel test", class_number=6,
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


class JournalPostingInvariantTests(TestCase):
    """Verifie que l'invariant de partie double est INFRANCHISSABLE :

    aucune JournalEntry desequilibree ou partielle ne doit subsister, quelle
    que soit l'anomalie (mouvement bi-directionnel, ventilation incoherente,
    compte SYCEBNL manquant en cours de generation). Ces tests negatifs
    gardent _assert_balanced + @transaction.atomic : si quelqu'un les retire,
    ils virent au rouge.
    """

    @classmethod
    def setUpTestData(cls):
        from apps.finance.models import BankAccount, ChartOfAccount
        from apps.projects.models import Project

        cls.bank = BankAccount.objects.create(name="Banque test invariant", bank_name="X")
        cls.treasury = ChartOfAccount.objects.create(
            code="5211.INV", name="Tresorerie test invariant", class_number=5,
            linked_bank_account=cls.bank,
        )
        cls.charge = ChartOfAccount.objects.create(
            code="66.INV", name="Charge test invariant", class_number=6,
        )
        # Compte 75x : declenche le split bailleur 162/462 sur un projet.
        cls.subv = ChartOfAccount.objects.create(
            code="75.INV", name="Subvention test invariant", class_number=7,
        )
        # Projet 80/20 -> le split bailleur cherchera les comptes 162 et 462,
        # VOLONTAIREMENT NON crees ici pour provoquer la PostingError.
        cls.project = Project.objects.create(
            code="INV-WB", title="Projet test invariant",
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
            investment_split_pct=Decimal("80.00"),
            administration_split_pct=Decimal("20.00"),
        )

    def test_movement_with_both_debit_and_credit_is_rejected(self):
        """Un mouvement bi-directionnel leve PostingError et ne cree rien."""
        from apps.finance.models import BankMovement, JournalEntry
        from apps.finance.posting import PostingError, post_bank_movement

        m = BankMovement.objects.create(
            account=self.bank, date_operation=date(2026, 3, 1),
            reference="BIDIR-1", label="Mouvement incoherent",
            debit=Decimal("50000"), credit=Decimal("50000"),
            contra_account=self.charge,
        )
        # Le signal a deja avale la PostingError -> aucune ecriture.
        self.assertFalse(JournalEntry.objects.filter(source_bank_movement=m).exists())
        # L'appel direct doit lever explicitement.
        with self.assertRaises(PostingError):
            post_bank_movement(m, regenerate=True)
        self.assertFalse(JournalEntry.objects.filter(source_bank_movement=m).exists())

    def test_incomplete_allocation_is_rejected(self):
        """Allocations qui ne totalisent pas le mouvement -> PostingError,
        aucune ecriture desequilibree posee (rollback atomique)."""
        from apps.finance.models import (
            BankMovement, BankMovementAllocation, JournalEntry,
        )
        from apps.finance.posting import PostingError, post_bank_movement

        m = BankMovement.objects.create(
            account=self.bank, date_operation=date(2026, 3, 2),
            reference="VENTIL-1", label="Cheque a ventiler",
            debit=Decimal("0"), credit=Decimal("1000000"),
        )
        # 700 000 != 1 000 000 : ventilation incomplete.
        BankMovementAllocation.objects.create(
            movement=m, contra_account=self.charge, amount=Decimal("400000"),
            description="Poste 1",
        )
        BankMovementAllocation.objects.create(
            movement=m, contra_account=self.charge, amount=Decimal("300000"),
            description="Poste 2",
        )
        with self.assertRaises(PostingError):
            post_bank_movement(m, regenerate=True)
        # Le rollback atomique ne laisse NI en-tete NI ligne.
        self.assertFalse(JournalEntry.objects.filter(source_bank_movement=m).exists())

    def test_missing_sycebnl_account_rolls_back_partial_entry(self):
        """Bug d'origine reproduit : la ligne tresorerie est creee AVANT le
        lookup du compte 162 (absent). Sans @transaction.atomic, une ecriture
        partielle (tresorerie seule, desequilibree, posted=True) subsistait.
        Le correctif doit garantir : PostingError + aucune ecriture du tout."""
        from apps.finance.models import BankMovement, JournalEntry, JournalLine
        from apps.finance.posting import PostingError, post_bank_movement

        m = BankMovement.objects.create(
            account=self.bank, date_operation=date(2026, 3, 3),
            reference="DISB-NO162", label="Decaissement bailleur sans compte 162",
            debit=Decimal("0"), credit=Decimal("150000000"),
            contra_account=self.subv, project=self.project,
        )
        # Le signal a avale la PostingError : aucune ecriture partielle laissee.
        self.assertFalse(JournalEntry.objects.filter(source_bank_movement=m).exists())
        # Aucune JournalLine orpheline non plus.
        self.assertFalse(JournalLine.objects.filter(account=self.treasury).exists())
        # L'appel direct leve explicitement et ne persiste rien.
        with self.assertRaises(PostingError):
            post_bank_movement(m, regenerate=True)
        self.assertFalse(JournalEntry.objects.filter(source_bank_movement=m).exists())
        self.assertFalse(JournalLine.objects.filter(account=self.treasury).exists())


class SycebnlProjectFundingTests(TestCase):
    """Mecanique SYCEBNL projets de developpement (App.8 du guide) :
    - decaissement bailleur sur compte projet -> split 162 / 462
    - charge de fonctionnement sur projet     -> neutralisation 462 / 702.
    """

    @classmethod
    def setUpTestData(cls):
        from datetime import date
        from apps.finance.models import BankAccount, ChartOfAccount
        from apps.projects.models import Project

        # Comptes SYCEBNL critiques (162, 462, 702) - requis par posting.py
        cls.fonds_invest = ChartOfAccount.objects.create(
            code="162", name="Fonds affectes aux investissements", class_number=1,
        )
        cls.fonds_admin = ChartOfAccount.objects.create(
            code="462", name="Fonds d'administration", class_number=4,
        )
        cls.quote_part = ChartOfAccount.objects.create(
            code="702", name="Quote-part fonds admin transferes", class_number=7,
        )

        cls.bank = BankAccount.objects.create(
            name="Banque test SYCEBNL projet", bank_name="X",
        )
        cls.treasury = ChartOfAccount.objects.create(
            code="5211.SYC", name="Tresorerie projet", class_number=5,
            linked_bank_account=cls.bank,
        )
        # Compte 75x subvention bailleur (declenche le split decaissement)
        cls.subv = ChartOfAccount.objects.create(
            code="75.SYC", name="Subvention bailleur test", class_number=7,
        )
        # Compte de charge de fonctionnement (declenche la neutralisation 462/702)
        cls.charge = ChartOfAccount.objects.create(
            code="66.SYC", name="Charges de personnel projet", class_number=6,
        )

        # Projet 80/20 type Banque Mondiale (App.8 du guide)
        cls.project = Project.objects.create(
            code="WB-INFRA-N", title="Projet infra WB",
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
            investment_split_pct=Decimal("80.00"),
            administration_split_pct=Decimal("20.00"),
        )
        # Projet 0/100 (EVE par defaut, tout fonctionnement)
        cls.project_admin_only = Project.objects.create(
            code="EVE-FONC-N", title="Projet 100% fonctionnement",
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
            investment_split_pct=Decimal("0.00"),
            administration_split_pct=Decimal("100.00"),
        )

    def test_donor_disbursement_splits_into_162_and_462(self):
        """App.8 SYCEBNL : decaissement 150M sur projet 80/20 ->
        162 = 120M (invest), 462 = 30M (admin)."""
        from datetime import date
        from apps.finance.models import BankMovement, JournalEntry

        m = BankMovement.objects.create(
            account=self.bank, date_operation=date(2026, 1, 5),
            reference="WB-DISB-1", label="Decaissement Banque Mondiale",
            debit=Decimal("0"), credit=Decimal("150000000"),
            contra_account=self.subv, project=self.project,
        )
        entry = JournalEntry.objects.get(source_bank_movement=m)
        self.assertTrue(entry.is_balanced)

        # 3 lignes : tresorerie debit 150M + 162 credit 120M + 462 credit 30M
        self.assertEqual(entry.lines.count(), 3)
        self.assertEqual(
            entry.lines.get(account=self.treasury).debit, Decimal("150000000")
        )
        self.assertEqual(
            entry.lines.get(account=self.fonds_invest).credit, Decimal("120000000")
        )
        self.assertEqual(
            entry.lines.get(account=self.fonds_admin).credit, Decimal("30000000")
        )
        # Le compte 75x subvention n'apparait PAS (remplace par 162/462)
        self.assertFalse(entry.lines.filter(account=self.subv).exists())

    def test_donor_disbursement_100pct_admin_skips_162_line(self):
        """Projet 0/100 : pas de ligne 162, tout passe en 462."""
        from datetime import date
        from apps.finance.models import BankMovement, JournalEntry

        m = BankMovement.objects.create(
            account=self.bank, date_operation=date(2026, 1, 10),
            reference="EVE-DISB-1", label="Decaissement fonctionnement",
            debit=Decimal("0"), credit=Decimal("5000000"),
            contra_account=self.subv, project=self.project_admin_only,
        )
        entry = JournalEntry.objects.get(source_bank_movement=m)
        self.assertTrue(entry.is_balanced)
        self.assertEqual(entry.lines.count(), 2)  # treasury + 462 (pas de 162)
        self.assertFalse(entry.lines.filter(account=self.fonds_invest).exists())
        self.assertEqual(
            entry.lines.get(account=self.fonds_admin).credit, Decimal("5000000")
        )

    def test_operating_charge_on_project_adds_462_702_neutralization(self):
        """App.8 SYCEBNL : charge fonctionnement 28M sur projet ->
        ecriture charge + ecriture neutralisation 462 / 702."""
        from datetime import date
        from apps.finance.models import BankMovement, JournalEntry

        m = BankMovement.objects.create(
            account=self.bank, date_operation=date(2026, 3, 15),
            reference="CHARGE-1", label="Salaires equipe projet",
            debit=Decimal("28000000"), credit=Decimal("0"),
            contra_account=self.charge, project=self.project,
        )
        entry = JournalEntry.objects.get(source_bank_movement=m)
        self.assertTrue(entry.is_balanced)

        # 4 lignes : charge debit + treasury credit + 462 debit + 702 credit
        self.assertEqual(entry.lines.count(), 4)
        self.assertEqual(
            entry.lines.get(account=self.charge).debit, Decimal("28000000")
        )
        self.assertEqual(
            entry.lines.get(account=self.treasury).credit, Decimal("28000000")
        )
        self.assertEqual(
            entry.lines.get(account=self.fonds_admin).debit, Decimal("28000000")
        )
        self.assertEqual(
            entry.lines.get(account=self.quote_part).credit, Decimal("28000000")
        )

    def test_no_sycebnl_split_without_project(self):
        """Mouvement sans projet rattache -> ecriture standard 2 lignes,
        meme avec un compte 75x ou 6x."""
        from datetime import date
        from apps.finance.models import BankMovement, JournalEntry

        m = BankMovement.objects.create(
            account=self.bank, date_operation=date(2026, 2, 1),
            reference="BG-1", label="Decaissement BG",
            debit=Decimal("0"), credit=Decimal("2000000"),
            contra_account=self.subv,
            # project=None
        )
        entry = JournalEntry.objects.get(source_bank_movement=m)
        self.assertEqual(entry.lines.count(), 2)
        self.assertTrue(entry.lines.filter(account=self.subv).exists())
        # Aucune ligne 162/462/702
        self.assertFalse(entry.lines.filter(account=self.fonds_invest).exists())
        self.assertFalse(entry.lines.filter(account=self.fonds_admin).exists())
        self.assertFalse(entry.lines.filter(account=self.quote_part).exists())

    def test_immobilisation_charge_on_project_no_neutralization(self):
        """Acquisition d'immo (classe 2) sur projet : pas de 462/702.
        L'extourne fonds invest se fait en cloture (App.8 page 20)."""
        from datetime import date
        from apps.finance.models import BankMovement, JournalEntry, ChartOfAccount

        immo = ChartOfAccount.objects.create(
            code="2442.SYC", name="Materiel informatique test", class_number=2,
        )
        m = BankMovement.objects.create(
            account=self.bank, date_operation=date(2026, 2, 10),
            reference="ACHAT-PC", label="Achat ordinateurs projet",
            debit=Decimal("5000000"), credit=Decimal("0"),
            contra_account=immo, project=self.project,
        )
        entry = JournalEntry.objects.get(source_bank_movement=m)
        self.assertEqual(entry.lines.count(), 2)  # pas de neutralisation
        self.assertFalse(entry.lines.filter(account=self.fonds_admin).exists())
        self.assertFalse(entry.lines.filter(account=self.quote_part).exists())


class FinancialStatementsSycebnlTests(TestCase):
    """Etats financiers au format officiel SYCEBNL (REF AA/CA/XA/FA).

    Scenario minimal :
      - 2 comptes bancaires (5211.x) avec ouvertures
      - 1 charge salaires (6611)
      - 1 produit subvention exploitation (71)
      - 1 acquisition immobilisation (244)
    Verifie que les lignes officielles sortent au bon endroit.
    """

    @classmethod
    def setUpTestData(cls):
        from datetime import date
        from apps.finance.models import (
            BankAccount, ChartOfAccount, JournalEntry, JournalLine,
        )

        # Comptes SYCEBNL essentiels
        cls.bank = BankAccount.objects.create(name="Banque FE test", bank_name="X")
        cls.treasury = ChartOfAccount.objects.create(
            code="5211.FE", name="Tresorerie test", class_number=5,
            linked_bank_account=cls.bank,
        )
        cls.charge_salaires = ChartOfAccount.objects.create(
            code="6611", name="Salaires", class_number=6,
        )
        cls.subv = ChartOfAccount.objects.create(
            code="71", name="Subvention d'exploitation", class_number=7,
        )
        cls.immo = ChartOfAccount.objects.create(
            code="244", name="Materiel mobilier", class_number=2,
        )
        cls.fournisseur = ChartOfAccount.objects.create(
            code="481", name="Fournisseurs d'investissement", class_number=4,
        )

        # Ecriture 1 : subvention recue 5 000 000 (debit tresorerie / credit 71)
        e1 = JournalEntry.objects.create(entry_date=date(2026, 1, 5), label="Subvention test")
        JournalLine.objects.create(entry=e1, account=cls.treasury,
                                   debit=Decimal("5000000"), credit=Decimal("0"))
        JournalLine.objects.create(entry=e1, account=cls.subv,
                                   debit=Decimal("0"), credit=Decimal("5000000"))

        # Ecriture 2 : salaire paye 800 000 (debit charge / credit tresorerie)
        e2 = JournalEntry.objects.create(entry_date=date(2026, 2, 15), label="Salaire")
        JournalLine.objects.create(entry=e2, account=cls.charge_salaires,
                                   debit=Decimal("800000"), credit=Decimal("0"))
        JournalLine.objects.create(entry=e2, account=cls.treasury,
                                   debit=Decimal("0"), credit=Decimal("800000"))

        # Ecriture 3 : acquisition mobilier 1 500 000 (debit immo / credit fournisseur)
        e3 = JournalEntry.objects.create(entry_date=date(2026, 3, 1), label="Mobilier")
        JournalLine.objects.create(entry=e3, account=cls.immo,
                                   debit=Decimal("1500000"), credit=Decimal("0"))
        JournalLine.objects.create(entry=e3, account=cls.fournisseur,
                                   debit=Decimal("0"), credit=Decimal("1500000"))

    def test_balance_sheet_asset_lines(self):
        from apps.finance.financial_statements_sycebnl import (
            compute_balance_sheet_asset,
        )
        lines = compute_balance_sheet_asset()
        by_ref = {l["ref"]: l for l in lines}

        # AL Materiel mobilier = 1 500 000 (debiteur)
        self.assertEqual(by_ref["AL"]["amount"], Decimal("1500000"))
        # AH Immobilisations corporelles (subtotal) = 1 500 000
        self.assertEqual(by_ref["AH"]["amount"], Decimal("1500000"))
        # BW Banques tresorerie = 5 000 000 - 800 000 = 4 200 000 (5211.FE debiteur)
        self.assertEqual(by_ref["BW"]["amount"], Decimal("4200000"))
        # BX TOTAL TRESORERIE ACTIF = 4 200 000
        self.assertEqual(by_ref["BX"]["amount"], Decimal("4200000"))
        # AZ TOTAL ACTIF IMMOBILISE = 1 500 000
        self.assertEqual(by_ref["AZ"]["amount"], Decimal("1500000"))
        # BZ TOTAL GENERAL = AZ + BF + BX = 1 500 000 + 0 + 4 200 000 = 5 700 000
        self.assertEqual(by_ref["BZ"]["amount"], Decimal("5700000"))

    def test_balance_sheet_liability_lines_and_balance(self):
        from apps.finance.financial_statements_sycebnl import (
            compute_balance_sheet_asset, compute_balance_sheet_liability,
        )
        passif = compute_balance_sheet_liability()
        by_ref = {l["ref"]: l for l in passif}

        # DH Fournisseurs (40, 481, 488) = 1 500 000 (creditear sur 481)
        self.assertEqual(by_ref["DH"]["amount"], Decimal("1500000"))
        # CH Solde exercice = subv 5M - salaires 800K = 4 200 000 excedent
        self.assertEqual(by_ref["CH"]["amount"], Decimal("4200000"))
        # CK TOTAL FONDS PROPRES = CH = 4 200 000 (autres sont zero)
        self.assertEqual(by_ref["CK"]["amount"], Decimal("4200000"))
        # DZ TOTAL PASSIF = CK + DV (DH=1.5M) = 4 200 000 + 1 500 000 = 5 700 000
        self.assertEqual(by_ref["DZ"]["amount"], Decimal("5700000"))

        # Bilan equilibre : Actif BZ == Passif DZ
        actif = compute_balance_sheet_asset()
        by_ref_a = {l["ref"]: l for l in actif}
        self.assertEqual(by_ref_a["BZ"]["amount"], by_ref["DZ"]["amount"])

    def test_income_statement_lines(self):
        from apps.finance.financial_statements_sycebnl import (
            compute_income_statement,
        )
        lines = compute_income_statement()
        by_ref = {l["ref"]: l for l in lines}

        # RF Subventions d'exploitations = 5 000 000
        self.assertEqual(by_ref["RF"]["amount"], Decimal("5000000"))
        # TJ Charges de personnel = 800 000
        self.assertEqual(by_ref["TJ"]["amount"], Decimal("800000"))
        # XA REVENUS ACTIVITES ORDINAIRES = 5 000 000
        self.assertEqual(by_ref["XA"]["amount"], Decimal("5000000"))
        # XB CHARGES ACTIVITES ORDINAIRES = 800 000
        self.assertEqual(by_ref["XB"]["amount"], Decimal("800000"))
        # XC RESULTAT ACTIVITES ORDINAIRES = XA - XB = 4 200 000
        self.assertEqual(by_ref["XC"]["amount"], Decimal("4200000"))
        # XE SOLDE EXERCICE = XC + XD = 4 200 000
        self.assertEqual(by_ref["XE"]["amount"], Decimal("4200000"))

    def test_cash_flow_statement_lines(self):
        from apps.finance.financial_statements_sycebnl import (
            compute_cash_flow_statement,
        )
        tft = compute_cash_flow_statement(opening_treasury=Decimal("0"))
        by_ref = {l["ref"]: l for l in tft["lines"]}

        # FB Encaissement subventions exploitation = 5 000 000 (credit brut 71)
        self.assertEqual(by_ref["FB"]["amount"], Decimal("5000000"))
        # FG Decaissement personnel = 800 000 (debit brut 66)
        self.assertEqual(by_ref["FG"]["amount"], Decimal("800000"))
        # FJ Acquisitions corporelles = 1 500 000 (debit brut 22-24)
        self.assertEqual(by_ref["FJ"]["amount"], Decimal("1500000"))


class FinancialStatementsHaoBalanceTests(TestCase):
    """Garde-fou : le bilan doit rester equilibre EN PRESENCE d'operations HAO
    (classe 8). Avant correctif, le solde de l'exercice (CH) ne sommait que les
    classes 6 et 7 ; une cession d'immobilisation (charges 81 / produits 82)
    desequilibrait le bilan du montant net HAO. Ce test echoue sur l'ancien code.

    Scenario (cession avec plus-value) :
      - subvention recue 3 000 000   (tresorerie / 71)
      - acquisition immo 1 500 000   (244 / tresorerie)
      - cession, sortie VNC          (81 / 244)  -> charge HAO 1 500 000
      - cession, encaissement        (tresorerie / 82) -> produit HAO 2 000 000
    Resultat attendu = 3 000 000 (subv) + 2 000 000 (82) - 1 500 000 (81)
                     = 3 500 000, et Actif BZ == Passif DZ == 3 500 000.
    """

    @classmethod
    def setUpTestData(cls):
        from datetime import date
        from apps.finance.models import (
            BankAccount, ChartOfAccount, JournalEntry, JournalLine,
        )

        cls.bank = BankAccount.objects.create(name="Banque HAO test", bank_name="X")
        cls.treasury = ChartOfAccount.objects.create(
            code="5211.HAO", name="Tresorerie HAO", class_number=5,
            linked_bank_account=cls.bank,
        )
        cls.subv = ChartOfAccount.objects.create(
            code="71", name="Subvention d'exploitation", class_number=7,
        )
        cls.immo = ChartOfAccount.objects.create(
            code="244", name="Materiel mobilier", class_number=2,
        )
        cls.charge_hao = ChartOfAccount.objects.create(
            code="81", name="Valeurs comptables des cessions d'immobilisations",
            class_number=8,
        )
        cls.produit_hao = ChartOfAccount.objects.create(
            code="82", name="Produits des cessions d'immobilisations",
            class_number=8,
        )

        def entry(label, d, lines):
            e = JournalEntry.objects.create(entry_date=d, label=label)
            for acc, deb, cred in lines:
                JournalLine.objects.create(
                    entry=e, account=acc, debit=deb, credit=cred,
                )

        entry("Subvention", date(2026, 1, 5), [
            (cls.treasury, Decimal("3000000"), Decimal("0")),
            (cls.subv, Decimal("0"), Decimal("3000000")),
        ])
        entry("Acquisition mobilier", date(2026, 2, 1), [
            (cls.immo, Decimal("1500000"), Decimal("0")),
            (cls.treasury, Decimal("0"), Decimal("1500000")),
        ])
        entry("Cession - sortie VNC", date(2026, 3, 1), [
            (cls.charge_hao, Decimal("1500000"), Decimal("0")),
            (cls.immo, Decimal("0"), Decimal("1500000")),
        ])
        entry("Cession - encaissement", date(2026, 3, 1), [
            (cls.treasury, Decimal("2000000"), Decimal("0")),
            (cls.produit_hao, Decimal("0"), Decimal("2000000")),
        ])

    def test_hao_result_includes_class_8(self):
        from apps.finance.financial_statements_sycebnl import (
            compute_balance_sheet_liability, compute_income_statement,
        )
        passif = {l["ref"]: l for l in compute_balance_sheet_liability()}
        income = {l["ref"]: l for l in compute_income_statement()}

        # Le solde de l'exercice au bilan inclut le net HAO (+500 000).
        self.assertEqual(passif["CH"]["amount"], Decimal("3500000"))
        # ... et coincide avec le solde du compte d'exploitation (XE).
        self.assertEqual(income["XE"]["amount"], Decimal("3500000"))
        self.assertEqual(passif["CH"]["amount"], income["XE"]["amount"])

    def test_balance_sheet_balances_with_hao(self):
        from apps.finance.financial_statements_sycebnl import (
            compute_balance_sheet_asset, compute_balance_sheet_liability,
        )
        actif = {l["ref"]: l for l in compute_balance_sheet_asset()}
        passif = {l["ref"]: l for l in compute_balance_sheet_liability()}

        # Actif = tresorerie 3 500 000 (immo nette = 0 apres cession).
        self.assertEqual(actif["BZ"]["amount"], Decimal("3500000"))
        # Bilan equilibre malgre l'operation HAO.
        self.assertEqual(actif["BZ"]["amount"], passif["DZ"]["amount"])


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


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="EVE Pilot <no-reply@eve-sn.org>",
    SITE_BASE_URL="http://testserver",
)
class ExpenseNotificationTests(TestCase):
    """Notifications email du workflow de demande de depense."""

    @classmethod
    def setUpTestData(cls):
        from apps.accounts.models import Role, User, UserRole
        from apps.finance.models import BudgetLine, ExpenseRequest, ExpenseValidation
        from apps.hr.models import Employee

        cls.raf = Role.objects.create(code="RAF", name="RAF")
        cls.dp = Role.objects.create(code="DP", name="DP")
        cls.se = Role.objects.create(code="SE", name="SE")
        cls.category = BudgetCategory.objects.create(code="NOTIF_CAT", name="Cat notif")
        cls.budget_line = BudgetLine.objects.create(
            project=None,
            category=cls.category,
            code="NOTIF-LINE-1",
            description="Ligne notif",
            planned_amount=Decimal("0"),
            fiscal_year=2026,
        )
        cls.requester_employee = Employee.objects.create(
            matricule="NOTIF-001",
            first_name="Demandeur",
            last_name="Notif",
            hire_date=date(2024, 1, 1),
            status=Employee.Status.ACTIVE,
            email_professional="demandeur@eve-sn.org",
        )
        # Valideurs avec comptes User + roles
        cls.user_raf = User.objects.create_user(
            username="raf_user", email="raf@eve-sn.org",
            first_name="Le", last_name="Raf", password="x",
        )
        cls.user_dp = User.objects.create_user(
            username="dp_user", email="dp@eve-sn.org",
            first_name="Le", last_name="Dp", password="x",
        )
        cls.user_se = User.objects.create_user(
            username="se_user", email="se@eve-sn.org",
            first_name="Le", last_name="Se", password="x",
        )
        UserRole.objects.create(user=cls.user_raf, role=cls.raf)
        UserRole.objects.create(user=cls.user_dp, role=cls.dp)
        UserRole.objects.create(user=cls.user_se, role=cls.se)

    def _make_submitted_request(self):
        from apps.finance.models import ExpenseRequest, ExpenseValidation

        req = ExpenseRequest.objects.create(
            project=None,
            budget_line=self.budget_line,
            requester=self.requester_employee,
            title="Achat fournitures",
            motif="Test notification",
            requested_amount=Decimal("30000"),
            status=ExpenseRequest.Status.SUBMITTED,
        )
        for role in (self.raf, self.dp, self.se):
            ExpenseValidation.objects.create(
                request=req, role=role, decision=ExpenseValidation.Decision.PENDING
            )
        return req

    def test_notify_validators_on_submit_emails_all_three(self):
        from apps.finance.notifications import notify_validators_on_submit

        req = self._make_submitted_request()
        mail.outbox = []
        sent = notify_validators_on_submit(req)
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertCountEqual(
            msg.to, ["raf@eve-sn.org", "dp@eve-sn.org", "se@eve-sn.org"]
        )
        self.assertIn(f"DD-{req.id}", msg.subject)

    def test_notify_requester_on_decision_emails_requester(self):
        from apps.finance.models import ExpenseRequest
        from apps.finance.notifications import notify_requester_on_decision

        req = self._make_submitted_request()
        req.status = ExpenseRequest.Status.APPROVED
        req.save(update_fields=["status", "updated_at"])
        mail.outbox = []
        sent = notify_requester_on_decision(req)
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["demandeur@eve-sn.org"])
        self.assertIn("APPROUVEE", mail.outbox[0].body)

    def test_notify_requester_without_email_returns_false(self):
        from apps.finance.models import ExpenseRequest
        from apps.finance.notifications import notify_requester_on_decision
        from apps.hr.models import Employee

        no_email_emp = Employee.objects.create(
            matricule="NOTIF-002",
            first_name="Sans",
            last_name="Mail",
            hire_date=date(2024, 1, 1),
            status=Employee.Status.ACTIVE,
        )
        req = self._make_submitted_request()
        req.requester = no_email_emp
        req.status = ExpenseRequest.Status.REJECTED
        req.save(update_fields=["requester", "status", "updated_at"])
        mail.outbox = []
        sent = notify_requester_on_decision(req)
        self.assertFalse(sent)
        self.assertEqual(len(mail.outbox), 0)

    def test_submit_action_triggers_validator_notification(self):
        from apps.accounts.models import User
        from apps.finance.models import ExpenseRequest

        # Le demandeur a besoin d'un compte User lie a son Employee.
        requester_user = User.objects.create_user(
            username="demandeur_user", email="demandeur@eve-sn.org",
            first_name="Demandeur", last_name="Notif", password="x",
        )
        requester_user.employee = self.requester_employee
        requester_user.save(update_fields=["employee"])

        req = ExpenseRequest.objects.create(
            project=None,
            budget_line=self.budget_line,
            requester=self.requester_employee,
            title="Achat via UI",
            motif="Test soumission",
            requested_amount=Decimal("12000"),
            status=ExpenseRequest.Status.DRAFT,
        )
        client = Client()
        client.force_login(requester_user)
        mail.outbox = []
        response = client.post(
            f"/finance/demandes/{req.id}/", {"action": "submit"}
        )
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, ExpenseRequest.Status.SUBMITTED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f"DD-{req.id}", mail.outbox[0].subject)


class SaintLouisBudgetLinkingTests(TestCase):
    """Commande link_budget_lines_to_activities_saint_louis : prefix -> Activity."""

    @classmethod
    def setUpTestData(cls):
        from apps.activities.models import Activity

        cls.project = Project.objects.create(
            code="NOUSCIMS-SL-2026",
            title="SL test",
            start_date=date(2025, 8, 1),
            end_date=date(2028, 7, 31),
        )
        cls.category = BudgetCategory.objects.create(code="SL_TEST", name="cat test")
        # Trois activites cibles, plus une activite hors mapping.
        cls.a_r1_a2 = Activity.objects.create(
            project=cls.project, code="SL-R1-A2", title="Orientation des elus"
        )
        cls.a_r3_a1 = Activity.objects.create(
            project=cls.project, code="SL-R3-A1", title="Conventions tripartites"
        )
        cls.a_r3_a8 = Activity.objects.create(
            project=cls.project, code="SL-R3-A8", title="Prise en charge malnutris"
        )
        # 4 lignes : 3 doivent matcher, 1 reste transverse.
        cls.bl_t1 = BudgetLine.objects.create(
            project=cls.project, category=cls.category,
            code="SL-A111-T1-S1-2026", description="Theme 1 / sub 1",
            planned_amount=Decimal("100000"), fiscal_year=2026,
        )
        cls.bl_pec_mam = BudgetLine.objects.create(
            project=cls.project, category=cls.category,
            code="SL-A114-02-2026", description="PEC MAM",
            planned_amount=Decimal("1400000"), fiscal_year=2026,
        )
        cls.bl_conv = BudgetLine.objects.create(
            project=cls.project, category=cls.category,
            code="SL-A114-01-2026", description="Conventions tripartites",
            planned_amount=Decimal("3000000"), fiscal_year=2026,
        )
        cls.bl_admin = BudgetLine.objects.create(
            project=cls.project, category=cls.category,
            code="SL-A4-01-2026", description="Location bureau",
            planned_amount=Decimal("3000000"), fiscal_year=2026,
        )

    def test_linking_assigns_correct_activities(self):
        from django.core.management import call_command

        call_command("link_budget_lines_to_activities_saint_louis")
        self.bl_t1.refresh_from_db()
        self.bl_pec_mam.refresh_from_db()
        self.bl_conv.refresh_from_db()
        self.bl_admin.refresh_from_db()
        self.assertEqual(self.bl_t1.activity_id, self.a_r1_a2.id)
        self.assertEqual(self.bl_pec_mam.activity_id, self.a_r3_a8.id)
        self.assertEqual(self.bl_conv.activity_id, self.a_r3_a1.id)
        # Ligne transverse : non rattachee.
        self.assertIsNone(self.bl_admin.activity_id)

    def test_linking_is_idempotent(self):
        from django.core.management import call_command

        call_command("link_budget_lines_to_activities_saint_louis")
        call_command("link_budget_lines_to_activities_saint_louis")
        self.bl_t1.refresh_from_db()
        self.assertEqual(self.bl_t1.activity_id, self.a_r1_a2.id)


class SaintLouisBudgetAmountsImportTests(TestCase):
    """Helper _row_total et garde-fou fichier absent de l'import xls."""

    def _mock_sheet(self, rows):
        class _Sheet:
            def __init__(self, data):
                self._data = data

            def cell_value(self, row, col):
                return self._data[row][col]
        return _Sheet(rows)

    def test_row_total_uses_total_column_when_filled(self):
        from apps.finance.management.commands.import_budget_amounts_saint_louis import (
            _row_total,
        )

        row = ["", "lib", 25000.0, 6.0, 75000.0, "", 50000.0, "", "", "", 125000.0]
        sheet = self._mock_sheet([row])
        self.assertEqual(_row_total(sheet, 0), Decimal("125000.0"))

    def test_row_total_falls_back_to_annual_sum_when_total_empty(self):
        from apps.finance.management.commands.import_budget_amounts_saint_louis import (
            _row_total,
        )

        # Cas A.1.5/1 : col TOTAL vide, seule ANNEE 1 renseignee.
        row = ["", "lib", 100000.0, 1.0, 100000.0, "", "", "", "", "", ""]
        sheet = self._mock_sheet([row])
        self.assertEqual(_row_total(sheet, 0), Decimal("100000.0"))

    def test_row_total_returns_none_when_all_empty(self):
        from apps.finance.management.commands.import_budget_amounts_saint_louis import (
            _row_total,
        )

        row = ["", "header sans montant", "", "", "", "", "", "", "", "", ""]
        sheet = self._mock_sheet([row])
        self.assertIsNone(_row_total(sheet, 0))

    def test_command_fails_clean_when_xls_missing(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError

        Project.objects.create(
            code="NOUSCIMS-SL-2026", title="SL",
            start_date=date(2025, 8, 1), end_date=date(2028, 7, 31),
        )
        with self.assertRaises(CommandError):
            call_command(
                "import_budget_amounts_saint_louis",
                file="/tmp/this-file-does-not-exist-xyz.xls",
            )


class SupplierAccountsDistinctTests(TestCase):
    """Garde-fou Phase 0 bascule engagement : 401 (fournisseurs d'exploitation)
    et 4812 (fournisseurs d'investissement) DOIVENT rester des comptes
    distincts et actifs.

    La migration 0016_remap_to_official_sycebnl avait fusionne 401 -> 481 sur
    une premisse fausse ('le plan officiel n'a pas de 40x ordinaire'). Le guide
    SYCEBNL projets de developpement distingue pourtant l'engagement des charges
    (Dr 6x / Cr 401, Section 2.2) de l'engagement des immobilisations
    (Dr 2 / Cr 481, Section 2.3). Ce test echoue si une future modification
    re-fusionne les deux, ce qui casserait la comptabilite d'engagement.
    """

    def test_seed_keeps_401_and_4812_distinct_and_active(self):
        from io import StringIO
        from django.core.management import call_command
        from apps.finance.models import ChartOfAccount

        call_command("seed_chart_of_accounts", stdout=StringIO())

        exploitation = ChartOfAccount.objects.filter(
            code="401", is_active=True, deleted_at__isnull=True
        ).first()
        investissement = ChartOfAccount.objects.filter(
            code="4812", is_active=True, deleted_at__isnull=True
        ).first()

        self.assertIsNotNone(
            exploitation,
            "401 'Fournisseurs - exploitation' doit etre seede et actif "
            "(credite a l'engagement des charges).",
        )
        self.assertIsNotNone(
            investissement,
            "4812 'Fournisseurs d'investissement' doit etre seede et actif "
            "(credite a l'engagement des immobilisations).",
        )
        # Distinction non negociable : deux comptes de tiers separes.
        self.assertNotEqual(exploitation.pk, investissement.pk)
        self.assertEqual(exploitation.class_number, 4)
        self.assertEqual(investissement.class_number, 4)


class SupplierAuxiliaryLedgerTests(TestCase):
    """Phase 1 bascule engagement : master fournisseurs + auxiliaire 401.x."""

    @classmethod
    def setUpTestData(cls):
        from apps.finance.models import ChartOfAccount

        # Parent 401 requis pour rattacher les sous-comptes auxiliaires.
        cls.parent_401 = ChartOfAccount.objects.create(
            code="401", name="Fournisseurs - exploitation", class_number=4,
        )

    def test_supplier_autocreates_linked_401_subaccount(self):
        from apps.finance.models import ChartOfAccount, Supplier

        supplier = Supplier.objects.create(name="SODISEN SARL")

        self.assertEqual(supplier.code, "F001")
        account = ChartOfAccount.objects.filter(code="401.F001").first()
        self.assertIsNotNone(account, "le sous-compte auxiliaire 401.F001 doit etre cree")
        self.assertEqual(account.class_number, 4)
        self.assertEqual(account.parent_id, self.parent_401.pk)
        self.assertEqual(account.linked_supplier_id, supplier.pk)
        # La propriete chart_account retrouve bien le compte.
        self.assertEqual(supplier.chart_account.pk, account.pk)

    def test_supplier_code_autoincrements(self):
        from apps.finance.models import Supplier

        s1 = Supplier.objects.create(name="Fournisseur A")
        s2 = Supplier.objects.create(name="Fournisseur B")
        self.assertEqual(s1.code, "F001")
        self.assertEqual(s2.code, "F002")

    def test_explicit_code_is_respected(self):
        from apps.finance.models import ChartOfAccount, Supplier

        supplier = Supplier.objects.create(code="F042", name="Fournisseur impose")
        self.assertEqual(supplier.code, "F042")
        self.assertTrue(ChartOfAccount.objects.filter(code="401.F042").exists())

    def test_resolve_charge_account_inherits_from_category_then_override(self):
        from datetime import date
        from apps.finance.models import BudgetLine, ChartOfAccount, Commitment
        from apps.references.models import BudgetCategory

        charge_6221 = ChartOfAccount.objects.create(
            code="6221", name="Location de batiments", class_number=6,
        )
        charge_6582 = ChartOfAccount.objects.create(
            code="6582", name="Frais de reception", class_number=6,
        )
        category = BudgetCategory.objects.create(
            code="LOC", name="Locations", default_charge_account=charge_6221,
        )
        line = BudgetLine.objects.create(
            category=category, description="Location salle", planned_amount=Decimal("100000"),
        )
        commitment = Commitment.objects.create(
            budget_line=line, amount=Decimal("100000"), commitment_date=date(2026, 7, 1),
        )

        # Sans charge_account explicite : herite de la categorie.
        self.assertEqual(commitment.resolve_charge_account().pk, charge_6221.pk)

        # Avec surcharge : la valeur explicite prime.
        commitment.charge_account = charge_6582
        commitment.save(update_fields=["charge_account"])
        self.assertEqual(commitment.resolve_charge_account().pk, charge_6582.pk)


class CommitmentPostingTests(TestCase):
    """Phase 2 bascule engagement : ecriture d'engagement post_commitment().

    Schema officiel (guide SYCEBNL projets de developpement, S2.2) :
      Dr 6x charge / Cr 401.x fournisseur + (si projet) Dr 462 / Cr 702.
    """

    @classmethod
    def setUpTestData(cls):
        from datetime import date
        from apps.finance.models import (
            BankAccount, BudgetLine, ChartOfAccount, Commitment, Supplier,
        )
        from apps.references.models import BudgetCategory
        from apps.projects.models import Project

        cls.parent_401 = ChartOfAccount.objects.create(
            code="401", name="Fournisseurs - exploitation", class_number=4,
        )
        cls.charge = ChartOfAccount.objects.create(
            code="6221", name="Location de batiments", class_number=6,
        )
        cls.fonds_admin = ChartOfAccount.objects.create(
            code="462", name="Fonds d'administration", class_number=4,
        )
        cls.quote_part = ChartOfAccount.objects.create(
            code="702", name="Quote-part fonds admin transferes", class_number=7,
        )
        cls.bank = BankAccount.objects.create(name="Banque ENG test", bank_name="X")
        cls.treasury = ChartOfAccount.objects.create(
            code="5211.ENG", name="Tresorerie test", class_number=5,
            linked_bank_account=cls.bank,
        )
        cls.supplier = Supplier.objects.create(name="SODISEN SARL")
        cls.category = BudgetCategory.objects.create(
            code="LOC", name="Locations", default_charge_account=cls.charge,
        )
        cls.project = Project.objects.create(
            code="ENG-PROJ", title="Projet engagement",
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        cls.line = BudgetLine.objects.create(
            category=cls.category, project=cls.project,
            description="Location salle", planned_amount=Decimal("500000"),
        )
        cls.commitment = Commitment.objects.create(
            budget_line=cls.line, amount=Decimal("300000"),
            commitment_date=date(2026, 7, 1), supplier=cls.supplier,
        )

    def _lines_by_code(self, entry):
        return {l.account.code: l for l in entry.lines.all()}

    def test_engagement_books_charge_supplier_and_neutralization(self):
        from apps.finance.posting import post_commitment

        entry = post_commitment(self.commitment)

        self.assertTrue(entry.is_balanced)
        self.assertTrue(entry.posted)
        lines = self._lines_by_code(entry)
        # Dr 6221 charge / Cr 401.<code> fournisseur
        self.assertEqual(lines["6221"].debit, Decimal("300000"))
        supplier_code = self.supplier.chart_account.code  # 401.F00x
        self.assertEqual(lines[supplier_code].credit, Decimal("300000"))
        # Neutralisation projet : Dr 462 / Cr 702
        self.assertEqual(lines["462"].debit, Decimal("300000"))
        self.assertEqual(lines["702"].credit, Decimal("300000"))

    def test_engagement_is_idempotent(self):
        from apps.finance.posting import post_commitment

        e1 = post_commitment(self.commitment)
        e2 = post_commitment(self.commitment)
        self.assertEqual(e1.pk, e2.pk)
        self.assertEqual(e1.lines.count(), 4)

    def test_engagement_without_project_skips_neutralization(self):
        from datetime import date
        from apps.finance.models import BudgetLine, Commitment
        from apps.finance.posting import post_commitment

        bg_line = BudgetLine.objects.create(
            category=self.category, project=None,
            description="Loyer BG", planned_amount=Decimal("100000"),
        )
        bg_commitment = Commitment.objects.create(
            budget_line=bg_line, amount=Decimal("80000"),
            commitment_date=date(2026, 7, 2), supplier=self.supplier,
        )
        entry = post_commitment(bg_commitment)
        codes = set(self._lines_by_code(entry))
        self.assertEqual(entry.lines.count(), 2)  # pas de 462/702 hors projet
        self.assertNotIn("462", codes)
        self.assertNotIn("702", codes)

    def test_engagement_requires_supplier_and_charge(self):
        from datetime import date
        from apps.finance.models import BudgetLine, Commitment
        from apps.finance.posting import post_commitment, PostingError
        from apps.references.models import BudgetCategory

        # Sans fournisseur -> refus.
        no_supplier = Commitment.objects.create(
            budget_line=self.line, amount=Decimal("1000"),
            commitment_date=date(2026, 7, 3),
        )
        with self.assertRaises(PostingError):
            post_commitment(no_supplier)

        # Sans compte de charge (categorie sans default) -> refus.
        empty_cat = BudgetCategory.objects.create(code="EMPTY", name="Sans compte")
        empty_line = BudgetLine.objects.create(
            category=empty_cat, project=self.project,
            description="X", planned_amount=Decimal("1000"),
        )
        no_charge = Commitment.objects.create(
            budget_line=empty_line, amount=Decimal("1000"),
            commitment_date=date(2026, 7, 3), supplier=self.supplier,
        )
        with self.assertRaises(PostingError):
            post_commitment(no_charge)

    def test_no_double_neutralization_engagement_then_payment(self):
        """LE garde-fou : engagement + paiement sur 401.x => 462/702 UNE seule fois.

        L'engagement neutralise (Dr 462 / Cr 702). Le paiement, impute sur le
        401.x (classe 4), solde le fournisseur (Dr 401.x / Cr 5211) SANS
        re-neutraliser. Total sur 462 et 702 = le montant, exactement une fois.
        """
        from datetime import date
        from apps.finance.models import BankMovement, JournalLine
        from apps.finance.posting import post_commitment, post_bank_movement
        from django.db.models import Sum

        supplier_account = self.supplier.chart_account

        # 1) Engagement.
        eng = post_commitment(self.commitment)

        # 2) Paiement : sortie bancaire imputee sur le 401.x du fournisseur.
        movement = BankMovement.objects.create(
            account=self.bank, date_operation=date(2026, 7, 10),
            label="Reglement SODISEN", debit=Decimal("300000"),
            contra_account=supplier_account, project=self.project,
        )
        pay = post_bank_movement(movement)

        # L'ecriture de paiement solde le 401.x et ne touche PAS 462/702.
        pay_codes = {l.account.code for l in pay.lines.all()}
        self.assertIn(supplier_account.code, pay_codes)
        self.assertIn("5211.ENG", pay_codes)
        self.assertNotIn("462", pay_codes)
        self.assertNotIn("702", pay_codes)

        # Cumul global 462/702 sur TOUTES les ecritures = 300000 une seule fois.
        agg_462 = JournalLine.objects.filter(account__code="462").aggregate(d=Sum("debit"))["d"]
        agg_702 = JournalLine.objects.filter(account__code="702").aggregate(c=Sum("credit"))["c"]
        self.assertEqual(agg_462, Decimal("300000"))
        self.assertEqual(agg_702, Decimal("300000"))

    def test_immobilisation_engagement_uses_481_without_neutralization(self):
        """Engagement d'une IMMOBILISATION (guide S2.3) : Dr 2x / Cr 481.x,
        SANS neutralisation 462/702 (le fonds 162 s'extourne en fin de projet).
        """
        from datetime import date
        from apps.finance.models import BudgetLine, ChartOfAccount, Commitment
        from apps.finance.posting import post_commitment

        # Parent investissement + compte d'immobilisation (classe 2).
        ChartOfAccount.objects.create(code="4812", name="Fournisseurs d'investissement", class_number=4)
        immo = ChartOfAccount.objects.create(code="2444", name="Materiel de bureau", class_number=2)

        line = BudgetLine.objects.create(
            category=self.category, project=self.project,
            description="Achat mobilier", planned_amount=Decimal("1500000"),
        )
        commitment = Commitment.objects.create(
            budget_line=line, amount=Decimal("1500000"),
            commitment_date=date(2026, 7, 5), supplier=self.supplier,
            charge_account=immo,  # surcharge : compte d'immobilisation classe 2
        )

        entry = post_commitment(commitment)
        self.assertTrue(entry.is_balanced)
        codes = {l.account.code for l in entry.lines.all()}
        # Dr 2444 immobilisation / Cr 481.<code> fournisseur d'investissement.
        self.assertIn("2444", codes)
        self.assertEqual(self.supplier.investment_account.code, f"481.{self.supplier.code}")
        self.assertIn(self.supplier.investment_account.code, codes)
        # PAS de neutralisation pour une immobilisation.
        self.assertNotIn("462", codes)
        self.assertNotIn("702", codes)
        self.assertEqual(entry.lines.count(), 2)


class CommitmentAdminActionTests(TestCase):
    """Phase 3 : l'action admin 'Comptabiliser l'engagement' declenche post_commitment."""

    def test_admin_action_posts_engagement(self):
        from datetime import date
        from django.contrib.admin.sites import AdminSite
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory
        from apps.finance.admin import CommitmentAdmin
        from apps.finance.models import (
            BudgetLine, ChartOfAccount, Commitment, JournalEntry, Supplier,
        )
        from apps.references.models import BudgetCategory
        from apps.projects.models import Project

        ChartOfAccount.objects.create(code="401", name="Fournisseurs", class_number=4)
        charge = ChartOfAccount.objects.create(code="6221", name="Location", class_number=6)
        ChartOfAccount.objects.create(code="462", name="Fonds admin", class_number=4)
        ChartOfAccount.objects.create(code="702", name="Quote-part", class_number=7)
        supplier = Supplier.objects.create(name="SODISEN")
        category = BudgetCategory.objects.create(code="LOC", name="Loc", default_charge_account=charge)
        project = Project.objects.create(
            code="P", title="P", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        line = BudgetLine.objects.create(
            category=category, project=project, description="L", planned_amount=Decimal("1000"),
        )
        commitment = Commitment.objects.create(
            budget_line=line, amount=Decimal("1000"),
            commitment_date=date(2026, 7, 1), supplier=supplier,
        )

        admin_obj = CommitmentAdmin(Commitment, AdminSite())
        request = RequestFactory().post("/")
        request.session = {}
        request._messages = FallbackStorage(request)

        admin_obj.comptabiliser_engagement(request, Commitment.objects.filter(pk=commitment.pk))

        self.assertTrue(JournalEntry.objects.filter(source_commitment=commitment).exists())


class ExpenseRequestFormRenderingTests(TestCase):
    """Non-regression : le <select budget_line> doit rendre ses <option>.

    Bug (commit 5edbba8) : ExpenseRequestForm remplacait le widget de
    budget_line par ProjectAwareSelect sans reattacher les choices -> 0 option
    rendue -> dropdown vide sur /finance/demandes/nouvelle/. Le JS de filtrage
    par data-project n'avait alors rien a filtrer.
    """

    @classmethod
    def setUpTestData(cls):
        cls.donor = Donor.objects.create(
            name="Donor Rendu", donor_type=Donor.DonorType.MULTILATERAL
        )
        cls.project = Project.objects.create(
            code="RENDER-001",
            title="Projet rendu",
            primary_donor=cls.donor,
            total_budget=Decimal("10000000.00"),
            currency="XOF",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status=Project.Status.ACTIVE,
            sector="NUTRITION",
        )
        cls.category = BudgetCategory.objects.create(
            code="RENDER_TEST", name="Rendu test"
        )
        cls.line = BudgetLine.objects.create(
            project=cls.project,
            category=cls.category,
            code="RENDER-LINE-1",
            description="Ligne active a rendre",
            planned_amount=Decimal("1000000.00"),
            currency="XOF",
            fiscal_year=2026,
        )

    def test_budget_line_select_renders_active_option(self):
        from apps.finance.forms import ExpenseRequestForm

        html = str(ExpenseRequestForm(user=None)["budget_line"])
        # Option vide ("-- Ligne budgetaire --") + la ligne active -> >= 2 options.
        self.assertGreaterEqual(
            html.count("<option"), 2,
            "Le <select budget_line> ne rend aucune option (widget vide).",
        )
        # La ligne active est presente, taguee avec le pk du projet pour le JS.
        self.assertIn(f'value="{self.line.pk}"', html)
        self.assertIn(f'data-project="{self.project.pk}"', html)

    def test_soft_deleted_budget_line_excluded(self):
        from apps.finance.forms import ExpenseRequestForm

        self.line.soft_delete()  # is_active=False, deleted_at renseigne
        html = str(ExpenseRequestForm(user=None)["budget_line"])
        # La ligne soft-deleted disparait du dropdown (.active() la filtre).
        self.assertNotIn(f'value="{self.line.pk}"', html)


class SoftDeleteAdminReadonlyTests(TestCase):
    """Le champ soft-delete deleted_at doit etre readonly sur les admins des
    TrackedModel (protection globale, cf. apps/common/admin.py) : evite qu'un
    autofill navigateur le renseigne a la creation et rende l'objet invisible.
    """

    def test_deleted_at_readonly_on_budget_line_admin(self):
        from django.contrib import admin as dj_admin
        from apps.finance.models import BudgetLine

        model_admin = dj_admin.site._registry[BudgetLine]
        self.assertIn("deleted_at", model_admin.get_readonly_fields(request=None))

    def test_deleted_at_readonly_on_project_admin(self):
        from django.contrib import admin as dj_admin
        from apps.projects.models import Project as ProjectModel

        model_admin = dj_admin.site._registry.get(ProjectModel)
        if model_admin is None:
            self.skipTest("Project non enregistre dans l'admin")
        self.assertIn("deleted_at", model_admin.get_readonly_fields(request=None))
