from django import forms

from .models import Produto


class ProdutoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nome"].label = "Nome do produto"
        self.fields["nome"].widget.attrs["placeholder"] = "Ex.: Oleo para barba premium"
        self.fields["categoria"].label = "Categoria"
        self.fields["categoria"].widget.attrs["placeholder"] = "Ex.: Finalizacao, cuidados, acessorios"
        self.fields["preco"].label = "Preco"
        self.fields["preco"].widget.attrs["placeholder"] = "0,00"
        self.fields["estoque"].label = "Quantidade em estoque"
        self.fields["estoque"].widget.attrs["placeholder"] = "0"
        self.fields["descricao"].label = "Descricao"
        self.fields["descricao"].widget.attrs["placeholder"] = "Descreva rapidamente o produto e para quem ele e indicado."
        self.fields["especificacoes"].label = "Especificacoes tecnicas"
        self.fields["especificacoes"].widget.attrs["placeholder"] = "Liste tamanho, composicao, fragrancia, cor, modo de uso ou qualquer detalhe importante."
        self.fields["foto"].label = "Foto do produto"
        self.fields["foto"].required = False
        self.fields["ativo"].label = "Produto ativo para venda"
        self.fields["destaque_publico"].label = "Mostrar este produto no portal do cliente"

    class Meta:
        model = Produto
        fields = [
            "nome",
            "categoria",
            "preco",
            "estoque",
            "descricao",
            "especificacoes",
            "foto",
            "ativo",
            "destaque_publico",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
            "especificacoes": forms.Textarea(attrs={"rows": 4}),
            "foto": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

