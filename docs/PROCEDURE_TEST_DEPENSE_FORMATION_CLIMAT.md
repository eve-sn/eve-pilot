# Test de procédure SYCEBNL — Exécution d'une dépense de A à Z
## Cas pilote : formation thématique « climat » du mardi 23 juin 2026

> Objet : tester avec toute l'équipe le circuit complet d'une dépense dans
> EVE Pilot — **planification → demande → validation → engagement → décaissement
> → réalisation → comptabilisation** — avec les pièces justificatives conformes
> et les écritures SYCEBNL (comptabilité d'engagement).
>
> Aujourd'hui = **mercredi 17/06/2026**. Activité = **mardi 23/06/2026**.
> Jours ouvrés disponibles : 17, 18, 19 juin, puis 22 juin (lun) → 4 jours pour
> tout boucler avant l'activité. **Le tempo est serré : tenir le calendrier.**

---

## 0. Prérequis techniques (RAF / admin, à faire AVANT de convoquer l'équipe)

Sans ça, les testeurs sont bloqués dès la première étape :

```bash
# 1) Lier chaque compte à sa fiche employé (sinon « créer une demande » est refusé)
sudo -u eve /srv/eve_pilot/.venv/bin/python /srv/eve_pilot/manage.py link_users_employees

# 2) Vérifier que les rôles valideurs existent (RAF/DP/SE)
sudo -u eve /srv/eve_pilot/.venv/bin/python /srv/eve_pilot/manage.py seed_expense_validation_roles

# 3) S'assurer que le projet choisi a au moins une LIGNE BUDGÉTAIRE éligible
#    (la demande de dépense s'impute obligatoirement sur une ligne budgétaire).
```

À la fin de l'étape 1, les 4 comptes **personnel d'appui / stagiaires** (BALDE,
TOURE, SENGHOR, NDIONE) seront signalés « sans fiche » : c'est normal, ils ne
créent pas de demande mais participent à la logistique et à la documentation.

---

## 1. PARTIE A — Programme de la formation (la dépense à exécuter)

**Thème** : *Adaptation au changement climatique et pratiques résilientes en
milieu communautaire* (à ajuster en réunion de planification selon le projet
porteur : ISF-AXA / ECO-AVENIR / WASH).

| | |
|---|---|
| **Date** | Mardi 23 juin 2026, 08h30 – 17h00 |
| **Lieu** | *À confirmer en réunion de planification (J-6)* |
| **Public** | *À confirmer (relais communautaires, animateurs, partenaires) — viser 25 à 30 participants* |
| **Porteur** | Projet à dominante climat + ligne budgétaire « formation / renforcement de capacités » |
| **Objectif général** | Renforcer les capacités des participants sur la compréhension des risques climatiques et l'adoption de pratiques d'adaptation |

**Déroulé pédagogique (à joindre comme TDR) :**

| Horaire | Séquence | Animation |
|---|---|---|
| 08h30 | Accueil, enregistrement, émargement | Secrétaire + appui |
| 09h00 | Ouverture officielle | DP / SE |
| 09h15 | Contexte : changement climatique au Sénégal | Référent technique |
| 10h00 | Module 1 — Vulnérabilités et risques climatiques locaux | Formateur / référent |
| 10h45 | Pause-café | Logistique |
| 11h00 | Module 2 — Pratiques d'adaptation et agriculture résiliente | Formateur |
| 12h30 | Déjeuner | Logistique |
| 13h30 | Module 3 — Gestion de l'eau / agroécologie | Formateur / chargé de suivi |
| 14h30 | Travaux de groupe — étude de cas terrain | Chargés de suivi |
| 15h30 | Pause | Logistique |
| 15h45 | Restitution + plan d'action communautaire | Référent |
| 16h30 | Évaluation de la formation + clôture | Chargé de suivi / DP |
| 17h00 | Fin | — |

**Budget prévisionnel type** (montants à fixer en planification — imputation SYCEBNL) :

| Poste | Compte SYCEBNL | Base de calcul |
|---|---|---|
| Location de salle | **6221** | forfait journée |
| Restauration (pauses + déjeuner) | **6582** | nb participants × coût/repas |
| Frais de formation / animation thématique | **633** ou **6277** | forfait atelier |
| Honoraires formateur externe | **6381** | si consultant |
| Perdiem / transport participants | **6132 / 6181** | nb participants × barème |
| Fournitures et supports pédagogiques | **6054 / 6011** | kits, blocs, impressions |
| Communication / visibilité bailleur | **6274** | banderole, attestations |
| Carburant déplacement (véhicule EVE) | **6057** | mission chauffeur |

---

## 2. PARTIE B — Rôle de chaque collègue (les 20 comptes)

| Compte | Rôle EVE | Contribution dans ce test |
|---|---|---|
| **alydiouf** | RAF | Valideur n°1 ; autorise l'engagement et le décaissement ; peut marquer l'exécution ; contrôle de conformité financière |
| **sndiaye** | DP | Valideur n°2 (opportunité / cohérence programme) ; ouvre la formation |
| **abdoudiouf** | SE | Valideur n°3 (validation institutionnelle finale) |
| **amyseck** | ARAF | Contrôle de l'imputation budgétaire et de la disponibilité de crédit (BG) avant validation |
| **ssakho** | COMPTABLE | Saisit l'**engagement** et le **décaissement**, génère la **pièce comptable**, comptabilise la dépense, rapproche, archive en compta |
| **taphafall** | CHEF_PROJET | Pilote la planification ; co-rédige le TDR et le budget ; peut être le **demandeur** |
| **ksylla / morndiaye / adioumandiongue / maguevedrame / dioumandour** | CHARGE_SUIVI | Contenu pédagogique ; **création de la demande de dépense (demandeur)** ; suivi de la réalisation ; liste de présence ; rapport d'activité |
| **cheikhpathe** | REFERENT | Validation du contenu technique « climat » ; appui méthodologique ; restitution |
| **habibdiouf / khalifadieng** | GESTIONNAIRE | Logistique : 3 devis/proforma, PV de sélection, bons de commande, gestion fournisseurs, collecte des factures, états de perdiem |
| **rokhayaba** | SECRETAIRE | Invitations/convocations ; émargement ; **gestion documentaire et archivage des pièces** ; courriers |
| **ismailabalde / abdoulayetoure** | PERSONNEL D'APPUI | Installation salle, matériel, accueil, appui terrain le jour J |
| **henriettesenghor / annemarie** | STAGIAIRE | Prise de notes, photos, appui au rapport et à la documentation |
| **ousseynouseck** | CHAUFFEUR | Transport participants/matériel ; ordre de mission ; carnet de bord ; justificatif carburant |

---

## 3. PARTIE C — Procédure pas à pas dans EVE Pilot (7 phases)

> Convention : **DD** = demande de dépense (`/finance/demandes/`).
> Chaque ligne indique *qui*, *quoi dans l'appli*, *quelle pièce*, *quel effet*.

### Phase 1 — Planification — mer 17/06 (J-6)
| Qui | Action | Pièce produite |
|---|---|---|
| DP + CHEF_PROJET + REFERENT + CHARGES_SUIVI | Réunion : arrêter thème, **lieu, participants**, date confirmée, budget prévisionnel, projet + ligne budgétaire d'imputation | **PV de réunion de planification** |
| CHARGE_SUIVI + REFERENT | Rédiger les **TDR** (objectifs, programme, public, budget) | **TDR signés** |

### Phase 2 — Préparation des pièces amont — jeu 18/06 (J-5)
| Qui | Action | Pièce |
|---|---|---|
| GESTIONNAIRE | Demander **3 devis/proforma** (salle, restauration, transport) puis établir le **PV de sélection** du fournisseur | Proforma ×3 + **PV de sélection** |
| SECRETAIRE | Préparer invitations / convocations | Invitations |

### Phase 3 — Demande de dépense (DD) — ven 19/06 (J-4)
| Qui | Action dans EVE Pilot | Pièce / statut |
|---|---|---|
| CHARGE_SUIVI (demandeur) | `Finance ▸ Demandes ▸ Nouvelle` : projet, **ligne budgétaire**, intitulé, motif, montant | DD créée → **BROUILLON** |
| CHARGE_SUIVI | Onglet de la DD ▸ **Ajouter document** : joindre TDR, budget, **PROFORMA**, PV de sélection | Pièces typées attachées |
| ARAF | Vérifier l'imputation et la disponibilité de crédit sur la ligne | (contrôle préalable) |
| CHARGE_SUIVI | Bouton **Soumettre** | → **SOUMISE** ; 3 validations RAF/DP/SE créées + valideurs notifiés |

### Phase 4 — Validation (triple signature) — ven 19/06 (J-4)
| Qui | Action | Effet |
|---|---|---|
| RAF (alydiouf) | Sur la DD : **Approuver / Rejeter** + commentaire | Signature 1 |
| DP (sndiaye) | **Approuver / Rejeter** + commentaire | Signature 2 |
| SE (abdoudiouf) | **Approuver / Rejeter** + commentaire | Signature 3 |
| — | Quand **les 3 sont APPROUVÉES** | DD → **APPROUVÉE** (déblocage de l'exécution) |

> Si un valideur rejette → DD **REJETÉE**, le demandeur est notifié et corrige.

### Phase 5 — Engagement (budgétaire) — lun 22/06 (J-1)
> ⚠️ **Ce que fait réellement EVE Pilot** : l'engagement à ce stade est
> **budgétaire / de gestion** (la commande consomme du crédit sur la ligne), il
> n'y a **pas encore d'écriture comptable postée**. L'écriture en partie double
> est générée **automatiquement au décaissement** (Phase 6). La comptabilité
> d'engagement « pure » (Dr 6xxx / Cr 401 dès la commande) n'est pas auto-postée
> dans cette version : si on la veut, c'est une écriture manuelle du comptable.

| Qui | Action | Effet |
|---|---|---|
| GESTIONNAIRE | Émettre les **bons de commande** sur la base de la DD approuvée | **BC** ; engagement de crédit sur la ligne |
| COMPTABLE (ssakho) | Enregistrer l'engagement (n° de commande / `Commitment`) pour le suivi budgétaire | Engagement budgétaire tracé |

### Phase 6 — Décaissement + écriture automatique — lun 22/06 (J-1)
| Qui | Action dans EVE Pilot | Écriture **auto-générée** |
|---|---|---|
| RAF | Autoriser le décaissement | (autorisation) |
| COMPTABLE | `DD ▸ Saisir paiement` : créer le **BankMovement / CashMovement** en désignant **le compte de charge** (contra_account, ex. 633 / 6221 / 6132) ; DD → **EXÉCUTÉE** | **Dr 6xxx** (charge) / **Cr 5211.x** Banque (ou **571.x** Caisse) |
| — | *posting.py ajoute la neutralisation du fonds dédié (SYCEBNL App.8)* | **Dr 462** Fonds d'administration / **Cr 702** Quote-part *(automatique)* |
| COMPTABLE | Éditer la **pièce comptable** (bouton *Pièce* / *Pièce PDF* sur le mouvement) | **Pièce comptable + annexes** |
| CHAUFFEUR | Ordre de mission + carnet de bord (si déplacement) | Ordre de mission |

> Note : l'écriture passe **directement charge → trésorerie** (recognition à la
> dépense), avec le miroir 462/702 pour neutraliser l'impact sur le résultat du
> projet. Le compte **401 Fournisseurs** n'intervient que si vous choisissez de
> tenir l'engagement fournisseur en écriture manuelle.

### Phase 7 — Réalisation + Comptabilisation finale — mar 23/06 (J) → mar 30/06 (J+5)
| Qui | Action | Pièce / écriture |
|---|---|---|
| Toute l'équipe terrain (appui, stagiaires, chauffeur) | Tenir la formation | Photos, notes |
| SECRETAIRE | Faire **émarger la liste de présence** (par demi-journée) | **Liste de présence émargée** |
| GESTIONNAIRE | Collecter **factures définitives** + reçus acquittés + **états de perdiem signés** (avec copies CNI) | Factures, reçus, états |
| CHARGE_SUIVI + STAGIAIRE | Rédiger le **rapport d'activité** (narratif + résultats + évaluation) | **Rapport d'activité** |
| COMPTABLE | Solder les fournisseurs (paiement du solde) | **Dr 401 / Cr 5211.x** |
| COMPTABLE | Régulariser l'écart **proforma ↔ facture** s'il existe ; rapprocher ; clôturer la dépense | Écritures de régularisation |
| SECRETAIRE | **Archiver** l'ensemble des pièces (rattachées à la DD et au mouvement) | Dossier complet |

---

## 4. PARTIE D — Pièces justificatives conformes (check-list)

**Obligatoires** pour une dépense de formation conforme (bailleur + SYCEBNL) :

- [ ] PV de réunion de planification
- [ ] TDR signés
- [ ] Budget prévisionnel détaillé
- [ ] Demande de dépense (DD dans EVE Pilot)
- [ ] 3 devis/proforma + **PV de sélection** du fournisseur *(si montant > seuil interne)*
- [ ] Bon de commande / contrat fournisseur
- [ ] Liste de présence **émargée** (par demi-journée) avec contacts
- [ ] États de perdiem signés + copies CNI des bénéficiaires
- [ ] Factures définitives **acquittées** + reçus
- [ ] Rapport d'activité (narratif + résultats)
- [ ] Pièce comptable EVE Pilot (avec annexes)

**Recommandées** : photos, attestations de participation, ordre de mission +
carnet de bord chauffeur, supports pédagogiques distribués.

---

## 5. PARTIE E — Calendrier récapitulatif

| Jour | Date | Étape | Pilote |
|---|---|---|---|
| J-6 | mer 17/06 | Planification + TDR | DP / CHEF_PROJET / REFERENT |
| J-5 | jeu 18/06 | Devis, PV sélection, invitations | GESTIONNAIRE / SECRETAIRE |
| J-4 | ven 19/06 | **DD + pièces + soumission + triple validation** | CHARGE_SUIVI → RAF/DP/SE |
| J-1 | lun 22/06 | **Engagement + décaissement avance + BC** | COMPTABLE / RAF / GESTIONNAIRE |
| **J** | **mar 23/06** | **Réalisation de la formation** | Toute l'équipe |
| J+1→J+5 | 24→30/06 | Justification + solde + comptabilisation + archivage | COMPTABLE / SECRETAIRE |

---

## 6. PARTIE F — Suite : autres types d'activités (à tester ensuite)

Le même circuit (DD → validation → engagement → décaissement → justification)
se décline pour : ateliers, supervisions terrain, achats d'équipement, études,
distributions. **Une variante allégée** sera testée séparément pour :

- **Dépenses de fonctionnement** (loyer, eau, électricité, télécoms, carburant) :
  récurrentes, sur ligne BG, validation simplifiée, imputation 60x/62x.
- **Petites dépenses / petite caisse** (`CashRegister`, comptes 571.x) :
  plafonnées, pièce = reçu/ticket, décaissement caisse, régularisation périodique.

> Ces deux procédures spéciales feront l'objet d'un document dédié après ce
> premier test « grandeur nature ».

---

*Document de travail — pilote EVE Pilot. Les barèmes (perdiem, seuils de mise en
concurrence) et le compte exact de consommation du fonds dédié (462/702 selon la
source de financement) sont à confirmer avec le RAF et le comptable, conformément
à la spec `SPEC_SYCEBNL_COMPTABILITE_ENGAGEMENT.md`.*
