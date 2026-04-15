from django import forms
import re
from .business_profiles import (
    DEFAULT_BUSINESS_TYPE,
    get_business_type_choices,
    normalize_business_type,
)
from .models import Empresa
from profissionais.models import Profissional
from .permissions import PROFISSIONAL_MODULE_CHOICES, normalize_profissional_modules


def _normalize_hex_color(value):
    raw = (value or "").strip().lower()
    if not raw:
        return ""

    if not raw.startswith("#"):
        raw = f"#{raw}"

    if not re.fullmatch(r"#[0-9a-f]{6}", raw):
        raise forms.ValidationError("Use uma cor hexadecimal valida, como #0f4c81.")

    return raw

class CadastroEmpresaForm(forms.Form):
    nome_completo = forms.CharField(label='Nome completo', max_length=100)
    data_nascimento = forms.DateField(label='Data de nascimento', widget=forms.DateInput(attrs={'type': 'date'}))
    cpf_cnpj = forms.CharField(label='CPF ou CNPJ', max_length=18)
    tipo_empresa = forms.ChoiceField(label='Tipo de empresa', choices=get_business_type_choices())
    nome_empresa = forms.CharField(label='Nome da empresa', max_length=100)
    whatsapp = forms.CharField(label='WhatsApp da empresa', max_length=20, required=False)
    logo = forms.ImageField(label='Logo da empresa (upload opcional)', required=False)
    cor_primaria = forms.CharField(label='Cor primaria (hex opcional)', max_length=7, required=False)
    cor_secundaria = forms.CharField(label='Cor secundaria (hex opcional)', max_length=7, required=False)
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
        self.fields['logo'].widget.attrs.update({
            'accept': 'image/*',
        })
        self.fields['cor_primaria'].widget.attrs.update({
            'placeholder': '#0f4c81',
            'autocomplete': 'off',
        })
        self.fields['cor_secundaria'].widget.attrs.update({
            'placeholder': '#188fa7',
            'autocomplete': 'off',
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

    def clean_cor_primaria(self):
        return _normalize_hex_color(self.cleaned_data.get('cor_primaria'))

    def clean_cor_secundaria(self):
        return _normalize_hex_color(self.cleaned_data.get('cor_secundaria'))


class EmpresaConfiguracaoForm(forms.ModelForm):
    tipo = forms.ChoiceField(label='Tipo de empresa', choices=get_business_type_choices())
    plano = forms.ChoiceField(label='Plano do sistema', choices=Empresa.PLANO_CHOICES)
    limite_profissionais = forms.IntegerField(
        label='Quantidade de funcionarios no plano',
        min_value=1,
        max_value=5,
        required=False,
        help_text='No plano Start, escolha de 1 a 5 funcionarios ativos.',
    )
    cor_primaria = forms.CharField(label='Cor primaria (hex opcional)', max_length=7, required=False)
    cor_secundaria = forms.CharField(label='Cor secundaria (hex opcional)', max_length=7, required=False)
    texto_cabecalho = forms.CharField(
        label='Texto do cabecalho (opcional)',
        max_length=80,
        required=False,
        help_text='Texto exibido abaixo do nome da empresa no topo do sistema.',
    )

    PLAN_PRICES = {
        Empresa.PLANO_SOLO: 97,
        Empresa.PLANO_START: 147,
        Empresa.PLANO_ADMIN_ONLY: 127,
    }

    class Meta:
        model = Empresa
        fields = [
            'nome',
            'tipo',
            'whatsapp',
            'plano',
            'limite_profissionais',
            'logo',
            'cor_primaria',
            'cor_secundaria',
            'texto_cabecalho',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nome'].label = 'Nome da empresa'
        self.fields['tipo'].label = 'Tipo de empresa'
        self.fields['whatsapp'].label = 'WhatsApp da empresa'
        self.fields['plano'].label = 'Plano do sistema'
        self.fields['logo'].label = 'Logo da empresa (upload opcional)'

        self.fields['nome'].widget.attrs.update({'placeholder': 'Ex.: Studio Bela Vista'})
        self.fields['whatsapp'].widget.attrs.update({'placeholder': '(65) 99999-9999'})
        self.fields['limite_profissionais'].widget.attrs.update({'placeholder': 'De 1 a 5'})
        self.fields['logo'].widget.attrs.update({'accept': 'image/*'})
        self.fields['cor_primaria'].widget.attrs.update({'placeholder': '#0f4c81'})
        self.fields['cor_secundaria'].widget.attrs.update({'placeholder': '#188fa7'})
        self.fields['texto_cabecalho'].widget.attrs.update({'placeholder': 'Ex.: Agenda premium com atendimento personalizado'})

    def clean(self):
        cleaned_data = super().clean()
        plano = cleaned_data.get('plano')
        limite = cleaned_data.get('limite_profissionais')

        if plano == Empresa.PLANO_SOLO:
            cleaned_data['limite_profissionais'] = 1
        elif plano == Empresa.PLANO_ADMIN_ONLY:
            cleaned_data['limite_profissionais'] = 5
        elif plano == Empresa.PLANO_START and not limite:
            self.add_error('limite_profissionais', 'Informe a quantidade de funcionarios para o plano Start.')

        limite_final = cleaned_data.get('limite_profissionais')
        if self.instance and limite_final:
            profissionais_ativos = self.instance.profissional_set.filter(ativo=True).count()
            if profissionais_ativos > limite_final:
                self.add_error(
                    'plano',
                    f'Nao e possivel aplicar este plano agora: voce possui {profissionais_ativos} profissionais ativos.'
                )

        return cleaned_data

    def clean_tipo(self):
        return normalize_business_type(self.cleaned_data['tipo'])

    def clean_whatsapp(self):
        return ''.join(filter(str.isdigit, self.cleaned_data.get('whatsapp', '')))

    def clean_cor_primaria(self):
        return _normalize_hex_color(self.cleaned_data.get('cor_primaria'))

    def clean_cor_secundaria(self):
        return _normalize_hex_color(self.cleaned_data.get('cor_secundaria'))

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.valor_mensal = self.PLAN_PRICES.get(instance.plano, instance.valor_mensal)
        if commit:
            instance.save()
        return instance


def parse_profissional_modules_from_post(request_post, profissionais):
    updates = {}
    valid = {key for key, _label in PROFISSIONAL_MODULE_CHOICES}

    for profissional in profissionais:
        selected = [key for key in request_post.getlist(f'acessos_{profissional.pk}') if key in valid]
        updates[profissional.pk] = normalize_profissional_modules(selected)

    return updates


def profissional_module_choices():
    return list(Profissional.MODULE_CHOICES)
