from django import forms
from .models import Servico
from empresas.business_profiles import get_business_profile


class ServicoForm(forms.ModelForm):
    CUSTOM_CATEGORY_VALUE = "__nova_categoria__"

    categoria_custom = forms.CharField(
        required=False,
        max_length=50,
        label="Nova categoria",
    )

    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = empresa
        profile = get_business_profile(getattr(empresa, 'tipo', None))
        categoria_atual = self.initial.get('categoria') or getattr(self.instance, 'categoria', '')

        categorias = list(profile['service_categories'])
        valores_existentes = {value for value, _label in categorias}

        if empresa is not None:
            categorias_empresa = (
                Servico.objects
                .filter(empresa=empresa)
                .exclude(categoria__in=valores_existentes)
                .values_list('categoria', flat=True)
                .distinct()
            )
            for categoria in categorias_empresa:
                if categoria:
                    categorias.append((categoria, categoria.replace('_', ' ').title()))
                    valores_existentes.add(categoria)

        if categoria_atual and categoria_atual not in valores_existentes:
            categorias.append((categoria_atual, categoria_atual.replace('_', ' ').title()))

        categorias.append((self.CUSTOM_CATEGORY_VALUE, 'Criar nova categoria...'))

        self.fields['nome'].label = profile['service_name_label']
        self.fields['nome'].widget.attrs['placeholder'] = profile['service_name_placeholder']
        self.fields['categoria'].label = profile['service_category_label']
        self.fields['categoria'].widget = forms.Select(choices=categorias)
        self.fields['categoria'].choices = categorias
        self.fields['categoria'].help_text = (
            f"Categorias sugeridas para {profile['label'].lower()} ou crie uma personalizada."
        )
        self.fields['categoria_custom'].widget.attrs.update({
            'placeholder': 'Ex.: Alongamento premium',
        })
        self.fields['categoria_custom'].help_text = 'Opcional. Preencha apenas se escolher Criar nova categoria.'
        self.fields['descricao'].label = profile['service_description_label']
        self.fields['descricao'].widget.attrs['placeholder'] = profile['service_description_placeholder']
        self.fields['preco'].label = 'Preco'
        self.fields['preco'].widget.attrs['placeholder'] = '0,00'
        self.fields['tempo'].label = 'Duracao (minutos)'
        self.fields['tempo'].widget.attrs['placeholder'] = '60'
        self.fields['ativo'].label = f"{profile['service_term_singular']} ativo"

    def clean(self):
        cleaned_data = super().clean()
        categoria = cleaned_data.get('categoria')

        if categoria == self.CUSTOM_CATEGORY_VALUE:
            categoria_custom = (cleaned_data.get('categoria_custom') or '').strip()
            if not categoria_custom:
                self.add_error('categoria_custom', 'Informe o nome da nova categoria.')
            else:
                cleaned_data['categoria'] = categoria_custom

        return cleaned_data

    class Meta:
        model = Servico
        fields = ['nome', 'categoria', 'descricao', 'preco', 'tempo', 'ativo']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
        }
