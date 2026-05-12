from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.hr.models import Contract, Employee, WorkforceGeography, WorkforceSnapshot
from apps.hr.reference_data import (
    RH_REFERENCE_COMMUNES,
    RH_REFERENCE_GEOGRAPHIES,
    RH_REFERENCE_PERSONNEL,
    RH_REFERENCE_PROJECTS,
    RH_REFERENCE_SNAPSHOT,
    RH_REFERENCE_SOURCE,
)
from apps.projects.models import Donor, Project, ProjectTeam
from apps.references.models import Commune, ContractType, SystemSetting


class Command(BaseCommand):
    help = "Importe le referentiel RH EVE 2025-2026 dans la base RH."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Import du referentiel RH EVE 2025-2026...")

        communes = self._seed_communes()
        contract_types = self._seed_contract_types()
        donors = self._seed_donors()
        projects = self._seed_projects(donors)
        snapshot = self._seed_snapshot()
        self._seed_geographies(snapshot)
        employees = self._seed_employees(communes)
        self._seed_contracts(employees, projects, contract_types)
        self._seed_project_assignments(employees, projects)
        self._seed_settings(snapshot)

        self.stdout.write(
            self.style.SUCCESS(
                f"Referentiel RH importe: {len(employees)} personnes nominatifs et 1 snapshot RH."
            )
        )

    def _seed_communes(self):
        result = {}
        for item in RH_REFERENCE_COMMUNES:
            commune, _ = Commune.objects.update_or_create(
                code=item["code"],
                defaults={
                    "name": item["name"],
                    "department": item["department"],
                    "region": item["region"],
                    "is_intervention_zone": True,
                },
            )
            result[item["code"]] = commune
        return result

    def _seed_contract_types(self):
        specs = {
            "SALARIE_REF": {
                "name": "Salarie / contractuel (referentiel RH)",
                "max_duration_months": None,
                "is_permanent": False,
            },
            "PRESTATION": {
                "name": "Contrat de prestation",
                "max_duration_months": 12,
                "is_permanent": False,
            },
            "CONSULTANCE": {
                "name": "Contrat de consultance",
                "max_duration_months": 12,
                "is_permanent": False,
            },
        }
        result = {}
        for code, defaults in specs.items():
            contract_type, _ = ContractType.objects.update_or_create(code=code, defaults=defaults)
            result[code] = contract_type
        return result

    def _seed_donors(self):
        specs = {
            "Fondation Nous-Cims": {"short_name": "Nous-Cims", "donor_type": Donor.DonorType.FOUNDATION},
            "DGPSN": {"short_name": "DGPSN", "donor_type": Donor.DonorType.GOVERNMENT},
            "OXFAM": {"short_name": "OXFAM", "donor_type": Donor.DonorType.FOUNDATION},
        }
        result = {}
        for name, defaults in specs.items():
            donor, _ = Donor.objects.update_or_create(name=name, defaults=defaults)
            result[name] = donor
        return result

    def _seed_projects(self, donors):
        result = {}
        for item in RH_REFERENCE_PROJECTS:
            project, _ = Project.objects.update_or_create(
                code=item["code"],
                defaults={
                    "title": item["title"],
                    "short_title": item["short_title"],
                    "primary_donor": donors[item["partner_name"]],
                    "total_budget": None,
                    "currency": "XOF",
                    "start_date": date(2025, 1, 1),
                    "end_date": date(2026, 12, 31),
                    "status": Project.Status.ACTIVE,
                    "sector": item["sector"],
                    "target_beneficiaries": item["target_beneficiaries"],
                    "progress_percentage": 0,
                },
            )
            result[item["code"]] = project
        return result

    def _seed_snapshot(self):
        snapshot, _ = WorkforceSnapshot.objects.update_or_create(
            reference_code=RH_REFERENCE_SNAPSHOT["reference_code"],
            defaults={
                "title": RH_REFERENCE_SNAPSHOT["title"],
                "scope": RH_REFERENCE_SNAPSHOT["scope"],
                "source_date": RH_REFERENCE_SNAPSHOT["source_date"],
                "reported_total_staff": RH_REFERENCE_SNAPSHOT["reported_total_staff"],
                "detailed_total_staff": RH_REFERENCE_SNAPSHOT["detailed_total_staff"],
                "salaried_and_contractual_count": RH_REFERENCE_SNAPSHOT["salaried_and_contractual_count"],
                "service_provider_count": RH_REFERENCE_SNAPSHOT["service_provider_count"],
                "consultant_count": RH_REFERENCE_SNAPSHOT["consultant_count"],
                "relay_worker_count": RH_REFERENCE_SNAPSHOT["relay_worker_count"],
                "icp_count": RH_REFERENCE_SNAPSHOT["icp_count"],
                "health_post_count": RH_REFERENCE_SNAPSHOT["health_post_count"],
                "companion_count": RH_REFERENCE_SNAPSHOT["companion_count"],
                "community_supervisor_count": RH_REFERENCE_SNAPSHOT["community_supervisor_count"],
                "covered_regions_count": RH_REFERENCE_SNAPSHOT["covered_regions_count"],
                "notes": RH_REFERENCE_SNAPSHOT["notes"],
            },
        )
        return snapshot

    def _seed_geographies(self, snapshot):
        for item in RH_REFERENCE_GEOGRAPHIES:
            WorkforceGeography.objects.update_or_create(
                snapshot=snapshot,
                label=item["label"],
                defaults={
                    "sort_order": item["sort_order"],
                    "relay_worker_count": item["relay_worker_count"],
                    "support_structures": item["support_structures"],
                    "beneficiary_scope": item["beneficiary_scope"],
                },
            )

    def _seed_employees(self, communes):
        result = {}
        for item in RH_REFERENCE_PERSONNEL:
            employee, _ = Employee.objects.update_or_create(
                matricule=item["matricule"],
                defaults={
                    "first_name": item["first_name"],
                    "last_name": item["last_name"],
                    "position": item["position"],
                    "department": item["department"],
                    "workforce_category": item["category"],
                    "organizational_unit": item["organizational_unit"],
                    "assignment_label": item["assignment_label"],
                    "reference_source": RH_REFERENCE_SOURCE,
                    "commune": communes.get(item["commune_code"]),
                    "hire_date": date(2025, 1, 1),
                    "status": Employee.Status.ACTIVE,
                    "email_professional": "",
                    "phone_primary": "",
                },
            )
            result[item["matricule"]] = employee
        return result

    def _seed_contracts(self, employees, projects, contract_types):
        category_map = {
            Employee.WorkforceCategory.SALARIED: contract_types["SALARIE_REF"],
            Employee.WorkforceCategory.SERVICE_PROVIDER: contract_types["PRESTATION"],
            Employee.WorkforceCategory.CONSULTANT: contract_types["CONSULTANCE"],
        }
        for item in RH_REFERENCE_PERSONNEL:
            employee = employees[item["matricule"]]
            project = projects.get(item.get("project_code"))
            Contract.objects.update_or_create(
                contract_number=f"{item['matricule']}-CTR",
                defaults={
                    "employee": employee,
                    "contract_type": category_map[employee.workforce_category],
                    "project": project,
                    "start_date": date(2025, 1, 1),
                    "end_date": date(2026, 12, 31),
                    "status": Contract.Status.ACTIVE,
                    "notes": f"Importe depuis {RH_REFERENCE_SOURCE}. Affectation: {employee.assignment_label}.",
                },
            )

    def _seed_project_assignments(self, employees, projects):
        for item in RH_REFERENCE_PERSONNEL:
            project_code = item.get("project_code")
            if not project_code:
                continue
            ProjectTeam.objects.get_or_create(
                project=projects[project_code],
                employee=employees[item["matricule"]],
                start_date=date(2025, 1, 1),
                defaults={
                    "role": item["position"],
                    "allocation_percentage": 100,
                },
            )

    def _seed_settings(self, snapshot):
        SystemSetting.objects.update_or_create(
            key="RH_REFERENCE_ACTIVE_CODE",
            defaults={
                "value": snapshot.reference_code,
                "description": "Code du referentiel RH actuellement injecte dans la base",
            },
        )
        SystemSetting.objects.update_or_create(
            key="RH_REFERENCE_IMPORT_SOURCE",
            defaults={
                "value": RH_REFERENCE_SOURCE,
                "description": "Source documentaire du referentiel RH importe",
            },
        )
