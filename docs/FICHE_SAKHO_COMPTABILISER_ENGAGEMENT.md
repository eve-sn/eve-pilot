# Fiche SAKHO — Comptabiliser un engagement (compta d'engagement SYCEBNL)

> Objet : créer un fournisseur, saisir un engagement, le comptabiliser, puis
> lire l'écriture. Tout se passe dans l'**admin** : `https://pilot.eve-sn.org/admin/`,
> section **Finance**.
>
> Rappel du schéma produit : à la comptabilisation, l'appli génère
> automatiquement `Dr 6x (charge) / Cr 401.x (fournisseur)` **+**, sur un projet,
> la neutralisation `Dr 462 / Cr 702`. Le décaissement (paiement) viendra
> **après**, imputé sur le `401.x`, et ne re-neutralise pas.

---

## Étape 1 — Créer le fournisseur (une seule fois par fournisseur)

1. Admin ▸ **Finance** ▸ **Suppliers** ▸ bouton **« Ajouter Supplier »** (en haut à droite).
2. Renseigner :
   - **Name** : nom du fournisseur (ex. `ATELIER FORMATION CLIMAT`).
   - **Nif** : NIF si disponible (sinon laisser vide).
   - **Phone / Address** : facultatif.
   - **Is service provider** : cocher si c'est un **prestataire de services**.
3. **Enregistrer**.

> ✅ À l'enregistrement, l'appli crée automatiquement le **code** (`F001`, `F002`…)
> **et** son sous-compte auxiliaire **`401.<code>`** dans le plan de comptes.
> Rien à faire de plus côté comptes.

> ⚠️ **Ne pas recréer** un fournisseur qui existe déjà : chercher d'abord dans la
> liste (barre de recherche). Un doublon = deux comptes 401 pour un même
> fournisseur, et un grand-livre auxiliaire faux.

---

## Étape 2 — Saisir l'engagement

1. Admin ▸ **Finance** ▸ **Commitments** ▸ **« Ajouter Commitment »**.
2. Renseigner :
   - **Budget line** : la ligne budgétaire imputée (taper pour rechercher, ex.
     `FORM-CLIMAT` / `Formation thématique climat`).
   - **Supplier** : le fournisseur de l'étape 1 (taper pour rechercher).
   - **Amount** : montant engagé en FCFA (ex. `1200000`).
   - **Commitment date** : date de l'engagement.
   - **Commitment type** : Bon de commande / Contrat fournisseur / Achat direct / Mission.
   - **Description** : objet (ex. `Formation climat ECO-AVENIR - location + restauration`).
   - **Charge account** : **laisser VIDE** → le compte de charge est déduit
     automatiquement de la catégorie de la ligne (ex. formation → **633**).
     **Ne le remplir que pour surcharger** (ex. immobilisation classe 2, ou un
     compte plus précis que le défaut de la catégorie).
3. **Enregistrer**.

> Laisser **Supplier name / Supplier nif** (champs texte) vides : ce sont les
> anciens champs libres, remplacés par **Supplier**.

---

## Étape 3 — Comptabiliser

1. Revenir à la liste **Commitments**.
2. **Cocher** la case de l'engagement (ou de plusieurs).
3. Menu déroulant **« Action »** (en haut) ▸ choisir
   **« Comptabiliser l'engagement (Dr 6x / Cr 401.x + neutralisation 462/702) »**.
4. Cliquer **« Envoyer / Go »**.

> ✅ Bandeau vert : *« N engagement(s) comptabilisé(s) »*. La colonne
> **« Comptabilise »** de la liste passe au ✔ vert.
>
> L'action est **idempotente** : la relancer sur un engagement déjà comptabilisé
> ne crée pas de doublon.

---

## Étape 4 — Lire l'écriture produite

1. Admin ▸ **Finance** ▸ **Journal entries**.
2. Ouvrir l'écriture dont la **référence** = numéro d'engagement (ou `ENG-<id>`).
3. Vérifier les lignes (exemple formation 1 200 000 sur projet) :

   | Compte | Débit | Crédit |
   |---|---:|---:|
   | **633** Frais sur formations… | 1 200 000 | |
   | **401.F001** Fournisseur… | | 1 200 000 |
   | **462** Fonds d'administration | 1 200 000 | |
   | **702** Quote-part… | | 1 200 000 |

   → **Total débit = total crédit** (écriture équilibrée). C'est la charge engagée
   et neutralisée à l'engagement.

---

## En cas de message d'erreur (bandeau rouge)

| Message | Cause | Correctif |
|---|---|---|
| *aucun fournisseur (Supplier) rattaché* | Champ **Supplier** vide | Ouvrir l'engagement, choisir le fournisseur, enregistrer |
| *aucun compte de charge (ni surcharge, ni défaut sur la catégorie)* | La catégorie de la ligne n'a pas de compte par défaut (catégorie non engageable, ou nouvelle) | Renseigner **Charge account** à la main sur l'engagement, **ou** demander au référent de mapper la catégorie |
| *montant nul ou négatif* | **Amount** ≤ 0 | Corriger le montant |
| *le compte d'emploi … est de classe N…* | Charge account d'une classe autre que 6 (charge) ou 2 (immobilisation) | Choisir un compte de charge 6x (ou un compte d'immobilisation 2x pour du matériel capitalisé) |

---

## Rappels comptables

- **Paiement plus tard** : au décaissement, créer le mouvement bancaire en
  l'imputant sur le **compte du fournisseur `401.<code>`** (pas sur le compte de
  charge 6x). L'écriture sera `Dr 401.x / Cr 5211` (banque), **sans** re-neutralisation.
  Imputer le paiement sur le 6x au lieu du 401.x **double-compterait la charge**.
- **Immobilisation** (matériel > 300 000 FCFA) : mettre en **Charge account** un
  compte d'immobilisation **classe 2** ; l'écriture devient `Dr 2x / Cr 481.x`,
  **sans** neutralisation. *(Prérequis : que les comptes classe 2 soient actifs —
  à vérifier avec le référent.)*
