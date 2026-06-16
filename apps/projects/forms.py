"""Formulaires Django pour la couche publique Projets."""

from django import forms

from apps.projects.models import Project

ACTIVE_DOMAIN = {"is_active": True, "deleted_at__isnull": True}


class ProjectForm(forms.ModelForm):
    """Création / édition manuelle d'un projet."""

    class Meta:
        model = Project
        fields = [
            "code",
            "title",
            "short_title",
            "description",
            "primary_donor",
            "total_budget",
            "currency",
            "start_date",
            "end_date",
            "project_manager",
            "status",
            "sector",
            "objectives",
            "target_beneficiaries",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "objectives": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "code": forms.TextInput(attrs={"placeholder": "Ex: PDBH-2026"}),
            "title": forms.TextInput(attrs={"placeholder": "Intitulé complet du projet"}),
            "short_title": forms.TextInput(attrs={"placeholder": "Nom court (optionnel)"}),
            "sector": forms.TextInput(attrs={"placeholder": "Ex: Nutrition, WASH, Gouvernance…"}),
        }
        labels = {
            "code": "Code projet",
            "title": "Intitulé",
            "short_title": "Nom court",
            "primary_donor": "Bailleur principal",
            "total_budget": "Budget total",
            "start_date": "Date de début",
            "end_date": "Date de fin",
            "project_manager": "Responsable du projet",
            "sector": "Secteur",
            "target_beneficiaries": "Bénéficiaires visés",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Listes filtrées sur les enregistrements actifs.
        if "primary_donor" in self.fields:
            self.fields["primary_donor"].queryset = (
                self.fields["primary_donor"].queryset.filter(**ACTIVE_DOMAIN).order_by("name")
            )
            self.fields["primary_donor"].required = False
        if "project_manager" in self.fields:
            self.fields["project_manager"].queryset = (
                self.fields["project_manager"].queryset.filter(**ACTIVE_DOMAIN)
                .order_by("last_name", "first_name")
            )
            self.fields["project_manager"].required = False

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "La date de fin doit être postérieure à la date de début.")
        return cleaned
