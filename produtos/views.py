from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from empresas.tenancy import get_active_empresa

from .forms import ProdutoForm
from .models import Produto


@login_required
def produtos_list(request):
    empresa = get_active_empresa(request)

    if not empresa:
        return redirect("cadastro_empresa")

    produtos = Produto.objects.filter(empresa=empresa)
    return render(request, "produtos/produtos_list.html", {"produtos": produtos})


@login_required
def produtos_form(request, pk=None):
    empresa = get_active_empresa(request)

    if not empresa:
        return redirect("cadastro_empresa")

    produto = get_object_or_404(Produto, pk=pk, empresa=empresa) if pk else None

    if request.method == "POST":
        form = ProdutoForm(request.POST, request.FILES, instance=produto)
        if form.is_valid():
            produto = form.save(commit=False)
            produto.empresa = empresa
            produto.save()
            return redirect("produtos_list")
    else:
        form = ProdutoForm(instance=produto)

    return render(request, "produtos/produtos_form.html", {
        "form": form,
        "page_title": "Editar produto" if produto else "Novo produto",
        "page_subtitle": (
            "Cadastre produtos com foto, estoque, descricao e especificacoes para manter a vitrine "
            "da sua empresa organizada dentro do sistema."
        ),
    })


@login_required
def produtos_delete(request, pk):
    empresa = get_active_empresa(request)

    if not empresa:
        return redirect("cadastro_empresa")

    produto = get_object_or_404(Produto, pk=pk, empresa=empresa)

    if request.method == "POST":
        produto.delete()
        return redirect("produtos_list")

    return render(request, "produtos/produtos_delete.html", {"produto": produto})

