from django import forms

from .models import Note


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
