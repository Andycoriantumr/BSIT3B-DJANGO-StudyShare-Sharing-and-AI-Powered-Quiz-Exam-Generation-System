from django import forms

from .models import Note, NoteReport, Subject


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = [
            'title', 'subject', 'instructor', 'topic', 'school_year',
            'description', 'content', 'file', 'is_public',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Chapter 5 - Photosynthesis notes'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Biology, Math, IT Capstone', 'list': 'subject-list'}),
            'instructor': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Prof. Santos'}),
            'topic': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Cell Division'}),
            'school_year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2024-2025 or 3rd Year'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Short summary of the notes...'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Paste the note text here (used for search + AI quiz generation)...'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Biology'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. BIO101'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ReportForm(forms.ModelForm):
    class Meta:
        model = NoteReport
        fields = ['reason', 'details']
        widgets = {
            'reason': forms.Select(attrs={'class': 'form-select'}),
            'details': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describe the problem...'}),
        }
