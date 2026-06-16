# Note de validation — Comptabilisation SYCEBNL d'EVE (1 page)

**À l'attention de :** l'expert-comptable / commissaire aux comptes — **De :** EVE (Eau Vie Environnement) — **Date :** 2026-06-14
**Objet :** valider les schémas d'écriture avant le passage de la comptabilité de **trésorerie** à la comptabilité **d'engagement** (SYCEBNL système normal). Détail complet : `SPEC_SYCEBNL_COMPTABILITE_ENGAGEMENT.md` (v1.7).

---

### Constat
Aujourd'hui les écritures ne sont générées qu'au **décaissement** (compta de trésorerie). EVE dépassant 30 M FCFA/an de financements → **système normal = engagement obligatoire**. Le mécanisme « projets de développement » (162/462/702) déjà en place est conforme ; **seul le fait générateur** (engagement vs paiement) et **l'absence de comptes fournisseurs / RAS** sont à corriger.

### Schémas d'écriture soumis à validation (Dr = débit, Cr = crédit ; 5211 = banque)

| # | Opération | Écriture |
|---|---|---|
| **E1** | Réception financement bailleur affecté | `Dr 5211 / Cr 162 (part invest.) / Cr 462 (part fonctionnement)` |
| **E2a** | Facture fournisseur (engagement) | `Dr 6xx (charge) / Cr 401 (fournisseur)` |
| **E2b** | Rattachement au résultat — **à l'engagement** | `Dr 462 / Cr 702` |
| **E2c** | Paiement fournisseur | `Dr 401 / Cr 5211` |
| **RAS** | Paiement prestataire/loyer avec **retenue à la source 5 %** | `Dr 6xx (brut) / Cr 447 (5 %) / Cr 5211 (95 %)` |
| **E3a** | Paie — constatation du brut | `Dr 6611 / Cr 422` |
| **E3b** | Retenues salariales (IPRES sal. 5,4 % / ISR / TRIMF) | `Dr 422 / Cr 432 (IPRES sal.) / Cr 447 (ISR+TRIMF)` |
| **E3c** | Charges patronales (IPRES 8,4 % + CSS 7 % + AT 1 %) | `Dr 664 / Cr 432 / Cr 431` |
| **E3d** | CFCE 3 % du brut (employeur) | `Dr 6413 / Cr 44` |
| **E3e** | Quote-part au résultat — à l'engagement | `Dr 462 / Cr 702 (brut + charges patronales)` |
| **E3f** | Règlements (net, social, fiscal) | `Dr 422 / 431 / 432 / 44 / Cr 5211` |
| **E4** | Immobilisation sur projet + reprise du fonds au rythme de l'amortissement | `Dr 28x` amort. ; `Dr 162 / Cr 792x` (reprise) |
| **E5** | Clôture (cut-off) | charges à payer `Cr 408/428/438/4486` ; produits à recevoir `Dr 4487` |

*Note paie : EVE Pilot enregistre un **récap mensuel** (totaux issus des états BRS/VRS/DNS + facture CSS/IPRES) ; la paie per-employé viendra en phase RH. Taux IPRES/CSS confirmés par la facture CSS/IPRES mai 2026 (n° 999000121651).*

### Points précis à confirmer (4)
1. **Reprise du compte 162** (part investissement bailleur) au résultat : compte **792x** ? (le guide donne 165→7925, 167→792, 14→799 ; 162 non explicite).
2. **Sous-compte du CFCE** : **6413 « Taxes sur salaires »** convient-il ?
3. **RAS 5 % (BRS)** : catégories et seuils exacts soumis (prestataires, loyers) ?
4. **Cumul IPRES Régime Général + Régime Cadre** pour un cadre : assiettes (432 000 puis jusqu'à 1 296 000) — règle exacte ?

### Déjà confirmé (sources : guide d'application SYCEBNL + déclarations réelles EVE)
Comptes 13/14/16/40/42/43/44/46/70 (fonctionnement) ; sens 462/702 ; comptes fournisseurs 401/408/409/481 ; taux IPRES RG 14 % (8,4/5,4) / Cadre 6 % (3,6/2,4) / CSS 7 % / AT **1 %** / CFCE 3 %.

---

**Validation de l'expert**

☐ Schémas approuvés en l'état ☐ Approuvés avec les réserves ci-dessous

Réserves / corrections : _______________________________________________________________

Nom : ___________________________  Signature / cachet : ___________________  Date : __________
