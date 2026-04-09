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


class VendaForm(forms.ModelForm):
    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = empresa

        if empresa:
            self.fields["produto"].queryset = Produto.objects.filter(empresa=empresa, ativo=True).order_by("nome")
            self.fields["cliente"].queryset = Pessoa.objects.filter(empresa=empresa).order_by("nome")

        self.fields["produto"].label = "Produto"
        self.fields["produto"].empty_label = "Selecione o produto"
        self.fields["cliente"].label = "Cliente cadastrado (opcional)"
        self.fields["cliente"].empty_label = "Nenhum — informar nome abaixo"
        self.fields["cliente_nome_avulso"].label = "Nome do cliente (se não cadastrado)"
        self.fields["cliente_nome_avulso"].widget.attrs["placeholder"] = "Ex.: João Silva"
        self.fields["quantidade"].label = "Quantidade"
        self.fields["custo"].label = "Custo de aquisição (R$)"
        self.fields["custo"].widget.attrs["placeholder"] = "0,00"
        self.fields["valor_mercado"].label = "Valor de mercado (R$)"
        self.fields["valor_mercado"].widget.attrs["placeholder"] = "0,00"
        self.fields["valor_final"].label = "Valor final cobrado (R$)"
        self.fields["valor_final"].widget.attrs["placeholder"] = "0,00"
        self.fields["metodo_pagamento"].label = "Forma de pagamento"
        self.fields["data_venda"].label = "Data da venda"
        self.fields["data_recebimento"].label = "Data de recebimento (deixe vazio se ainda não recebeu)"
        self.fields["observacoes"].label = "Observações"
        self.fields["observacoes"].widget.attrs["placeholder"] = "Anotações internas sobre esta venda."

    def clean(self):
        cleaned_data = super().clean()
        cliente = cleaned_data.get("cliente")
        nome_avulso = (cleaned_data.get("cliente_nome_avulso") or "").strip()
        if not cliente and not nome_avulso:
            self.add_error("cliente_nome_avulso", "Informe o cliente ou preencha o nome abaixo.")
        return cleaned_data

    class Meta:
        model = VendaProduto
        fields = [
            "produto",
            "cliente",
            "cliente_nome_avulso",
            "quantidade",
            "custo",
            "valor_mercado",
            "valor_final",
            "metodo_pagamento",
            "data_venda",
            "data_recebimento",
            "observacoes",
        ]
        widgets = {
            "data_venda": forms.DateInput(attrs={"type": "date"}),
            "data_recebimento": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

