from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.activities.models import Activity, ActivityEvidence, ActivityLocation, ActivityReport, Beneficiary
from apps.accounts.models import Permission, Role
from apps.finance.models import BudgetLine, Commitment, Disbursement, SupportingDoc
from apps.hr.models import Contract, Employee, EmployeeDocument, Evaluation, Leave, Payslip
from apps.projects.models import Donor, Indicator, IndicatorValue, Project, ProjectDonor, ProjectLocation, ProjectTeam
from apps.references.models import BudgetCategory, Commune, ContractType, DocumentType, SystemSetting
from apps.reporting.models import Report, ReportExport, ReportTemplate


class Command(BaseCommand):
    help = "Load a coherent EVE Pilot demo dataset."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Seeding EVE Pilot demo data...")

        self._seed_settings()
        contract_types = self._seed_contract_types()
        document_types = self._seed_document_types()
        budget_categories = self._seed_budget_categories()
        communes = self._seed_communes()
        roles = self._seed_roles()
        self._seed_permissions()
        donors = self._seed_donors()
        employees = self._seed_employees(communes)
        projects = self._seed_projects(donors, employees, communes)
        self._seed_contracts(contract_types, employees, projects)
        self._seed_employee_documents(document_types, employees)
        self._seed_leaves(employees)
        self._seed_payslips(employees)
        self._seed_evaluations(employees)
        activities = self._seed_activities(projects, employees, communes)
        self._seed_activity_reports(activities, communes)
        budget_lines = self._seed_budget_lines(projects, activities, donors, budget_categories)
        self._seed_commitments_and_disbursements(budget_lines)
        self._seed_reports(projects, donors)

        self.stdout.write(self.style.SUCCESS("Demo data loaded successfully."))

    def _seed_settings(self):
        defaults = {
            "ORG_NAME": ("ONG Eau Vie Environnement", "Nom de l'organisation"),
            "DEFAULT_CURRENCY": ("XOF", "Devise principale"),
            "ANNUAL_LEAVE_DAYS": ("24", "Quota annuel de conges"),
            "COUNTRY": ("Senegal", "Pays principal"),
            "TIMEZONE": ("Africa/Dakar", "Fuseau horaire"),
        }
        for key, (value, description) in defaults.items():
            SystemSetting.objects.update_or_create(
                key=key,
                defaults={"value": value, "description": description},
            )

    def _seed_contract_types(self):
        data = {
            "CDI": ("Contrat a duree indeterminee", None, True),
            "CDD": ("Contrat a duree determinee", 24, False),
            "PRESTATION": ("Contrat de prestation", 12, False),
            "STAGE": ("Convention de stage", 12, False),
        }
        result = {}
        for code, (name, duration, permanent) in data.items():
            result[code], _ = ContractType.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "max_duration_months": duration,
                    "is_permanent": permanent,
                },
            )
        return result

    def _seed_document_types(self):
        data = {
            "CNI": ("Carte nationale d'identite", True, True),
            "CV": ("Curriculum Vitae", True, False),
            "CONTRAT": ("Contrat signe", True, True),
            "DIPLOME": ("Diplome", False, False),
        }
        result = {}
        for code, (name, required, expiry) in data.items():
            result[code], _ = DocumentType.objects.update_or_create(
                code=code,
                defaults={"name": name, "is_required": required, "expiry_tracking": expiry},
            )
        return result

    def _seed_budget_categories(self):
        data = {
            "PERSONNEL": "Personnel",
            "LOGISTIQUE": "Logistique",
            "ACTIVITES": "Activites",
            "COMMUNICATION": "Communication",
        }
        result = {}
        for code, name in data.items():
            result[code], _ = BudgetCategory.objects.update_or_create(
                code=code,
                defaults={"name": name},
            )
        return result

    def _seed_communes(self):
        data = [
            ("PIK-W", "Pikine Ouest", "Pikine", "Dakar", True),
            ("PIK-N", "Pikine Nord", "Pikine", "Dakar", True),
            ("DIA", "Diamniadio", "Rufisque", "Dakar", True),
            ("THI", "Thiaroye", "Pikine", "Dakar", True),
            ("MBO", "Mbour", "Mbour", "Thiès", False),
        ]
        result = {}
        for code, name, department, region, is_zone in data:
            result[code], _ = Commune.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "department": department,
                    "region": region,
                    "is_intervention_zone": is_zone,
                },
            )
        return result

    def _seed_roles(self):
        data = {
            "DIRECTION": "Direction EVE",
            "RAF": "Responsable Administratif et Financier",
            "CHEF_PROJET": "Chef de projet",
            "COMPTABLE": "Comptable",
            "RH_OFFICER": "RH Officer",
            "ANIMATEUR_TERRAIN": "Animateur terrain",
        }
        result = {}
        for code, name in data.items():
            result[code], _ = Role.objects.update_or_create(code=code, defaults={"name": name})
        return result

    def _seed_permissions(self):
        permissions = [
            ("dashboard.view", "dashboard"),
            ("hr.employee.view", "hr"),
            ("projects.view", "projects"),
            ("activities.report.validate", "activities"),
            ("finance.budget.view", "finance"),
            ("reports.generate", "reports"),
        ]
        for code, module in permissions:
            Permission.objects.update_or_create(code=code, defaults={"module": module})

    def _seed_donors(self):
        data = {
            "UNICEF": {"short_name": "UNICEF", "donor_type": "MULTILATERAL", "country": "International"},
            "AFD": {"short_name": "AFD", "donor_type": "BILATERAL", "country": "France"},
            "UE": {"short_name": "Union Europeenne", "donor_type": "MULTILATERAL", "country": "Union Europeenne"},
        }
        result = {}
        for name, defaults in data.items():
            result[name], _ = Donor.objects.update_or_create(name=name, defaults=defaults)
        return result

    def _seed_employees(self, communes):
        data = [
            {
                "matricule": "EVE-0001",
                "first_name": "Aly",
                "last_name": "Diop",
                "position": "Responsable Administratif et Financier",
                "department": "Administration",
                "email_professional": "aly.diop@eve.sn",
                "phone_primary": "+221770000001",
                "commune": communes["DIA"],
            },
            {
                "matricule": "EVE-0002",
                "first_name": "Fatou",
                "last_name": "Mbaye",
                "position": "Cheffe de projet",
                "department": "Programmes",
                "email_professional": "fatou.mbaye@eve.sn",
                "phone_primary": "+221770000002",
                "commune": communes["PIK-W"],
            },
            {
                "matricule": "EVE-0003",
                "first_name": "Marieme",
                "last_name": "Ba",
                "position": "Chargee Suivi-Evaluation",
                "department": "Programmes",
                "email_professional": "marieme.ba@eve.sn",
                "phone_primary": "+221770000003",
                "commune": communes["DIA"],
            },
            {
                "matricule": "EVE-0004",
                "first_name": "Ousmane",
                "last_name": "Ndiaye",
                "position": "Animateur terrain",
                "department": "Terrain",
                "email_professional": "ousmane.ndiaye@eve.sn",
                "phone_primary": "+221770000004",
                "commune": communes["PIK-N"],
            },
            {
                "matricule": "EVE-0005",
                "first_name": "Aissatou",
                "last_name": "Diallo",
                "position": "Comptable projet",
                "department": "Finances",
                "email_professional": "aissatou.diallo@eve.sn",
                "phone_primary": "+221770000005",
                "commune": communes["DIA"],
            },
        ]
        result = {}
        for item in data:
            employee, _ = Employee.objects.update_or_create(
                matricule=item["matricule"],
                defaults={
                    "first_name": item["first_name"],
                    "last_name": item["last_name"],
                    "position": item["position"],
                    "department": item["department"],
                    "email_professional": item["email_professional"],
                    "phone_primary": item["phone_primary"],
                    "commune": item["commune"],
                    "hire_date": timezone.datetime(2024, 1, 15).date(),
                    "status": Employee.Status.ACTIVE,
                },
            )
            result[item["matricule"]] = employee

        result["EVE-0002"].manager = result["EVE-0001"]
        result["EVE-0002"].save(update_fields=["manager", "updated_at"])
        result["EVE-0003"].manager = result["EVE-0002"]
        result["EVE-0003"].save(update_fields=["manager", "updated_at"])
        result["EVE-0004"].manager = result["EVE-0002"]
        result["EVE-0004"].save(update_fields=["manager", "updated_at"])
        result["EVE-0005"].manager = result["EVE-0001"]
        result["EVE-0005"].save(update_fields=["manager", "updated_at"])
        return result

    def _seed_projects(self, donors, employees, communes):
        data = [
            {
                "code": "ACEC-PIKINE-2026",
                "title": "ACEC Pikine",
                "short_title": "ACEC Pikine",
                "primary_donor": donors["UNICEF"],
                "total_budget": Decimal("184000000.00"),
                "project_manager": employees["EVE-0002"],
                "status": Project.Status.ACTIVE,
                "sector": "EAU",
                "progress_percentage": Decimal("78.00"),
                "target_beneficiaries": 10000,
                "locations": [communes["PIK-W"], communes["PIK-N"], communes["THI"]],
            },
            {
                "code": "WASH-DIAM-2026",
                "title": "WASH Diamniadio",
                "short_title": "WASH Diamniadio",
                "primary_donor": donors["AFD"],
                "total_budget": Decimal("242000000.00"),
                "project_manager": employees["EVE-0002"],
                "status": Project.Status.ACTIVE,
                "sector": "ASSAINISSEMENT",
                "progress_percentage": Decimal("62.00"),
                "target_beneficiaries": 8500,
                "locations": [communes["DIA"]],
            },
            {
                "code": "NUTRI-COM-2026",
                "title": "Nutrition Communaute",
                "short_title": "Nutrition",
                "primary_donor": donors["UE"],
                "total_budget": Decimal("96000000.00"),
                "project_manager": employees["EVE-0003"],
                "status": Project.Status.ACTIVE,
                "sector": "NUTRITION",
                "progress_percentage": Decimal("49.00"),
                "target_beneficiaries": 6200,
                "locations": [communes["PIK-W"], communes["DIA"]],
            },
        ]
        result = {}
        for item in data:
            project, _ = Project.objects.update_or_create(
                code=item["code"],
                defaults={
                    "title": item["title"],
                    "short_title": item["short_title"],
                    "primary_donor": item["primary_donor"],
                    "total_budget": item["total_budget"],
                    "currency": "XOF",
                    "start_date": timezone.datetime(2026, 1, 1).date(),
                    "end_date": timezone.datetime(2026, 12, 31).date(),
                    "project_manager": item["project_manager"],
                    "status": item["status"],
                    "sector": item["sector"],
                    "progress_percentage": item["progress_percentage"],
                    "target_beneficiaries": item["target_beneficiaries"],
                },
            )
            result[item["code"]] = project
            for commune in item["locations"]:
                ProjectLocation.objects.get_or_create(project=project, commune=commune)

        ProjectDonor.objects.get_or_create(
            project=result["ACEC-PIKINE-2026"],
            donor=donors["UNICEF"],
            defaults={"contribution_amount": Decimal("184000000.00"), "contribution_percentage": Decimal("100.00")},
        )
        ProjectDonor.objects.get_or_create(
            project=result["WASH-DIAM-2026"],
            donor=donors["AFD"],
            defaults={"contribution_amount": Decimal("242000000.00"), "contribution_percentage": Decimal("100.00")},
        )
        ProjectDonor.objects.get_or_create(
            project=result["NUTRI-COM-2026"],
            donor=donors["UE"],
            defaults={"contribution_amount": Decimal("96000000.00"), "contribution_percentage": Decimal("100.00")},
        )

        team_assignments = [
            ("ACEC-PIKINE-2026", "EVE-0002", "Cheffe de projet", Decimal("100.00")),
            ("ACEC-PIKINE-2026", "EVE-0003", "Suivi-Evaluation", Decimal("70.00")),
            ("ACEC-PIKINE-2026", "EVE-0004", "Animateur terrain", Decimal("100.00")),
            ("ACEC-PIKINE-2026", "EVE-0005", "Comptable projet", Decimal("40.00")),
            ("WASH-DIAM-2026", "EVE-0002", "Cheffe de projet", Decimal("60.00")),
            ("WASH-DIAM-2026", "EVE-0005", "Comptable projet", Decimal("30.00")),
            ("NUTRI-COM-2026", "EVE-0003", "Point focal", Decimal("80.00")),
        ]
        for project_code, employee_code, role, allocation in team_assignments:
            ProjectTeam.objects.get_or_create(
                project=result[project_code],
                employee=employees[employee_code],
                start_date=timezone.datetime(2026, 1, 1).date(),
                defaults={"role": role, "allocation_percentage": allocation},
            )

        indicators = [
            ("ACEC-PIKINE-2026", "OS1.1", "Menages avec acces ameliore a l'eau", "OUTPUT", Decimal("1200"), Decimal("840")),
            ("ACEC-PIKINE-2026", "OS2.1", "Sessions d'hygiene communautaire realisees", "OUTPUT", Decimal("60"), Decimal("41")),
            ("WASH-DIAM-2026", "IR1", "Points d'eau rehabilites", "OUTPUT", Decimal("18"), Decimal("11")),
            ("NUTRI-COM-2026", "IR2", "Meres accompagnées", "OUTCOME", Decimal("2500"), Decimal("1250")),
        ]
        for project_code, code, name, indicator_type, target, current in indicators:
            indicator, _ = Indicator.objects.update_or_create(
                project=result[project_code],
                code=code,
                defaults={
                    "name": name,
                    "indicator_type": indicator_type,
                    "unit": "nombre",
                    "target_value": target,
                    "current_value": current,
                    "frequency": Indicator.Frequency.MONTHLY,
                },
            )
            IndicatorValue.objects.get_or_create(
                indicator=indicator,
                value=current,
                defaults={
                    "period_start": timezone.datetime(2026, 4, 1).date(),
                    "period_end": timezone.datetime(2026, 4, 30).date(),
                },
            )
        return result

    def _seed_contracts(self, contract_types, employees, projects):
        contracts = [
            ("EVE-0001", "CDI", None, None, Decimal("950000"), Decimal("780000"), "ACTIF"),
            ("EVE-0002", "CDD", "ACEC-PIKINE-2026", "CTR-2026-001", Decimal("720000"), Decimal("590000"), "ACTIF"),
            ("EVE-0003", "CDD", "NUTRI-COM-2026", "CTR-2026-002", Decimal("540000"), Decimal("430000"), "ACTIF"),
            ("EVE-0004", "PRESTATION", "ACEC-PIKINE-2026", "CTR-2026-003", Decimal("320000"), Decimal("320000"), "ACTIF"),
            ("EVE-0005", "CDI", None, "CTR-2026-004", Decimal("610000"), Decimal("490000"), "ACTIF"),
        ]
        for employee_code, contract_code, project_code, number, gross, net, status in contracts:
            Contract.objects.update_or_create(
                contract_number=number or f"{employee_code}-DEFAULT",
                defaults={
                    "employee": employees[employee_code],
                    "contract_type": contract_types[contract_code],
                    "project": projects.get(project_code) if project_code else None,
                    "start_date": timezone.datetime(2026, 1, 1).date(),
                    "end_date": timezone.datetime(2026, 12, 31).date() if contract_code != "CDI" else None,
                    "gross_salary": gross,
                    "net_salary": net,
                    "status": status,
                },
            )

    def _seed_employee_documents(self, document_types, employees):
        for employee_code, employee in employees.items():
            EmployeeDocument.objects.get_or_create(
                employee=employee,
                document_type=document_types["CV"],
                title=f"CV {employee.first_name} {employee.last_name}",
                defaults={"file_url": f"/media/documents/{employee_code.lower()}_cv.pdf"},
            )
            EmployeeDocument.objects.get_or_create(
                employee=employee,
                document_type=document_types["CONTRAT"],
                title=f"Contrat {employee.matricule}",
                defaults={"file_url": f"/media/documents/{employee_code.lower()}_contract.pdf"},
            )

    def _seed_leaves(self, employees):
        Leave.objects.get_or_create(
            employee=employees["EVE-0003"],
            leave_type=Leave.LeaveType.ANNUAL,
            start_date=timezone.datetime(2026, 5, 5).date(),
            end_date=timezone.datetime(2026, 5, 9).date(),
            defaults={"days_count": Decimal("5.00"), "status": Leave.Status.PENDING, "reason": "Conge annuel"},
        )
        Leave.objects.get_or_create(
            employee=employees["EVE-0004"],
            leave_type=Leave.LeaveType.SICK,
            start_date=timezone.datetime(2026, 4, 10).date(),
            end_date=timezone.datetime(2026, 4, 11).date(),
            defaults={"days_count": Decimal("2.00"), "status": Leave.Status.APPROVED, "reason": "Repos medical"},
        )

    def _seed_payslips(self, employees):
        month = 4
        year = 2026
        nets = {
            "EVE-0001": Decimal("780000"),
            "EVE-0002": Decimal("590000"),
            "EVE-0003": Decimal("430000"),
            "EVE-0004": Decimal("320000"),
            "EVE-0005": Decimal("490000"),
        }
        for employee_code, net in nets.items():
            Payslip.objects.update_or_create(
                employee=employees[employee_code],
                period_year=year,
                period_month=month,
                defaults={
                    "gross_salary": net * Decimal("1.18"),
                    "net_salary": net,
                    "ipres_amount": net * Decimal("0.05"),
                    "css_amount": net * Decimal("0.03"),
                    "ir_amount": net * Decimal("0.04"),
                    "trimf_amount": net * Decimal("0.01"),
                    "status": Payslip.Status.VALIDATED,
                },
            )

    def _seed_evaluations(self, employees):
        Evaluation.objects.update_or_create(
            employee=employees["EVE-0003"],
            evaluation_year=2025,
            defaults={
                "evaluator": employees["EVE-0002"],
                "overall_score": Decimal("8.5"),
                "status": Evaluation.Status.FINALIZED,
                "strengths": "Rigueur dans le suivi et qualite des analyses.",
                "areas_for_improvement": "Renforcer l'anticipation des besoins terrain.",
            },
        )

    def _seed_activities(self, projects, employees, communes):
        data = [
            {
                "project": projects["ACEC-PIKINE-2026"],
                "code": "ACT-001",
                "title": "Formation relais communautaires",
                "activity_type": "FORMATION",
                "start": timezone.datetime(2026, 4, 29).date(),
                "end": timezone.datetime(2026, 4, 29).date(),
                "budget": Decimal("4200000"),
                "responsible": employees["EVE-0004"],
                "status": Activity.Status.IN_PROGRESS,
                "completion_rate": Decimal("68.00"),
                "locations": [communes["PIK-W"]],
            },
            {
                "project": projects["ACEC-PIKINE-2026"],
                "code": "ACT-002",
                "title": "Mission de suivi communal",
                "activity_type": "MISSION",
                "start": timezone.datetime(2026, 5, 5).date(),
                "end": timezone.datetime(2026, 5, 5).date(),
                "budget": Decimal("1900000"),
                "responsible": employees["EVE-0002"],
                "status": Activity.Status.PLANNED,
                "completion_rate": Decimal("20.00"),
                "locations": [communes["THI"]],
            },
            {
                "project": projects["WASH-DIAM-2026"],
                "code": "ACT-003",
                "title": "Collecte de donnees WASH",
                "activity_type": "COLLECTE",
                "start": timezone.datetime(2026, 5, 2).date(),
                "end": timezone.datetime(2026, 5, 4).date(),
                "budget": Decimal("3100000"),
                "responsible": employees["EVE-0003"],
                "status": Activity.Status.PLANNED,
                "completion_rate": Decimal("12.00"),
                "locations": [communes["DIA"]],
            },
            {
                "project": projects["NUTRI-COM-2026"],
                "code": "ACT-004",
                "title": "Sensibilisation nutritionnelle",
                "activity_type": "SENSIBILISATION",
                "start": timezone.datetime(2026, 4, 18).date(),
                "end": timezone.datetime(2026, 4, 18).date(),
                "budget": Decimal("1600000"),
                "responsible": employees["EVE-0003"],
                "status": Activity.Status.COMPLETED,
                "completion_rate": Decimal("100.00"),
                "locations": [communes["PIK-W"]],
            },
        ]
        result = {}
        for item in data:
            activity, _ = Activity.objects.update_or_create(
                project=item["project"],
                code=item["code"],
                defaults={
                    "title": item["title"],
                    "activity_type": item["activity_type"],
                    "planned_start_date": item["start"],
                    "planned_end_date": item["end"],
                    "planned_budget": item["budget"],
                    "responsible": item["responsible"],
                    "status": item["status"],
                    "completion_rate": item["completion_rate"],
                },
            )
            result[item["code"]] = activity
            for commune in item["locations"]:
                ActivityLocation.objects.get_or_create(activity=activity, commune=commune)
        return result

    def _seed_activity_reports(self, activities, communes):
        report, _ = ActivityReport.objects.update_or_create(
            activity=activities["ACT-004"],
            report_date=timezone.datetime(2026, 4, 18).date(),
            defaults={
                "actual_location": "Centre communautaire Pikine Ouest",
                "commune": communes["PIK-W"],
                "participants_count": 46,
                "male_count": 11,
                "female_count": 29,
                "children_count": 6,
                "narrative": "Bonne mobilisation communautaire et forte participation des femmes leaders.",
                "validation_status": ActivityReport.ValidationStatus.VALIDATED,
            },
        )
        ActivityEvidence.objects.get_or_create(
            activity_report=report,
            evidence_type=ActivityEvidence.EvidenceType.PHOTO,
            caption="Photo de groupe en fin de session",
            defaults={"file_url": "/media/evidences/act004-photo1.jpg"},
        )
        Beneficiary.objects.get_or_create(
            activity_report=report,
            first_name="Awa",
            last_name="Sow",
            defaults={"gender": Beneficiary.Gender.FEMALE, "age": 34, "commune": communes["PIK-W"]},
        )

    def _seed_budget_lines(self, projects, activities, donors, budget_categories):
        data = [
            ("ACEC-PIKINE-2026", "PERSONNEL", None, "UNICEF", "BL-001", "Personnel terrain", Decimal("48000000"), 2026),
            ("ACEC-PIKINE-2026", "ACTIVITES", "ACT-001", "UNICEF", "BL-002", "Ateliers communautaires", Decimal("26000000"), 2026),
            ("ACEC-PIKINE-2026", "LOGISTIQUE", "ACT-002", "UNICEF", "BL-003", "Transport et logistique", Decimal("18000000"), 2026),
            ("WASH-DIAM-2026", "ACTIVITES", "ACT-003", "AFD", "BL-004", "Collecte et supervision WASH", Decimal("35000000"), 2026),
            ("NUTRI-COM-2026", "COMMUNICATION", "ACT-004", "UE", "BL-005", "Supports de sensibilisation", Decimal("7000000"), 2026),
        ]
        result = {}
        for project_code, category_code, activity_code, donor_name, code, description, planned_amount, year in data:
            line, _ = BudgetLine.objects.update_or_create(
                code=code,
                project=projects[project_code],
                defaults={
                    "category": budget_categories[category_code],
                    "activity": activities.get(activity_code) if activity_code else None,
                    "donor": donors[donor_name],
                    "description": description,
                    "planned_amount": planned_amount,
                    "committed_amount": planned_amount * Decimal("0.72"),
                    "disbursed_amount": planned_amount * Decimal("0.64"),
                    "fiscal_year": year,
                },
            )
            result[code] = line
        return result

    def _seed_commitments_and_disbursements(self, budget_lines):
        commitment_specs = [
            ("BL-002", "BC-2026-019", "BON_COMMANDE", "Fournitures atelier Pikine", Decimal("4200000")),
            ("BL-003", "CTR-2026-004", "CONTRAT_FOURNISSEUR", "Location vehicule mission terrain", Decimal("8900000")),
            ("BL-005", "BC-2026-021", "BON_COMMANDE", "Impression supports nutrition", Decimal("1100000")),
        ]
        for budget_code, number, commitment_type, supplier_name, amount in commitment_specs:
            commitment, _ = Commitment.objects.update_or_create(
                commitment_number=number,
                defaults={
                    "budget_line": budget_lines[budget_code],
                    "commitment_type": commitment_type,
                    "supplier_name": supplier_name,
                    "amount": amount,
                    "commitment_date": timezone.datetime(2026, 4, 20).date(),
                    "status": Commitment.Status.IN_PROGRESS,
                },
            )
            disbursement, _ = Disbursement.objects.update_or_create(
                payment_number=f"PAY-{number}",
                defaults={
                    "commitment": commitment,
                    "budget_line": budget_lines[budget_code],
                    "payment_date": timezone.datetime(2026, 4, 24).date(),
                    "amount": amount * Decimal("0.8"),
                    "payment_method": Disbursement.PaymentMethod.TRANSFER,
                    "beneficiary_name": supplier_name,
                    "status": Disbursement.Status.VALIDATED,
                },
            )
            SupportingDoc.objects.get_or_create(
                disbursement=disbursement,
                commitment=commitment,
                document_number=f"DOC-{number}",
                defaults={
                    "document_type": SupportingDoc.DocumentType.INVOICE,
                    "amount": disbursement.amount,
                    "file_url": f"/media/supporting_docs/{number.lower()}.pdf",
                },
            )

    def _seed_reports(self, projects, donors):
        donor_template, _ = ReportTemplate.objects.update_or_create(
            name="Rapport bailleur trimestriel",
            defaults={"report_type": ReportTemplate.ReportType.DONOR, "donor": donors["UNICEF"]},
        )
        direction_template, _ = ReportTemplate.objects.update_or_create(
            name="Synthese direction mensuelle",
            defaults={"report_type": ReportTemplate.ReportType.INTERNAL_MONTHLY},
        )

        report1, _ = Report.objects.update_or_create(
            title="ACEC Pikine - Rapport narratif T2",
            project=projects["ACEC-PIKINE-2026"],
            defaults={
                "template": donor_template,
                "period_start": timezone.datetime(2026, 4, 1).date(),
                "period_end": timezone.datetime(2026, 6, 30).date(),
                "status": Report.Status.DRAFT,
                "generated_file_url": "/media/reports/acec_t2.docx",
            },
        )
        ReportExport.objects.get_or_create(
            report=report1,
            export_format=ReportExport.ExportFormat.DOCX,
            file_url="/media/reports/acec_t2.docx",
        )

        report2, _ = Report.objects.update_or_create(
            title="Synthese Direction Avril 2026",
            defaults={
                "template": direction_template,
                "project": projects["WASH-DIAM-2026"],
                "period_start": timezone.datetime(2026, 4, 1).date(),
                "period_end": timezone.datetime(2026, 4, 30).date(),
                "status": Report.Status.VALIDATED,
                "generated_file_url": "/media/reports/direction_avril_2026.pdf",
            },
        )
        ReportExport.objects.get_or_create(
            report=report2,
            export_format=ReportExport.ExportFormat.PDF,
            file_url="/media/reports/direction_avril_2026.pdf",
        )
