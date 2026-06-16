"""
Seed du plan de comptes SYCEBNL EVE - racines + comptes EBNL specifiques.

Conforme au guide d'application SYCEBNL (OHADA / SYSCOHADA Revise) :
    - Classe 1 : Fonds propres EBNL (dotations, fonds affectes, fonds
        d'administration, fonds non consommes, dons et legs d'immo).
    - Classe 2 : Immobilisations (terrains, batiments, mobilier, info, auto,
        usufruit, immo destinees a la vente, amortissements).
    - Classe 4 : Tiers (fournisseurs, adherents, personnel, etat, securite
        sociale, fonds d'administration, apporteurs en nature/numeraire,
        dettes dons et legs).
    - Classe 5 : Tresorerie (521 / 5211 Banques en monnaies locales, 571
        Caisse).
    - Classe 6 : Charges - num NUMEROTATION SYSCOHADA REVISE :
        60 Achats - 61 Transports - 62 Services A - 63 Services B
        64 Impots et taxes - 65 Autres charges - 66 Charges de personnel
        67 Frais financiers - 68 Dotations aux amortissements.
    - Classe 7 : Produits - 70 Ventes/Cotisations/Quote-parts - 75 Dons et
        subventions - 78 Reprises - 79 Reprises de fonds affectes / subv.
    - Classe 8 : Engagements (818 VNC immo, 828 creances cessions).
    - Classe 9 : Contributions volontaires en nature (analytique) :
        90/91 emplois et ressources benevolat.

Les sous-comptes 181.x (liaison projets), 521.x (banques EVE), 571.x (caisses
EVE) sont generes automatiquement a partir des objets metier (Project,
BankAccount, CashRegister).

Idempotente (update_or_create par code SYCEBNL).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import BankAccount, CashRegister, ChartOfAccount
from apps.projects.models import Project


# Racines normalisees SYCEBNL. Ordre = ordre d'insertion (parent avant enfant).
# (code, name, class_number, parent_code, description)
ROOT_ACCOUNTS = [
    # ============ Classe 1 - Fonds propres et fonds dedies ============
    ("11", "Reserves et report a nouveau", 1, None, ""),
    ("1101", "Report a nouveau", 1, "11",
        "Solde des exercices anterieurs reporte au bilan d'ouverture."),
    ("1102", "Report a nouveau - resultats anterieurs", 1, "11", ""),

    ("10", "Dotations et apports des EBNL", 1, None, ""),
    ("101", "Dotations consomptibles et non consomptibles", 1, "10", ""),
    ("1015", "Dotation non consomptible sans droit de reprise", 1, "101",
        "Apports definitifs des adherents en nature ou en numeraire."),
    ("1021", "Dotation non consomptible avec droit de reprise en numeraire", 1, "101",
        "Apports provisoires des adherents en numeraire (cheque, especes)."),
    ("1025", "Dotation non consomptible avec droit de reprise en nature", 1, "101",
        "Apports provisoires des adherents en nature (mobilier, materiel)."),
    ("1041", "Dotation consomptible", 1, "101",
        "Fonds destines a couvrir les charges de fonctionnement."),
    ("1049", "Dotation consomptible inscrite au compte de resultat", 1, "101",
        "Compte d'ajustement de cloture (couverture charges de la periode)."),
    ("103", "Droits d'entree et fonds d'adhesion", 1, "10",
        "Droits d'entree percus a l'admission de nouveaux adherents."),

    ("14", "Subventions d'investissement", 1, None, ""),
    ("1417", "Subventions d'equipement - Organismes internationaux", 1, "14",
        "Subventions d'investissement re�ues d'organismes internationaux."),

    ("16", "Emprunts et dettes assimilees - EBNL", 1, None, ""),
    ("162", "Fonds affectes aux investissements", 1, "16",
        "CLE SYCEBNL projets de developpement - part invest du decaissement bailleur."),
    ("165", "Fonds non consommes en fin d'exercice", 1, "16",
        "Carry-over inter-exercices des fonds d'investissement non utilises."),
    ("167", "Fonds provenant des dons et legs d'immobilisations", 1, "16",
        "Contrepartie au bilan des immobilisations re�ues en don."),
    ("1679", "Engagement aupres du donateur", 1, "16",
        "Contre-partie de la quote-part rapportee au resultat."),
    ("171", "Donation temporaire d'usufruit", 1, "16",
        "Usufruit temporaire d'un bien cede a titre gratuit a l'entite."),
    ("172", "Legs non encore re�us d'immobilisations destinees a la vente", 1, "16",
        "Engagement re�u au titre de legs d'immobilisations destinees a la vente."),

    ("18", "Comptes de liaison et fonds dedies internes", 1, None,
        "Comptes EVE internes de liaison projet <-> Budget General."),
    ("181", "Comptes de liaison projets EVE", 1, "18", ""),
    ("1851", "Depots re�us", 1, "18", "Depots de garantie re�us des adherents."),
    ("192", "Provisions pour charges sur legs et dons", 1, None,
        "Provisions au passif des engagements aupres donateurs."),

    # ============ Classe 2 - Immobilisations ============
    ("20", "Charges immobilisees", 2, None, ""),
    ("2011", "Usufruit temporaire", 2, "20", "Immo incorporelle issue d'une donation d'usufruit."),
    ("203", "Batiments destines a la vente provenant de legs non encore re�us", 2, "20", ""),
    ("204", "Materiels destines a la vente provenant de legs non encore re�us", 2, "20", ""),

    ("22", "Terrains", 2, None, ""),
    ("2221", "Terrains a batir", 2, "22", ""),
    ("2234", "Terrains nus", 2, "22", ""),

    ("23", "Batiments, installations techniques", 2, None, ""),
    ("2313", "Batiments administratifs et commerciaux", 2, "23", ""),
    ("2318", "Autres batiments", 2, "23", ""),

    ("24", "Materiel, mobilier, agencements", 2, None, ""),
    ("2441", "Mobilier de bureau", 2, "24", ""),
    ("2442", "Materiel informatique", 2, "24", ""),
    ("2443", "Materiel telephonique et bureautique", 2, "24", ""),
    ("2451", "Materiel automobile", 2, "24", ""),

    ("25", "Avances et acomptes verses sur immobilisations", 2, None, ""),
    ("252", "Avances et acomptes verses sur immobilisations corporelles", 2, "25", ""),

    ("28", "Amortissements", 2, None, ""),
    ("280", "Amortissements d'usufruit temporaire", 2, "28", ""),
    ("2838", "Amortissements des batiments", 2, "28", ""),
    ("2844", "Amortissements du mobilier de bureau et materiel", 2, "28", ""),
    ("2845", "Amortissements du materiel automobile", 2, "28", ""),

    ("29", "Depreciations des immobilisations", 2, None, ""),
    ("2902", "Depreciations des immobilisations destinees a la vente", 2, "29", ""),

    # ============ Classe 4 - Tiers ============
    ("40", "Fournisseurs", 4, None, ""),
    ("401", "Fournisseurs - exploitation", 4, "40", ""),
    ("4011", "Fournisseurs locaux", 4, "40", ""),

    ("41", "Adherents, clients et comptes rattaches", 4, None, ""),
    ("411", "Adherents", 4, "41", "Creances sur adherents (cotisations a recevoir)."),
    ("412", "Clients-usagers", 4, "41", "Creances sur usagers / beneficiaires payants."),
    ("4161", "Adherents, cotisations douteuses", 4, "41", ""),

    ("42", "Personnel", 4, None, ""),
    ("422", "Personnel, remunerations dues", 4, "42",
        "Dette envers salaries au titre des salaires nets a payer."),

    ("43", "Organismes sociaux", 4, None, ""),
    ("431", "Securite sociale", 4, "43",
        "Dette envers CSS (cotisations patronales et salariales)."),
    ("432", "Caisses de retraite", 4, "43", "Dette envers IPRES."),

    ("44", "Etat et collectivites publiques", 4, None, ""),
    ("4421", "Etat, impots et taxes d'Etat", 4, "44",
        "IRPP retenu, TRIMF, CFCE, vignettes, etc. - dette envers le tresor."),
    ("4451", "Etat, TVA recuperable", 4, "44", ""),
    ("4453", "Etat, TVA collectee", 4, "44", ""),

    ("45", "Apporteurs et associes", 4, None, ""),
    ("4511", "Apporteurs en nature", 4, "45",
        "Souscription a la constitution / nouvelle dotation en nature."),
    ("4512", "Apporteurs en numeraire", 4, "45",
        "Souscription a la constitution / nouvelle dotation en numeraire."),

    ("46", "Bailleurs - fonds dedies", 4, None,
        "Comptes specifiques EBNL pour la mecanique des projets de developpement."),
    ("462", "Fonds d'administration", 4, "46",
        "CLE SYCEBNL projets de developpement - part fonctionnement du decaissement bailleur. "
        "Au fur et a mesure de l'engagement des charges, on debite 462 / credite 702."),

    ("47", "Comptes transitoires et a regulariser", 4, None, ""),
    ("4732", "Subventions d'equipement a recevoir - Organismes internationaux", 4, "47", ""),
    ("475", "Generosites financieres a recevoir", 4, "47",
        "Promesses de dons et legs en numeraire signees mais non encaissees."),
    ("476", "Charges comptabilisees d'avance", 4, "47", ""),

    ("48", "Creances et dettes hors activites ordinaires", 4, None, ""),
    ("4812", "Fournisseurs d'investissement - immobilisations corporelles", 4, "48", ""),
    ("4861", "Dettes des dons et legs d'immobilisations", 4, "48", ""),

    # ============ Classe 5 - Tresorerie ============
    ("52", "Banques", 5, None, ""),
    ("521", "Banques en monnaies locales", 5, "52", ""),
    ("5211", "Banques EVE - XOF", 5, "521",
        "Sous-comptes 5211.x crees a partir des BankAccount EVE actifs."),

    ("57", "Caisse", 5, None, ""),
    ("571", "Caisse en monnaie locale", 5, "57",
        "Sous-comptes 571.x crees a partir des CashRegister EVE actifs."),

    ("58", "Virements internes", 5, None, ""),
    ("585", "Virements internes - banque vers caisse / inter-comptes", 5, "58",
        "Compte tampon pour les transferts entre comptes EVE (banque -> banque, banque -> caisse)."),

    # ============ Classe 6 - Charges (SYSCOHADA REVISE) ============
    ("60", "Achats et variations de stocks", 6, None, ""),
    ("61", "Transports", 6, None, "Transports du personnel, transports sur missions, voyages."),
    ("62", "Services exterieurs A", 6, None, "Locations, entretien, primes d'assurance, etudes, recherches."),
    ("63", "Services exterieurs B", 6, None, "Frais bancaires, frais de formation, frais de recherche de fonds, redevances."),
    ("64", "Impots et taxes", 6, None, "IRPP/TRIMF (charge sur salaires), TVA, CFCE, vignettes, patente."),
    ("65", "Autres charges", 6, None, "Subventions versees aux beneficiaires, dons cotisations, pertes sur creances."),
    ("66", "Charges de personnel", 6, None, "Appointements, salaires, charges sociales (IPRES, CSS, IPM)."),
    ("67", "Frais financiers et charges assimilees", 6, None, "Interets emprunts, agios, pertes de change, frais bancaires de tenue."),
    ("68", "Dotations aux amortissements, provisions et depreciations", 6, None, ""),
    ("69", "Dotations aux depreciations hors activites ordinaires", 6, None, ""),

    # ============ Classe 7 - Produits ============
    ("70", "Ventes, cotisations et quote-parts EBNL", 7, None, ""),
    ("701", "Cotisations des adherents", 7, "70", ""),
    ("702", "Quote-part de fonds d'administration transferes", 7, "70",
        "CLE SYCEBNL - produit de neutralisation des charges engagees sur fonds d'administration 462. "
        "Au fur et a mesure de l'engagement, on debite 462 / credite 702 pour neutraliser l'impact resultat."),
    ("703", "Quote-part des dotations consomptibles transferees", 7, "70",
        "Couverture des charges engagees sur dotation consomptible 1041 (cf. 1049)."),
    ("7041", "Dons en numeraire courants", 7, "70", ""),
    ("7044", "Zakat", 7, "70", ""),
    ("7045", "Celebrations et evenements religieux", 7, "70", ""),
    ("706", "Revenus des manifestations", 7, "70", ""),
    ("7081", "Ventes de dons en nature", 7, "70", ""),
    ("7082", "Revenus d'usufruit", 7, "70", ""),

    ("75", "Subventions et dons re�us", 7, None,
        "Subventions d'exploitation et dons - usage en EBNL hors mecanique 162/462."),
    ("751", "Subventions bailleurs internationaux", 7, "75", ""),
    ("752", "Contribution du fondateur", 7, "75",
        "Contribution annuelle du fondateur pour couverture frais de fonctionnement."),
    ("7542", "Dons en nature re�us a distribuer", 7, "75", ""),
    ("7583", "Benevoles - contributions en nature", 7, "75", ""),

    ("78", "Transferts de charges", 7, None, ""),
    ("79", "Reprises de provisions, depreciations et fonds dedies", 7, None, ""),
    ("7923", "Fonds provenant des dons et legs - reprise au resultat", 7, "79", ""),
    ("7925", "Reprises de fonds affectes a un projet specifique", 7, "79", ""),
    ("7952", "Reprises des depreciations d'immobilisations re�ues", 7, "79", ""),
    ("7961", "Reprises de fonds provenant d'usufruit temporaire", 7, "79", ""),
    ("7962", "Legs non encore re�us d'immobilisations destinees a la vente - reprise", 7, "79", ""),
    ("799", "Reprises de subventions d'investissement", 7, "79", ""),

    # ============ Classe 8 - Engagements et engagements hors bilan ============
    ("81", "Valeurs comptables des cessions d'immobilisations", 8, None, ""),
    ("818", "VNC des immobilisations re�ues destinees a la vente", 8, "81", ""),
    ("82", "Produits des cessions d'immobilisations", 8, None, ""),
    ("828", "Creances sur cessions d'immobilisations", 8, "82", ""),

    # ============ Classe 9 - Contributions volontaires en nature (analytique) ============
    # SYCEBNL recommande de tracer le benevolat et les dons en nature en
    # comptabilite analytique parallele (emplois 90 / ressources 91).
    ("90", "Contributions volontaires en nature - emplois", 1, None,
        "Comptabilite analytique : emplois (utilisation des contributions volontaires)."),
    ("901", "Mise a disposition gratuite de biens", 1, "90", ""),
    ("904", "Personnel benevole", 1, "90", ""),
    ("91", "Contributions volontaires en nature - ressources", 1, None,
        "Comptabilite analytique : ressources (origine des contributions volontaires)."),
    ("910", "Dons en nature", 1, "91", ""),
    ("914", "Benevolat", 1, "91", ""),
]


# Mapping nom BankAccount -> code SYCEBNL 5211.x (banques en monnaies locales)
BANK_TO_CODE = {
    "Banque Atlantique": ("5211.10", "Banque Atlantique - EVE"),
    "EVE-OXFAM": ("5211.20", "SUNU BANK - EVE-OXFAM (AXA + ECO)"),
    "EVE service": ("5211.30", "CBAO - EVE service (Saint-Louis)"),
    "EVE-SODIS": ("5211.40", "SUNU BANK - EVE-SODIS (ONAS PDBH)"),
    "EVE": ("5211.50", "BOA - EVE (ChildFund)"),
    "Budget General": ("5211.60", "SUNU BANK - Budget General"),
}


# Mapping nom CashRegister -> code SYCEBNL 571.x
CASH_REGISTER_TO_CODE = {
    "Caisse centrale BG": ("571.00", "Caisse centrale BG"),
}


# Comptes de liaison "speciaux" : projets clos hors-perimetre dont le reliquat
# continue de transiter.
EXTRA_LIAISON_ACCOUNTS = [
    {
        "code": "181.110",
        "name": "Liaison Pikine Phase I (cloture - reliquat)",
        "description": (
            "Compte de liaison du projet AGIR Pikine Phase I, cloture en "
            "fevrier 2026 et donc hors base Project. Son reliquat continue de "
            "transiter par le Budget General en 2026."
        ),
    },
]


def _suffix_for_project(index: int) -> str:
    """Suffixe sur 3 chiffres pour tri lexicographique stable (010, 020...)."""
    return f"{(index + 1) * 10:03d}"


class Command(BaseCommand):
    help = "[OBSOLETE] Remplace par seed_chart_of_accounts_official."

    @transaction.atomic
    def handle(self, *args, **options):
        from django.core.management.base import CommandError
        raise CommandError(
            "Ce seed est obsolete depuis la migration 0016 (refonte plan "
            "SYCEBNL officiel). Il utilisait des codes inventes (1101, 23, "
            "40, 4011...) qui ne sont pas conformes SYCEBNL et qui ont ete "
            "remappes par la migration 0016.\n\n"
            "Utiliser a la place :\n"
            "  python manage.py seed_chart_of_accounts_official\n"
        )
        # Code mort conserve pour reference historique :
        self.stdout.write("Seed plan comptable SYCEBNL EVE (racines + EBNL)...")

        # 1) Racines (sans parent_code resolu sur le 1er passage)
        accounts: dict[str, ChartOfAccount] = {}
        for code, name, cls_num, parent_code, description in ROOT_ACCOUNTS:
            acc, created = ChartOfAccount.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "class_number": cls_num,
                    "description": description,
                },
            )
            accounts[code] = acc
            self.stdout.write(f"  {acc.code:6} {'cree' if created else 'mis a jour'}")

        # 2) Resolution des parent_code
        for code, name, cls_num, parent_code, description in ROOT_ACCOUNTS:
            if parent_code:
                acc = accounts[code]
                acc.parent = accounts[parent_code]
                acc.save(update_fields=["parent", "updated_at"])

        # 3) Comptes de liaison 181.x par projet actif
        projects = list(
            Project.objects.filter(is_active=True, deleted_at__isnull=True).order_by("code")
        )
        for index, project in enumerate(projects):
            suffix = _suffix_for_project(index)
            code = f"181.{suffix}"
            name = f"Liaison {project.short_title or project.title or project.code}"
            acc, created = ChartOfAccount.objects.update_or_create(
                code=code,
                defaults={
                    "name": name[:200],
                    "class_number": 1,
                    "parent": accounts["181"],
                    "is_liaison": True,
                    "linked_project": project,
                    "description": f"Compte de liaison interne EVE pour le projet {project.code}.",
                },
            )
            self.stdout.write(
                f"  {code} ({project.code}): {'cree' if created else 'mis a jour'}"
            )

        # 3 bis) Comptes de liaison speciaux (projets clos / hors base)
        for spec in EXTRA_LIAISON_ACCOUNTS:
            acc, created = ChartOfAccount.objects.update_or_create(
                code=spec["code"],
                defaults={
                    "name": spec["name"],
                    "class_number": 1,
                    "parent": accounts["181"],
                    "is_liaison": True,
                    "description": spec.get("description", ""),
                },
            )
            self.stdout.write(
                f"  {spec['code']} (liaison speciale): {'cree' if created else 'mis a jour'}"
            )

        # 4) Comptes bancaires 5211.x
        for bank_name, (code, label) in BANK_TO_CODE.items():
            try:
                bank = BankAccount.objects.get(
                    name=bank_name, is_active=True, deleted_at__isnull=True
                )
            except BankAccount.DoesNotExist:
                self.stderr.write(
                    f"  /!\\ BankAccount '{bank_name}' introuvable, compte {code} non lie."
                )
                continue
            acc, created = ChartOfAccount.objects.update_or_create(
                code=code,
                defaults={
                    "name": label,
                    "class_number": 5,
                    "parent": accounts["5211"],
                    "linked_bank_account": bank,
                },
            )
            self.stdout.write(
                f"  {code} ({bank_name}): {'cree' if created else 'mis a jour'}"
            )

        # 5) Caisses 571.x
        for register_name, (code, label) in CASH_REGISTER_TO_CODE.items():
            register = CashRegister.objects.filter(name=register_name).first()
            if register is None:
                register, _ = CashRegister.objects.get_or_create(
                    name=register_name, defaults={"currency": "XOF"},
                )
                self.stdout.write(f"  Caisse '{register_name}' cree a la volee.")
            acc, created = ChartOfAccount.objects.update_or_create(
                code=code,
                defaults={
                    "name": label,
                    "class_number": 5,
                    "parent": accounts["571"],
                    "linked_cash_register": register,
                },
            )
            self.stdout.write(
                f"  {code} ({register_name}): {'cree' if created else 'mis a jour'}"
            )

        self.stdout.write(self.style.SUCCESS("Plan comptable SYCEBNL (racines + EBNL) seede."))
