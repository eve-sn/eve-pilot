"""Tests du module Activites : CRUD activite + workflow rapport terrain."""

from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase

from apps.accounts.models import Role, User, UserRole
from apps.activities.forms import ActivityForm, ActivityReportDecisionForm
from apps.activities.models import (
    Activity,
    ActivityEvidence,
    ActivityReport,
    Beneficiary,
)
from apps.projects.models import Project


class ActivitiesAuthTests(TestCase):
    """L'espace Activites exige un utilisateur connecte."""

    def test_anonymous_redirects_to_login(self):
        response = Client().get("/activites/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/connexion/", response.url)
        self.assertIn("next=/activites/", response.url)


class ActivityCrudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.project = Project.objects.create(
            code="ACT-P1",
            title="Projet test activites",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        cls.user = User.objects.create_user(
            username="agent", email="agent@eve-sn.org",
            first_name="Agent", last_name="Terrain", password="x",
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_activity_list_returns_200(self):
        response = self.client.get("/activites/")
        self.assertEqual(response.status_code, 200)

    def test_activity_create(self):
        response = self.client.post(
            "/activites/nouvelle/",
            {
                "project": self.project.id,
                "code": "A-01",
                "title": "Formation relais communautaires",
                "description": "Session de formation",
                "activity_type": "Formation",
                "planned_start_date": "2026-03-10",
                "planned_end_date": "2026-03-12",
                "planned_budget": "500000",
                "status": Activity.Status.PLANNED,
                "completion_rate": "0",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        activity = Activity.objects.get(title="Formation relais communautaires")
        self.assertEqual(activity.project_id, self.project.id)
        self.assertEqual(activity.created_by, self.user)

    def test_activity_form_rejects_end_before_start(self):
        form = ActivityForm(
            data={
                "project": self.project.id,
                "title": "Activite incoherente",
                "planned_start_date": "2026-03-12",
                "planned_end_date": "2026-03-10",
                "status": Activity.Status.PLANNED,
                "completion_rate": "0",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("planned_end_date", form.errors)

    def test_activity_detail_returns_200(self):
        activity = Activity.objects.create(
            project=self.project,
            title="Activite affichee",
            planned_start_date=date(2026, 4, 1),
        )
        response = self.client.get(f"/activites/{activity.public_uuid}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Activite affichee")


class ActivityReportWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.project = Project.objects.create(
            code="ACT-P2",
            title="Projet rapports",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        cls.activity = Activity.objects.create(
            project=cls.project,
            title="Activite a rapporter",
            planned_start_date=date(2026, 2, 1),
        )
        cls.agent = User.objects.create_user(
            username="agent2", email="agent2@eve-sn.org",
            first_name="Agent", last_name="Deux", password="x",
        )
        cls.se_role = Role.objects.create(code="SE", name="Suivi et Evaluation")
        cls.se_user = User.objects.create_user(
            username="se_user", email="se@eve-sn.org",
            first_name="Madame", last_name="SE", password="x",
        )
        UserRole.objects.create(user=cls.se_user, role=cls.se_role)

    def _make_report(self):
        return ActivityReport.objects.create(
            activity=self.activity,
            report_date=date(2026, 2, 15),
            participants_count=20,
            reported_by=self.agent,
            validation_status=ActivityReport.ValidationStatus.SUBMITTED,
        )

    def test_report_create_sets_submitted_and_reporter(self):
        client = Client()
        client.force_login(self.agent)
        response = client.post(
            f"/activites/{self.activity.public_uuid}/rapport/",
            {
                "report_date": "2026-02-20",
                "actual_location": "Pikine",
                "participants_count": "30",
                "male_count": "12",
                "female_count": "18",
                "children_count": "0",
                "narrative": "Deroulement nominal.",
                "outcomes": "",
                "challenges": "",
                "recommendations": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        report = ActivityReport.objects.get(activity=self.activity)
        self.assertEqual(report.validation_status, ActivityReport.ValidationStatus.SUBMITTED)
        self.assertEqual(report.reported_by, self.agent)

    def test_report_form_rejects_gender_sum_over_total(self):
        client = Client()
        client.force_login(self.agent)
        response = client.post(
            f"/activites/{self.activity.public_uuid}/rapport/",
            {
                "report_date": "2026-02-20",
                "participants_count": "10",
                "male_count": "8",
                "female_count": "8",
                "children_count": "0",
                "narrative": "",
                "outcomes": "",
                "challenges": "",
                "recommendations": "",
            },
        )
        self.assertEqual(response.status_code, 200)  # re-render avec erreurs
        self.assertEqual(ActivityReport.objects.count(), 0)

    def test_se_user_can_validate_report(self):
        report = self._make_report()
        client = Client()
        client.force_login(self.se_user)
        response = client.post(
            f"/activites/rapports/{report.public_uuid}/",
            {"action": "decide", "decision": ActivityReport.ValidationStatus.VALIDATED, "comment": ""},
        )
        self.assertEqual(response.status_code, 302)
        report.refresh_from_db()
        self.assertEqual(report.validation_status, ActivityReport.ValidationStatus.VALIDATED)
        self.assertEqual(report.validated_by, self.se_user)
        self.assertIsNotNone(report.validated_at)

    def test_non_se_user_cannot_validate_report(self):
        report = self._make_report()
        client = Client()
        client.force_login(self.agent)  # pas de role SE
        client.post(
            f"/activites/rapports/{report.public_uuid}/",
            {"action": "decide", "decision": ActivityReport.ValidationStatus.VALIDATED, "comment": ""},
        )
        report.refresh_from_db()
        self.assertEqual(report.validation_status, ActivityReport.ValidationStatus.SUBMITTED)

    def test_reject_requires_comment(self):
        form = ActivityReportDecisionForm(
            data={"decision": ActivityReport.ValidationStatus.REJECTED, "comment": ""}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("comment", form.errors)

    def test_add_beneficiary_to_report(self):
        report = self._make_report()
        client = Client()
        client.force_login(self.agent)
        client.post(
            f"/activites/rapports/{report.public_uuid}/",
            {
                "action": "add_beneficiary",
                "last_name": "Diop",
                "first_name": "Awa",
                "gender": "F",
                "age": "34",
                "phone": "",
                "id_card_number": "",
            },
        )
        self.assertEqual(Beneficiary.objects.filter(activity_report=report).count(), 1)

    def test_add_evidence_to_report(self):
        report = self._make_report()
        client = Client()
        client.force_login(self.agent)
        upload = SimpleUploadedFile("preuve.txt", b"contenu", content_type="text/plain")
        client.post(
            f"/activites/rapports/{report.public_uuid}/",
            {
                "action": "add_evidence",
                "evidence_type": ActivityEvidence.EvidenceType.DOCUMENT,
                "file": upload,
                "caption": "Liste de presence",
            },
        )
        self.assertEqual(ActivityEvidence.objects.filter(activity_report=report).count(), 1)


class SaintLouisImportTests(TestCase):
    """Commande d'import du cadre logique du projet Saint-Louis."""

    @classmethod
    def setUpTestData(cls):
        cls.project = Project.objects.create(
            code="NOUSCIMS-SL-2026",
            title="Saint-Louis - Gouvernance Multisectorielle (Nous-Cims)",
            start_date=date(2025, 8, 1),
            end_date=date(2028, 7, 31),
        )

    def test_import_creates_17_activities(self):
        call_command("import_activities_saint_louis")
        activities = Activity.objects.filter(project=self.project)
        self.assertEqual(activities.count(), 17)
        # Une activite par resultat est presente, dates non calendarisees.
        a = Activity.objects.get(code="SL-R1-A1")
        self.assertIsNone(a.planned_start_date)
        self.assertEqual(a.status, Activity.Status.PLANNED)
        self.assertIn("Objectif specifique 1", a.description)

    def test_import_is_idempotent(self):
        call_command("import_activities_saint_louis")
        call_command("import_activities_saint_louis")
        self.assertEqual(Activity.objects.filter(project=self.project).count(), 17)
