from django import forms
from .models import Servico
from empresas.business_profiles import get_business_profile

class ServicoForm(forms.ModelForm):
    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        profile = get_business_profile(getattr(empresa, 'tipo', None))
        categoria_atual = self.initial.get('categoria') or getattr(self.instance, 'categoria', '')

        categorias = list(profile['service_categories'])
        valores_existentes = {value for value, _label in categorias}
        if categoria_atual and categoria_atual not in valores_existentes:
            categorias.append((categoria_atual, categoria_atual.replace('_', ' ').title()))

        self.fields['nome'].label = profile['service_name_label']
        self.fields['nome'].widget.attrs['placeholder'] = profile['service_name_placeholder']
        self.fields['categoria'].label = profile['service_category_label']
        self.fields['categoria'].widget = forms.Select(choices=categorias)
        self.fields['categoria'].choices = categorias
        self.fields['categoria'].help_text = f"Categorias sugeridas para {profile['label'].lower()}."
        self.fields['descricao'].label = profile['service_description_label']
        self.fields['descricao'].widget.attrs['placeholder'] = profile['service_description_placeholder']
        self.fields['preco'].label = 'Preco'
        self.fields['preco'].widget.attrs['placeholder'] = '0,00'
        self.fields['tempo'].label = 'Duracao (minutos)'
        self.fields['tempo'].widget.attrs['placeholder'] = '60'
        self.fields['ativo'].label = f"{profile['service_term_singular']} ativo"

    class Meta:
        model = Servico
        fields = ['nome', 'categoria', 'descricao', 'preco', 'tempo', 'ativo']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
        }
