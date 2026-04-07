from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.db import transaction
from .forms import CadastroEmpresaForm
from .models import Empresa
from .business_profiles import get_business_profile, get_registration_profiles_payload
from .tenancy import get_accessible_empresas, set_active_empresa

def cadastro_empresa(request):
    if request.method == 'POST':
        form = CadastroEmpresaForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            senha = form.cleaned_data['senha']

            # 🔒 VALIDAÇÃO DE USUÁRIO EXISTENTE
            if User.objects.filter(username=email).exists():
                messages.error(request, 'Este e-mail já está cadastrado.')
                return render(request, 'registration/cadastro.html', {'form': form})

            # ✅ Cria usuário e empresa em transação atômica
            plano_escolhido = form.cleaned_data['plano']
            tabela_valor = {
                Empresa.PLANO_SOLO: 97,
                Empresa.PLANO_START: 147,
                Empresa.PLANO_ADMIN_ONLY: 127,
            }
            with transaction.atomic():
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=senha,
                    first_name=form.cleaned_data['nome_completo']
                )
                Empresa.objects.create(
                    usuario=user,
                    nome=form.cleaned_data['nome_empresa'],
                    tipo=form.cleaned_data['tipo_empresa'],
                    cnpj=form.cleaned_data['cpf_cnpj'],
                    whatsapp=form.cleaned_data['whatsapp'],
                    plano=plano_escolhido,
                    valor_mensal=tabela_valor.get(plano_escolhido, 147),
                    limite_profissionais=form.cleaned_data['limite_profissionais'],
                )

            messages.success(request, 'Cadastro realizado com sucesso! Faça login para continuar.')
            return redirect('login')
    else:
        form = CadastroEmpresaForm()

    selected_business_type = form['tipo_empresa'].value()
    profile = get_business_profile(selected_business_type)

    return render(request, 'registration/cadastro.html', {
        'form': form,
        'registration_profile': profile,
        'business_profiles_payload': get_registration_profiles_payload(),
    })


@login_required
def selecionar_empresa(request):
    destino = request.POST.get('next') or reverse('dashboard_home')

    if request.method != 'POST':
        return redirect(destino)

    empresa_id = request.POST.get('empresa_id')
    empresas = get_accessible_empresas(request)

    if not empresa_id or not empresas.exists():
        return redirect(destino)

    empresa = get_object_or_404(empresas, pk=empresa_id)
    set_active_empresa(request, empresa)
    return redirect(destino)
