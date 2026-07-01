# Design — Brancher l'engagement SYCEBNL sur le workflow des demandes de dépense

> Statut : **PROPOSITION, à valider avant construction** (2026-07-01).
> Objectif : que le circuit `ExpenseRequest` produise la comptabilité d'**engagement**
> (Dr 6x / Cr 401 puis Dr 401 / Cr 5x), au lieu de l'écriture de **trésorerie** unique
> actuelle (Dr 6x / Cr 5x au paiement).

## 1. État actuel (constaté dans le code)

- Circuit : `DRAFT → SUBMITTED → (3 validations RAF/DP/SE) → APPROVED → [facture] → « Saisir la dépense » → EXECUTED`.
- « Saisir la dépense » (`expense_record_payment`, `RecordPaymentForm`) crée un `BankMovement`/`CashMovement`
  (débit = sortie), `contra_account` **choisi librement** par le comptable, et le signal
  `post_bank_movement` poste **une seule écriture** : `Dr [contra] / Cr 5x`.
  → avec un contra 6x, c'est de la **trésorerie** : la charge naît au paiement, pas de 401.
- Le moteur d'engagement `post_commitment()` **existe et est prouvé** (Dr 6x/Cr 401 + neutralisation
  462/702 projet ; immobilisation Dr 2/Cr 481 ; idempotent ; anti-double-neutralisation structurel),
  mais **n'est appelé que par une action admin manuelle sur un `Commitment`**. `Commitment` n'a
  **aucun lien** vers `ExpenseRequest`.

**Écart :** aucune écriture d'engagement dans le circuit des demandes ; la charge est constatée au décaissement.

## 2. Cible

`… APPROVED → ENGAGED → EXECUTED`, avec :
1. **Engager** : `Dr 6x / Cr 401.x` (+ `Dr 462 / Cr 702` si projet opérationnel), via `post_commitment()`.
2. Réalisation + justification (facture définitive).
3. **Saisir le paiement** : `Dr 401.x / Cr 5x` (solde le fournisseur), **sans re-passer la charge**.

## 3. Décision de fond — TRANCHÉE : Option L (liquidation / facture)

**La charge `Dr 6x / Cr 401` naît à la LIQUIDATION (facture / service fait)**, décision de
l'expert le 2026-07-01. L'étape « Engager » reste **budgétaire** ; `post_commitment()` est
déclenché **quand la facture définitive est attachée**.

### 3bis. Flux retenu (Option L)

| Transition | Action | Effet comptable | Effet budgétaire | Statut |
|---|---|---|---|---|
| APPROVED → | valider 3/3 | — | — | APPROVED |
| → ENGAGED | **Engager** (choix fournisseur) | **aucune écriture GL** | `committed_amount += montant` | ENGAGED |
| → LIQUIDATED | **attacher facture définitive** | `post_commitment()` : `Dr 6x / Cr 401.x` (+ `Dr 462 / Cr 702` si projet) | — | LIQUIDATED |
| → EXECUTED | **Saisir le paiement** | `Dr 401.x / Cr 5x` (solde fournisseur) | `disbursed_amount += payé` | EXECUTED |

- « Engager » ne poste **rien** au grand-livre : il réserve le budget et fixe le fournisseur
  (nécessaire au futur 401.x). C'est la phase « en attente de réalisation ».
- La **facture** est le pivot : elle constate la charge (liquidation SYCEBNL).
- Le **paiement** solde le 401, sans re-charge (garde-fou structurel).
- Cohérence avec la page projet (Prévu / **Engagé** / **Décaissé**) : `committed_amount` bougé à
  l'engagement, `disbursed_amount` au paiement.

> Statuts : ajouter **ENGAGED** et **LIQUIDATED** (`choices`, pas de schéma). LIQUIDATED peut aussi
> être dérivé de l'existence de `JournalEntry.source_commitment` — mais un statut explicite clarifie l'UI.

## 4. Décisions de conception (à valider)

### 4.1 Statut ENGAGED
Ajouter `ExpenseRequest.Status.ENGAGED` entre APPROVED et EXECUTED. Pas de changement de schéma
(les statuts sont des `choices`).

### 4.2 Lien demande ↔ engagement
`ExpenseRequest.commitment = OneToOneField("finance.Commitment", null=True, blank=True, SET_NULL)`.
Nul tant que non engagée. **1 migration.**

### 4.3 Fournisseur (401.x)
`post_commitment()` exige `commitment.supplier`. `ExpenseRequest` n'a pas de fournisseur.
→ Choix du fournisseur **au moment de l'action « Engager »** (petit formulaire : `supplier`,
override optionnel du compte de charge, date d'engagement). Le compte de charge par défaut vient
de `budget_line.category.default_charge_account` (déjà seedé).

### 4.4 Le paiement solde le 401
`RecordPaymentForm` : si la demande est ENGAGED (a un `commitment`), **forcer**
`contra_account = commitment.supplier.chart_account` (401.x) au lieu du choix libre 6x.
⇒ `post_bank_movement` poste `Dr 401.x / Cr 5x`, contra de classe 4 ⇒ **pas de neutralisation,
pas de re-charge** (garde-fou structurel déjà en place). Le chemin trésorerie actuel (contra 6x libre)
reste dispo pour les demandes **non engagées** (rétro-compat).

### 4.5 Immobilisations
Déjà géré par `post_commitment` : compte d'emploi de classe 2 ⇒ `Dr 2 / Cr 481.x`, paiement
`Dr 481.x / Cr 5x`. Rien à ajouter.

## 5. Cas limites (à valider)

- **Montant engagé ≠ payé** (TVA, remise) : v1 = l'écart laisse un **solde résiduel sur le 401**
  à réconcilier (signalé à l'écran). Ajustement automatique = hors v1.
- **Annulation après engagement** : v1 = **bloquer l'annulation** une fois ENGAGED (la
  contre-passation d'engagement est une évolution ultérieure).
- **Paiement partiel** : v1 = un seul paiement solde le 401. Multi-paiement = hors v1.

## 6. Garde-fous & tests

- **Anti-double-charge** : structurel (paiement sur 401 classe 4). Test dédié :
  engager → `Dr6/Cr401` (+462/702) ; payer → `Dr401/Cr5` ; **charge comptée une seule fois** ;
  solde 401 = 0 après paiement au montant engagé.
- `post_commitment` refuse déjà si supplier/charge manquant (`PostingError`) ; le form d'engagement
  rend le fournisseur obligatoire.
- Test immobilisation (Dr2/Cr481 → Dr481/Cr5).
- Test rétro-compat : demande non engagée → chemin trésorerie inchangé.

## 7. Découpage de livraison (après validation)

1. Migration : `ExpenseRequest.commitment` (OneToOne) + statut ENGAGED.
2. Action « Engager » + formulaire fournisseur → crée `Commitment` (+ `post_commitment` selon Option E/L).
3. Paiement : forcer `contra_account` = 401.x quand la demande est engagée.
4. UI : bouton « Engager » (fiche APPROVED) ; masquer le formulaire « lier un mouvement existant »
   quand il est vide (dette UX déjà notée) ; afficher l'écriture d'engagement sur la fiche ENGAGED.
5. Tests (section 6).

## 8. Ce qui NE change pas

- `post_commitment()` / `post_bank_movement()` : réutilisés tels quels (prouvés en UAT).
- Le plan comptable, le mapping catégorie→6x, les fournisseurs 401.x : déjà en place.
- Le circuit de validation à 3 (RAF/DP/SE) : inchangé.
