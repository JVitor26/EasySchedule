from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Sum

from empresas.tenancy import get_active_empresa
from empresas.permissions import is_profissional_user

from .forms import ProdutoForm, VendaForm
from .models import Produto, VendaProduto


def _is_owner(request, empresa):
    """Apenas o proprietário da empresa (ou global admin) acessa vendas."""
    from empresas.permissions import is_global_admin
    if is_global_admin(request.user):
        return True
    try:
        return request.user.empresa == empresa
    except Exception:
        return False


@login_required
def produtos_list(request):
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para a area de agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect("cadastro_empresa")

    produtos = Produto.objects.filter(empresa=empresa)
    return render(request, "produtos/produtos_list.html", {
        "produtos": produtos,
        "is_owner": _is_owner(request, empresa),
    })


@login_required
def produtos_form(request, pk=None):
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para a area de agenda.')
        return redirect('dashboard_home')

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
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para a area de agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect("cadastro_empresa")

    produto = get_object_or_404(Produto, pk=pk, empresa=empresa)

    if request.method == "POST":
        produto.delete()
        return redirect("produtos_list")

    return render(request, "produtos/produtos_delete.html", {"produto": produto})


# ============================================================
# VENDAS — somente proprietário da empresa
# ============================================================

@login_required
def vendas_list(request):
    empresa = get_active_empresa(request)
    if not empresa:
        return redirect("cadastro_empresa")

    if not _is_owner(request, empresa):
        messages.warning(request, "Apenas o proprietário pode acessar a área de vendas.")
        return redirect("dashboard_home")

    vendas = VendaProduto.objects.filter(empresa=empresa).select_related("produto", "cliente")

    # Filtros de data
    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")
    if data_inicio:
        vendas = vendas.filter(data_venda__gte=data_inicio)
    if data_fim:
        vendas = vendas.filter(data_venda__lte=data_fim)

    # Totais
    totais = vendas.aggregate(total_receita=Sum("valor_venda"))
    total_receita = float(totais["total_receita"] or 0)

    return render(request, "produtos/vendas_list.html", {
        "vendas": vendas,
        "data_inicio": data_inicio or "",
        "data_fim": data_fim or "",
        "total_receita": total_receita,
    })


@login_required
def vendas_form(request, pk=None):
    empresa = get_active_empresa(request)
    if not empresa:
        return redirect("cadastro_empresa")

    if not _is_owner(request, empresa):
        messages.warning(request, "Apenas o proprietário pode registrar vendas.")
        return redirect("dashboard_home")

    venda = get_object_or_404(VendaProduto, pk=pk, empresa=empresa) if pk else None

    if request.method == "POST":
        form = VendaForm(request.POST, instance=venda, empresa=empresa)
        if form.is_valid():
            v = form.save(commit=False)
            v.empresa = empresa
            v.save()
            messages.success(request, "Venda registrada com sucesso!")
            return redirect("vendas_list")
    else:
        form = VendaForm(instance=venda, empresa=empresa)

    return render(request, "produtos/vendas_form.html", {
        "form": form,
        "venda": venda,
        "page_title": "Editar venda" if venda else "Nova venda",
    })


@login_required
def vendas_delete(request, pk):
    empresa = get_active_empresa(request)
    if not empresa:
        return redirect("cadastro_empresa")

    if not _is_owner(request, empresa):
        messages.warning(request, "Apenas o proprietário pode excluir vendas.")
        return redirect("dashboard_home")

    venda = get_object_or_404(VendaProduto, pk=pk, empresa=empresa)

    if request.method == "POST":
        venda.delete()
        messages.success(request, "Venda excluída.")
        return redirect("vendas_list")

    return render(request, "produtos/vendas_delete.html", {"venda": venda})

