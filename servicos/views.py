from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Servico
from .forms import ServicoForm
from django.contrib.auth.decorators import login_required
from empresas.business_profiles import get_business_profile
from empresas.tenancy import get_active_empresa
from empresas.permissions import is_profissional_user

@login_required
def servicos_list(request):
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para a area de agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')
    
    servicos = Servico.objects.filter(empresa=empresa)
    return render(request, 'servicos/servicos_list.html', {'servicos': servicos})


@login_required
def servicos_form(request, pk=None):
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para a area de agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')
    
    if pk:
        servico = get_object_or_404(Servico, pk=pk, empresa=empresa)
    else:
        servico = None

    profile = get_business_profile(empresa.tipo)
    termo_servico = profile['service_term_singular']

    if request.method == 'POST':
        form = ServicoForm(request.POST, instance=servico, empresa=empresa)
        if form.is_valid():
            servico = form.save(commit=False)
            servico.empresa = empresa
            servico.save()
            return redirect('servicos_list')
    else:
        form = ServicoForm(instance=servico, empresa=empresa)

    return render(request, 'servicos/servicos_form.html', {
        'form': form,
        'page_title': f"Editar {termo_servico}" if servico else f"Novo {termo_servico}",
        'page_subtitle': f"Cadastre os {profile['service_term_plural'].lower()} que a sua equipe oferece.",
    })


@login_required
def servicos_delete(request, pk):
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para a area de agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')
    
    servico = get_object_or_404(Servico, pk=pk, empresa=empresa)

    if request.method == 'POST':
        servico.delete()
        return redirect('servicos_list')

    return render(request, 'servicos/servicos_delete.html', {'servico': servico})
