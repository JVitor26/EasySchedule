from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Profissional
from .forms import ProfissionalForm
from empresas.business_profiles import get_business_profile
from empresas.tenancy import get_active_empresa

@login_required
def profissionais_list(request):
    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    profissionais = Profissional.objects.filter(empresa=empresa)
    return render(request, 'profissionais/profissionais_list.html', {'profissionais': profissionais})


@login_required
def profissionais_form(request, pk=None):
    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    if pk:
        profissional = get_object_or_404(Profissional, pk=pk, empresa=empresa)
    else:
        profissional = None

    profile = get_business_profile(empresa.tipo)
    termo_profissional = profile['professional_term_singular']

    if request.method == 'POST':
        form = ProfissionalForm(request.POST, instance=profissional, empresa=empresa)
        if form.is_valid():
            profissional = form.save(commit=False)
            profissional.empresa = empresa
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
    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    profissional = get_object_or_404(Profissional, pk=pk, empresa=empresa)

    if request.method == 'POST':
        profissional.delete()
        return redirect('profissionais_list')

    return render(request, 'profissionais/profissionais_delete.html', {'profissional': profissional})
