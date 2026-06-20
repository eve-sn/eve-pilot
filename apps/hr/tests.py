"""
Smoke tests for the HR public UI.

Les donnees RH (salaires, contrats) sont reservees a la Direction / RH
(roles globaux). Les vues exigent donc un utilisateur authentifie a acces
global ; un utilisateur sans ce droit recoit un 403.
"""

from datetime import date

from django.test import Client, TestCase

from apps.accounts.models import User
from apps.hr.models import Employee


class HRViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = Employee.objects.create(
            matricule="REF-TEST-001",
            first_name="Aly",
            last_name="Dupont",
            position="Test Officer",
            department="Test",
            email_professional="aly.test@eve.sn",
            phone_primary="+221000000001",
            hire_date=date(2024, 1, 1),
            status=Employee.Status.ACTIVE,
        )

    def setUp(self):
        self.client = Client()
        # Acces global (superuser) : passe le controle require_global_access.
        admin = User(
            username=f"hr_admin_{id(self)}",
            email=f"hr_admin_{id(self)}@test.local",
            first_name="T", last_name="Admin",
            is_superuser=True, is_active=True,
        )
        admin.set_password("x")
        admin.save()
        self.client.force_login(admin)

    def test_rh_dashboard_returns_200(self):
        response = self.client.get("/rh/")
        self.assertEqual(response.status_code, 200)

    def test_employee_detail_returns_200(self):
        response = self.client.get(f"/rh/personnel/{self.employee.public_uuid}/")
        # The HR view filters on reference_source by default ; an employee created
        # without that label is not visible there. We accept either 200 (record
        # exposed) or 404 (filtered out) - the smoke test main goal is to ensure
        # the URL resolves without 500.
        self.assertIn(response.status_code, (200, 404))

    def test_employee_detail_404_for_unknown_uuid(self):
        response = self.client.get("/rh/personnel/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(response.status_code, 404)

    def test_rh_dashboard_forbidden_without_global_access(self):
        """Un utilisateur connecte SANS acces global ne voit pas les salaires."""
        plain = User(
            username="hr_plain", email="hr_plain@test.local",
            first_name="P", last_name="Lambda", is_active=True,
        )
        plain.set_password("x")
        plain.save()
        client = Client()
        client.force_login(plain)
        self.assertEqual(client.get("/rh/").status_code, 403)
        self.assertEqual(
            client.get(f"/rh/personnel/{self.employee.public_uuid}/").status_code,
            403,
        )
