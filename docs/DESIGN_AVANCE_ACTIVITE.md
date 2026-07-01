# Design — Flux d'avance sur activité (compte 409x / 425)

> Statut : **PLANIFIÉ, à construire APRÈS l'UAT** (2026-07-01, décision utilisateur).
> Contexte : les activités terrain (réunions, formations) sont décaissées en **avance**
> à un organisateur AVANT réalisation ; il justifie le réel et **rend le reliquat**.
> La charge doit naître à la **justification**, pas au décaissement.

## 1. Écritures cibles

| Étape | Écriture | Nature |
|---|---|---|
| Décaissement de l'avance | `Dr 409x (avance) / Cr 5x (trésorerie)` | mouvement trésorerie, **PAS de charge** |
| Justification (après activité) | `Dr 6x (charge) / Cr 409x` — montant réel justifié | **OD (sans trésorerie)** |
| Reliquat rendu | `Dr 5x (caisse/banque) / Cr 409x` — résiduel | mouvement trésorerie |

**Invariant :** `409x` revient à **0** (avance = justifié + reliquat). La charge = le réel justifié.

## 2. Prérequis manquants (constatés dans le code, 2026-07-01)

### 2.1 Compte d'avance absent du plan
`seed_chart_of_accounts` n'a **ni 409x ni 425**. À ajouter en **UPDATE in-place** (jamais
DELETE+CREATE — casserait les FK, cf. règle projet). **Décision comptable à trancher :**
- **4091** « Fournisseurs, avances et acomptes versés sur commandes » — si l'organisateur est traité comme un tiers/fournisseur.
- **425** « Personnel, avances et acomptes » — si l'organisateur est un salarié (souvent le cas : facilitateur, chargé de suivi).
> Recommandation : probablement **425** pour les avances aux staff (organisateurs d'activité), 4091 réservé aux avances fournisseurs. À confirmer par l'expert.

### 2.2 Aucune saisie d'OD (écriture manuelle équilibrée)
`JournalEntry` ne naît que d'un `BankMovement` / `CashMovement` / `Commitment`. La
**justification** (`Dr 6x / Cr 409x`, cashless) n'a pas de mouvement de trésorerie → il
faut une **brique OD** : écriture manuelle à N lignes, débit = crédit obligatoire
(`_assert_balanced`). **Réutilisable bien au-delà** : reclassements, régularisations,
à-nouveaux, corrections. C'est le vrai livrable structurant de ce chantier.

## 3. Modèle & workflow

- **Brique OD** : soit un modèle `ManualJournalEntry` (en-tête + lignes saisies), soit
  `JournalEntry` avec une source "OD" et des lignes libres, passé par un `post_od()`
  qui valide l'équilibre. Form + UI de saisie (choisir comptes, débits/crédits, pièce).
- **Demande** : à la saisie du paiement, un mode **« Avance à régulariser »** (vs paiement
  définitif). En mode avance : le mouvement poste `Dr 409x / Cr 5x` (contra = 409x, classe 4
  → pas de charge, garde-fou structurel comme pour le 401). Statut demande → **ADVANCED**.
- **Action « Régulariser l'avance »** (sur une demande ADVANCED) : saisir le **montant justifié**
  + le **reliquat** ; poste (a) l'OD `Dr 6x / Cr 409x` du justifié, (b) le mouvement trésorerie
  `Dr 5x / Cr 409x` du reliquat. Contrôle : justifié + reliquat = avance. Statut → EXECUTED.
- **Suivi** : solde 409x par avance (résiduel non régularisé visible).

## 4. Garde-fous & tests

- L'avance ne poste **aucune charge** (contra 409x, classe 4).
- Régularisation : `justifié + reliquat == avance` sinon refus (équilibre du 409x).
- OD : **débit = crédit** obligatoire (`_assert_balanced`), sinon rollback.
- Test bout en bout : avance `Dr 409/Cr 5` → justif `Dr 6/Cr 409` → reliquat `Dr 5/Cr 409` ;
  **409 net = 0**, charge = réel justifié, trésorerie = sortie nette réelle.
- Reliquat rendu en caisse puis reversé banque : transfert trésorerie (déjà faisable via
  mouvements existants), à documenter dans le pas-à-pas.

## 5. Découpage de livraison (après validation)

1. Ajouter le compte d'avance (409x et/ou 425) au `seed_chart_of_accounts` (UPDATE in-place).
2. **Brique OD** : modèle/posting équilibré + form + UI (livrable réutilisable).
3. Mode « avance » à la saisie de paiement + statut ADVANCED (migration statut).
4. Action « Régulariser » (OD justification + mouvement reliquat).
5. Tests (section 4).

## 6. En attendant (contournement UAT, sans dev — cf. session 2026-07-01)

Décaisser via `Dr 6x / Cr 5x` (contra 638) pour le total, puis à la rentrée du reliquat :
`Dr 571.caisse / Cr 638` (retour caisse) puis `Dr 5211.banque / Cr 571.caisse` (reversement).
Position finale exacte (charge = réel) ; seule impureté : charge surévaluée entre décaissement
et retour (quelques jours), et pas de compte d'avance. Acceptable pour une activité réglée
dans la foulée.
