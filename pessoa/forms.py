from django import forms
from .models import Pessoa
from empresas.business_profiles import get_business_profile

class PessoaForm(forms.ModelForm):
    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        profile = get_business_profile(getattr(empresa, 'tipo', None))

        self.fields['nome'].label = profile['client_name_label']
        self.fields['nome'].widget.attrs['placeholder'] = profile['client_name_placeholder']
        self.fields['email'].widget.attrs['placeholder'] = 'cliente@exemplo.com'
        self.fields['email'].required = True
        self.fields['telefone'].label = 'Whatsapp'
        self.fields['telefone'].widget.attrs['placeholder'] = '(65) 99999-9999'
        self.fields['documento'].label = 'Documento'
        self.fields['documento'].widget.attrs['placeholder'] = 'CPF ou documento principal'
        self.fields['documento'].required = True
        self.fields['data_nascimento'].required = True
        self.fields['endereco'].widget.attrs['placeholder'] = 'Endereco completo'
        self.fields['observacoes'].label = profile['client_notes_label']
        self.fields['observacoes'].widget.attrs['placeholder'] = profile['client_notes_placeholder']

    class Meta:
        model = Pessoa
        fields = [
            'nome',
            'email',
            'telefone',
            'documento',
            'data_nascimento',
            'endereco',
            'observacoes',
        ]

        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'documento': forms.TextInput(attrs={'class': 'form-control'}),
            'data_nascimento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'endereco': forms.TextInput(attrs={'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control'}),
        }
