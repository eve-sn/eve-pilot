# -*- coding: utf-8 -*-
"""Peuple le projet AGIR2-NUT-2025 (Pikine) : equipe, communes, indicateurs.

Idempotent (get_or_create). Rejouable apres chaque wipe de base.

Cadrage (2026-07-01) :
- EQUIPE : les 8 agents sont supposes DEJA presents dans le module RH. La
  commande les retrouve par (nom + prenom) et cree seulement le lien ProjectTeam.
  Elle NE CREE PAS d'Employee (eviterait un doublon paie). Tout agent introuvable
  ou ambigu (ex. deux DIOUF) est SIGNALE, pas devine.
- INDICATEURS : premier jet QUALITATIF. target_value est obligatoire cote modele
  -> pose a 0 (sentinelle "a renseigner"). Cibles connues du logframe affichees
  en fin d'execution pour saisie ulterieure via l'admin.
- COMMUNES : le logframe cite 12 communes (districts sanitaires de Pikine ET
  Mbao) mais SANS les nommer. La liste COMMUNES est donc VIDE : la remplir avec
  les noms exacts avant de rejouer, sinon la section communes est ignoree.
"""

import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

PROJECT_CODE = "AGIR2-NUT-2025"

# Employes a GARANTIR en base s'ils manquent. Donnees officielles = bulletins de
# forfait mai/2026 (Documents officiels/Forfait honoraires *.pdf). Ces deux
# facilitateurs sont salaries mais absents de la base wipee. Cle = matricule
# (get_or_create -> pas de doublon si l'import paie les cree ensuite).
# (matricule, nom, prenom, fonction, date_entree, cni)
EMPLOYEES_TO_ENSURE = [
    ("58621-FD", "THIAO", "MOSS", "Facilitateur de district", "2026-01-01", "2613200400401"),
    ("58620-FD", "NDIAYE", "NDIARE", "Facilitatrice de district", "2026-01-01", "2781199900919"),
]

# (prenom, nom, role<=60). Nom = patronyme senegalais (FALL, SAKHO, ...).
TEAM = [
    ("Cheikh Pathe", "FALL", "Referent technique nutrition & securite alimentaire"),
    ("Serigne Souaibou", "SAKHO", "Comptable"),
    ("Adiouma", "NDIONGUE", "Facilitateur de district"),
    ("Cecile Constance", "TINE", "Facilitatrice de district"),
    ("Moss", "THIAO", "Facilitateur de district"),
    ("Ndiare", "NDIAYE", "Facilitatrice de district"),
    ("Khalifa Abacar", "DIENG", "Specialiste concertations & engagement communautaire"),
    ("El Hadji Habib Timack", "DIOUF", "Charge du suivi-evaluation"),
]

# (code, nom<=200, description, cible, unite). Libelles issus du cadre logique
# (Annexe 1). Cible = 0 quand le logframe ne la chiffre pas (R1..R6 : refuse
# d'inventer ; a renseigner via l'admin). Seuls OS et R7 sont chiffres dans le doc.
INDICATORS = [
    ("OS1", "Enfants 6-59 mois depistes et MAM/MAS pris en charge",
     "13236 enfants 6-59 mois (2% du total) depistes et enfants MAM & MAS pris en charge selon le protocole national.",
     13236, "enfants"),
    ("OS2", "Femmes organisees en initiatives communautaires mettant en oeuvre des micro-projets",
     "200 femmes regroupees au sein de 20 initiatives communautaires mettent en oeuvre 20 micro-projets de maniere satisfaisante.",
     20, "micro-projets"),
    ("R1", "Dispositifs de prevention/PEC de la malnutrition renforces (depistage, MAM recuperes, MAS references)",
     "Nombre d'enfants depistes ; % MAM recuperes en sites communautaires ; % MAS references/gueris ; % d'unites de PEC aux normes ; nb d'acteurs formes/recycles CIP ; % de meres satisfaites des services.",
     0, ""),
    ("R2", "Comportements nutritionnels ameliores (causeries educatives, VAD)",
     "Nombre de femmes/gardiennes assistant aux causeries educatives ; nb de VAD organisees ; % de meres reconnaissant une amelioration de leur comportement alimentaire.",
     0, ""),
    ("R3", "Acteurs locaux engages (rencontres CCDN/CDDN, fora de plaidoyer)",
     "Nombre de rencontres des Comites Communaux de Developpement de la Nutrition et CDDN ; nb de categories d'acteurs mobilises ; nb de fora communautaires de plaidoyer organises.",
     0, ""),
    ("R4", "Consommation d'aliments diversifies (initiatives communautaires)",
     "Nombre d'initiatives communautaires de production/consommation d'aliments riches et diversifies ; % de meres/gardiens beneficiant d'une formation.",
     0, ""),
    ("R5", "Pratiques culinaires a base de produits locaux (plats ACEC)",
     "Nombre de plats prepares par les femmes membres des ACEC ; nb de plats vendus ; % de meres reconnaissant une amelioration.",
     0, ""),
    ("R6", "Autonomisation economique des femmes ACEC (espaces, formation, revenus)",
     "Nombre d'ACEC selectionnees ; nb d'espaces amenages/fonctionnels ; nb de femmes formees ; nb d'espaces dotes d'intrants ; % de femmes au pouvoir economique renforce.",
     0, ""),
    ("R7", "Mecanismes de perennisation (fonds communaux de soutien)",
     "Nombre de fonds communaux mis en place ; % d'enfants MAM pris en charge a partir des fonds d'appui communaux (12 communes beneficiaires).",
     12, "fonds"),
]

# 12 communes du departement de Pikine (2 arrondissements), perimetre post-2021
# apres creation du departement de Keur Massar. Source : Wikipedia "Departement
# de Pikine". (nom, departement, region)
COMMUNES = [
    ("Dalifort", "Pikine", "Dakar"),
    ("Djidah Thiaroye Kaw", "Pikine", "Dakar"),
    ("Guinaw Rail Nord", "Pikine", "Dakar"),
    ("Guinaw Rail Sud", "Pikine", "Dakar"),
    ("Pikine Est", "Pikine", "Dakar"),
    ("Pikine Nord", "Pikine", "Dakar"),
    ("Pikine Ouest", "Pikine", "Dakar"),
    ("Tivaouane Diacksao", "Pikine", "Dakar"),
    ("Diamaguene Sicap Mbao", "Pikine", "Dakar"),
    ("Mbao", "Pikine", "Dakar"),
    ("Thiaroye-sur-Mer", "Pikine", "Dakar"),
    ("Thiaroye Gare", "Pikine", "Dakar"),
]


class Command(BaseCommand):
    help = "Peuple AGIR2-NUT-2025 : equipe (lien RH), indicateurs (qualitatifs), communes."

    @transaction.atomic
    def handle(self, *args, **options):
        from apps.projects.models import Project, ProjectTeam, ProjectLocation, Indicator
        from apps.hr.models import Employee
        from apps.references.models import Commune

        project = Project.objects.filter(
            code=PROJECT_CODE, is_active=True, deleted_at__isnull=True
        ).first()
        if project is None:
            self.stderr.write(f"/!\\ Projet {PROJECT_CODE} introuvable (actif). Rien fait.")
            return

        # --- Employes a garantir (facilitateurs, bulletins officiels) ---------
        self.stdout.write(self.style.MIGRATE_HEADING("Employes garantis (bulletins de forfait) :"))
        for mat, last, first, position, hire, cni in EMPLOYEES_TO_ENSURE:
            _, created = Employee.objects.get_or_create(
                matricule=mat,
                defaults={
                    "last_name": last,
                    "first_name": first,
                    "position": position,
                    "hire_date": datetime.date.fromisoformat(hire),
                    "id_card_number": cni,
                    "department": "PROJETS ET PROGRAMMES",
                    "workforce_category": Employee.WorkforceCategory.SALARIED,
                },
            )
            self.stdout.write(f"  {'+' if created else '~'} {mat} {first} {last}")

        # --- Equipe : lien (les Employee doivent exister, cf. ci-dessus) -------
        self.stdout.write(self.style.MIGRATE_HEADING("Equipe :"))
        linked = missing = 0
        for first, last, role in TEAM:
            qs = Employee.objects.filter(last_name__iexact=last)
            if qs.count() == 1:
                # Patronyme unique -> lien direct (tolerant aux accents du prenom).
                match = qs
            else:
                # Homonymes (ex. deux DIOUF) -> departager par le prenom.
                match = qs.filter(first_name__iexact=first)
                if match.count() != 1:
                    tok = first.split()[0]
                    match = qs.filter(first_name__istartswith=tok)
            if match.count() == 1:
                emp = match.first()
                _, created = ProjectTeam.objects.get_or_create(
                    project=project, employee=emp, start_date=None,
                    defaults={"role": role[:60]},
                )
                if not created:
                    ProjectTeam.objects.filter(
                        project=project, employee=emp, start_date=None
                    ).update(role=role[:60])
                linked += 1
                self.stdout.write(f"  OK  {first} {last} -> {role}")
            else:
                missing += 1
                why = "ambigu" if match.count() > 1 else "introuvable"
                self.stderr.write(f"  /!\\ {first} {last} : {why} en RH -> lien NON cree (a rattacher a la main).")
        self.stdout.write(f"  => {linked} lie(s), {missing} non trouve(s)/ambigu(s).")

        # --- Indicateurs (cibles chiffrees du logframe ; 0 = non chiffre) -----
        self.stdout.write(self.style.MIGRATE_HEADING("Indicateurs :"))
        for code, name, desc, target, unit in INDICATORS:
            obj, created = Indicator.objects.get_or_create(
                project=project, code=code,
                defaults={
                    "name": name[:200], "description": desc,
                    "target_value": target, "unit": unit,
                },
            )
            if not created:
                obj.name = name[:200]
                obj.description = desc
                obj.target_value = target
                obj.unit = unit
                obj.save(update_fields=["name", "description", "target_value", "unit"])
            flag = f"cible={target} {unit}".strip() if target else "cible a renseigner"
            self.stdout.write(f"  {'+' if created else '~'} {code} ({flag}) {name[:44]}")
        self.stdout.write("  (R1..R6 non chiffres dans le logframe -> cible 0, a renseigner via l'admin.)")

        # --- Communes / localisations -----------------------------------------
        self.stdout.write(self.style.MIGRATE_HEADING("Communes :"))
        if not COMMUNES:
            self.stdout.write("  (liste COMMUNES vide : remplir les noms exacts dans le seed puis rejouer.)")
        for i, (name, dept, region) in enumerate(COMMUNES, 1):
            commune, _ = Commune.objects.get_or_create(
                name=name,
                defaults={
                    "code": f"PIK{i:02d}",  # code unique requis (Commune.code unique)
                    "department": dept,
                    "region": region,
                    "is_intervention_zone": True,
                },
            )
            ProjectLocation.objects.get_or_create(project=project, commune=commune)
            self.stdout.write(f"  OK  {name} ({dept})")

        self.stdout.write(self.style.SUCCESS("Seed AGIR2-NUT-2025 termine."))
