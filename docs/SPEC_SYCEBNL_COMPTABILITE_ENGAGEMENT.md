# Spécification — Passage à la comptabilité d'engagement SYCEBNL

> **Statut :** brouillon de travail (v1.7, 2026-06-14) — **prêt pour validation expert-comptable.** Toutes les valeurs du Palier 1 sont sourcées et chiffrées.
> - **v1.7** : **séquencement & module RH** clarifiés — la paie/RH est dans le périmètre EVE Pilot mais en **phase ultérieure** (après compta valide). Fondation RH existante (`apps/hr` : `Employee`/`Contract`/`Payslip`) documentée (§6-bis). Palier 1 paie = **récap mensuel** (pas de per-employé). `Payslip` à étendre (charges patronales) en phase RH.
> - **v1.6** : **facture CSS/IPRES réelle d'EVE (mai 2026)** intégrée → ATMPF d'EVE = **1 %** confirmé, mécanique de plafonnement validée (base CSS = 11 × 63 000), exemple chiffré réel (699 099 FCFA). Plus aucune valeur de paie en suspens.
> - **v1.5** : **taux IPRES/CSS officiels** intégrés (secusociale.sn) — RG 14 %/plafond 432 000, Cadre 6 %/1 296 000, CSS 7 % + ATMPF 1-5 %/plafond 63 000. Le Palier 1 paie est désormais entièrement chiffré.
> - **v1.4** : intégration des **déclarations fiscales/sociales réelles d'EVE** (BRS, VRS, DNS) → composantes de paie confirmées (ISR/TRIMF/CFCE 3 %/IPRES/CSS), **RAS tiers 5 %** ajoutée, et **cadrage : la paie est calculée hors EVE Pilot** (le système enregistre le récap, ne le recalcule pas).
> - **v1.3** : intégration **comptes 40 (fournisseurs) et 42/43/44 (paie)** → schéma de paie E3 corrigé (transit par le 42, brut au crédit) ; comptes fournisseurs 401/408/409/481 confirmés. **Palier 1 entièrement sourcé.**
> - **v1.2** : fonctionnement comptes 46 et 70 → mécanisme 462/702 certifié juste sur comptes et sens ; seul défaut = **fait générateur** (engagement vs décaissement).
> - **v1.1** : comptes 13, 14, 16. Cf. §8 pour les schémas confirmés et les pages encore requises.
> **Auteur du brouillon :** assistant technique, à partir (a) du plan de comptes SYCEBNL déjà seedé dans l'application, (b) du guide d'application OHADA SYCEBNL, (c) des principes généraux de comptabilité des entités à but non lucratif.
> **Périmètre :** module `apps.finance` (BankMovement / CashMovement → JournalEntry), entité EVE et ses projets bailleurs.

---

## 0. Avertissement de fiabilité (à lire avant tout)

Je ne suis pas expert-comptable SYCEBNL certifié. Ce document est ma **meilleure reconstruction** à partir de ton propre plan de comptes (qui fait foi dans ton système) et des principes OHADA/EBNL. **Les schémas d'écriture ci-dessous doivent être validés par ton expert-comptable ou ton commissaire aux comptes avant d'être codés.** Les points que je n'ai pas pu certifier à 100 % sont signalés `⚠️ À CONFIRMER`.

Les sources web officielles OHADA (guide d'application, Acte uniforme) n'ont pas pu être extraites automatiquement (PDF image / trop volumineux). **La référence contraignante reste le guide d'application SYCEBNL** que possède manifestement l'auteur du module actuel (le code cite « App.8 », « guide chapitre 3 »).

---

## 1. Rectification d'un diagnostic précédent

Lors d'un échange antérieur, j'avais affirmé que les comptes **462** et **702** utilisés par le moteur d'écriture étaient « non standards / faux ». **C'était une erreur de ma part.** Après extraction du plan seedé, ces comptes sont bien ceux du **modèle SYCEBNL « projets de développement » :**

| Compte | Intitulé (plan seedé) | Rôle |
|---|---|---|
| 161 | Fonds projet de développement - avances de fonds à justifier | Avance bailleur reçue, à justifier |
| 162 | Fonds affectés aux investissements du projet de développement - bailleurs | Part **investissement** du financement (passif/fonds) |
| 165 | Fonds affectés à un projet spécifique | Fonds affecté générique |
| 169 | Fonds affectés à recevoir | Créance de financement |
| **462** | **Bailleurs - projet de développement, Fonds d'administration** | Part **fonctionnement** du financement (passif/fonds) |
| 469 | Fonds d'administration à recevoir | Créance de fonds de fonctionnement |
| **702** | **Quote-part de fonds d'administration transférés au compte de résultat** | Reconnaissance en **produit** de la part fonctionnement consommée |
| 703 | Quote-part des dotations consomptibles transférées au résultat | Idem pour dotations consomptibles |
| 792 / 796 / 799 | Reprises de fonds affectés / fonds reportés / subventions d'investissement | Reconnaissance produit pour la part **investissement** (en clôture) |

**Conclusion :** sur la *mécanique de rattachement du financement au résultat*, le module actuel est **conforme** au modèle SYCEBNL projets de développement. Mon erreur venait du raisonnement par analogie avec le SYSCOHADA entreprises (où 46 = associés, 70 = ventes) ; SYCEBNL a réaffecté ces racines aux EBNL.

**✅ Désormais certifié par le guide (fonctionnement du compte 46) :** le compte 46 est crédité à la mise à disposition (par débit trésorerie) et débité « au fur et à mesure de **l'engagement des charges** par le crédit du 702 ». Les **comptes et le sens** du moteur EVE (`Dr 5211 / Cr 462` puis `Dr 462 / Cr 702`) sont donc **justes**.

**Ce qui reste à corriger** (le cœur du problème), confirmé a contrario par ce même texte : le moteur déclenche `Dr 462 / Cr 702` au **décaissement**, alors que le guide l'exige à **l'engagement de la charge**. La nuance n'est pas cosmétique : entre l'engagement et le paiement, les états financiers d'EVE sont faux (charges et quote-parts non constatées). C'est l'objet de cette spec.

---

## 2. Cadre normatif

- SYCEBNL = Acte uniforme OHADA relatif au Système Comptable des Entités à But Non Lucratif, **en vigueur depuis le 1er janvier 2024**.
- **Principe : comptabilité d'engagement** (constatation des droits/obligations) sous le **système normal**.
- **Système Minimal de Trésorerie (SMT)** = dérogation **réservée aux entités dont subventions + dons + legs annuels ≤ 30 000 000 FCFA** (art. 6). Au-delà sur un exercice → bascule **automatique** au système normal.
- EVE gère plusieurs projets bailleurs (ChildFund/P&G, NOUSCIMS, etc.) pour des montants très supérieurs à 30 M FCFA/an → **système normal obligatoire → engagement obligatoire**. Ce n'est pas optionnel.

*Sources en fin de document.*

---

## 3. Constat de l'existant (code actuel)

### 3.1 Ce qui est correct
- Génération en partie double équilibrée (`apps/finance/posting.py`).
- Mécanique SYCEBNL projets de développement : split 162/462 à l'encaissement, neutralisation 462/702 à la charge de fonctionnement, 162 intact jusqu'à la clôture pour les immobilisations.
- Soft-delete / extourne propre, idempotence de l'import.

### 3.2 Ce qui manque (base trésorerie)
1. **Aucune écriture à l'engagement.** Seuls `BankMovement` / `CashMovement` génèrent des écritures (`signals.py`). Le modèle `Commitment` (bons de commande, contrats) **ne comptabilise rien**.
2. **Aucun compte fournisseur (classe 40) dans le plan seedé** → impossible de constater une dette fournisseur. Conséquence directe de la base caisse.
3. **Paie comptabilisée en brut au décaissement**, sans retenues ni charges patronales :
   - Actuel (BM-133) : `Dr 6611 (2 636 000) / Cr 5211` — un seul bloc.
   - Les comptes nécessaires existent pourtant (422, 431, 432, 447x, 664) mais ne sont pas mobilisés.
4. **Aucun travail de clôture / cut-off** : pas de charges à payer (408/428/438/448), pas de produits à recevoir, pas de report des ressources non utilisées.
5. **Engagements hors bilan** : les `Commitment` ne sont jamais rapprochés du réalisé en comptabilité.

---

## 4. Plan de comptes cible

### 4.1 Comptes déjà présents et à mobiliser
| Usage | Compte(s) |
|---|---|
| Personnel, rémunérations dues (net à payer) | **422** |
| Personnel, oppositions/saisies | 423 |
| Sécurité sociale (CSS prestations, AT) | 431 (4311, 4312) |
| Caisses de retraite (IPRES) | 432 (4321, 4322) |
| Autres organismes sociaux (mutuelle) | 433 |
| Impôts sur salaires retenus (IR/TRIMF) | **4472**, 4471 |
| Charges sociales patronales | **664** (6641 national / 6642 non national) |
| Charges à payer — personnel / sociaux / État | 428 / 438 / 4486 |
| Produits à recevoir | 4487 / 4387 / 4287 |
| Charges constatées d'avance / produits constatés d'avance | 476 / 477 |
| Fonds affectés investissement / fonctionnement | 162 / 462 |
| Quote-part au résultat (fonctionnement / consomptible) | 702 / 703 |
| Reprises fonds affectés / reportés / subv. invest. | 792 / 796 / 799 |

### 4.2 Comptes MANQUANTS à seeder (⚠️ bloquant pour l'engagement)
**✅ Numérotation CONFIRMÉE par le guide (compte 40) :**
| Compte | Intitulé SYCEBNL exact (guide) | Raison |
|---|---|---|
| **401** | Fournisseurs, dettes en compte | Constatation de la dette à réception facture |
| 4011 | Fournisseurs | Détail dette ordinaire |
| 4013 | Fournisseurs, sous-traitants | Sous-traitance |
| 4017 | Fournisseurs, retenues de garantie | Retenues sur marchés |
| 402 | Fournisseurs, effets à payer | Si effets de commerce |
| **408** | Fournisseurs, factures non parvenues (4081) | **Cut-off de clôture** (charges à payer fournisseurs) |
| 409 | Fournisseurs débiteurs (4091 avances et acomptes versés) | Acomptes fournisseurs |
| **481** | Fournisseurs d'investissements | Achats d'immobilisations à crédit (≠ 401 exploitation) |

> ℹ️ La classe 40 (401 Fournisseurs - exploitation, 4011 Fournisseurs locaux) et le compte 4812 (fournisseurs d'investissement) sont intégrés au plan comptable resserré conforme. Source unique : `seed_chart_of_accounts`. Les sous-comptes de cut-off 408/409 restent à ajouter si la clôture l'exige.

---

## 5. Modèles d'écriture cibles (système normal / engagement)

> Convention : `Dr` = débit, `Cr` = crédit. `5211` = banque (compte de trésorerie lié). Les montants sont illustratifs.

### E1 — Réception d'un financement bailleur affecté à un projet
À l'encaissement sur le compte projet (inchangé vs actuel, c'est déjà correct) :
```
Dr 5211   Banque                                   X
   Cr 162  Fonds affectés investissements              part_invest
   Cr 462  Bailleurs - Fonds d'administration          part_fonctionnement
```
Le split invest/fonctionnement suit la clé du projet (`investment_split_pct` / `administration_split_pct`).

**✅ CONFIRMÉ (Guide d'application, compte 16) :**
- 161 = « Fonds de développement – avances de fonds à justifier » : utilisé quand le bailleur verse une avance que l'entité devra justifier ; reclassé ensuite en 162-164.
- 162 à 164 = « Fonds affectés aux **investissements** du projet de développement » (162 bailleurs / 163 État / 164 autres organismes). La part **investissement** va donc bien en 162.
- Les **avances à justifier (161)** et **fonds à recevoir (169)** sont présentés **via le compte 46** (côté fonctionnement / Bailleurs). Cela valide la racine 46 pour la part fonctionnement du modèle EVE.
- 165 = « Fonds affectés à un **projet spécifique** » : `Dr 52 (banque) / Cr 165` à la mise à disposition, **repris via 7925 au fur et à mesure de la consommation**.

**✅ CONFIRMÉ (Guide d'application, FONCTIONNEMENT du compte 46) :**
- Le compte 46 (Bailleurs, fonds d'administration) est **crédité lors de la mise à disposition** du projet, **par le débit d'un compte de trésorerie** (ou de charges payées directement par le bailleur). → la direction `Dr 5211 / Cr 462` de E1 est **certifiée**.
- **Exclusions du compte 46** : il ne doit PAS enregistrer les **fonds d'investissement** des bailleurs (→ **16**), la **dotation** (→ 10), les **cotisations** d'adhérents (→ 411). → le split invest **162** / admin **462** est donc l'architecture correcte.

> ⚠️ **RESTE À CONFIRMER (page P1)** : *« Fonctionnement du compte 16 »* (le tableau crédit/débit) pour le compte de **reprise du 162**. Par analogie avec 165→7925 et 167→792, c'est très probablement **792x** ; les commentaires du compte 16 fournis ne donnent pas le sous-compte exact du 162.

### E2 — Engagement et règlement d'un fournisseur (charge de fonctionnement)
**(a) Réception de la facture — ENGAGEMENT (nouveau, manquant aujourd'hui)**
```
Dr 6xx    Charge (ex: 6056, 624, 618...)           HT
   Cr 401  Fournisseurs                                 TTC
```
**(b) Rattachement du financement au résultat — quote-part (au moment de l'engagement, pas du paiement)**
```
Dr 462   Bailleurs - Fonds d'administration        montant_charge
   Cr 702  Quote-part fonds d'administration au résultat   montant_charge
```
**✅ CONFIRMÉ (Guide d'application, FONCTIONNEMENT du compte 46) — texte officiel :**
> « Au fur et à mesure de **l'engagement des charges** : est débité le compte 46 des charges engagées par le projet ; **par le crédit du compte 702 Quote-part de fonds d'administration transférés**. »

Donc le sens `Dr 462 / Cr 702` du moteur actuel est **correct**, mais le fait générateur officiel est **l'engagement de la charge**, pas le décaissement. C'est la correction centrale à apporter.

**(c) Paiement (le `BankMovement` actuel devient un simple règlement de dette)**
```
Dr 401   Fournisseurs                              TTC
   Cr 5211 Banque                                       TTC
```
> Différence clé avec l'existant : aujourd'hui (a)+(c) sont fusionnés en `Dr 6xx / Cr 5211` au décaissement, et (b) y est accroché **au décaissement** au lieu de l'engagement. Cible : (a)+(b) au **fait générateur (facture/engagement)**, (c) au paiement.

### E3 — Paie (méthode du guide : transit par le compte 42)
> ✅ **CONFIRMÉ (Guide, fonctionnement comptes 42, 43, 44).** Point clé corrigé par rapport à v1.1 : le compte **42 est crédité du BRUT** (`Dr 66 / Cr 42`), puis **débité** des retenues (`Dr 42 / Cr 43` cotisations salariales, `Dr 42 / Cr 44` impôts retenus). Le solde de 42 = le **net à payer**. On ne crédite PAS les retenues directement depuis la charge.

**(a) Constatation de la paie — ENGAGEMENT (brut au crédit de 42)**
```
Dr 6611  Appointements salaires (BRUT)             brut
   Cr 422  Personnel, rémunérations dues               brut
```
> *Guide compte 42 (crédit) : « crédité des rémunérations brutes à payer au personnel, par le débit des comptes de charges 66 ».*

**(b) Sortie des retenues salariales du compte 42**
```
Dr 422   Personnel, rémunérations dues             cot_salariales + IR
   Cr 431/432 Organismes sociaux (part salariale)      cot_salariales
   Cr 447  État, impôts retenus à la source (IR/TRIMF)  retenue_IR
```
> *Guide compte 42 (débit) : « débité des versements aux organismes sociaux pour le compte du personnel (cotisations salariales), par le crédit du compte 43 ». Le 422 ne conserve alors que le NET.*

**(c) Charges sociales patronales**
```
Dr 664   Charges sociales (patronales)             cot_patronales
   Cr 431/432 Organismes sociaux (part patronale)      cot_patronales
```
> *Guide compte 43 (crédit) : « crédité des cotisations sociales salariales ET patronales, par le débit du 664 (patronale) et du 422 (salariale) ».*

**(d) Quote-part de financement (à l'ENGAGEMENT) — sur total charges (6611 + 664)**
```
Dr 462   Bailleurs - Fonds d'administration        (brut + patronales)
   Cr 702  Quote-part fonds d'administration au résultat   (brut + patronales)
```

**(e) Paiements (les `BankMovement` réels = simples règlements de dettes)**
```
Dr 422   Personnel rémunérations dues (NET)        net      |  Cr 5211 Banque
Dr 43    Organismes sociaux (sal. + patronale)     cot_tot  |  Cr 5211 Banque  (échéance sociale)
Dr 44    État, impôts retenus                       IR       |  Cr 5211 Banque  (échéance fiscale)
```
> *Guide comptes 43 et 44 (débit) : « débité des règlements aux organismes sociaux / à l'État, par le crédit de la trésorerie ».*

> ✅ **RÉSOLU (déclarations réelles EVE — états BRS/VRS mai 2026, DNS IPRES-CSS).** EVE **applique bien** les retenues. Composantes confirmées ci-dessous.

#### E3-bis — Composantes réelles de la paie EVE (Sénégal) et mapping comptable
D'après les états V.R.S. et la DNS d'EVE, chaque bulletin comporte :

| Composante | Nature | % constaté / barème | Compte de dette (crédit) |
|---|---|---|---|
| **I.S.R.** (Impôt sur le Salaire Retenu) | retenue **salariale** | progressif (barème IR) | 447 État, impôts retenus à la source (4472 Impôts sur salaires) |
| **T.R.I.M.F.** (taxe min. fiscal) | retenue **salariale** | fixe par tranche (500 / 1 000 / 1 500…) | 447 État |
| **C.F.C.E.** (Contrib. Forfaitaire à la Charge de l'Employeur) | **charge patronale** | **3 % du brut** (confirmé : 36 268 / 1 208 948) | Dr **641/6413** Taxes sur salaires / Cr 44 État |
| **IPRES** retraite — Régime Général | salariale **+** patronale | **14 %** (8,4 % pat + 5,4 % sal), plafond **432 000**/mois | 432 Caisses de retraite |
| **IPRES** retraite — Régime Cadre (complémentaire) | salariale **+** patronale | **6 %** (3,6 % pat + 2,4 % sal), plafond **1 296 000**/mois | 432 Caisses de retraite |
| **CSS** Prestations familiales | **patronale** | **7 %**, plafond **63 000**/mois | 431 Sécurité sociale |
| **CSS** ATMPF (accident travail) | **patronale** | **1 %** pour EVE (confirmé facture CSS mai 2026), plafond **63 000**/mois | 431 Sécurité sociale |

> ✅ **Taux IPRES/CSS officiels (source : online.secusociale.sn) ET confirmés par la facture CSS/IPRES réelle d'EVE (mai 2026).** Assiette **plafonnée** (cotisation = taux × min(brut, plafond) par salarié).

> **Exemple réel — facture CSS/IPRES mai 2026 (employeur 0007485811, 699 099 FCFA) :**
> IPRES RG : 4 079 443 × 14 % = 571 122 · IPRES Cadre : 1 208 948 × 6 % = 72 537 → **Total IPRES 643 659**.
> CSS Prest. familiales : 693 000 × 7 % = 48 510 · AT/MP : 693 000 × 1 % = 6 930 → **Total CSS 55 440**.
> Base CSS 693 000 = **11 salariés × 63 000** (plafond/salarié) → confirme la mécanique de plafonnement. CFCE 3 % = sur brut **total** (non plafonné, cf. VRS).
> **Écriture du règlement** (le `BankMovement` qui paie les 699 099, justificatif = cette facture) : `Dr 431 (55 440) + Dr 432 (643 659) / Cr 5211 (699 099)`.

Schéma complet d'un mois de paie (constatation à l'engagement) :
```
Dr 6611   Salaires (BRUT)                          brut
   Cr 422  Personnel, rémunérations dues               brut
Dr 422    Personnel                                 ISR+TRIMF+IPRES_sal
   Cr 447  État (ISR + TRIMF)                          ISR + TRIMF
   Cr 432  IPRES (part salariale)                      ipres_sal
Dr 664    Charges sociales patronales               ipres_pat + css
   Cr 432  IPRES (part patronale)                      ipres_pat
   Cr 431  CSS (prest. familiales + AT)                css
Dr 6413   Taxes sur salaires (CFCE)                 3% du brut
   Cr 44   État (CFCE)                                 cfce
Dr 462    Bailleurs - Fonds d'administration        (brut + 664 + CFCE)   } quote-part
   Cr 702  Quote-part au résultat                      (brut + 664 + CFCE) } à l'engagement
```
> **Cadrage produit décisif (révisé) :** la **paie/RH fait partie du périmètre EVE Pilot, mais en PHASE ULTÉRIEURE** — après la mise en conformité SYCEBNL. Une fondation RH existe déjà (`apps/hr` : `Employee`, `Contract`, `Payslip`, `Leave`…). Voir §6-bis.
>
> **Conséquence sur la compta (maintenant) :** pour rendre la compta SYCEBNL valide **sans attendre** le module paie complet, le Palier 1 enregistre la paie sous forme de **récapitulatif mensuel** (un `JournalEntry` par mois, totaux par composante saisis depuis les états BRS/VRS/DNS + facture CSS/IPRES). Pas de calcul, pas de per-employé. Le passage au per-employé (via `hr.Payslip`) se fera en phase RH.

> ⚠️ **Restent à fixer** (valeurs, pas structure) : taux exacts IPRES (RG vs Cadre) et CSS, sous-compte exact du CFCE (6413 vs autre). À prendre dans les bordereaux IPRES/CSS chiffrés (le template DNS fourni ne contient que la structure, pas les taux).

#### E3-ter — Retenue à la source sur tiers/prestataires (B.R.S. 5 %)
L'état **B.R.S.** d'EVE montre une retenue de **5 %** sur les paiements aux **prestataires** (staff de terrain SL/FD payé hors salariat) et sur les **loyers** (ex. LOCATION SIEGE 500 000 → 25 000). À intégrer dans E2 (règlement fournisseur/prestataire) :
```
Dr 6xx    Charge (honoraires, loyer…)              brut
   Cr 447  État, retenue à la source (BRS 5%)          5% du brut
   Cr 401/5211  Fournisseur / Banque (net)             95% du brut
```
> Conséquence : tout paiement à un prestataire ou bailleur de locaux doit gérer la **RAS tiers 5 %**. Le moteur actuel l'ignore (paiement brut direct). À cadrer avec l'expert : seuils et catégories exactes soumises à la BRS.

### E4 — Acquisition d'immobilisation sur projet
```
(a) Dr 2xx Immobilisation / Cr 401 (ou 481) Fournisseur d'investissement
(b) Paiement : Dr 401 / Cr 5211
(c) PAS de neutralisation 462/702 immédiate (162 reste intact).
(d) À chaque clôture, amortissement + reprise du fonds, AU MÊME RYTHME que l'amortissement :
      Dr 6813 Dotation aux amortissements / Cr 28x Amortissements
      Dr <compte fonds> / Cr <compte reprise>   (à hauteur de la dotation de l'exercice)
```
**✅ CONFIRMÉ (Guide d'application — fonctionnement comptes 14, 16, commentaires) — le compte de reprise dépend de la nature du fonds :**

| Origine du financement de l'immobilisation | Compte fonds (passif) | Reprise au résultat (produit) | Rythme |
|---|---|---|---|
| Subvention d'investissement (État, organismes) | 14 (141…) | **799** Reprises de subventions d'investissement | Rythme des amortissements |
| Fonds affecté à un **projet spécifique** | 165 | **7925** Reprises de fonds affectés à un projet spécifique | Au fur et à mesure de la consommation |
| Dons et legs d'immobilisations conservées | 167 | **792** Reprises de fonds affectés / dons et legs | Même taux d'amortissement du bien |

> ⚠️ **RESTE À CONFIRMER** : le compte de reprise du **162** (« fonds affectés aux investissements du projet de développement – bailleurs ») n'est pas explicite sur les pages fournies. Par analogie il devrait être **792x**, mais il faut la page *« Fonctionnement du compte 16 »* pour trancher 792 vs un sous-compte dédié. Au passage : à la **cession** de l'actif, le solde non encore rapporté est repris (cf. compte 14 → 799 à la cession).

### E5 — Travaux de clôture (cut-off)
```
Charges engagées non encore facturées : Dr 6xx / Cr 408 (fournisseurs FNP)
Charges de personnel à payer (congés)  : Dr 6613/664 / Cr 428 / 438
Impôts à payer                          : Dr 6xx / Cr 4486
Produits à recevoir                     : Dr 4487 / Cr 7xx
Ressources affectées non consommées     : RESTENT en 162/165/462 (déjà au passif).
   ✅ CONFIRMÉ (compte 16) : les fonds affectés non entièrement consommés en fin
   d'exercice demeurent en classe 16 "conformément aux directives du tiers financeur".
   PAS de reclassement en 17x (la classe 17 "Fonds reportés" vise l'usufruit et les
   dons/legs d'immobilisations destinées à la vente, pas les reliquats de projets).
Extourne des écritures de cut-off à l'ouverture de l'exercice suivant.
```

---

## 6. Impact technique sur le code

### 6.1 Nouveaux faits générateurs d'écriture
Aujourd'hui : `post_bank_movement` / `post_cash_movement` (trésorerie).
Cible : ajouter des fonctions de posting déclenchées par **l'engagement**, pas la trésorerie :
- `post_supplier_invoice(commitment_or_invoice)` → E2(a)+(b)
- `post_payroll(payroll_run)` → E3(a)+(b)+(c)
- le `BankMovement` devient, quand il solde une dette, un **règlement** : `Dr 401/422/43x / Cr 5211` (E2c, E3d) au lieu de `Dr 6xx / Cr 5211`.

### 6.2 Nouveaux modèles probables
- `SupplierInvoice` (ou enrichir `Commitment` avec un statut « facturé » qui poste).
- **Paie Palier 1 : `PayrollSummary`** = un récap mensuel (totaux : brut, ISR, TRIMF, CFCE, IPRES sal/pat, CSS, net) → 1 `JournalEntry`. **PAS** de `PayrollRun`/`PayrollLine` per-employé en Palier 1 (ça viendra via `hr.Payslip` en phase RH — §6-bis).
- Lien `BankMovement.settles` → FK vers la dette soldée (401/422/43x) pour router le paiement en règlement de dette plutôt qu'en charge.

### 6.3 Refonte de `posting.py`
- `_post_simple` / `_post_with_allocations` : distinguer **charge directe** (cas sans engagement préalable, ex. petite caisse) vs **règlement de dette** (engagement préexistant).
- La neutralisation 462/702 doit migrer du décaissement vers l'**engagement**.

### 6.4 Seed
- Source unique du plan comptable : `seed_chart_of_accounts` (plan SYCEBNL/SYSCOHADA resserré et conforme, ~236 comptes). Remplace l'ancien trio `_sycebnl` / `_detailed` / `_official`.
- Classe 40 intégrée (401, 4011) ; 4812 pour les fournisseurs d'investissement. 408/409 (cut-off) à ajouter si la clôture l'exige.

---

## 6-bis. Module RH/paie — existant et raccordement futur

EVE Pilot **inclut** la paie/RH, mais en **phase ultérieure** (après la conformité SYCEBNL). Une fondation existe déjà dans `apps/hr` :

| Modèle existant (`apps/hr`) | Contenu | Suffisant pour la compta ? |
|---|---|---|
| `Employee` | matricule, n° IPRES/CSS/fiscal, banque, catégorie | ✅ |
| `Contract` | salaire brut/net, type, projet | ✅ |
| `Payslip` | période, gross, **ipres/css/ir/trimf**, net, statut BROUILLON/VALIDE/PAYE | ⚠️ **incomplet** : ne capte que les **retenues salariales**, pas les **charges patronales** (CFCE, IPRES/CSS part employeur) ni le projet d'imputation |
| `Leave`, `Evaluation`, `EmployeeDocument` | congés, évaluations, pièces | hors compta |

**Raccordement futur (phase RH) :**
1. Étendre `Payslip` avec les **charges patronales** (cfce_amount, ipres_employer, css_employer) + lien projet/budget_line.
2. `Payslip.status = VALIDE` → déclenche l'écriture E3 **par employé** (remplace le `PayrollSummary` mensuel du Palier 1).
3. `Payslip.status = PAYE` → le `BankMovement` de paiement solde 422 (net).
4. Le **barème catégoriel** (secteur privé) et le **barème IRPP** alimentent le **calcul** du bulletin dans ce module — c'est là, et seulement là, qu'ils servent.

> En clair : Palier 1 = paie en **récap mensuel** (compta valide tout de suite). Phase RH = paie **per-employé** via `hr.Payslip` qui poste en compta. Le second remplacera proprement le premier.

---

## 7. Plan de migration progressif (recommandé)

Ne pas tout basculer d'un coup. Trois paliers :

- **Palier 0 — Décision de périmètre.** Confirmer l'audience (bailleur/CAC exigent des états SYCEBNL audités ? → système normal complet). Confirmer l'éligibilité (>30M → oui). Faire valider cette spec par l'expert-comptable.
- **Palier 1 — Engagement (compta).** Seeder la classe 40 ; `SupplierInvoice` (fournisseurs à l'engagement) ; **RAS tiers 5 %** ; **paie en récap mensuel** (`PayrollSummary` → 1 écriture/mois, E3) ; router les `BankMovement` de règlement en `Dr 401/422/43x/44 / Cr 5211`. C'est l'essentiel de la mise en conformité.
- **Palier 2 — Clôture & cut-off.** Écritures de fin d'exercice (E5), reprises d'amortissement neutralisées, états financiers SYCEBNL (bilan, compte de résultat, tableau des emplois/ressources).
- **Phase RH (ultérieure, après compta valide)** — paie **per-employé** : étendre `hr.Payslip` (charges patronales + projet), pont `Payslip → JournalEntry` (remplace le récap mensuel du Palier 1), calcul du bulletin (barèmes catégoriel + IRPP). **Sa propre spec.**

> Séquencement validé par le porteur : **compta SYCEBNL valide et fonctionnelle d'abord, paie/RH ensuite.** Le récap mensuel du Palier 1 garantit une compta juste sans attendre le module RH complet.
> Pendant la transition, possibilité d'un **hybride documenté** : caisse au quotidien + écritures d'ajustement d'engagement à la clôture. À faire valider par le CAC.

---

## 8. Points à confirmer — protocole « page du guide »

**Méthode adoptée :** pour chaque schéma incertain, on nomme la **section précise du guide d'application** ; l'utilisateur fournit la page ; on grave le schéma dans la spec avec la citation. Le guide d'application fait foi.

### ✅ Résolus par les pages déjà fournies (comptes 13, 14, 16)
- Avance bailleur : 161 avances à justifier → reclassement 162-164 ; avances/à-recevoir présentés via 46 (E1).
- Reprise immobilisation : 14 → **799** (rythme amortissements) ; 165 → **7925** (consommation) ; 167 → **792** (taux d'amortissement) (E4).
- Ressources affectées non consommées : **restent en classe 16**, pas de 17x (E5).
- Compte 13 (résultat) : soldé par classes 6/7/8, sans court-circuit des comptes de gestion.

### ✅ Résolus par les pages fournies (comptes 46, 70)
- **P2 — fonds d'administration + quote-part : CONFIRMÉ.** `Dr trésorerie / Cr 46` à la mise à disposition ; `Dr 46 / Cr 702` **à l'engagement des charges**. Sens du moteur EVE certifié juste ; timing à corriger (engagement, pas décaissement). Exclusions du 46 (invest→16, dotation→10, cotisations→411) validant l'architecture 162/462.
- Compte 70 (Revenus) : crédité des facturations HT (701-708) / Cr 443 TVA, débit 41 ou trésorerie ; soldé en 13 à la clôture. Subventions d'exploitation → 71 (exclusion). N'impacte pas le mécanisme bailleur (qui passe par 46/702, pas 70x courants).

### ✅ Résolus par les pages fournies (comptes 40, 42, 43, 44)
- **P3 — fournisseurs : CONFIRMÉ.** 401 (4011/4013/4017), 408 (4081 factures non parvenues), 409 (4091 avances versées), 481 fournisseurs d'investissements. **Tous absents du seed → à créer (Palier 1).**
- **P4 — paie : CONFIRMÉ et schéma E3 corrigé.** Transit par 42 : `Dr 66 / Cr 42` (brut) → `Dr 42 / Cr 43` (cotis. salariales) + `Dr 42 / Cr 44` (IR retenu) → solde 42 = net. 43 reçoit salariale (par 422) + patronale (par 664). Règlements : `Dr 42/43/44 / Cr trésorerie`.

### ⏳ Pages du guide encore nécessaires (par ordre de priorité)
| # | Schéma à confirmer | Section précise demandée |
|---|---|---|
| P1 | Compte de **reprise du 162** (part investissement bailleur) — probablement 792x | **« Fonctionnement du compte 16 »** (le tableau crédit/débit, comme pour 13/14/46). *Les pages fournies sont le Contenu/Commentaires du 16, pas son tableau de fonctionnement.* Priorité **basse** (immos rares chez EVE). |
| P5 | Opérations spécifiques projets de développement (cycle complet bailleur) | **Partie 3 : Opérations et problèmes spécifiques aux EBNL, chapitre 1** |
| P6 | États financiers EBNL (bilan, compte de résultat, tableau emplois/ressources) | **Partie sur les états financiers SYCEBNL** |

### ✅ Résolu par les déclarations réelles d'EVE (états BRS/VRS mai 2026, DNS IPRES-CSS)
- **EVE applique bien les retenues.** Paie salariée : **ISR + TRIMF** (salarial → 447 État), **CFCE 3 %** (patronal → 6413/44), **IPRES** (sal+pat → 432), **CSS** (pat → 431). Cf. E3-bis.
- **RAS tiers 5 % (BRS)** sur prestataires et loyers → 447 État. Cf. E3-ter. Le moteur actuel l'ignore.
- **Cadrage : la paie est calculée hors EVE Pilot** (logiciel de paie dédié). EVE Pilot **enregistre** le récap mensuel, ne le recalcule pas → pas de barème IR à coder.
- **Taux IPRES/CSS CONFIRMÉS (secusociale.sn) :** IPRES RG 14 % (8,4/5,4) plafond 432 000 ; IPRES Cadre 6 % (3,6/2,4) plafond 1 296 000 ; CSS prest. fam. 7 % plafond 63 000 ; CSS ATMPF 1/3/5 % plafond 63 000. CFCE 3 % brut total.

### ✅ Confirmé par la facture CSS/IPRES réelle (mai 2026)
- **ATMPF d'EVE = 1 %.** IPRES RG 14 %, Cadre 6 %, CSS prest. fam. 7 % — tous appliqués sur assiette plafonnée par salarié. Cf. exemple chiffré en E3-bis.

### ⚖️ Détails résiduels (mineurs, n'empêchent pas le Palier 1)
- Sous-compte exact du **CFCE** (6413 « Taxes sur salaires » vs autre) — simple libellé de compte.
- Catégories/seuils exacts soumis à la **BRS 5 %** (prestataires, loyers) — à border avec l'expert.
- *Ces points relèvent du paramétrage de libellés/comptes, pas de la structure. La paie étant calculée hors EVE Pilot, ils n'affectent que l'enregistrement.*

---

## 9. Sources

- [OHADA — Acte uniforme SYCEBNL (présentation officielle)](https://www.ohada.com/actualite/6569/acte-uniforme-relatif-au-systeme-comptable-des-entites-a-but-non-lucratif-sycebnl.html)
- [OHADA — Disponibilité de l'Acte uniforme SYCEBNL](https://www.ohada.com/actualite/6692/disponibilite-de-lacte-uniforme-ohada-relatif-au-systeme-comptable-des-entites-a-but-non-lucratif.html)
- [Guide d'application SYCEBNL (PDF officiel ohada.org)](https://www.ohada.org/wp-content/uploads/2023/04/SYCEBNL-GUIDE-D-APPLICATION.pdf) — *référence contraignante*
- **Guide d'application — pages fournies par l'utilisateur (comptes 13, 14, 16 ; fonctionnement 46, 70, 40, 42, 43, 44)** — *intégrées en v1.1 à v1.3, source primaire*
- [CAB Consulting — Pratique du SYCEBNL (seuils système normal / SMT)](https://cab-consulting.net/fr/2025/02/26/pratique-du-systeme-comptable-des-entites-a-but-non-lucratif-sycebnl/)
- [Mécanisme des fonds dédiés (référence association, comparatif)](https://www.compta-online.com/la-comptabilisation-des-fonds-dedies-dans-les-associations-ao1252)
- **Plan de comptes seedé dans l'application** (`apps.finance.ChartOfAccount`) — *source opérante interne*.
- **Déclarations réelles EVE (mai 2026)** : état B.R.S., état V.R.S., template DNS IPRES-CSS — *source primaire pour les composantes de paie ; intégrées en v1.4*.
- [CSS-IPRES — Taux et plafonds de cotisations (employeur)](https://online.secusociale.sn/cssipreslanding/employeur) — *taux officiels IPRES/CSS, intégrés en v1.5*.
- **Facture cotisations sociales CSS/IPRES n° 999000121651 (mai 2026, ONG Eau Vie Environnement)** — *confirme ATMPF 1 % et le plafonnement ; intégrée en v1.6*.

---

*Fin de la spécification v1.7. Prête pour validation expert-comptable.*
