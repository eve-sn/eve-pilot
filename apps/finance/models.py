from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.models import TrackedModel


class ChartOfAccount(TrackedModel):
    """Plan de comptes SYCEBNL (Systeme Comptable des Entites a But Non Lucratif,
    declinaison SYSCOHADA pour les ONG).

    Convention :
    - `class_number` 1 a 8 selon la classification OHADA :
        1 Fonds propres / fonds dedies (inclut les comptes de liaison 181/180)
        2 Immobilisations
        3 Stocks
        4 Tiers (creances/dettes)
        5 Tresorerie (banques 512, caisse 571)
        6 Charges
        7 Produits
        8 Engagements hors bilan
    - `code` libre (peut etre 3, 4 ou 5 chiffres avec un point separateur EVE
      ex: '181.10', '512.60'). Unique sur l'application.
    - `parent` permet une hierarchie SYCEBNL (compte de regroupement vs
      sous-compte de detail).
    - `is_liaison` marque les comptes de liaison 18x (mouvements internes
      projet <-> BG).
    - `linked_project` / `linked_bank_account` / `linked_cash_register`
      permettent de tracer un sous-compte vers l'objet metier dont il
      represente le solde (un compte 181.10 vise NOUSCIMS-PIK-MBAO-2026,
      un compte 512.60 vise le BankAccount Budget General, etc.).
    """

    class AccountClass(models.IntegerChoices):
        FUNDS = 1, "1 - Fonds propres et fonds dedies"
        FIXED_ASSETS = 2, "2 - Immobilisations"
        STOCKS = 3, "3 - Stocks"
        THIRD_PARTIES = 4, "4 - Tiers"
        TREASURY = 5, "5 - Tresorerie"
        EXPENSES = 6, "6 - Charges"
        REVENUE = 7, "7 - Produits"
        OFF_BALANCE = 8, "8 - Engagements hors bilan"
        VOLUNTARY_CONTRIBUTIONS = 9, "9 - Contributions volontaires en nature"

    code = models.CharField(max_length=15, unique=True)
    name = models.CharField(max_length=200)
    class_number = models.PositiveSmallIntegerField(choices=AccountClass.choices)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="children",
    )
    is_liaison = models.BooleanField(
        default=False,
        help_text="Compte de liaison interne (18x : flux projet <-> BG).",
    )
    linked_project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="chart_accounts",
        help_text="Projet associe (pour les comptes de liaison 181.x).",
    )
    linked_bank_account = models.ForeignKey(
        "finance.BankAccount",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="chart_account",
        help_text="Compte bancaire reel associe (pour les comptes 512.x).",
    )
    linked_cash_register = models.ForeignKey(
        "finance.CashRegister",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="chart_account",
        help_text="Caisse reelle associee (pour les comptes 571.x).",
    )
    linked_supplier = models.ForeignKey(
        "finance.Supplier",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="chart_accounts",
        help_text="Fournisseur associe (pour les sous-comptes auxiliaires 401.x).",
    )
    description = models.TextField(blank=True)

    class Meta:
        db_table = "chart_of_accounts"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class BankAccount(TrackedModel):
    """Compte bancaire EVE. Plusieurs projets peuvent partager un meme compte
    (cf. Banque Atlantique pour ECP/Pikine Phase II/GT Wallu Dome)."""

    name = models.CharField(max_length=100, unique=True, help_text="Nom interne EVE du compte (ex: 'EVE-OXFAM', 'EVE service').")
    bank_name = models.CharField(max_length=100, blank=True, help_text="Nom de la banque (ex: 'SUNU BANK SENEGAL', 'CBAO', 'BOA').")
    account_reference = models.CharField(max_length=50, blank=True, help_text="RIB / IBAN si renseigne (libre).")
    currency = models.CharField(max_length=3, default="XOF")
    opening_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Solde d'ouverture connu (au plus recent snapshot).",
    )
    opening_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date du solde d'ouverture / dernier rapprochement.",
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "bank_accounts"
        ordering = ["name"]

    def __str__(self):
        if self.bank_name:
            return f"{self.name} ({self.bank_name})"
        return self.name


class BankAccountSnapshot(TrackedModel):
    """Solde date d'un compte bancaire. Permet de tracer l'evolution du solde
    dans le temps (rapprochements successifs, releves bancaires recus)."""

    account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name="snapshots")
    date = models.DateField()
    balance = models.DecimalField(max_digits=14, decimal_places=2)
    source_note = models.TextField(blank=True, help_text="Source du chiffre (releve bancaire, rapprochement compta, etc.).")

    class Meta:
        db_table = "bank_account_snapshots"
        ordering = ["account__name", "-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "date"],
                name="uq_bank_account_snapshot_per_date",
            )
        ]

    def __str__(self):
        return f"{self.account.name} @ {self.date}: {self.balance}"


class BankMovement(TrackedModel):
    """Mouvement bancaire reel constate sur un compte (releve bancaire ou
    rapprochement compta). Permet de reconstituer la trajectoire reelle d'un
    compte, par opposition au plan previsionnel CashflowEntry.

    Un mouvement = une ligne de relevé. Conventions :
      - debit  > 0 : sortie de tresorerie (paiement, retrait, frais).
      - credit > 0 : entree de tresorerie (virement recu, encaissement).
      - exactement l'un des deux est non nul.
      - balance_after : solde de la ligne tel qu'imprime sur le releve
        (optionnel, pour reconciliation).

    Imputation analytique :
      - budget_line designe la ligne budgetaire eligible (du BG ou d'un projet).
      - project peut etre deduit de budget_line.project mais reste stocke
        independamment pour les cas ou la budget_line n'est pas (encore)
        renseignee.
      - commentary porte la justification metier (numero piece, beneficiaire
        reel, motif).
    """

    account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name="movements")
    date_operation = models.DateField(help_text="Date d'operation telle qu'imprimee sur le releve.")
    date_value = models.DateField(blank=True, null=True, help_text="Date de valeur, si differente.")
    reference = models.CharField(max_length=50, blank=True, help_text="Reference banque (ex: G167265, F856524).")
    label = models.CharField(max_length=300, help_text="Libelle complet du mouvement tel que sur le releve.")
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance_after = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Solde apres operation tel que sur le releve.",
    )
    budget_line = models.ForeignKey(
        "finance.BudgetLine",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="bank_movements",
        help_text="Imputation analytique : ligne budgetaire (BG ou projet) eligible.",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="bank_movements",
        help_text="Projet auquel le mouvement se rapporte. Cohere avec budget_line.project quand les deux sont renseignes.",
    )
    cashflow_entry = models.ForeignKey(
        "CashflowEntry",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="bank_movements",
        help_text="Ligne de plan tresorerie matchee, si applicable (suivi reel/prevu).",
    )
    contra_account = models.ForeignKey(
        "finance.ChartOfAccount",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="bank_movements_contra",
        help_text="Compte SYCEBNL contrepartie (charge 6x, produit 7x, liaison 18x).",
    )
    commentary = models.TextField(
        blank=True,
        help_text="Justification metier de l'operation (numero piece, beneficiaire reel, motif).",
    )
    source_document = models.CharField(
        max_length=200,
        blank=True,
        help_text="Document source (ex: 'Releve Banque Atlantique decembre 2025').",
    )
    recipient = models.CharField(
        max_length=200,
        blank=True,
        help_text="Beneficiaire de la sortie ou source du credit (nom employe, fournisseur, bailleur).",
    )
    justification = models.FileField(
        upload_to="bank_justifications/%Y/%m/",
        blank=True,
        null=True,
        help_text="Piece justificative scannee (facture, ordre virement, avis credit).",
    )

    class Meta:
        db_table = "bank_movements"
        ordering = ["-date_operation", "-id"]
        indexes = [
            models.Index(fields=["account", "-date_operation"]),
            models.Index(fields=["reference"]),
            models.Index(fields=["budget_line"]),
        ]
        constraints = [
            # Idempotence des IMPORTS de releve uniquement : on ne deduplique
            # que les lignes qui portent une reference banque ET qui sont
            # actives. La saisie manuelle (reference vide) n'est jamais bloquee,
            # et une ligne annulee (soft-delete) ne bloque pas une re-saisie
            # identique. Cf. update_or_create() de import_bank_statement_xls.
            models.UniqueConstraint(
                fields=["account", "date_operation", "reference", "debit", "credit"],
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(reference=""),
                name="uq_bank_movement_idempotent_key",
            )
        ]

    def __str__(self):
        amount = self.credit if self.credit else -self.debit
        return f"{self.account.name} {self.date_operation} {amount:+.2f}"


class BankMovementAllocation(TrackedModel):
    """Ventilation analytique d'un BankMovement sur plusieurs imputations.

    Permet de decomposer un mouvement bancaire global (ex: cheque salaires
    equipe Saint-Louis 4,2M FCFA, frais atelier composes de plusieurs postes,
    factures fournisseurs multi-categories) en autant de lignes comptables
    que necessaire.

    Conventions :
      - chaque allocation porte son propre couple (project, budget_line,
        contra_account, amount, description) ;
      - la somme des allocation.amount doit egaler le BankMovement.debit OU
        BankMovement.credit selon le sens du mouvement ;
      - si aucune allocation n'existe, le BankMovement est traite comme une
        imputation simple via son contra_account principal.

    Le signal de finance.posting genere une JournalLine par allocation.
    """

    movement = models.ForeignKey(
        BankMovement, on_delete=models.CASCADE, related_name="allocations",
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, blank=True, null=True,
        related_name="bank_allocations",
    )
    budget_line = models.ForeignKey(
        "finance.BudgetLine", on_delete=models.SET_NULL, blank=True, null=True,
        related_name="bank_allocations",
    )
    contra_account = models.ForeignKey(
        "finance.ChartOfAccount", on_delete=models.PROTECT,
        related_name="bank_allocations",
        help_text="Compte SYCEBNL de charge (6x) ou de produit (7x) pour cette ligne.",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(
        max_length=300, blank=True,
        help_text="Detail de la ligne (ex: 'Salaire animateur 1 janvier 2026').",
    )

    class Meta:
        db_table = "bank_movement_allocations"
        ordering = ["movement_id", "id"]

    def __str__(self):
        return f"{self.movement_id} | {self.contra_account.code} | {self.amount}"


class BankMovementDocument(TrackedModel):
    """Piece justificative attachee a un mouvement bancaire.

    Permet d'attacher plusieurs documents (TDR, facture proforma, bon de
    commande, facture definitive, bordereau livraison, rapport activite,
    feuille presence, contrat, PV de selection, etc.).
    """

    class DocumentType(models.TextChoices):
        TDR = "TDR", "Termes de reference"
        PROFORMA = "PROFORMA", "Facture proforma"
        CONTRAT = "CONTRAT", "Contrat / convention"
        AVENANT = "AVENANT", "Avenant au contrat"
        PV_SELECTION = "PV_SELECTION", "PV de selection fournisseur"
        BC = "BC", "Bon de commande"
        FACTURE = "FACTURE", "Facture definitive"
        BORDEREAU = "BORDEREAU", "Bordereau de livraison"
        PRESENCE = "PRESENCE", "Feuille de presence"
        RAPPORT = "RAPPORT", "Rapport activite / livrable"
        ORDRE_VIREMENT = "ORDRE_VIREMENT", "Ordre de virement bancaire"
        AVIS_CREDIT = "AVIS_CREDIT", "Avis de credit bancaire"
        RELEVE = "RELEVE", "Extrait de releve bancaire"
        AUTRE = "AUTRE", "Autre piece"

    movement = models.ForeignKey(
        BankMovement, on_delete=models.CASCADE, related_name="documents",
    )
    document_type = models.CharField(max_length=25, choices=DocumentType.choices)
    file = models.FileField(upload_to="bank_documents/%Y/%m/")
    label = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_movement_documents"
        ordering = ["movement_id", "document_type"]

    def __str__(self):
        return f"{self.movement_id} / {self.document_type} : {self.label or self.file.name}"


class BankStatementImport(TrackedModel):
    """Brouillon d'import en lot d'un releve bancaire PDF.

    Workflow :
      1. Le comptable uploade un PDF de releve via /finance/banque/import-releve/
      2. Le parser extrait les lignes et auto-suggere les comptes contrepartie.
      3. Le brouillon est stocke (parsed_lines JSON) pour permettre la revue.
      4. Le comptable valide / corrige / supprime les lignes sur l'ecran.
      5. La validation finale cree les BankMovement en lot.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon en revue"
        IMPORTED = "IMPORTED", "Importe"
        CANCELLED = "CANCELLED", "Annule"

    account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE, related_name="statement_imports",
    )
    source_file = models.FileField(
        upload_to="bank_statements/%Y/%m/",
        help_text="PDF du releve bancaire original.",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT,
    )
    parsed_lines = models.JSONField(
        default=list,
        help_text=(
            "Liste des lignes extraites du PDF avec auto-suggestion. "
            "Chaque entree: {date_operation, label, debit, credit, "
            "suggested_contra_code, suggested_contra_name, raw_text}."
        ),
    )
    nb_lines_parsed = models.PositiveIntegerField(default=0)
    nb_lines_imported = models.PositiveIntegerField(default=0)
    submitted_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, blank=True, null=True,
        related_name="bank_statement_imports",
    )
    imported_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "bank_statement_imports"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Import {self.account.name} {self.created_at:%Y-%m-%d} - {self.status}"


class CashRegister(TrackedModel):
    """Caisse centrale EVE (menue depense). Une seule caisse a date.

    Regles metier :
    - Plafond unitaire : 40 000 FCFA par operation (rejet si depassement).
    - Plafond hebdomadaire (semaine ISO) : 200 000 FCFA cumule sur les
      sorties de caisse (rejet si depassement).
    """

    UNIT_LIMIT = Decimal("40000.00")
    WEEKLY_LIMIT = Decimal("200000.00")

    name = models.CharField(max_length=80, unique=True, default="Caisse centrale BG")
    currency = models.CharField(max_length=3, default="XOF")
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    opening_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "cash_registers"
        ordering = ["name"]

    def __str__(self):
        return self.name


class JournalEntry(TrackedModel):
    """Ecriture comptable en partie double (SYCEBNL).

    Une ecriture regroupe N JournalLine dont la somme des debits doit egaler
    la somme des credits. Une ecriture peut etre auto-generee a partir d'un
    BankMovement ou d'un CashMovement (la source est tracee par FK), ou
    saisie manuellement.
    """

    entry_date = models.DateField(help_text="Date comptable de l'ecriture.")
    reference = models.CharField(max_length=50, blank=True, help_text="Reference piece (numero d'ecriture).")
    label = models.CharField(max_length=300, help_text="Libelle de l'ecriture.")
    source_bank_movement = models.OneToOneField(
        "finance.BankMovement",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="journal_entry",
        help_text="Mouvement bancaire a l'origine de l'ecriture, si auto-generee.",
    )
    source_cash_movement = models.OneToOneField(
        "finance.CashMovement",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="journal_entry",
        help_text="Mouvement caisse a l'origine de l'ecriture, si auto-generee.",
    )
    source_commitment = models.OneToOneField(
        "finance.Commitment",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="journal_entry",
        help_text="Engagement (Commitment) a l'origine de l'ecriture d'engagement "
        "(Dr 6x / Cr 401.x + neutralisation Dr 462 / Cr 702).",
    )
    posted = models.BooleanField(default=True, help_text="True = ecriture validee (sortie du brouillard).")

    class Meta:
        db_table = "journal_entries"
        ordering = ["-entry_date", "-id"]
        indexes = [models.Index(fields=["-entry_date"])]
        verbose_name = "Journal entry"
        verbose_name_plural = "Journal entries"

    def __str__(self):
        return f"Ecriture {self.id or '?'} {self.entry_date} - {self.label}"

    @property
    def total_debit(self):
        from decimal import Decimal as _D
        return sum((line.debit for line in self.lines.all()), _D("0"))

    @property
    def total_credit(self):
        from decimal import Decimal as _D
        return sum((line.credit for line in self.lines.all()), _D("0"))

    @property
    def is_balanced(self):
        return self.total_debit == self.total_credit


class JournalLine(TrackedModel):
    """Ligne d'ecriture comptable : un compte SYCEBNL, un debit OU un credit."""

    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(
        "finance.ChartOfAccount",
        on_delete=models.PROTECT,
        related_name="journal_lines",
    )
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    label = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = "journal_lines"
        ordering = ["entry_id", "id"]
        indexes = [models.Index(fields=["account", "entry"])]

    def __str__(self):
        return f"{self.account.code if self.account_id else '?'} D:{self.debit} C:{self.credit}"


def _expense_doc_upload_to(instance, filename):
    """Range les pieces justificatives sous media/expense_documents/<request_id>/."""
    rid = instance.request_id or "draft"
    return f"expense_documents/{rid}/{filename}"


class ExpenseRequest(TrackedModel):
    """Demande de depense initiee par un responsable projet et soumise a
    validation triple (RAF + DP + SE)."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        SUBMITTED = "SUBMITTED", "Soumise"
        APPROVED = "APPROVED", "Approuvee"
        REJECTED = "REJECTED", "Rejetee"
        EXECUTED = "EXECUTED", "Executee"
        CANCELLED = "CANCELLED", "Annulee"

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="expense_requests",
        help_text="Projet d'imputation. Null = Budget General.",
    )
    budget_line = models.ForeignKey(
        "finance.BudgetLine",
        on_delete=models.PROTECT,
        related_name="expense_requests",
        help_text="Ligne budgetaire eligible.",
    )
    requester = models.ForeignKey(
        "hr.Employee",
        on_delete=models.PROTECT,
        related_name="expense_requests_created",
        help_text="Employe initiateur (responsable projet).",
    )
    title = models.CharField(max_length=200, help_text="Intitule court de la demande.")
    motif = models.TextField(help_text="Justification metier detaillee.")
    requested_amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="XOF")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    submitted_at = models.DateTimeField(blank=True, null=True)
    decided_at = models.DateTimeField(blank=True, null=True)
    executed_at = models.DateTimeField(blank=True, null=True)
    executed_bank_movement = models.ForeignKey(
        "finance.BankMovement",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="originating_expense_requests",
    )
    executed_cash_movement = models.ForeignKey(
        "finance.CashMovement",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="originating_expense_requests",
    )

    class Meta:
        db_table = "expense_requests"
        ordering = ["-id"]

    def __str__(self):
        return f"DD {self.id or '?'} - {self.title} - {self.requested_amount} {self.currency}"

    def recompute_status(self):
        """Met a jour le status global en fonction des ExpenseValidation.

        - Si la demande est encore en DRAFT/EXECUTED/CANCELLED on ne touche pas.
        - Sinon : si une validation est REJECTED -> REJECTED.
                  si toutes APPROVED -> APPROVED.
                  sinon -> SUBMITTED (en attente).
        """
        from django.utils import timezone

        if self.status in (
            self.Status.DRAFT,
            self.Status.EXECUTED,
            self.Status.CANCELLED,
        ):
            return
        validations = list(self.validations.filter(is_active=True, deleted_at__isnull=True))
        if not validations:
            return
        if any(v.decision == ExpenseValidation.Decision.REJECTED for v in validations):
            self.status = self.Status.REJECTED
            if not self.decided_at:
                self.decided_at = timezone.now()
            self.save(update_fields=["status", "decided_at", "updated_at"])
            return
        if all(v.decision == ExpenseValidation.Decision.APPROVED for v in validations):
            self.status = self.Status.APPROVED
            if not self.decided_at:
                self.decided_at = timezone.now()
            self.save(update_fields=["status", "decided_at", "updated_at"])
            return
        # Sinon, on reste a SUBMITTED.


class ExpenseValidation(TrackedModel):
    """Avis de validation d'une demande de depense par un role (RAF, DP, SE).

    Une demande SUBMITTED genere automatiquement N ExpenseValidation (une par
    role validateur) avec decision = PENDING. Le validateur fait passer
    l'enregistrement a APPROVED ou REJECTED.
    """

    class Decision(models.TextChoices):
        PENDING = "PENDING", "En attente"
        APPROVED = "APPROVED", "Approuvee"
        REJECTED = "REJECTED", "Rejetee"

    request = models.ForeignKey(
        ExpenseRequest, on_delete=models.CASCADE, related_name="validations"
    )
    role = models.ForeignKey(
        "accounts.Role",
        on_delete=models.PROTECT,
        related_name="expense_validations",
        help_text="Role attendu (RAF, DP, SE).",
    )
    validator = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="expense_validations_signed",
        help_text="Utilisateur ayant pris la decision (rempli au moment de signer).",
    )
    decision = models.CharField(
        max_length=15, choices=Decision.choices, default=Decision.PENDING
    )
    comment = models.TextField(blank=True)
    decided_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "expense_validations"
        ordering = ["request_id", "role__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["request", "role"],
                name="uq_expense_validation_per_role",
            )
        ]

    def __str__(self):
        return f"{self.request_id} / {self.role.code if self.role_id else '?'} : {self.decision}"

    def save(self, *args, **kwargs):
        from django.utils import timezone

        if self.decision in (self.Decision.APPROVED, self.Decision.REJECTED) and not self.decided_at:
            self.decided_at = timezone.now()
        super().save(*args, **kwargs)
        # Trigger recompute sur la demande parente
        if self.request_id:
            request = ExpenseRequest.objects.filter(pk=self.request_id).first()
            if request:
                request.recompute_status()


class ExpenseDocument(TrackedModel):
    """Piece justificative attachee a une demande de depense.

    Types attendus (selon le workflow EVE) :
      PROFORMA      : facture proforma ou contrat soumis avec la demande
      BC            : bon de commande
      PV_SELECTION  : proces-verbal de selection fournisseur
      FACTURE       : facture definitive
      RAPPORT       : rapport d'execution / livrable
      AUTRE         : tout autre justificatif
    """

    class DocumentType(models.TextChoices):
        PROFORMA = "PROFORMA", "Facture proforma / contrat (initial)"
        BC = "BC", "Bon de commande"
        PV_SELECTION = "PV_SELECTION", "PV de selection"
        FACTURE = "FACTURE", "Facture definitive"
        RAPPORT = "RAPPORT", "Rapport / livrable"
        AUTRE = "AUTRE", "Autre justificatif"

    request = models.ForeignKey(
        ExpenseRequest, on_delete=models.CASCADE, related_name="documents"
    )
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    file = models.FileField(upload_to=_expense_doc_upload_to)
    label = models.CharField(max_length=200, blank=True)
    uploaded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="expense_documents_uploaded",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "expense_documents"
        ordering = ["request_id", "document_type"]

    def __str__(self):
        return f"{self.request_id} / {self.document_type} : {self.label or self.file.name}"


class CashMovement(TrackedModel):
    """Mouvement de caisse. Cf. plafonds CashRegister.

    Conventions identiques a BankMovement : debit/credit en positif,
    exactement l'un des deux non nul.
    """

    register = models.ForeignKey(CashRegister, on_delete=models.CASCADE, related_name="movements")
    date_operation = models.DateField()
    reference = models.CharField(max_length=50, blank=True)
    label = models.CharField(max_length=300)
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    budget_line = models.ForeignKey(
        "finance.BudgetLine",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="cash_movements",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="cash_movements",
    )
    contra_account = models.ForeignKey(
        "finance.ChartOfAccount",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="cash_movements_contra",
        help_text="Compte SYCEBNL contrepartie (charge 6x, produit 7x, liaison 18x).",
    )
    justification = models.FileField(
        upload_to="cash_justifications/%Y/%m/",
        blank=True,
        null=True,
        help_text="Piece justificative (ticket, recu, facturette) - photo ou PDF.",
    )
    recipient = models.CharField(
        max_length=150,
        blank=True,
        help_text="Beneficiaire de la sortie de caisse (nom, prestataire, etc.).",
    )
    commentary = models.TextField(blank=True)

    class Meta:
        db_table = "cash_movements"
        ordering = ["-date_operation", "-id"]
        indexes = [
            models.Index(fields=["register", "-date_operation"]),
            models.Index(fields=["budget_line"]),
        ]

    def clean(self):
        """Validation stricte des plafonds caisse."""
        from django.core.exceptions import ValidationError

        if self.debit and self.credit:
            raise ValidationError("Un mouvement caisse a soit un debit, soit un credit, pas les deux.")
        if not self.debit and not self.credit:
            raise ValidationError("Un mouvement caisse doit avoir un debit ou un credit non nul.")

        # Plafond unitaire (sur le debit, sortie de caisse)
        if self.debit and self.debit > CashRegister.UNIT_LIMIT:
            raise ValidationError(
                f"Plafond unitaire caisse depasse : {self.debit} FCFA > "
                f"{CashRegister.UNIT_LIMIT} FCFA autorises par operation."
            )

        # Plafond hebdomadaire (semaine ISO du date_operation, cumul des debits)
        if self.debit and self.date_operation:
            year, week, _ = self.date_operation.isocalendar()
            week_qs = CashMovement.objects.filter(
                register=self.register,
                is_active=True,
                deleted_at__isnull=True,
            )
            if self.pk:
                week_qs = week_qs.exclude(pk=self.pk)
            same_week_debit = Decimal("0")
            for other in week_qs.only("debit", "date_operation"):
                if not other.date_operation:
                    continue
                oy, ow, _ = other.date_operation.isocalendar()
                if (oy, ow) == (year, week):
                    same_week_debit += other.debit or Decimal("0")
            projected = same_week_debit + self.debit
            if projected > CashRegister.WEEKLY_LIMIT:
                raise ValidationError(
                    f"Plafond hebdomadaire caisse depasse : cumul "
                    f"semaine ISO {year}-W{week:02d} = {projected} FCFA "
                    f"(deja {same_week_debit} + cette operation {self.debit}), "
                    f"plafond {CashRegister.WEEKLY_LIMIT} FCFA."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        amount = self.credit if self.credit else -self.debit
        return f"Caisse {self.date_operation} {amount:+.2f}"


class CashflowEntry(TrackedModel):
    """Ligne du plan de tresorerie mensuel.

    Une ligne = un (mois, libelle, direction). Le couple (period_year,
    period_month, label, direction) doit etre unique pour permettre les
    re-imports idempotents depuis l'onglet 7 du budget previsionnel.

    Encaissement : project peut etre renseigne (la plupart le sont).
    Decaissement : category peut etre renseignee (categorie BudgetCategory).
    L'un ou l'autre peut etre NULL si la ligne n'est rattachable a rien
    (ex: 'AGIR Pikine Phase I' deja clos, pas dans la base Project).
    """

    class Direction(models.TextChoices):
        INCOMING = "ENCAISSEMENT", "Encaissement"
        OUTGOING = "DECAISSEMENT", "Decaissement"

    period_year = models.PositiveIntegerField()
    period_month = models.PositiveIntegerField()
    label = models.CharField(max_length=200, help_text="Libelle de la ligne tel que ecrit dans le plan source.")
    direction = models.CharField(max_length=20, choices=Direction.choices)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="cashflow_entries",
    )
    category = models.ForeignKey(
        "references.BudgetCategory",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="cashflow_entries",
    )
    planned_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    actual_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Montant reel constate (mois revolu). None = pas encore renseigne.",
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "cashflow_entries"
        ordering = ["period_year", "period_month", "direction", "label"]
        constraints = [
            models.UniqueConstraint(
                fields=["period_year", "period_month", "label", "direction"],
                name="uq_cashflow_entry_per_period_label_direction",
            )
        ]

    def __str__(self):
        return f"{self.period_year}-{self.period_month:02d} {self.direction} {self.label}: {self.planned_amount}"


class BudgetLine(TrackedModel):
    # project nullable: une ligne sans projet appartient au Budget General EVE
    # (charges fixes et masse salariale supportees par la tresorerie centrale,
    # alimentee par les contributions de fonctionnement des projets).
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="budget_lines",
        blank=True,
        null=True,
    )
    category = models.ForeignKey(
        "references.BudgetCategory",
        on_delete=models.RESTRICT,
        related_name="budget_lines",
    )
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="budget_lines",
    )
    donor = models.ForeignKey(
        "projects.Donor",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="budget_lines",
    )
    code = models.CharField(max_length=30, blank=True)
    description = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    unit = models.CharField(max_length=30, blank=True)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    planned_amount = models.DecimalField(max_digits=14, decimal_places=2)
    committed_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    disbursed_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="XOF")
    fiscal_year = models.PositiveIntegerField(blank=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "budget_lines"
        ordering = ["project__code", "category__code", "description"]

    def __str__(self):
        return self.description


class Supplier(TrackedModel):
    """Fournisseur / prestataire - master du grand-livre auxiliaire.

    Identite STABLE d'un fournisseur, condition d'un auxiliaire 401 fiable :
    le texte libre (Commitment.supplier_name) fragmenterait l'auxiliaire au
    moindre ecart de saisie. Chaque Supplier porte un code interne stable
    (F001, F002, ...) et obtient, a sa creation, un sous-compte auxiliaire
    '401.<code>' (cf. ensure_chart_account) - meme mecanique que les
    sous-comptes 5211.x / 571.x generes depuis les objets metier.

    Le NIF (Numero d'Identification Fiscale) est conserve comme attribut,
    mais N'EST PAS la cle : il est souvent vide pour les fournisseurs
    informels / locaux au Senegal.
    """

    code = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        help_text="Code interne stable (F001, F002, ...). Genere si vide.",
    )
    name = models.CharField(max_length=150)
    nif = models.CharField(max_length=30, blank=True, help_text="Numero d'Identification Fiscale (facultatif).")
    phone = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=255, blank=True)
    is_service_provider = models.BooleanField(
        default=False,
        help_text="Prestataire de services (soumis a la retenue a la source 5% - phase ulterieure).",
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "suppliers"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}" if self.code else self.name

    @staticmethod
    def _next_code() -> str:
        """Calcule le prochain code F### (max existant + 1).

        Concurrence faible (saisie manuelle ONG) : un simple max+1 suffit.
        """
        last = (
            Supplier.objects.filter(code__startswith="F")
            .order_by("-code")
            .values_list("code", flat=True)
            .first()
        )
        n = 0
        if last and last[1:].isdigit():
            n = int(last[1:])
        return f"F{n + 1:03d}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._next_code()
        super().save(*args, **kwargs)
        # Garantit le sous-compte auxiliaire 401.<code> apres l'insertion
        # (besoin du pk et d'un code stable). Idempotent.
        self.ensure_chart_account()

    def ensure_chart_account(self) -> "ChartOfAccount":
        """Cree (ou retrouve) le sous-compte auxiliaire 401.<code> du fournisseur.

        Rattache au parent '401' (Fournisseurs - exploitation) si seede.
        Idempotent : un seul compte par fournisseur.
        """
        account_code = f"401.{self.code}"
        parent = ChartOfAccount.objects.filter(
            code="401", is_active=True, deleted_at__isnull=True
        ).first()
        account, _ = ChartOfAccount.objects.update_or_create(
            code=account_code,
            defaults={
                "name": f"Fournisseur {self.name}"[:200],
                "class_number": 4,
                "parent": parent,
                "linked_supplier": self,
                "is_active": True,
                "deleted_at": None,
            },
        )
        return account

    @property
    def chart_account(self):
        """Le sous-compte auxiliaire d'EXPLOITATION 401.x de ce fournisseur, ou None."""
        return (
            ChartOfAccount.objects.filter(
                linked_supplier=self, code__startswith="401.",
                is_active=True, deleted_at__isnull=True,
            ).first()
        )

    def ensure_investment_account(self) -> "ChartOfAccount":
        """Cree (ou retrouve) le sous-compte auxiliaire d'INVESTISSEMENT 481.<code>.

        Utilise pour l'engagement des IMMOBILISATIONS (Dr 2 / Cr 481, guide
        SYCEBNL S2.3), distinct du 401.x d'exploitation. Genere a la demande
        (la plupart des fournisseurs ne vendent jamais d'immobilisation).
        """
        account_code = f"481.{self.code}"
        parent = (
            ChartOfAccount.objects.filter(
                code__in=("481", "4812", "48"), is_active=True, deleted_at__isnull=True
            )
            .order_by("code")
            .first()
        )
        account, _ = ChartOfAccount.objects.update_or_create(
            code=account_code,
            defaults={
                "name": f"Fournisseur invest. {self.name}"[:200],
                "class_number": 4,
                "parent": parent,
                "linked_supplier": self,
                "is_active": True,
                "deleted_at": None,
            },
        )
        return account

    @property
    def investment_account(self):
        """Le sous-compte auxiliaire d'INVESTISSEMENT 481.x de ce fournisseur, ou None."""
        return (
            ChartOfAccount.objects.filter(
                linked_supplier=self, code__startswith="481.",
                is_active=True, deleted_at__isnull=True,
            ).first()
        )


class Commitment(TrackedModel):
    class CommitmentType(models.TextChoices):
        PURCHASE_ORDER = "BON_COMMANDE", "Bon de commande"
        SUPPLIER_CONTRACT = "CONTRAT_FOURNISSEUR", "Contrat fournisseur"
        DIRECT_PURCHASE = "ACHAT_DIRECT", "Achat direct"
        MISSION = "MISSION", "Mission"

    class Status(models.TextChoices):
        IN_PROGRESS = "EN_COURS", "En cours"
        SETTLED = "SOLDE", "Solde"
        CANCELED = "ANNULE", "Annule"

    budget_line = models.ForeignKey(BudgetLine, on_delete=models.CASCADE, related_name="commitments")
    commitment_number = models.CharField(max_length=30, unique=True, blank=True, null=True)
    commitment_type = models.CharField(max_length=30, choices=CommitmentType.choices, blank=True)
    # supplier_name / supplier_nif : texte libre historique, conserve le temps
    # du backfill vers le master Supplier (FK ci-dessous). A terme deprecie.
    supplier_name = models.CharField(max_length=150, blank=True)
    supplier_nif = models.CharField(max_length=30, blank=True)
    supplier = models.ForeignKey(
        "finance.Supplier",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="commitments",
        help_text="Fournisseur (master). Son sous-compte 401.x est credite a l'engagement.",
    )
    # Compte de charge (classe 6) debite a l'engagement. Herite par defaut de
    # budget_line.category.default_charge_account (cf. Phase 0), surchargeable.
    charge_account = models.ForeignKey(
        "finance.ChartOfAccount",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="commitments_as_charge",
        help_text="Compte de charge 6x impute a l'engagement (Dr 6x / Cr 401.x).",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    commitment_date = models.DateField()
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    approved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="approved_commitments",
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    document_url = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "commitments"
        ordering = ["-commitment_date", "-created_at"]

    def __str__(self):
        return self.commitment_number or f"Commitment {self.pk}"

    def resolve_charge_account(self):
        """Compte de charge 6x effectif pour l'engagement.

        Priorite : charge_account explicite (surcharge) sinon la valeur par
        defaut de la categorie budgetaire (Phase 0). None si rien n'est
        configure - le posting (Phase 2) devra alors refuser l'engagement
        plutot que de deviner.
        """
        if self.charge_account_id:
            return self.charge_account
        category = getattr(self.budget_line, "category", None)
        return getattr(category, "default_charge_account", None) if category else None


class Disbursement(TrackedModel):
    class PaymentMethod(models.TextChoices):
        TRANSFER = "VIREMENT", "Virement"
        CASH = "ESPECES", "Especes"
        CHEQUE = "CHEQUE", "Cheque"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile money"

    class Status(models.TextChoices):
        DRAFT = "BROUILLON", "Brouillon"
        VALIDATED = "VALIDE", "Valide"
        CANCELED = "ANNULE", "Annule"

    commitment = models.ForeignKey(
        Commitment,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="disbursements",
    )
    budget_line = models.ForeignKey(BudgetLine, on_delete=models.CASCADE, related_name="disbursements")
    payment_number = models.CharField(max_length=30, unique=True, blank=True, null=True)
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="XOF")
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=1,
        validators=[MinValueValidator(0.0001)],
    )
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, blank=True)
    beneficiary_name = models.CharField(max_length=150, blank=True)
    beneficiary_account = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)
    bank_reference = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.VALIDATED)
    validated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="validated_disbursements",
    )

    class Meta:
        db_table = "disbursements"
        ordering = ["-payment_date", "-created_at"]

    def __str__(self):
        return self.payment_number or f"Disbursement {self.pk}"


class SupportingDoc(TrackedModel):
    class DocumentType(models.TextChoices):
        INVOICE = "FACTURE", "Facture"
        RECEIPT = "RECU", "Recu"
        QUOTE = "DEVIS", "Devis"
        CONTRACT = "CONTRAT", "Contrat"
        DELIVERY_NOTE = "BON_LIVRAISON", "Bon de livraison"
        OTHER = "AUTRE", "Autre"

    disbursement = models.ForeignKey(
        Disbursement,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="supporting_docs",
    )
    commitment = models.ForeignKey(
        Commitment,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="supporting_docs",
    )
    document_type = models.CharField(max_length=30, choices=DocumentType.choices, blank=True)
    document_number = models.CharField(max_length=50, blank=True)
    document_date = models.DateField(blank=True, null=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    file_url = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="uploaded_supporting_docs",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "supporting_docs"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.document_number or self.file_url
