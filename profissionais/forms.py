from django import forms
from .models import Profissional
from empresas.business_profiles import get_business_profile

class ProfissionalForm(forms.ModelForm):
    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        profile = get_business_profile(getattr(empresa, 'tipo', None))

        self.fields['nome'].label = profile['professional_name_label']
        self.fields['nome'].widget.attrs['placeholder'] = profile['professional_name_placeholder']
        self.fields['especialidade'].label = profile['specialty_label']
        self.fields['especialidade'].widget.attrs['placeholder'] = profile['specialty_placeholder']
        self.fields['telefone'].label = 'Whatsapp'
        self.fields['telefone'].widget.attrs['placeholder'] = '(65) 99999-9999'
        self.fields['email'].widget.attrs['placeholder'] = 'profissional@exemplo.com'
        self.fields['cpf'].label = 'Documento'
        self.fields['cpf'].widget.attrs['placeholder'] = 'CPF do profissional'
        self.fields['endereco'].widget.attrs['placeholder'] = 'Endereco completo'
        self.fields['ativo'].label = f"{profile['professional_term_singular']} ativo"
        self.fields['observacoes'].label = f"Observacoes do {profile['professional_term_singular'].lower()}"
        self.fields['observacoes'].widget.attrs['placeholder'] = 'Informacoes adicionais para a equipe.'

    class Meta:
        model = Profissional
        fields = [
            'nome',
            'especialidade',
            'telefone',
            'email',
            'cpf',
            'data_nascimento',
            'endereco',
            'ativo',
            'observacoes',
        ]
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'especialidade': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'cpf': forms.TextInput(attrs={'class': 'form-control'}),
            'endereco': forms.TextInput(attrs={'class': 'form-control'}),
            'data_nascimento': forms.DateInput(attrs={'type': 'date'}),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }
