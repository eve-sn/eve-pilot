"""Formulaires Django pour l'espace RH."""

from django import forms

from apps.hr.models import Employee


class EmployeeForm(forms.ModelForm):
    """Création / édition manuelle d'une fiche du personnel (réservée RH)."""

    class Meta:
        model = Employee
        fields = [
            "matricule",
            "first_name",
            "last_name",
            "gender",
            "birth_date",
            "nationality",
            "id_card_number",
            "phone_primary",
            "email_professional",
            "position",
            "department",
            "workforce_category",
            "assignment_label",
            "hire_date",
            "end_date",
            "status",
            "ipres_number",
            "css_number",
            "tax_number",
            "bank_name",
            "bank_account",
        ]
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
            "hire_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "matricule": forms.TextInput(attrs={"placeholder": "Ex: EVE-026"}),
            "position": forms.TextInput(attrs={"placeholder": "Ex: Chargé de suivi-évaluation"}),
            "assignment_label": forms.TextInput(attrs={"placeholder": "Projet(s) / zone d'intervention"}),
        }
        labels = {
            "matricule": "Matricule",
            "first_name": "Prénom(s)",
            "last_name": "Nom",
            "gender": "Sexe",
            "birth_date": "Date de naissance",
            "nationality": "Nationalité",
            "id_card_number": "N° pièce d'identité",
            "phone_primary": "Téléphone",
            "email_professional": "Email professionnel",
            "position": "Poste",
            "department": "Département",
            "workforce_category": "Catégorie",
            "assignment_label": "Affectation",
            "hire_date": "Date d'embauche",
            "end_date": "Date de fin (si applicable)",
            "status": "Statut",
            "ipres_number": "N° IPRES",
            "css_number": "N° CSS",
            "tax_number": "N° fiscal",
            "bank_name": "Banque",
            "bank_account": "N° de compte",
        }

    def clean(self):
        cleaned = super().clean()
        hire = cleaned.get("hire_date")
        end = cleaned.get("end_date")
        if hire and end and end < hire:
            self.add_error("end_date", "La date de fin doit être postérieure à la date d'embauche.")
        return cleaned
