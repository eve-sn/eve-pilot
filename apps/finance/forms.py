"""Formulaires Django pour la couche publique Finance."""

from django import forms
from django.db.models import Q

from apps.finance.models import (
    BankMovement,
    BankMovementDocument,
    ExpenseDocument,
    ExpenseRequest,
    ExpenseValidation,
)


class AccountChoiceField(forms.ModelChoiceField):
    """ModelChoiceField pour ChartOfAccount qui affiche 'CODE - LIBELLE'.

    Permet a SAKHO de chercher par code OU par mots-cles du libelle via la
    recherche client-side de l'input HTML. Tri par code par defaut.
    """

    def label_from_instance(self, obj):
        # Tronque le libelle a 70 chars pour rester lisible dans un select
        name = (obj.name or "").strip()
        if len(name) > 70:
            name = name[:67] + "..."
        return f"{obj.code} - {name}"


class BankMovementQuickForm(forms.Form):
    """Saisie directe d'un mouvement bancaire par le comptable.

    Permet au comptable projet (SAKHO sur ses 10 projets) de saisir au fil de
    l'eau les depenses et recettes constatees sur les releves bancaires, avec
    piece justificative, sans passer par le workflow de demande de depense
    formelle.

    Le signal finance.posting.post_bank_movement genere automatiquement
    l'ecriture comptable SYCEBNL en partie double a la sauvegarde.
    """

    from decimal import Decimal as _Decimal
    from datetime import date as _date
    from apps.finance.models import BankAccount, BudgetLine, ChartOfAccount
    from apps.projects.models import Project
    from apps.references.models import BudgetCategory

    OPERATION_CHOICES = [
        ("DEBIT", "Sortie d'argent (debit bancaire - le compte EVE diminue)"),
        ("CREDIT", "Entree d'argent (credit bancaire - le compte EVE s'enrichit)"),
    ]

    operation = forms.ChoiceField(
        choices=OPERATION_CHOICES, widget=forms.RadioSelect,
        initial="DEBIT", label="Type d'operation",
        help_text=(
            "Convention du releve bancaire (point de vue de la banque) : la "
            "colonne 'Debit' = sorties, la colonne 'Credit' = entrees. "
            "La compta SYCEBNL en partie double inversera automatiquement "
            "le sens pour le compte de tresorerie 5211.x (ex. une sortie = "
            "credit du compte 5211 en compta interne)."
        ),
    )
    account = forms.ModelChoiceField(
        queryset=BankAccount.objects.filter(is_active=True, deleted_at__isnull=True).order_by("name"),
        empty_label=None,
        label="Compte bancaire",
    )
    date_operation = forms.DateField(
        label="Date d'operation",
        widget=forms.DateInput(attrs={"type": "date", "min": "2026-01-01"}),
        help_text="Saisie permise depuis janvier 2026. Back-datage autorise pour rattrapage releves.",
    )
    reference = forms.CharField(
        max_length=50, required=False,
        label="Reference releve",
        widget=forms.TextInput(attrs={"placeholder": "Ex: G167265, F856524"}),
        help_text="Reference banque sur le releve (utile pour le rapprochement).",
    )
    label = forms.CharField(
        max_length=300,
        label="Libelle",
        widget=forms.TextInput(attrs={"placeholder": "Libelle complet tel que sur le releve"}),
    )
    amount = forms.DecimalField(
        max_digits=14, decimal_places=2,
        label="Montant",
    )
    recipient = forms.CharField(
        max_length=200, required=False,
        label="Beneficiaire / source",
        widget=forms.TextInput(attrs={"placeholder": "Nom personne, fournisseur ou bailleur"}),
    )
    project = forms.ModelChoiceField(
        queryset=Project.objects.filter(is_active=True, deleted_at__isnull=True).order_by("code"),
        required=False,
        empty_label="-- Projet (optionnel) --",
        label="Imputation projet",
    )
    budget_category = forms.ModelChoiceField(
        queryset=BudgetCategory.objects.filter(is_active=True, deleted_at__isnull=True).order_by("code"),
        required=False,
        empty_label="-- Rubrique budgetaire (optionnel) --",
        label="Rubrique budgetaire",
    )
    contra_account = AccountChoiceField(
        queryset=ChartOfAccount.objects.filter(
            is_active=True, deleted_at__isnull=True,
        ).order_by("code"),
        required=False,
        empty_label="-- (rempli automatiquement si ventilation) --",
        label="Compte SYCEBNL contrepartie",
        help_text="Sortie : compte de charge 6xx. Recette : compte de produit 7xx. Laisser vide si vous ventilez sur plusieurs lignes ci-dessous.",
        widget=forms.Select(attrs={"data-account-select": "1"}),
    )
    justification = forms.FileField(
        required=False,
        label="Piece justificative principale",
        help_text="Une seule piece principale. Utilisez la section 'pieces multiples' pour ajouter TDR, BC, facture, BL, etc.",
    )
    commentary = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}),
        required=False,
        label="Commentaire",
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Filtre comptes bancaires selon le perimetre utilisateur.
        if user is not None:
            from apps.accounts.access import (
                accessible_bank_account_ids,
                accessible_project_ids,
                can_see_bg,
            )
            from apps.finance.models import BudgetLine as _BL
            bank_ids = accessible_bank_account_ids(user)
            if bank_ids is not None:
                self.fields["account"].queryset = self.fields["account"].queryset.filter(id__in=bank_ids)
            proj_ids = accessible_project_ids(user)
            if proj_ids is not None:
                self.fields["project"].queryset = self.fields["project"].queryset.filter(id__in=proj_ids)
                # Rubrique : ne montre que les categories qui ont au moins une
                # BudgetLine sur les projets accessibles (ou le BG si autorise).
                bl_scope = Q(project_id__in=proj_ids)
                if can_see_bg(user):
                    bl_scope |= Q(project__isnull=True)
                cat_ids = _BL.objects.filter(
                    bl_scope, is_active=True, deleted_at__isnull=True,
                ).values_list("category_id", flat=True).distinct()
                self.fields["budget_category"].queryset = self.fields["budget_category"].queryset.filter(id__in=cat_ids)

    def clean(self):
        cleaned = super().clean()
        amount = cleaned.get("amount")
        if amount is not None and amount <= self._Decimal("0"):
            self.add_error("amount", "Le montant doit etre strictement positif.")
        d = cleaned.get("date_operation")
        if d is not None and d < self._date(2026, 1, 1):
            self.add_error("date_operation", "Saisie autorisee a partir du 1er janvier 2026.")
        return cleaned


class CashMovementQuickForm(forms.Form):
    """Saisie rapide d'une operation de caisse avec piece justificative.

    Utilise par l'Assistante RAF (Amy) et le RAF/DP/SE pour saisir au fil de
    l'eau les petites depenses operationnelles (transport, carburant,
    restauration, produits d'entretien, materiel cuisine) et les recharges
    de caisse en provenance d'un compte bancaire (BG ou projet).
    """

    from decimal import Decimal as _Decimal
    from apps.finance.models import BudgetLine, CashRegister, ChartOfAccount
    from apps.projects.models import Project

    OPERATION_CHOICES = [
        ("DEBIT", "Sortie d'especes (la caisse diminue)"),
        ("CREDIT", "Entree / alimentation (la caisse augmente)"),
    ]

    operation = forms.ChoiceField(
        choices=OPERATION_CHOICES,
        widget=forms.RadioSelect,
        initial="DEBIT",
        label="Type d'operation",
        help_text=(
            "Du point de vue de la caisse EVE. La compta SYCEBNL inversera "
            "automatiquement le sens pour le compte 571.x (entree caisse = "
            "debit 571, sortie = credit 571 en compta interne)."
        ),
    )
    register = forms.ModelChoiceField(
        queryset=CashRegister.objects.filter(is_active=True, deleted_at__isnull=True).order_by("name"),
        empty_label=None,
        label="Caisse",
    )
    date_operation = forms.DateField(
        label="Date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    label = forms.CharField(
        max_length=300,
        label="Libelle",
        widget=forms.TextInput(
            attrs={"placeholder": "Ex: Transport Mme NDIAYE / mission Pikine"}
        ),
    )
    amount = forms.DecimalField(
        max_digits=14, decimal_places=2,
        label="Montant",
        help_text="Plafonds caisse SYCEBNL : 40 000 XOF par operation, 200 000 XOF par semaine.",
    )
    recipient = forms.CharField(
        max_length=150,
        required=False,
        label="Beneficiaire",
        widget=forms.TextInput(
            attrs={"placeholder": "Nom du beneficiaire (employe, prestataire, etc.)"}
        ),
    )
    project = forms.ModelChoiceField(
        queryset=Project.objects.filter(is_active=True, deleted_at__isnull=True).order_by("code"),
        required=False,
        empty_label="Budget General (aucun projet)",
        label="Imputation projet",
        help_text="Laisser vide pour imputer au Budget General.",
    )
    budget_line = forms.ModelChoiceField(
        queryset=BudgetLine.objects.filter(is_active=True, deleted_at__isnull=True)
            .select_related("project", "category").order_by("project__code", "code"),
        required=False,
        empty_label="-- Ligne budgetaire (optionnel) --",
        label="Ligne budgetaire",
    )
    contra_account = AccountChoiceField(
        queryset=ChartOfAccount.objects.filter(
            is_active=True, deleted_at__isnull=True,
        ).order_by("code"),
        label="Compte SYCEBNL contrepartie",
        help_text="Charges (6xx) pour une sortie, virement (585) pour une recharge depuis banque.",
        widget=forms.Select(attrs={"data-account-select": "1"}),
    )
    justification = forms.FileField(
        required=False,
        label="Piece justificative",
        help_text="Ticket, recu, facturette ou photo. PDF, JPG, PNG.",
    )
    commentary = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}),
        required=False,
        label="Commentaire",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tag data-project sur les lignes budgetaires pour filtrage JS.
        bl_qs = self.fields["budget_line"].queryset
        bl_to_project = dict(bl_qs.values_list("id", "project_id"))
        self.fields["budget_line"].widget = ProjectAwareSelect(
            bl_to_project=bl_to_project,
        )
        self.fields["budget_line"].widget.choices = self.fields["budget_line"].choices

    def clean(self):
        cleaned = super().clean()
        amount = cleaned.get("amount")
        if amount is not None and amount <= self._Decimal("0"):
            self.add_error("amount", "Le montant doit etre strictement positif.")
        return cleaned


class ProjectAwareSelect(forms.Select):
    """Select qui ajoute data-project="<id>" sur chaque option budget_line.

    Permet au JS du formulaire expense_create de filtrer dynamiquement
    les lignes budgetaires affichees en fonction du projet selectionne.
    """

    def __init__(self, *args, **kwargs):
        self._bl_to_project = kwargs.pop("bl_to_project", {})
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        actual_value = getattr(value, "value", value)
        try:
            actual_int = int(actual_value) if actual_value not in (None, "") else None
        except (TypeError, ValueError):
            actual_int = None
        if actual_int is not None:
            project_id = self._bl_to_project.get(actual_int)
            # "" = ligne BG (project null), "<id>" = projet specifique
            option["attrs"]["data-project"] = str(project_id) if project_id else ""
        return option


class ExpenseRequestForm(forms.ModelForm):
    """Saisie d'une nouvelle demande de depense (status DRAFT)."""

    class Meta:
        model = ExpenseRequest
        fields = ["project", "budget_line", "title", "motif", "requested_amount", "currency"]
        widgets = {
            "motif": forms.Textarea(attrs={"rows": 4}),
            "title": forms.TextInput(attrs={"placeholder": "Ex: Achat consommables bureau mai 2026"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # On n'affiche que les budget_lines actives.
        bl_qs = self.fields["budget_line"].queryset.filter(
            is_active=True, deleted_at__isnull=True
        ).select_related("project", "category")
        proj_qs = self.fields["project"].queryset.filter(
            is_active=True, deleted_at__isnull=True
        )

        # Restriction par perimetre projet : un chargee de suivi / comptable
        # ne peut deposer une demande que sur ses projets.
        if user is not None:
            from apps.accounts.access import accessible_project_ids, can_see_bg

            acc_ids = accessible_project_ids(user)
            if acc_ids is not None:
                proj_qs = proj_qs.filter(id__in=acc_ids)
                if can_see_bg(user):
                    bl_qs = bl_qs.filter(
                        Q(project_id__in=acc_ids) | Q(project__isnull=True)
                    )
                else:
                    bl_qs = bl_qs.filter(project_id__in=acc_ids)

        bl_qs = bl_qs.order_by("project__code", "code")
        self.fields["budget_line"].queryset = bl_qs

        # Widget personnalise pour exposer data-project="..." sur chaque option,
        # ce qui permet au JS du template de filtrer dynamiquement.
        bl_to_project = dict(bl_qs.values_list("id", "project_id"))
        self.fields["budget_line"].widget = ProjectAwareSelect(
            bl_to_project=bl_to_project
        )
        # Reattacher les choices : remplacer le widget d'un ModelChoiceField ne
        # transporte PAS les options (ModelChoiceField._set_queryset ne repeuple
        # que le widget present au moment de l'assignation du queryset, l.339 ci-dessus).
        # Sans cette ligne, le <select budget_line> est rendu VIDE. cf. l'autre
        # formulaire qui fait deja ce reattachement.
        self.fields["budget_line"].widget.choices = self.fields["budget_line"].choices

        self.fields["project"].queryset = proj_qs.order_by("code")
        self.fields["project"].required = False
        # Si l'utilisateur n'a pas acces au BG, on retire l'option "Budget General".
        if user is not None and not _user_can_see_bg(user):
            self.fields["project"].empty_label = None
            # Si tous les projets accessibles sont != BG, on rend le champ obligatoire.
            self.fields["project"].required = True
        else:
            self.fields["project"].empty_label = "Budget General (aucun projet)"

        # Le montant peut etre derive des lignes de detail (formset) : optionnel.
        self.fields["requested_amount"].required = False
        self.fields["requested_amount"].help_text = (
            "Laisser vide si tu saisis le detail ligne par ligne ci-dessous : "
            "le total sera calcule automatiquement."
        )


def _user_can_see_bg(user):
    from apps.accounts.access import can_see_bg
    return can_see_bg(user)


class ExpenseValidationDecisionForm(forms.Form):
    """Formulaire d'action d'un valideur sur une demande soumise."""

    DECISION_CHOICES = [
        (ExpenseValidation.Decision.APPROVED, "Approuver"),
        (ExpenseValidation.Decision.REJECTED, "Rejeter"),
    ]

    validation_id = forms.IntegerField(widget=forms.HiddenInput)
    decision = forms.ChoiceField(choices=DECISION_CHOICES, widget=forms.RadioSelect)
    comment = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)


class ExpenseDocumentForm(forms.ModelForm):
    class Meta:
        model = ExpenseDocument
        fields = ["document_type", "file", "label"]
        widgets = {
            "label": forms.TextInput(attrs={"placeholder": "Description courte du document"}),
        }


class ExpenseExecuteForm(forms.Form):
    """Lie une ExpenseRequest APPROUVEE a un BankMovement (ou CashMovement)
    existant. Bascule la demande en EXECUTED."""

    from apps.finance.models import BankMovement, CashMovement

    bank_movement = forms.ModelChoiceField(
        queryset=BankMovement.objects.filter(is_active=True, deleted_at__isnull=True).order_by("-date_operation"),
        required=False,
        empty_label="-- Choisir un mouvement bancaire --",
    )
    cash_movement = forms.ModelChoiceField(
        queryset=CashMovement.objects.filter(is_active=True, deleted_at__isnull=True).order_by("-date_operation"),
        required=False,
        empty_label="-- Choisir un mouvement caisse --",
    )

    def clean(self):
        cleaned = super().clean()
        bank = cleaned.get("bank_movement")
        cash = cleaned.get("cash_movement")
        if bool(bank) == bool(cash):
            raise forms.ValidationError(
                "Renseigner exactement l'un des deux : un mouvement bancaire OU un mouvement caisse."
            )
        return cleaned


class ExpenseEngageForm(forms.Form):
    """Engage une demande APPROUVEE (Option L) : fixe le fournisseur et reserve
    le budget. NE POSTE AUCUNE ecriture : la charge Dr 6x / Cr 401 naitra a la
    liquidation (attachement de la facture definitive)."""

    from apps.finance.models import Supplier, ChartOfAccount

    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_active=True, deleted_at__isnull=True).order_by("name"),
        label="Fournisseur",
        empty_label="-- Choisir un fournisseur --",
        help_text="Son sous-compte auxiliaire 401.x sera credite a la liquidation.",
    )
    charge_account = AccountChoiceField(
        queryset=ChartOfAccount.objects.filter(
            is_active=True, deleted_at__isnull=True,
        ).filter(Q(code__startswith="6") | Q(code__startswith="2")).order_by("code"),
        required=False,
        label="Compte d'emploi (override, optionnel)",
        help_text="Vide = herite du compte 6x de la categorie budgetaire. "
                  "Classe 2 pour une immobilisation.",
    )
    commitment_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Date d'engagement",
    )


class ExpenseLiquidateForm(forms.Form):
    """Liquide une demande ENGAGEE (Option L) : attache la facture definitive,
    saisit le montant facture, et declenche la charge Dr 6x / Cr 401 pour CE
    montant (le service fait est constate). Bascule la demande en LIQUIDATED."""

    from decimal import Decimal as _Decimal

    facture = forms.FileField(
        label="Facture definitive (PDF, JPG, PNG)",
        help_text="Piece justificative du service fait.",
    )
    facture_amount = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=_Decimal("0.01"),
        label="Montant facture",
        help_text="Montant reel de la facture. La charge Dr 6x / Cr 401 sera constatee pour ce montant.",
    )
    liquidation_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Date de la facture (service fait)",
    )


class RecordPaymentForm(forms.Form):
    """Saisie du paiement effectif d'une demande approuvee.

    Le comptable cree directement le mouvement de tresorerie (BankMovement
    ou CashMovement) lie a la demande. Le signal de finance.posting genere
    automatiquement l'ecriture de journal SYCEBNL en partie double.
    """

    from decimal import Decimal as _Decimal
    from apps.finance.models import BankAccount, CashRegister, ChartOfAccount

    METHOD_CHOICES = [
        ("BANK", "Virement bancaire / cheque"),
        ("CASH", "Caisse (especes)"),
    ]

    method = forms.ChoiceField(
        choices=METHOD_CHOICES,
        widget=forms.RadioSelect,
        initial="BANK",
        label="Mode de paiement",
    )
    bank_account = forms.ModelChoiceField(
        queryset=BankAccount.objects.filter(is_active=True, deleted_at__isnull=True).order_by("name"),
        required=False,
        empty_label="-- Compte bancaire --",
        label="Compte bancaire",
    )
    cash_register = forms.ModelChoiceField(
        queryset=CashRegister.objects.filter(is_active=True, deleted_at__isnull=True).order_by("name"),
        required=False,
        empty_label="-- Caisse --",
        label="Caisse",
    )
    date_operation = forms.DateField(
        label="Date d'operation",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Date reelle du debit bancaire ou de la sortie de caisse.",
    )
    reference = forms.CharField(
        max_length=80,
        label="Reference",
        help_text="Reference du releve bancaire ou numero de piece de caisse.",
    )
    actual_amount = forms.DecimalField(
        max_digits=14, decimal_places=2,
        label="Montant reel paye",
        help_text="Peut differer du montant demande (TVA, remise, etc.).",
    )
    contra_account = AccountChoiceField(
        queryset=ChartOfAccount.objects.filter(
            is_active=True, deleted_at__isnull=True,
        ).order_by("code"),
        label="Compte de charge / contrepartie SYCEBNL",
        help_text="Compte de classe 6 (charges) ou autre selon la nature de la depense.",
        widget=forms.Select(attrs={"data-account-select": "1"}),
    )
    commentary = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        label="Commentaire",
    )

    def __init__(self, *args, **kwargs):
        self.expense = kwargs.pop("expense", None)
        super().__init__(*args, **kwargs)
        # Restreint les comptes bancaires aux comptes rattaches au projet de
        # la demande (le projet finance la depense depuis ses propres comptes).
        if self.expense is not None and self.expense.project_id is not None:
            self.fields["bank_account"].queryset = self.fields["bank_account"].queryset.filter(
                projects=self.expense.project
            )
        # Flux engagement : la contrepartie est FORCEE au 401.x du fournisseur
        # dans la vue (Dr 401 / Cr 5x). La charge ayant deja ete constatee a la
        # liquidation, le comptable ne choisit pas de compte 6x ici.
        if self.expense is not None and getattr(self.expense, "commitment_id", None):
            self.fields.pop("contra_account", None)

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get("method")
        bank = cleaned.get("bank_account")
        cash = cleaned.get("cash_register")

        if method == "BANK":
            if not bank:
                self.add_error("bank_account", "Requis pour un paiement bancaire.")
            cleaned["cash_register"] = None
        elif method == "CASH":
            if not cash:
                self.add_error("cash_register", "Requis pour un paiement en caisse.")
            cleaned["bank_account"] = None

        amount = cleaned.get("actual_amount")
        if amount is not None and amount <= self._Decimal("0"):
            self.add_error("actual_amount", "Le montant doit etre strictement positif.")

        return cleaned


class BankMovementEditForm(forms.ModelForm):
    """Edition CONTROLEE d'un mouvement bancaire deja saisi.

    Conformite SYCEBNL / piste d'audit : on n'autorise QUE les champs non
    financiers (libelle, beneficiaire, commentaire, reference releve). Le
    montant, la date, le sens (debit/credit) et l'imputation comptable
    (contra_account / ventilations) ne sont PAS modifiables ici : une
    correction financiere passe par l'annulation (extourne) du mouvement
    puis une nouvelle saisie, afin de preserver la trace comptable.

    La reference est incluse car elle ne touche pas la balance et sert au
    rapprochement bancaire (utile pour distinguer deux lignes identiques).
    """

    class Meta:
        model = BankMovement
        fields = ["label", "recipient", "reference", "commentary"]
        widgets = {
            "label": forms.TextInput(attrs={"placeholder": "Libelle complet tel que sur le releve"}),
            "recipient": forms.TextInput(attrs={"placeholder": "Nom personne, fournisseur ou bailleur"}),
            "reference": forms.TextInput(attrs={"placeholder": "Ex: G167265, F856524"}),
            "commentary": forms.Textarea(attrs={"rows": 2}),
        }


class BankMovementDocumentForm(forms.ModelForm):
    """Ajout d'une piece justificative a un mouvement bancaire existant."""

    class Meta:
        model = BankMovementDocument
        fields = ["document_type", "file", "label"]
        widgets = {
            "label": forms.TextInput(attrs={"placeholder": "Description courte (ex: Facture EDF janvier)"}),
        }


# --- Lignes de detail d'une demande de depense (saisie ligne par ligne) --------
# Compta AGREGEE : ces lignes decrivent la depense (designation, qte, frequence,
# unite, PU) ; le total demande = somme des line_total. Une seule ecriture est
# passee au niveau de la demande (cf. docs/DESIGN_ENGAGEMENT_WORKFLOW.md).
def _build_expense_item_formset():
    from django.forms import inlineformset_factory
    from apps.finance.models import ExpenseRequest, ExpenseRequestItem

    return inlineformset_factory(
        ExpenseRequest,
        ExpenseRequestItem,
        fields=["designation", "quantity", "frequency", "unit", "unit_price"],
        extra=18,
        can_delete=True,
        widgets={
            "designation": forms.TextInput(attrs={"placeholder": "Designation de la ligne"}),
            "unit": forms.TextInput(attrs={"placeholder": "participant/jour, forfait..."}),
        },
    )


ExpenseItemFormSet = _build_expense_item_formset()
