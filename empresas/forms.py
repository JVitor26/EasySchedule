from django import forms
from .business_profiles import (
    DEFAULT_BUSINESS_TYPE,
    get_business_type_choices,
    normalize_business_type,
)
from .models import Empresa

class CadastroEmpresaForm(forms.Form):
    nome_completo = forms.CharField(label='Nome completo', max_length=100)
    data_nascimento = forms.DateField(label='Data de nascimento', widget=forms.DateInput(attrs={'type': 'date'}))
    cpf_cnpj = forms.CharField(label='CPF ou CNPJ', max_length=18)
    tipo_empresa = forms.ChoiceField(label='Tipo de empresa', choices=get_business_type_choices())
    nome_empresa = forms.CharField(label='Nome da empresa', max_length=100)
    whatsapp = forms.CharField(label='WhatsApp da empresa', max_length=20, required=False)
    plano = forms.ChoiceField(label='Plano', choices=Empresa.PLANO_CHOICES, initial=Empresa.PLANO_SOLO)
    limite_profissionais = forms.IntegerField(
        label='Quantidade de funcionarios no plano',
        min_value=1,
        max_value=5,
        initial=1,
        help_text='No plano Start, escolha de 1 a 5 funcionarios ativos.',
    )
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
        self.fields['whatsapp'].widget.attrs.update({
            'placeholder': '(65) 99999-9999',
            'autocomplete': 'tel',
        })
        self.fields['plano'].widget.attrs.update({
            'id': 'id_plano',
        })
        self.fields['limite_profissionais'].widget.attrs.update({
            'placeholder': 'De 1 a 5',
            'id': 'id_limite_profissionais',
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
        plano = cleaned_data.get('plano')
        limite = cleaned_data.get('limite_profissionais')

        if senha and senha2 and senha != senha2:
            self.add_error('senha2', 'As senhas não conferem.')

        if plano == Empresa.PLANO_SOLO:
            cleaned_data['limite_profissionais'] = 1
        elif plano == Empresa.PLANO_ADMIN_ONLY:
            if not limite:
                cleaned_data['limite_profissionais'] = 5
        elif not limite:
            self.add_error('limite_profissionais', 'Informe a quantidade de funcionarios para o plano Start.')

        return cleaned_data

    def clean_tipo_empresa(self):
        return normalize_business_type(self.cleaned_data['tipo_empresa'])

    def clean_whatsapp(self):
        return ''.join(filter(str.isdigit, self.cleaned_data.get('whatsapp', '')))
