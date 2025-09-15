from django import forms
from .models import UserFile, FileAccess, FileCategory
from django.contrib.auth import get_user_model

User = get_user_model()


class FileUploadForm(forms.ModelForm):
    class Meta:
        model = UserFile
        fields = ['name', 'description', 'file', 'category', 'visibility']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'File Name'}),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description (optional)'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'visibility': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = FileCategory.objects.all()
        self.fields['category'].empty_label = "Select Category (Optional)"


class FileEditForm(forms.ModelForm):
    class Meta:
        model = UserFile
        fields = ['name', 'description', 'category', 'visibility']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'visibility': forms.Select(attrs={'class': 'form-control'}),
        }


class FileAccessForm(forms.ModelForm):
    user_email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'User Email'})
    )

    class Meta:
        model = FileAccess
        fields = ['permission', 'expires_at']
        widgets = {
            'permission': forms.Select(attrs={'class': 'form-control'}),
            'expires_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }

    def clean_user_email(self):
        email = self.cleaned_data.get('user_email')
        try:
            user = User.objects.get(email=email, is_verified=True)
            return user
        except User.DoesNotExist:
            raise forms.ValidationError("User with this email does not exist or is not verified.")


class FileSearchForm(forms.Form):
    query = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search files...',
            'autocomplete': 'off'
        })
    )
    category = forms.ModelChoiceField(
        queryset=FileCategory.objects.all(),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    file_type = forms.ChoiceField(
        choices=[('', 'All Types'), ('.pdf', 'PDF'), ('.doc', 'Word'), ('.jpg', 'Image'), ('.mp4', 'Video')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
