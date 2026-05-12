from datetime import date


RH_REFERENCE_SNAPSHOT = {
    "title": "Tableau de Bord RH EVE 2025-2026",
    "scope": "Senegal - Projets 2025-2026",
    "source_date": date(2026, 4, 23),
    "staff": {
        "salaried_and_contractual": 22,
        "service_providers": 11,
        "consultants": 2,
        "detailed_total_listed": 35,
        "reported_summary_total": 33,
        "has_total_discrepancy": True,
    },
    "community": {
        "relay_workers": 572,
        "icp": 25,
        "health_posts": 34,
        "companions": 54,
        "community_supervisors": 10,
        "regions": 3,
        "total_actors": 695,
    },
    "geographies": [
        {
            "label": "Saint-Louis - Nous-Cims",
            "relay_workers": 60,
            "support_structures": "25 ICP + equipe cadre de district",
            "beneficiaries": "3 748 enfants de 6-59 mois",
        },
        {
            "label": "Pikine / Mbao - Nous-Cims Agir",
            "relay_workers": 102,
            "support_structures": "34 postes de sante",
            "beneficiaries": "7 081 menages",
        },
        {
            "label": "Kedougou - PNBSF",
            "relay_workers": 142,
            "support_structures": "10 superviseurs communautaires",
            "beneficiaries": "Zones rurales et urbaines",
        },
        {
            "label": "Dakar - PNBSF (67 quartiers)",
            "relay_workers": 268,
            "support_structures": "54 accompagnateurs",
            "beneficiaries": "268 groupes ACEC / AVEC actifs",
        },
    ],
}
