from django import forms
from django.contrib.auth.models import User
from .models import Profissional
from empresas.business_profiles import get_business_profile

class ProfissionalForm(forms.ModelForm):
    criar_acesso = forms.BooleanField(
        required=False,
        initial=True,
        label='Criar login para este profissional',
    )
    email_acesso = forms.EmailField(required=False, label='Email de acesso')
    senha_acesso = forms.CharField(
        required=False,
        label='Senha de acesso',
        widget=forms.PasswordInput(render_value=False),
    )
    senha_confirmacao_acesso = forms.CharField(
        required=False,
        label='Confirmar senha de acesso',
        widget=forms.PasswordInput(render_value=False),
    )

    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = empresa
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

        self.fields['email_acesso'].widget.attrs['placeholder'] = 'profissional@empresa.com'
        self.fields['email_acesso'].widget.attrs['autocomplete'] = 'off'
        self.fields['senha_acesso'].widget.attrs['placeholder'] = 'Minimo 8 caracteres'
        self.fields['senha_acesso'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['senha_confirmacao_acesso'].widget.attrs['placeholder'] = 'Repita a senha'
        self.fields['senha_confirmacao_acesso'].widget.attrs['autocomplete'] = 'new-password'

        has_existing_login = bool(self.instance and self.instance.pk and self.instance.usuario_id)
        if has_existing_login:
            usuario = self.instance.usuario
            self.fields['criar_acesso'].initial = True
            self.fields['criar_acesso'].disabled = True
            self.fields['criar_acesso'].help_text = f'Login ja vinculado: {usuario.username}'
            self.fields['email_acesso'].initial = usuario.email or usuario.username
            self.fields['email_acesso'].disabled = True
            self.fields['email_acesso'].help_text = 'Para trocar o email de login, crie um novo profissional.'
            self.fields['senha_acesso'].label = 'Nova senha de acesso (opcional)'
            self.fields['senha_confirmacao_acesso'].label = 'Confirmar nova senha'
        else:
            self.fields['criar_acesso'].help_text = 'Desmarque se este profissional nao deve acessar o sistema.'

        if empresa and not empresa.permite_acesso_profissional:
            for field_name in ('criar_acesso', 'email_acesso', 'senha_acesso', 'senha_confirmacao_acesso'):
                self.fields[field_name].disabled = True
                self.fields[field_name].required = False
            self.fields['criar_acesso'].initial = False
            self.fields['criar_acesso'].help_text = (
                'No plano somente administrador, funcionarios nao possuem acesso ao sistema.'
            )

    def clean(self):
        cleaned_data = super().clean()

        if self.empresa and not self.empresa.permite_acesso_profissional:
            cleaned_data['criar_acesso'] = False
            return cleaned_data

        has_existing_login = bool(self.instance and self.instance.pk and self.instance.usuario_id)
        criar_acesso = cleaned_data.get('criar_acesso')
        email_acesso = (cleaned_data.get('email_acesso') or '').strip().lower()
        senha = cleaned_data.get('senha_acesso') or ''
        senha_confirmacao = cleaned_data.get('senha_confirmacao_acesso') or ''

        if has_existing_login:
            if senha or senha_confirmacao:
                if senha != senha_confirmacao:
                    self.add_error('senha_confirmacao_acesso', 'As senhas nao conferem.')
                elif len(senha) < 8:
                    self.add_error('senha_acesso', 'A senha deve ter pelo menos 8 caracteres.')
            return cleaned_data

        if not criar_acesso:
            return cleaned_data

        if not email_acesso:
            self.add_error('email_acesso', 'Informe o email de acesso do profissional.')
        if not senha:
            self.add_error('senha_acesso', 'Informe uma senha para o profissional.')
        if senha != senha_confirmacao:
            self.add_error('senha_confirmacao_acesso', 'As senhas nao conferem.')
        elif senha and len(senha) < 8:
            self.add_error('senha_acesso', 'A senha deve ter pelo menos 8 caracteres.')

        if email_acesso and User.objects.filter(username__iexact=email_acesso).exists():
            self.add_error('email_acesso', 'Este email ja esta em uso no sistema.')

        return cleaned_data

    def provision_access_user(self):
        if self.empresa and not self.empresa.permite_acesso_profissional:
            return None

        has_existing_login = bool(self.instance and self.instance.pk and self.instance.usuario_id)
        senha = self.cleaned_data.get('senha_acesso') or ''

        if has_existing_login:
            usuario = self.instance.usuario
            if senha:
                usuario.set_password(senha)
                usuario.save(update_fields=['password'])
            return usuario

        if not self.cleaned_data.get('criar_acesso'):
            return None

        email_acesso = (self.cleaned_data.get('email_acesso') or '').strip().lower()
        nome = (self.cleaned_data.get('nome') or '').strip()
        return User.objects.create_user(
            username=email_acesso,
            email=email_acesso,
            password=senha,
            first_name=nome[:150],
        )

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
