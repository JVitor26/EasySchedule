from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Pessoa
from .forms import PessoaForm
from django.contrib.auth.decorators import login_required
from empresas.business_profiles import get_business_profile
from empresas.tenancy import get_active_empresa
from empresas.permissions import is_profissional_user

@login_required
def pessoa_list(request):
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para a area de agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    pessoas = Pessoa.objects.filter(empresa=empresa)
    return render(request, 'pessoa/pessoa_list.html', {'pessoas': pessoas})


@login_required
def pessoa_form(request, pk=None):
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para a area de agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    if pk:
        pessoa = get_object_or_404(Pessoa, pk=pk, empresa=empresa)
    else:
        pessoa = None

    profile = get_business_profile(empresa.tipo)
    termo_cliente = profile['client_term_singular']

    if request.method == 'POST':
        form = PessoaForm(request.POST, instance=pessoa, empresa=empresa)
        if form.is_valid():
            pessoa = form.save(commit=False)
            pessoa.empresa = empresa
            pessoa.save()
            return redirect('pessoa_list')
    else:
        form = PessoaForm(instance=pessoa, empresa=empresa)

    return render(request, 'pessoa/pessoa_form.html', {
        'form': form,
        'page_title': f"Editar {termo_cliente}" if pessoa else f"Novo {termo_cliente}",
        'page_subtitle': f"Cadastre os dados do {termo_cliente.lower()} para agilizar os proximos atendimentos.",
    })


@login_required
def pessoa_delete(request, pk):
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para a area de agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    pessoa = get_object_or_404(Pessoa, pk=pk, empresa=empresa)

    if request.method == 'POST':
        pessoa.delete()
        return redirect('pessoa_list')

    return render(request, 'pessoa/pessoa_delete.html', {'pessoa': pessoa})
