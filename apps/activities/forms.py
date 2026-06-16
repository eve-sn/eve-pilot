"""Formulaires Django pour la couche publique Activites."""

from django import forms

from apps.activities.models import (
    Activity,
    ActivityEvidence,
    ActivityReport,
    Beneficiary,
)

ACTIVE_DOMAIN = {"is_active": True, "deleted_at__isnull": True}


class ActivityForm(forms.ModelForm):
    """Creation / edition d'une activite (planification)."""

    class Meta:
        model = Activity
        fields = [
            "project",
            "code",
            "title",
            "description",
            "activity_type",
            "planned_start_date",
            "planned_end_date",
            "planned_budget",
            "responsible",
            "status",
            "completion_rate",
            "notes",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "planned_start_date": forms.DateInput(attrs={"type": "date"}),
            "planned_end_date": forms.DateInput(attrs={"type": "date"}),
            "title": forms.TextInput(
                attrs={"placeholder": "Ex: Formation des relais communautaires - Pikine"}
            ),
            "code": forms.TextInput(attrs={"placeholder": "Code interne (optionnel)"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        proj_qs = self.fields["project"].queryset.filter(**ACTIVE_DOMAIN)
        # Restriction par perimetre projet de l'utilisateur.
        if user is not None:
            from apps.accounts.access import accessible_project_ids
            acc_ids = accessible_project_ids(user)
            if acc_ids is not None:
                proj_qs = proj_qs.filter(id__in=acc_ids)
        self.fields["project"].queryset = proj_qs.order_by("code")
        self.fields["responsible"].queryset = (
            self.fields["responsible"].queryset.filter(**ACTIVE_DOMAIN).order_by(
                "last_name", "first_name"
            )
        )
        self.fields["responsible"].required = False
        self.fields["responsible"].empty_label = "-- Aucun responsable --"
        self.fields["planned_end_date"].required = False
        self.fields["planned_budget"].required = False
        # Le modele autorise une date vide (import cadre logique), mais la
        # saisie manuelle d'une activite doit rester calendarisee.
        self.fields["planned_start_date"].required = True

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("planned_start_date")
        end = cleaned.get("planned_end_date")
        if start and end and end < start:
            self.add_error(
                "planned_end_date",
                "La date de fin ne peut pas preceder la date de debut.",
            )
        return cleaned


class ActivityReportForm(forms.ModelForm):
    """Soumission d'un rapport d'activite terrain (status SOUMIS)."""

    class Meta:
        model = ActivityReport
        fields = [
            "report_date",
            "actual_location",
            "commune",
            "gps_latitude",
            "gps_longitude",
            "participants_count",
            "male_count",
            "female_count",
            "children_count",
            "narrative",
            "outcomes",
            "challenges",
            "recommendations",
        ]
        widgets = {
            "report_date": forms.DateInput(attrs={"type": "date"}),
            "narrative": forms.Textarea(attrs={"rows": 4}),
            "outcomes": forms.Textarea(attrs={"rows": 3}),
            "challenges": forms.Textarea(attrs={"rows": 3}),
            "recommendations": forms.Textarea(attrs={"rows": 3}),
            "actual_location": forms.TextInput(
                attrs={"placeholder": "Lieu reel de l'activite"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["commune"].queryset = self.fields["commune"].queryset.order_by("name")
        self.fields["commune"].required = False
        for name in (
            "gps_latitude",
            "gps_longitude",
            "participants_count",
            "male_count",
            "female_count",
            "children_count",
        ):
            self.fields[name].required = False

    def clean(self):
        cleaned = super().clean()
        total = cleaned.get("participants_count")
        male = cleaned.get("male_count") or 0
        female = cleaned.get("female_count") or 0
        if total is not None and (male or female) and (male + female) > total:
            self.add_error(
                "participants_count",
                "Le nombre d'hommes + femmes depasse le total des participants.",
            )
        return cleaned


class BeneficiaryForm(forms.ModelForm):
    """Ajout d'un beneficiaire nominatif a un rapport d'activite."""

    class Meta:
        model = Beneficiary
        fields = [
            "last_name",
            "first_name",
            "gender",
            "age",
            "phone",
            "commune",
            "id_card_number",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["commune"].queryset = self.fields["commune"].queryset.order_by("name")
        self.fields["commune"].required = False
        self.fields["age"].required = False


class ActivityEvidenceForm(forms.ModelForm):
    """Ajout d'une preuve (photo, liste de presence, document...) a un rapport."""

    class Meta:
        model = ActivityEvidence
        fields = ["evidence_type", "file", "caption"]
        widgets = {
            "caption": forms.TextInput(
                attrs={"placeholder": "Legende courte de la preuve"}
            ),
        }


class ActivityReportDecisionForm(forms.Form):
    """Decision du valideur Secretaire Executif sur un rapport soumis."""

    DECISION_CHOICES = [
        (ActivityReport.ValidationStatus.VALIDATED, "Valider"),
        (ActivityReport.ValidationStatus.REJECTED, "Rejeter"),
    ]

    decision = forms.ChoiceField(choices=DECISION_CHOICES, widget=forms.RadioSelect)
    comment = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        help_text="Obligatoire en cas de rejet.",
    )

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("decision") == ActivityReport.ValidationStatus.REJECTED
            and not cleaned.get("comment", "").strip()
        ):
            self.add_error("comment", "Un commentaire est obligatoire pour rejeter un rapport.")
        return cleaned
