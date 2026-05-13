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
