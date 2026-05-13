"""Formulaires Django pour la couche publique Finance."""

from django import forms

from apps.finance.models import ExpenseDocument, ExpenseRequest, ExpenseValidation


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
        super().__init__(*args, **kwargs)
        # On n'affiche que les budget_lines actives.
        self.fields["budget_line"].queryset = self.fields["budget_line"].queryset.filter(
            is_active=True, deleted_at__isnull=True
        ).select_related("project", "category").order_by("project__code", "code")
        self.fields["project"].queryset = self.fields["project"].queryset.filter(
            is_active=True, deleted_at__isnull=True
        ).order_by("code")
        self.fields["project"].required = False
        self.fields["project"].empty_label = "Budget General (aucun projet)"


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
