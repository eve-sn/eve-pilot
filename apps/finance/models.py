from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.models import TrackedModel


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
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="bank_movements",
        help_text="Projet auquel le mouvement se rapporte, si identifiable.",
    )
    cashflow_entry = models.ForeignKey(
        "CashflowEntry",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="bank_movements",
        help_text="Ligne de plan tresorerie matchee, si applicable (suivi reel/prevu).",
    )
    source_document = models.CharField(
        max_length=200,
        blank=True,
        help_text="Document source (ex: 'Releve Banque Atlantique decembre 2025').",
    )

    class Meta:
        db_table = "bank_movements"
        ordering = ["-date_operation", "-id"]
        indexes = [
            models.Index(fields=["account", "-date_operation"]),
            models.Index(fields=["reference"]),
        ]

    def __str__(self):
        amount = self.credit if self.credit else -self.debit
        return f"{self.account.name} {self.date_operation} {amount:+.2f}"


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
    supplier_name = models.CharField(max_length=150, blank=True)
    supplier_nif = models.CharField(max_length=30, blank=True)
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
