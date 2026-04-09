from decimal import Decimal
from django import forms

from pessoa.models import Pessoa
from .models import Produto, VendaProduto


class ProdutoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nome"].label = "Nome do produto"
        self.fields["nome"].widget.attrs["placeholder"] = "Ex.: Oleo para barba premium"
        self.fields["categoria"].label = "Categoria"
        self.fields["categoria"].widget.attrs["placeholder"] = "Ex.: Finalizacao, cuidados, acessorios"
        self.fields["preco"].label = "Preço de exibição"
        self.fields["preco"].widget.attrs["placeholder"] = "0,00"
        self.fields["valor_compra"].label = "Valor de compra (aquisição)"
        self.fields["valor_compra"].widget.attrs["placeholder"] = "0,00"
        self.fields["custo"].label = "Custo (operacional)"
        self.fields["custo"].widget.attrs["placeholder"] = "0,00"
        self.fields["valor_venda"].label = "Valor de venda ao cliente"
        self.fields["valor_venda"].widget.attrs["placeholder"] = "0,00"
        self.fields["valor_compra"].required = False
        self.fields["custo"].required = False
        self.fields["valor_venda"].required = False
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

    def clean(self):
        cleaned_data = super().clean()
        preco = cleaned_data.get("preco") or Decimal("0")
        valor_compra = cleaned_data.get("valor_compra") or Decimal("0")
        custo = cleaned_data.get("custo")
        valor_venda = cleaned_data.get("valor_venda")

        if custo in (None, ""):
            cleaned_data["custo"] = preco - valor_compra
        if valor_venda in (None, ""):
            cleaned_data["valor_venda"] = preco

        return cleaned_data

    class Meta:
        model = Produto
        fields = [
            "nome",
            "categoria",
            "preco",
            "valor_compra",
            "custo",
            "valor_venda",
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


class VendaForm(forms.ModelForm):
    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = empresa

        if empresa:
            self.fields["produto"].queryset = Produto.objects.filter(empresa=empresa, ativo=True).order_by("nome")
            self.fields["cliente"].queryset = Pessoa.objects.filter(empresa=empresa).order_by("nome")

        self.fields["produto"].label = "Produto"
        self.fields["produto"].empty_label = "Selecione o produto"
        self.fields["cliente"].label = "Cliente"
        self.fields["cliente"].empty_label = "Cliente não cadastrado"
        self.fields["cliente_nome_avulso"].label = "Nome do cliente (se não cadastrado)"
        self.fields["cliente_nome_avulso"].widget.attrs["placeholder"] = "Ex.: João Silva"
        self.fields["valor_venda"].label = "Valor de venda (R$)"
        self.fields["valor_venda"].widget.attrs["placeholder"] = "0,00"
        self.fields["data_venda"].label = "Data da venda"
        self.fields["data_pagamento"].label = "Data do pagamento (vazio = ainda não pago)"
        self.fields["observacoes"].label = "Observações"
        self.fields["observacoes"].widget.attrs["placeholder"] = "Anotações internas."

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("cliente") and not (cleaned_data.get("cliente_nome_avulso") or "").strip():
            self.add_error("cliente_nome_avulso", "Selecione um cliente ou informe o nome.")
        return cleaned_data

    class Meta:
        model = VendaProduto
        fields = [
            "produto",
            "cliente",
            "cliente_nome_avulso",
            "valor_venda",
            "data_venda",
            "data_pagamento",
            "observacoes",
        ]
        widgets = {
            "data_venda": forms.DateInput(attrs={"type": "date"}),
            "data_pagamento": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }
