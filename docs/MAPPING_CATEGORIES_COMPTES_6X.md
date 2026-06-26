# Mapping catégories budgétaires → comptes de charge 6x (SYCEBNL engagement)

> Prérequis de la **comptabilité d'engagement**. À l'engagement d'une dépense,
> le compte de charge débité (`Dr 6x`) est résolu via
> `BudgetCategory.default_charge_account` (Phase 0), surchargeable par
> engagement. Ce document fige le mapping validé avec le comptable
> (2026-06-26). Appliqué par la commande `seed_category_charge_accounts`.

## ⚠️ Risque réalignement OHADA futur

> Ce mapping pointe vers les PK des comptes actuels en base EVE
> (dont les libellés divergent du PDF OHADA officiel sur 6057,
> 6381, 6271-6277). Si une tâche future réaligne la base sur les
> libellés OHADA stricts, faire UPDATE in-place des libellés
> uniquement (préserver les PK), jamais DELETE+CREATE qui casserait
> ce mapping silencieusement.

## A. Catégories engageables (fournisseur) — compte 6x par défaut

Le compte ci-dessous est un **défaut**, surchargeable par engagement
(`Commitment.charge_account`). Pour les catégories larges, il n'est qu'un point
de départ.

| Catégorie (code) | Compte 6x | Libellé du compte (base EVE) | Note |
|---|---|---|---|
| FORM | 633 | Frais sur formations et séminaires bénéficiaires | 632 si formation du *personnel* EVE |
| PROJ_FORMATION | 633 | Frais sur formations et séminaires bénéficiaires | |
| PROJ_ACTIVITES | 638 | Honoraires et services intellectuels | ⚠️ 79 lignes, sac mélangé — à éclater à terme, surcharge fréquente |
| PROJ_COMMUNICATION | 6274 | Communication et visibilité bailleur | 6272 (Publications) selon contenu réel |
| PROJ_PRESTATION | 6381 | Honoraires consultants | (en base EVE 6381 = honoraires ; ≠ OHADA strict) |
| PROJ_SUIVI | 6261 | Études et recherches | **6181** si suivi surtout terrain |
| PROJ_INTRANTS | 6011 | Achats de fournitures liées à l'activité | |
| PROJ_LOGISTIQUE | 6181 | Voyages et déplacements - mission terrain | 6222 si location véhicule |
| ACHATS | 605 | Autres achats (non stockés) | carburant→6057, bureau→6054 |
| PROJ_ADMIN | 6221 | Location de bâtiments (loyer bureau) | loyer domine (6 M / 9,5 M) ; télécoms→628, élec→6052 |
| SERVICES_EXT | 638 | Honoraires et services intellectuels | large, surcharge |
| AUTRES_SVC_EXT | 638 | Honoraires et services intellectuels | large, surcharge |
| APPUIS_SUBV | 652 | Subventions versées par l'entité | (657 écarté = pénalités pénales en OHADA) |
| AUTRES_CHARGES | 658 | Charges diverses d'exploitation | |
| PROJ_DIVERS | 658 | Charges diverses d'exploitation | |
| PROJ_EQUIPEMENT | 6056 | Petit outillage et matériel | ⚠️ voir seuil d'immobilisation ci-dessous |

## B. Catégories NON engageables — pas de mapping (circuit distinct)

Ces catégories ne passent **pas** par un engagement fournisseur `Dr 6x / Cr 401`.
Laisser `default_charge_account` vide est un **choix explicite**.

| Catégorie(s) | Circuit comptable réel |
|---|---|
| CHARGES_PERSONNEL · CHARGES_PERSO_CRT · PROJ_PERSONNEL | Paie : `Dr 661 / Cr 422` (pas de fournisseur) |
| IPRES_CSS_2026 · VRS_BRS_CRT | Cotisations sociales / retenues : classes 43/44 |
| APUR_HISTORIQUE · APUR_IPRES_2025 · APUR_VRS_BRS_2025 | Apurement de **dettes** existantes : `Dr 4xx / Cr 5211` |
| PROJ_INDIRECTS | Recharge **interne** : liaison `181.x` sortant + `781` entrant ; % par convention bailleur (10-15 % selon Nous-Cims, AXA…) — **pas** une charge externe |

## Seuil d'immobilisation

**300 000 FCFA.** En-dessous : charge (compte 6056). Au-dessus : **immobilisation
classe 2** (`Dr 2 / Cr 481.x`, voir `post_commitment`). Règle de gestion pour le
comptable — **non imposée par le moteur** (qui se branche sur la classe du compte
choisi, pas sur le montant).

> ⚠️ **À faire avant de pouvoir capitaliser** : les comptes classe 2 d'immobilisation
> (244 « Matériel et mobilier », 245 « Matériel de transport » et sous-comptes)
> sont actuellement **inactifs** en base (seul 2451 « Matériel automobile » est
> actif). Tant qu'ils ne sont pas réactivés, l'override en immobilisation est
> impossible (aucun compte classe 2 sélectionnable). Tâche distincte à programmer
> si EVE compte capitaliser du matériel.

## Tâche connexe (à programmer)

Le plan de comptes EVE (`seed_chart_of_accounts`) est une personnalisation locale
**incomplète** du plan OHADA officiel. Certains sous-comptes officiels présents
dans le PDF OHADA manquent en base (ex. **6183**). 6181 et 6263, eux, sont **déjà
présents**. À compléter en relisant le PDF OHADA, en **UPDATE in-place** (cf.
encadré risque ci-dessus).
