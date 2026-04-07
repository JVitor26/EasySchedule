from django import forms
from .business_profiles import (
    DEFAULT_BUSINESS_TYPE,
    get_business_type_choices,
    normalize_business_type,
)

class CadastroEmpresaForm(forms.Form):
    nome_completo = forms.CharField(label='Nome completo', max_length=100)
    data_nascimento = forms.DateField(label='Data de nascimento', widget=forms.DateInput(attrs={'type': 'date'}))
    cpf_cnpj = forms.CharField(label='CPF ou CNPJ', max_length=18)
    tipo_empresa = forms.ChoiceField(label='Tipo de empresa', choices=get_business_type_choices())
    nome_empresa = forms.CharField(label='Nome da empresa', max_length=100)
    email = forms.EmailField(label='E-mail')
    senha = forms.CharField(label='Senha', widget=forms.PasswordInput)
    senha2 = forms.CharField(label='Confirmação de senha', widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['tipo_empresa'].initial = DEFAULT_BUSINESS_TYPE
        self.fields['nome_completo'].widget.attrs.update({
            'placeholder': 'Ex.: Maria Souza',
            'autocomplete': 'name',
        })
        self.fields['cpf_cnpj'].widget.attrs.update({
            'placeholder': 'Informe CPF ou CNPJ',
        })
        self.fields['nome_empresa'].widget.attrs.update({
            'placeholder': 'Ex.: Studio Bela Vista',
        })
        self.fields['email'].widget.attrs.update({
            'placeholder': 'voce@empresa.com',
            'autocomplete': 'email',
        })
        self.fields['senha'].widget.attrs.update({
            'placeholder': 'Crie uma senha forte',
            'autocomplete': 'new-password',
        })
        self.fields['senha2'].widget.attrs.update({
            'placeholder': 'Repita a senha',
            'autocomplete': 'new-password',
        })

    def clean(self):
        cleaned_data = super().clean()
        senha = cleaned_data.get('senha')
        senha2 = cleaned_data.get('senha2')
        if senha and senha2 and senha != senha2:
            self.add_error('senha2', 'As senhas não conferem.')
        return cleaned_data

    def clean_tipo_empresa(self):
        return normalize_business_type(self.cleaned_data['tipo_empresa'])
