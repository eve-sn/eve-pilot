"""
Plan comptable SYCEBNL/SYSCOHADA Revise detaille pour EVE.

Complete le seed seed_chart_of_accounts_sycebnl (qui pose les racines 60..67,
les comptes EBNL classe 1/2/4 et les comptes de liaison projets) avec
l'arborescence des sous-comptes operationnels reellement utilisables par EVE.

NUMEROTATION CONFORME SYSCOHADA REVISE (Acte Uniforme OHADA 2017) :
  - 60 Achats (601 stockes, 605 non stockes : eau, elec, telecom, fournitures, carburant)
  - 61 Transports (611 transports sur achats, 613 transports du personnel,
        618 voyages et deplacements - SYCEBNL App.8 utilise 6181)
  - 62 Services exterieurs A (622 locations, 623 redevances, 624 entretien,
        625 primes d'assurance, 626 etudes et recherches, 627 publicite,
        628 frais de telecom)
  - 63 Services exterieurs B (631 frais bancaires, 632 frais de formation,
        636 frais de recherche de fonds, 637 cotisations, 638 honoraires)
  - 64 Impots et taxes (641 IRPP / TRIMF, 645 CFCE, 646 patente / vignettes)
  - 65 Autres charges (651 pertes sur creances, 652 SUBVENTIONS VERSEES PAR
        L'ENTITE, 658 charges diverses : dons, hospitalites)
  - 66 Charges de personnel (661 appointements et salaires, 663 primes,
        664 charges sociales, 668 autres charges personnel)
  - 67 Frais financiers (671 interets emprunts, 672 interets decouverts,
        674 pertes de change, 678 autres charges financieres)

Idempotente (update_or_create par code).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import ChartOfAccount


# (code, parent_code, class_number, name, description)
DETAILED_ACCOUNTS = [
    # ============ Classe 6 - CHARGES (SYSCOHADA Revise) ============

    # 60 - Achats
    ("601", "60", 6, "Achats de marchandises", ""),
    ("6011", "60", 6, "Achats de fournitures liees a l'activite",
        "Petits stocks consommables, intrants formations, kits beneficiaires."),
    ("6035", "60", 6, "Variation de stocks de fournitures et autres approvisionnements", ""),
    ("605", "60", 6, "Autres achats (non stockes)",
        "Eau, electricite, telecoms, fournitures de bureau, carburant."),
    ("6051", "605", 6, "Frais d'eau", ""),
    ("6052", "605", 6, "Frais d'electricite", ""),
    ("6053", "605", 6, "Frais de telecommunications - mobile",
        "Abonnements mobile, recharges, forfaits Orange / Free / Expresso."),
    ("6054", "605", 6, "Fournitures de bureau", "Papier, stylos, classeurs, cartouches imprimante."),
    ("6055", "605", 6, "Produits d'entretien", "Detergents, balais, sacs poubelle."),
    ("6056", "605", 6, "Petit outillage et materiel",
        "Materiel cuisine, outils techniques, petits equipements terrain."),
    ("6057", "605", 6, "Carburants et lubrifiants",
        "Carburant vehicules, motos, generateurs (TOTAL, SHELL, VIVO, etc.)."),
    ("6058", "605", 6, "Autres fournitures non stockables", "Achats divers consommes immediatement."),

    # 61 - Transports
    ("611", "61", 6, "Transports sur achats", ""),
    ("613", "61", 6, "Transports du personnel",
        "Taxis, navettes, billets transport personnel sur lieu de travail."),
    ("6131", "613", 6, "Transport quotidien du personnel", "Taxis, transports urbains."),
    ("6132", "613", 6, "Perdiem et frais de mission",
        "Perdiem terrain, indemnites de mission."),
    ("618", "61", 6, "Voyages et deplacements",
        "Voyages, deplacements sur missions terrain. SYCEBNL App.8 = 6181."),
    ("6181", "618", 6, "Voyages et deplacements - mission terrain",
        "Frais de transport sur missions terrain (avion, train, bus, voiture location)."),

    # 62 - Services exterieurs A
    ("622", "62", 6, "Locations et charges locatives", ""),
    ("6221", "622", 6, "Location de batiments (loyer bureau)",
        "Loyer mensuel locaux administratifs."),
    ("6222", "622", 6, "Location de vehicules",
        "Location voitures pour missions, supervisions."),
    ("6223", "622", 6, "Location de materiel et outillage",
        "Location video-projecteur, sono, generateurs."),
    ("6224", "622", 6, "Charges locatives (eau/elec incluses)",
        "Charges integrees au loyer."),
    ("624", "62", 6, "Entretien, reparations et maintenance", ""),
    ("6241", "624", 6, "Entretien et reparations des vehicules",
        "Vidanges, pneus, reparations garages."),
    ("6242", "624", 6, "Entretien et reparations materiel de bureau",
        "Maintenance imprimantes, ordinateurs."),
    ("6243", "624", 6, "Entretien et reparations batiments",
        "Peinture, plomberie, electricite locaux."),
    ("625", "62", 6, "Primes d'assurance", ""),
    ("6251", "625", 6, "Assurance vehicules", ""),
    ("6252", "625", 6, "Assurance locaux et materiel", ""),
    ("6253", "625", 6, "Assurance responsabilite civile", ""),
    ("626", "62", 6, "Etudes, recherches et documentation", ""),
    ("6261", "626", 6, "Etudes et recherches", "Etudes de base, evaluations externes."),
    ("6263", "626", 6, "Documentation generale et abonnements", "Livres, revues, abonnements."),
    ("627", "62", 6, "Publicite, publications, relations publiques", ""),
    ("6272", "627", 6, "Publications", "Brochures, plaquettes, rapports imprimes."),
    ("6274", "627", 6, "Communication et visibilite bailleur",
        "Banderoles, t-shirts, supports terrain bailleur."),
    ("628", "62", 6, "Frais de telecommunications - fixes et internet", ""),
    ("6281", "628", 6, "Telephone fixe", ""),
    ("6282", "628", 6, "Internet et fibre", "Abonnements internet, fibre bureau."),
    ("6283", "628", 6, "Frais postaux et courriers", "Affranchissement, envois DHL."),

    # 63 - Services exterieurs B
    ("631", "63", 6, "Frais bancaires et services bancaires", ""),
    ("6311", "631", 6, "Commissions sur services bancaires",
        "Frais de virement, commissions tenue de compte."),
    ("6312", "631", 6, "Frais sur effets et cartes",
        "Frais de change, frais carte bancaire."),
    ("632", "63", 6, "Frais de formation du personnel",
        "Formations capitalisation personnel EVE (hors beneficiaires)."),
    ("633", "63", 6, "Frais sur formations et seminaires beneficiaires",
        "Formations beneficiaires - seminaires terrain."),
    ("636", "63", 6, "Frais de recherche de fonds",
        "SYCEBNL App.12 - frais engages pour rechercher dons et subventions."),
    ("637", "63", 6, "Redevances pour brevets, licences, droits", ""),
    ("638", "63", 6, "Honoraires et services intellectuels", ""),
    ("6381", "638", 6, "Honoraires consultants", "Experts ponctuels, consultants techniques."),
    ("6382", "638", 6, "Honoraires audit et expertise comptable",
        "Commissariat aux comptes, expertise comptable."),
    ("6383", "638", 6, "Honoraires juridiques", "Avocats, notaires."),

    # 64 - Impots et taxes (charge employeur sur salaires + autres)
    ("641", "64", 6, "Impots et taxes directs",
        "IRPP (retenue a la source), TRIMF cote employeur."),
    ("6411", "641", 6, "Taxes sur appointements et salaires",
        "IRPP retenu source sur salaires - charge de l'employeur."),
    ("6412", "641", 6, "TRIMF - taxe representative impot minimum forfaitaire", ""),
    ("645", "64", 6, "Impots et taxes d'exploitation", ""),
    ("6451", "645", 6, "CFCE - Contribution Forfaitaire Charge Employeur",
        "3% des salaires bruts - charge patronale."),
    ("646", "64", 6, "Droits d'enregistrement et autres", ""),
    ("6461", "646", 6, "Patente / Contribution economique locale", ""),
    ("6462", "646", 6, "Vignettes vehicules", ""),

    # 65 - Autres charges (incl. subventions versees par l'entite)
    ("651", "65", 6, "Pertes sur creances irrecouvrables", ""),
    ("652", "65", 6, "Subventions versees par l'entite",
        "SYCEBNL App. SE-2 - cofinancements et subventions versees aux partenaires de mise en oeuvre."),
    ("657", "65", 6, "Bourses, appuis et secours",
        "Appuis directs beneficiaires (cash transfer, kits), bourses etudiants/stagiaires."),
    ("658", "65", 6, "Charges diverses d'exploitation", ""),
    ("6581", "658", 6, "Dons et cotisations versees", "Cotisations associatives, dons divers."),
    ("6582", "658", 6, "Frais de reception et hospitalites",
        "Reception hotes, invites, partenaires."),
    ("6583", "658", 6, "Frais de representation", ""),

    # 66 - Charges de personnel
    ("661", "66", 6, "Appointements, salaires et commissions", ""),
    ("6611", "661", 6, "Salaires bruts personnel national",
        "SYCEBNL App.8 = 6611. Personnel salarie EVE (national)."),
    ("6612", "661", 6, "Salaires bruts personnel expatrie", "Si applicable."),
    ("6613", "661", 6, "Vacations et heures supplementaires", ""),
    ("663", "66", 6, "Primes et indemnites", ""),
    ("6631", "663", 6, "Primes et gratifications",
        "Primes performance, anciennete, fonction."),
    ("6632", "663", 6, "Indemnites prestataires terrain",
        "Animateurs relais communautaires, vacataires."),
    ("664", "66", 6, "Charges sociales",
        "SYCEBNL App.8 = compte 664 unique pour cotisations patronales."),
    ("6641", "664", 6, "IPRES - cotisations patronales retraite",
        "Part patronale 8.4% (cadre) ou 14% (non-cadre)."),
    ("6642", "664", 6, "CSS - Caisse de Securite Sociale",
        "Part patronale 7% (accidents) + 7% (alloc. familiales)."),
    ("6643", "664", 6, "Allocations familiales", ""),
    ("6644", "664", 6, "Accidents du travail", ""),
    ("6645", "664", 6, "IPM - Institut de Prevoyance Maladie",
        "Mutuelle medicale obligatoire."),
    ("668", "66", 6, "Autres charges de personnel", ""),
    ("6681", "668", 6, "Formation du personnel",
        "Formations internes EVE et seminaires."),
    ("6682", "668", 6, "Frais medicaux personnel", "Au-dela de l'IPM."),
    ("6683", "668", 6, "Hospitalites et restauration personnel",
        "Repas, evenements internes."),
    ("6684", "668", 6, "Hebergement personnel mission", ""),
    ("6685", "668", 6, "Oeuvres sociales et retraites complementaires", ""),

    # 67 - Frais financiers
    ("671", "67", 6, "Interets sur emprunts", ""),
    ("672", "67", 6, "Interets sur decouverts bancaires et agios",
        "Decouverts, interets debiteurs."),
    ("674", "67", 6, "Pertes de change", ""),
    ("678", "67", 6, "Autres charges financieres", ""),

    # 68 - Dotations aux amortissements (utilisees en cloture, hors UAT actuel)
    ("681", "68", 6, "Dotations aux amortissements d'exploitation", ""),
    ("6813", "681", 6, "Dotations aux amortissements des immobilisations corporelles", ""),
    ("680", "68", 6, "Dotations aux amortissements d'usufruit temporaire", ""),

    # 69 - Depreciations HAO
    ("6952", "69", 6, "Dotations aux depreciations immobilisations destinees a la vente", ""),

    # ============ Classe 7 - PRODUITS ============

    # 70 - Produits courants EBNL (cf. seed_sycebnl pour les racines 701, 702, 703...)
    # Les codes 701 / 702 / 703 / 7041 / 7044 / 7045 / 706 / 7081 / 7082 sont
    # crees dans seed_sycebnl.

    # 75 - Subventions et dons re�us (sous-comptes bailleurs EVE)
    ("7511", "751", 7, "Subventions Nous-Cims (Espagne)",
        "PNBSF, Saint-Louis, ECP, Pikine, GT-Wallu."),
    ("7512", "751", 7, "Subventions AXA Climate / ISF", "ISF-AXA."),
    ("7513", "751", 7, "Subventions Oghogho Meye / La Locomotiva",
        "Projet ECO-AVENIR."),
    ("7514", "751", 7, "Subventions ChildFund / P&G",
        "Reponse urgence inondations."),
    ("7515", "751", 7, "Subventions ONAS-AFD", "PDBH IEC."),
    ("7516", "751", 7, "Subventions OXFAM", ""),
    ("7517", "751", 7, "Subventions FNC (Fonds National de la Culture)",
        "PAR / autres conventions FNC."),
    ("7518", "751", 7, "Autres subventions bailleurs internationaux", ""),
    ("753", "75", 7, "Subventions et dons institutions locales",
        "Etat senegalais, collectivites territoriales."),
    ("754", "75", 7, "Subventions et dons particuliers", ""),
    ("758", "75", 7, "Autres dons et appuis re�us", ""),

    # 77 - Revenus financiers (gardes mais reclasses dans 7x)
    ("771", "77", 7, "Interets sur depots", ""),
    ("778", "77", 7, "Autres produits financiers",
        "Reprises sur agios, gains de change."),
]


class Command(BaseCommand):
    help = "[OBSOLETE] Remplace par seed_chart_of_accounts_official."

    @transaction.atomic
    def handle(self, *args, **options):
        from django.core.management.base import CommandError
        raise CommandError(
            "Ce seed est obsolete depuis la migration 0016 (refonte plan "
            "SYCEBNL officiel). Les sous-comptes detailles qu'il creait "
            "(6411 IRPP, 6611 salaires, 6441 IPRES...) ont ete remplaces "
            "par les codes officiels du XLSX SYCEBNL.\n\n"
            "Utiliser a la place :\n"
            "  python manage.py seed_chart_of_accounts_official\n"
        )
        # Code mort conserve pour reference historique :
        # Index des parents pour resolution rapide.
        parents = {a.code: a for a in ChartOfAccount.objects.all()}

        created = 0
        updated = 0
        skipped = 0
        for code, parent_code, cls_num, name, description in DETAILED_ACCOUNTS:
            parent = parents.get(parent_code)
            if parent is None and parent_code:
                self.stdout.write(self.style.WARNING(
                    f"Parent {parent_code} introuvable pour {code} - skip (lancer d'abord seed_chart_of_accounts_sycebnl)"
                ))
                skipped += 1
                continue
            defaults = {
                "name": name,
                "class_number": cls_num,
                "description": description,
                "parent": parent,
                "is_liaison": False,
                "is_active": True,
                "deleted_at": None,
            }
            obj, was_created = ChartOfAccount.objects.update_or_create(
                code=code, defaults=defaults,
            )
            parents[code] = obj  # Permet aux enfants suivants de pointer dessus.
            if was_created:
                created += 1
                self.stdout.write(f"  + {code:6} {name}")
            else:
                updated += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Plan comptable detail SYCEBNL : {created} comptes crees, "
            f"{updated} mis a jour, {skipped} skip ({created + updated + skipped} traites)."
        ))
