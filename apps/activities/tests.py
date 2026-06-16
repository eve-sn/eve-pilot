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
        # Acces global pour passer le filtre de perimetre projet.
        cls.user.is_superuser = True
        cls.user.save(update_fields=["is_superuser"])

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
        # Acces global pour les tests de workflow rapport terrain.
        cls.agent.is_superuser = True
        cls.agent.save(update_fields=["is_superuser"])
        cls.se_role = Role.objects.create(code="SE", name="Secretaire Executif")
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


class SaintLouisCommunesAndLocationsTests(TestCase):
    """Communes manquantes et rattachement geographique des activites."""

    @classmethod
    def setUpTestData(cls):
        cls.project = Project.objects.create(
            code="NOUSCIMS-SL-2026",
            title="Saint-Louis - test",
            start_date=date(2025, 8, 1),
            end_date=date(2028, 7, 31),
        )

    def test_seed_communes_creates_four_missing(self):
        from apps.references.models import Commune

        before = Commune.objects.count()
        call_command("seed_communes_saint_louis")
        after = Commune.objects.count()
        self.assertEqual(after - before, 4)
        for name in ("Mpal", "Fass Ngom", "Gandon", "Ndiebene Gandiol"):
            self.assertTrue(Commune.objects.filter(name=name).exists())

    def test_seed_communes_is_idempotent(self):
        call_command("seed_communes_saint_louis")
        call_command("seed_communes_saint_louis")
        from apps.references.models import Commune

        self.assertEqual(
            Commune.objects.filter(
                name__in=["Mpal", "Fass Ngom", "Gandon", "Ndiebene Gandiol"]
            ).count(),
            4,
        )

    def test_seed_activity_locations_creates_53_links(self):
        from apps.activities.models import ActivityLocation
        from apps.references.models import Commune

        # Saint-Louis doit exister.
        Commune.objects.create(
            name="Saint-Louis", department="Saint-Louis", region="Saint-Louis"
        )
        call_command("seed_communes_saint_louis")
        call_command("import_activities_saint_louis")
        call_command("seed_activity_locations_saint_louis")
        self.assertEqual(
            ActivityLocation.objects.filter(
                activity__project=self.project
            ).count(),
            53,
        )

    def test_seed_activity_locations_is_idempotent(self):
        from apps.activities.models import ActivityLocation
        from apps.references.models import Commune

        Commune.objects.create(
            name="Saint-Louis", department="Saint-Louis", region="Saint-Louis"
        )
        call_command("seed_communes_saint_louis")
        call_command("import_activities_saint_louis")
        call_command("seed_activity_locations_saint_louis")
        call_command("seed_activity_locations_saint_louis")
        self.assertEqual(
            ActivityLocation.objects.filter(
                activity__project=self.project
            ).count(),
            53,
        )


class SaintLouisScheduleTests(TestCase):
    """Calage des dates et du responsable (chronogramme + organigramme)."""

    @classmethod
    def setUpTestData(cls):
        from apps.hr.models import Employee

        cls.project = Project.objects.create(
            code="NOUSCIMS-SL-2026",
            title="Saint-Louis - test",
            start_date=date(2025, 8, 1),
            end_date=date(2028, 7, 31),
        )
        # Equipe locale Saint-Louis (7 personnes, matricules existants).
        cls.team = {}
        for matricule, fname, lname in [
            ("REF-2026-005", "Cheikh Pathe", "FALL"),
            ("REF-2026-011", "Moustapha", "FALL"),
            ("REF-2026-015", "Papa Iba Mar", "FALL"),
            ("REF-2026-016", "Farma", "DIEYE"),
            ("REF-2026-020", "Alassane", "BA"),
            ("REF-2026-021", "Youssoupha", "SY"),
            ("REF-2026-022", "Rokhaya", "BA"),
        ]:
            cls.team[matricule] = Employee.objects.create(
                matricule=matricule,
                first_name=fname,
                last_name=lname,
                position="Agent terrain",
                hire_date=date(2025, 8, 1),
                status=Employee.Status.ACTIVE,
            )
        cls.chef = cls.team["REF-2026-011"]

    def test_schedule_sets_dates_and_role_based_owner(self):
        call_command("import_activities_saint_louis")
        call_command("seed_activity_schedule_saint_louis")
        # Chef de projet pilote la ceremonie de lancement.
        a = Activity.objects.get(code="SL-R1-A1")
        self.assertEqual(a.planned_start_date, date(2025, 12, 1))
        self.assertEqual(a.responsible_id, self.chef.id)
        # Formation des elus pilotee par un animateur, pas le chef.
        a_anim = Activity.objects.get(code="SL-R1-A2")
        self.assertEqual(a_anim.responsible_id, self.team["REF-2026-015"].id)
        # Formation CIP pilotee par le Point focal nutrition.
        a_cip = Activity.objects.get(code="SL-R3-A3")
        self.assertEqual(a_cip.responsible_id, self.team["REF-2026-005"].id)
        # Activite "ongoing" : end_date est NULL.
        a_ongoing = Activity.objects.get(code="SL-R1-A6")
        self.assertIsNone(a_ongoing.planned_end_date)
        # Toutes les activites du projet ont un responsable.
        without_owner = Activity.objects.filter(
            project=self.project, responsible__isnull=True
        ).count()
        self.assertEqual(without_owner, 0)

    def test_schedule_fails_when_an_employee_is_missing(self):
        from django.core.management.base import CommandError

        # Supprime un animateur : la commande doit refuser de s'executer.
        self.team["REF-2026-015"].delete()
        call_command("import_activities_saint_louis")
        with self.assertRaises(CommandError):
            call_command("seed_activity_schedule_saint_louis")


class SaintLouisTeamSeedTests(TestCase):
    """Commande seed_saint_louis_team : maj fiches + ProjectTeam."""

    @classmethod
    def setUpTestData(cls):
        from apps.hr.models import Employee

        cls.project = Project.objects.create(
            code="NOUSCIMS-SL-2026",
            title="Saint-Louis - test",
            start_date=date(2025, 8, 1),
            end_date=date(2028, 7, 31),
        )
        cls.emp = Employee.objects.create(
            matricule="REF-2026-011",
            first_name="Moustapha",
            last_name="FALL",
            position="Agent terrain",  # position generique avant maj
            hire_date=date(2025, 8, 1),
            status=Employee.Status.ACTIVE,
        )

    def test_team_seed_updates_position_and_creates_project_team(self):
        from apps.projects.models import ProjectTeam

        call_command("seed_saint_louis_team")
        self.emp.refresh_from_db()
        self.assertEqual(
            self.emp.position, "Chef de projet charge du suivi-evaluation"
        )
        self.assertEqual(self.emp.assignment_label, "Nous-Cims Saint-Louis")
        # Une entree ProjectTeam doit avoir ete creee pour cet employe.
        self.assertTrue(
            ProjectTeam.objects.filter(
                project=self.project, employee=self.emp
            ).exists()
        )

    def test_team_seed_is_idempotent(self):
        from apps.projects.models import ProjectTeam

        call_command("seed_saint_louis_team")
        call_command("seed_saint_louis_team")
        self.assertEqual(
            ProjectTeam.objects.filter(
                project=self.project, employee=self.emp
            ).count(),
            1,
        )
