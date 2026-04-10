from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Profissional
from .forms import ProfissionalForm
from empresas.business_profiles import get_business_profile
from empresas.tenancy import get_active_empresa
from empresas.permissions import is_profissional_user

@login_required
def profissionais_list(request):
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para a area de agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    profissionais = Profissional.objects.filter(empresa=empresa)
    return render(request, 'profissionais/profissionais_list.html', {'profissionais': profissionais})


@login_required
def profissionais_form(request, pk=None):
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para a area de agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    if pk:
        profissional = get_object_or_404(Profissional, pk=pk, empresa=empresa)
    else:
        profissional = None

    profile = get_business_profile(empresa.tipo)
    termo_profissional = profile['professional_term_singular']

    if profissional is None and not empresa.can_add_profissional():
        messages.error(
            request,
            f"Seu plano permite ate {empresa.limite_profissionais} profissional(is) ativo(s). "
            "Faça upgrade para liberar mais vagas.",
        )
        return redirect('profissionais_list')

    if request.method == 'POST':
        form = ProfissionalForm(request.POST, instance=profissional, empresa=empresa)
        if form.is_valid():
            profissional = form.save(commit=False)
            profissional.empresa = empresa

            if profissional.pk is None and profissional.ativo and not empresa.can_add_profissional():
                form.add_error(None, f"Limite do plano atingido ({empresa.limite_profissionais} profissional(is) ativos).")
                return render(request, 'profissionais/profissionais_form.html', {
                    'form': form,
                    'page_title': f"Editar {termo_profissional}" if profissional else f"Novo {termo_profissional}",
                    'page_subtitle': f"Registre a equipe e a especialidade de cada {termo_profissional.lower()}.",
                })

            usuario_acesso = form.provision_access_user()
            profissional.usuario = usuario_acesso
            if usuario_acesso and not (profissional.email or '').strip():
                profissional.email = usuario_acesso.email

            profissional.save()
            return redirect('profissionais_list')
    else:
        form = ProfissionalForm(instance=profissional, empresa=empresa)

    return render(request, 'profissionais/profissionais_form.html', {
        'form': form,
        'page_title': f"Editar {termo_profissional}" if profissional else f"Novo {termo_profissional}",
        'page_subtitle': f"Registre a equipe e a especialidade de cada {termo_profissional.lower()}.",
    })


@login_required
def profissionais_delete(request, pk):
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para a area de agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    profissional = get_object_or_404(Profissional, pk=pk, empresa=empresa)

    if request.method == 'POST':
        profissional.delete()
        return redirect('profissionais_list')

    return render(request, 'profissionais/profissionais_delete.html', {'profissional': profissional})
