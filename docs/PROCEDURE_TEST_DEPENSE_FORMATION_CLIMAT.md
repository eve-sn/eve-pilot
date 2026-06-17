# Test de procédure SYCEBNL — Exécution d'une dépense de A à Z
## Cas pilote : formation « climat » sur le projet ECO-AVENIR

> Objet : tester avec toute l'équipe le circuit complet d'une dépense dans
> EVE Pilot — **planification → demande → validation → engagement → décaissement
> → réalisation → comptabilisation** — avec les pièces justificatives conformes
> et les écritures SYCEBNL (comptabilité d'engagement).
>
> Aujourd'hui = **mercredi 17/06/2026**.
> Une activité normale conforme suppose **~3 semaines de préparation** (planification,
> mise en concurrence, validation, engagement, décaissement) et **~2 semaines de
> clôture** après. Le 23/06 (6 jours) est **trop court pour un cycle conforme** :
> on retient une **date d'activité recommandée = mardi 14 juillet 2026** (à confirmer
> par la Direction). Le calendrier ci-dessous est exprimé en **J‑x** (réutilisable
> pour toute activité) puis décliné en dates concrètes.

---

## 0. Prérequis techniques (RAF / admin — DÉJÀ EXÉCUTÉS sur le serveur)

Ces commandes ont été lancées et vérifiées ; elles sont idempotentes (re-jouables) :

```bash
M="sudo -u eve /srv/eve_pilot/.venv/bin/python /srv/eve_pilot/manage.py"
$M link_users_employees           # lie chaque compte à sa fiche employé
$M seed_expense_validation_roles  # rôles valideurs RAF / DP / SE
$M set_pilot_emails               # adresses email réelles des comptes
$M setup_test_ecoavenir           # projet ECO-AVENIR + ligne FORM-CLIMAT-TEST
                                  #  + banque SUNU BANK + rattache Magueye DRAME
```

État obtenu : 14 comptes liés ; projet **OGHOGHO-ECOAVENIR-2026** actif avec la
ligne **FORM-CLIMAT-TEST** ; banque **SUNU BANK (EVE-OXFAM)** rattachée ;
demandeur **Magueye DRAME** dans l'équipe projet ; **emails opérationnels**
(SMTP 587/STARTTLS, envoi réel confirmé). Les comptes **appui / stagiaires**
(BALDE, TOURE, SENGHOR, NDIONE) restent « sans fiche » : normal, rôle logistique.

---

## 1. PARTIE A — Programme de la formation (la dépense à exécuter)

**Thème** : *Adaptation au changement climatique et pratiques résilientes en
milieu communautaire* — porté par le projet **ECO-AVENIR** (OGHOGHO-ECOAVENIR-2026,
bailleur Oghogho Meye / La Locomotiva), dont l'objet est précisément la résilience
des enfants et jeunes au changement climatique à Pikine.

| | |
|---|---|
| **Date** | Mardi 14 juillet 2026 (recommandée — voir calendrier §5), 08h30 – 17h00 |
| **Lieu** | *À confirmer en réunion de planification (J-6)* |
| **Public** | *À confirmer (relais communautaires, animateurs, partenaires) — viser 25 à 30 participants* |
| **Porteur** | Projet **ECO-AVENIR** (OGHOGHO-ECOAVENIR-2026) · ligne **FORM-CLIMAT-TEST** · banque **SUNU BANK (EVE-OXFAM)** |
| **Demandeur** | **Magueye DRAME** (`maguevedrame`, chargé de suivi rattaché au projet) |
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
| **amyseck** | ARAF | Appui au contrôle budgétaire (son périmètre propre = Budget Général ; ici la dépense est sur projet, elle intervient en appui) |
| **ssakho** | COMPTABLE | Saisit l'**engagement** et le **décaissement**, génère la **pièce comptable**, comptabilise la dépense, rapproche, archive en compta |
| **taphafall** | CHEF_PROJET | Pilote la planification ; co-rédige le TDR et le budget |
| **maguevedrame** (**DEMANDEUR de ce test**) | CHARGE_SUIVI | **Crée la demande de dépense sur ECO-AVENIR** ; contenu pédagogique ; suivi de la réalisation ; liste de présence ; rapport d'activité |
| ksylla / morndiaye / adioumandiongue / dioumandour | CHARGE_SUIVI | Mêmes attributions sur leurs projets respectifs |
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

### Phase 1 — Planification — J‑21 → J‑17 (lun 22 → ven 26 juin)
| Qui | Action | Pièce produite |
|---|---|---|
| DP + CHEF_PROJET + REFERENT + CHARGES_SUIVI | Réunion : arrêter thème, **lieu, participants**, date confirmée, budget prévisionnel, projet + ligne budgétaire d'imputation | **PV de réunion de planification** |
| CHARGE_SUIVI + REFERENT | Rédiger les **TDR** (objectifs, programme, public, budget) | **TDR signés** |

### Phase 2 — Mise en concurrence & préparation des pièces — J‑16 → J‑12 (28/06 → 02/07)
| Qui | Action | Pièce |
|---|---|---|
| GESTIONNAIRE | Demander **3 devis/proforma** (salle, restauration, transport) puis établir le **PV de sélection** du fournisseur | Proforma ×3 + **PV de sélection** |
| SECRETAIRE | Préparer invitations / convocations | Invitations |

### Phase 3 — Demande de dépense (DD) — J‑12 → J‑10 (02/07 → 04/07)
| Qui | Action dans EVE Pilot | Pièce / statut |
|---|---|---|
| **Magueye DRAME** (demandeur) | `Finance ▸ Demandes ▸ Nouvelle` : projet **ECO-AVENIR**, ligne **FORM-CLIMAT-TEST**, intitulé, motif, montant | DD créée → **BROUILLON** |
| Magueye DRAME | Onglet de la DD ▸ **Ajouter document** : joindre TDR, budget, **PROFORMA**, PV de sélection | Pièces typées attachées |
| Magueye DRAME | Bouton **Soumettre** | → **SOUMISE** ; 3 validations RAF/DP/SE créées ; **RAF + DP + SE notifiés par mail en même temps** |

### Phase 4 — Validation (triple signature) — J‑10 → J‑7 (04/07 → 07/07)
| Qui | Action | Effet |
|---|---|---|
| RAF (alydiouf) | Sur la DD : **Approuver / Rejeter** + commentaire | Signature 1 |
| DP (sndiaye) | **Approuver / Rejeter** + commentaire | Signature 2 |
| SE (abdoudiouf) | **Approuver / Rejeter** + commentaire | Signature 3 |
| — | Quand **les 3 sont APPROUVÉES** | DD → **APPROUVÉE** (déblocage de l'exécution) |

> Si un valideur rejette → DD **REJETÉE**, le demandeur est notifié et corrige.

> 📧 **Notifications email (opérationnelles, envoi réel via SMTP eve-sn.org)** :
> - à la **soumission** → **RAF + DP + SE** reçoivent un mail **en même temps** ;
> - à **chaque signature** → le **demandeur ET les autres valideurs** sont prévenus
>   de la progression (« untel a signé, il reste X ») ;
> - à la **décision finale** → le demandeur reçoit le résultat (approuvée / rejetée).
> Chaque mail contient un lien direct vers la demande (`https://pilot.eve-sn.org/...`).

### Phase 5 — Engagement (budgétaire) + bons de commande — J‑7 → J‑5 (07/07 → 09/07)
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

### Phase 6 — Décaissement (avance) + écriture automatique — J‑5 → J‑3 (09/07 → 11/07)
| Qui | Action dans EVE Pilot | Écriture **auto-générée** |
|---|---|---|
| RAF | Autoriser le décaissement | (autorisation) |
| COMPTABLE | `DD ▸ Saisir paiement` : créer le **BankMovement** sur **SUNU BANK (EVE-OXFAM)** en désignant **le compte de charge** (contra_account, ex. 633 / 6221 / 6132) ; DD → **EXÉCUTÉE** | **Dr 6xxx** (charge) / **Cr 5211.20** SUNU BANK (EVE-OXFAM) |
| — | *posting.py ajoute la neutralisation du fonds dédié (SYCEBNL App.8)* | **Dr 462** Fonds d'administration / **Cr 702** Quote-part *(automatique)* |
| COMPTABLE | Éditer la **pièce comptable** (bouton *Pièce* / *Pièce PDF* sur le mouvement) | **Pièce comptable + annexes** |
| CHAUFFEUR | Ordre de mission + carnet de bord (si déplacement) | Ordre de mission |

> Note : l'écriture passe **directement charge → trésorerie** (recognition à la
> dépense), avec le miroir 462/702 pour neutraliser l'impact sur le résultat du
> projet. Le compte **401 Fournisseurs** n'intervient que si vous choisissez de
> tenir l'engagement fournisseur en écriture manuelle.

### Phase 7 — Réalisation (J) + justification & comptabilisation — J → J+10 (14/07 → 24/07)
| Qui | Action | Pièce / écriture |
|---|---|---|
| Toute l'équipe terrain (appui, stagiaires, chauffeur) | Tenir la formation | Photos, notes |
| SECRETAIRE | Faire **émarger la liste de présence** (par demi-journée) | **Liste de présence émargée** |
| GESTIONNAIRE | Collecter **factures définitives** + reçus acquittés + **états de perdiem signés** (avec copies CNI) | Factures, reçus, états |
| CHARGE_SUIVI + STAGIAIRE | Rédiger le **rapport d'activité** (narratif + résultats + évaluation) | **Rapport d'activité** |
| COMPTABLE | Solder les fournisseurs (paiement du solde) | **Dr 6xxx / Cr 5211.20** (SUNU BANK) |
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

## 5. PARTIE E — Calendrier

### 5.1 Modèle standard conforme (réutilisable pour toute activité)

Délais minimaux recommandés pour une activité « normale » (atelier, formation,
supervision) soumise à mise en concurrence et triple validation.

| Échéance | Phase | Durée | Pourquoi ce délai |
|---|---|---|---|
| **J‑21 → J‑17** | Planification + TDR + budget + choix lieu/participants | 1 sem. | Cadrer l'activité et l'imputation avant d'engager |
| **J‑16 → J‑12** | Mise en concurrence (3 devis) + PV de sélection | 1 sem. | Laisser le temps aux fournisseurs de répondre |
| **J‑12 → J‑10** | Demande de dépense + pièces + soumission | 2‑3 j | Dossier complet avant validation |
| **J‑10 → J‑7** | Triple validation RAF / DP / SE | 3 j | Disponibilité des 3 signataires |
| **J‑7 → J‑5** | Engagement budgétaire + bons de commande | 2 j | Sécuriser fournisseurs et crédit |
| **J‑5 → J‑3** | Décaissement de l'avance + pièce comptable | 2 j | Provisionner la trésorerie de l'activité |
| **J‑3 → J‑1** | Logistique finale + convocations + confirmation participants | 2 j | Derniers réglages |
| **J** | Réalisation | 1 j | — |
| **J+1 → J+5** | Justification : factures, états perdiem, présence, rapport | 1 sem. | Collecte à chaud des pièces |
| **J+5 → J+10** | Décaissement du solde + comptabilisation + rapprochement | 1 sem. | Solde sur pièces définitives |
| **J+10 → J+15** | Archivage + clôture de la dépense | 1 sem. | Dossier auditable bouclé |

> Règle simple : **~3 semaines avant** (planif → décaissement avance) et
> **~2 semaines après** (justification → clôture). À raccourcir seulement pour
> les petites dépenses / le fonctionnement (procédure allégée, cf. §6).

### 5.2 Déclinaison concrète — activité recommandée **mardi 14 juillet 2026**

| Date | Étape | Pilote |
|---|---|---|
| sem. 22/06 | Planification + TDR + budget | DP / CHEF_PROJET / REFERENT |
| sem. 29/06 | 3 devis + PV de sélection + invitations | GESTIONNAIRE / SECRETAIRE |
| 02 → 04/07 | **DD + pièces + soumission** | CHARGE_SUIVI |
| 04 → 07/07 | **Triple validation** RAF / DP / SE | RAF / DP / SE |
| 07 → 09/07 | **Engagement + bons de commande** | COMPTABLE / GESTIONNAIRE |
| 09 → 11/07 | **Décaissement avance + pièce comptable** | RAF / COMPTABLE |
| 11 → 13/07 | Logistique finale, confirmation participants | GESTIONNAIRE / SECRETAIRE / appui |
| **mar 14/07** | **Réalisation de la formation** | Toute l'équipe |
| 15 → 21/07 | Justification (factures, perdiem, présence, rapport) | GESTIONNAIRE / CHARGE_SUIVI |
| 21 → 24/07 | Décaissement solde + comptabilisation + rapprochement | COMPTABLE |
| 24 → 29/07 | Archivage + clôture | SECRETAIRE / COMPTABLE |

> Si la Direction maintient une date plus proche, on bascule sur le chemin
> compressé (planif et validation en parallèle), mais la mise en concurrence et
> la triple validation restent incompressibles pour la conformité.

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

## 7. PARTIE G — Fiche d'évaluation du test (à remplir)

> But : vérifier que le circuit **fonctionne**, qu'il est **conforme SYCEBNL**, et
> identifier les blocages. Un référent (CHEF_PROJET ou RAF) consolide les retours.

### 7.1 Critères globaux de réussite (à cocher en fin de test)

- [ ] La demande a bien suivi les statuts : BROUILLON → SOUMISE → APPROUVÉE → EXÉCUTÉE
- [ ] Les **3 signatures** RAF / DP / SE ont été tracées (avec commentaires)
- [ ] Toutes les **pièces obligatoires** (§4) ont pu être attachées à la demande
- [ ] L'écriture comptable s'est **générée automatiquement** au décaissement
- [ ] L'écriture est juste : `Dr 6xxx / Cr 5211.x` **+** neutralisation `Dr 462 / Cr 702`
- [ ] La **pièce comptable** (PDF + annexes) est éditable et lisible
- [ ] Le décaissement du **solde** et le **rapprochement** ont pu être faits
- [ ] Le **rapport d'activité** est rattaché et le dossier est **archivé/auditable**

### 7.2 Grille par rôle (chaque testeur remplit sa ligne)

| Rôle / compte | A pu faire son étape ? (O/N) | Temps passé | Blocage rencontré | Suggestion |
|---|---|---|---|---|
| CHARGE_SUIVI (demandeur) | | | | |
| ARAF (contrôle budgétaire) | | | | |
| RAF (validation + exécution) | | | | |
| DP (validation) | | | | |
| SE (validation) | | | | |
| GESTIONNAIRE (devis, BC, factures) | | | | |
| COMPTABLE (engagement, écriture, pièce) | | | | |
| SECRETAIRE (pièces, archivage) | | | | |
| REFERENT (contenu technique) | | | | |
| Appui / stagiaire / chauffeur (terrain) | | | | |

### 7.3 Journal des anomalies

| # | Étape | Description du problème | Gravité (bloquant / gênant / mineur) | Signalé par | Action / correctif |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

### 7.4 Verdict de conformité SYCEBNL

| Question | Réponse | Commentaire |
|---|---|---|
| L'imputation (ligne budgétaire + compte de charge) est-elle correcte ? | | |
| La neutralisation du fonds dédié 462/702 est-elle correcte ? | | |
| Les pièces sont-elles conformes aux exigences bailleur ? | | |
| **Faut-il une vraie compta d'engagement (Dr 6xxx/Cr 401 à la commande) ?** | | *Décision Direction/RAF — cf. seuil 30 M* |
| Décision : procédure **validée / à ajuster / à revoir** | | |

---

*Document de travail — pilote EVE Pilot. Les barèmes (perdiem, seuils de mise en
concurrence) et le compte exact de consommation du fonds dédié (462/702 selon la
source de financement) sont à confirmer avec le RAF et le comptable, conformément
à la spec `SPEC_SYCEBNL_COMPTABILITE_ENGAGEMENT.md`.*
