from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.db import transaction
from .forms import (
    CadastroEmpresaForm,
    EmpresaConfiguracaoForm,
    parse_profissional_modules_from_post,
    profissional_module_choices,
)
from .models import Empresa
from .business_profiles import get_business_profile, get_registration_profiles_payload
from .services import delete_empresa_account
from .tenancy import get_accessible_empresas, get_active_empresa, set_active_empresa
from .permissions import can_manage_empresa_settings, is_profissional_user
from profissionais.models import Profissional


def _get_configurable_empresa_or_redirect(request):
    empresa = get_active_empresa(request)
    if not empresa:
        return None, redirect('cadastro_empresa')

    if not can_manage_empresa_settings(request.user, empresa):
        if is_profissional_user(request.user):
            messages.warning(request, 'Somente administrador pode abrir as configuracoes da empresa.')
        else:
            messages.error(request, 'Voce nao possui permissao para alterar esta empresa.')
        return None, redirect('dashboard_home')

    return empresa, None

def cadastro_empresa(request):
    if request.method == 'POST':
        form = CadastroEmpresaForm(request.POST, request.FILES)
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
                    logo=form.cleaned_data['logo'],
                    cor_primaria=form.cleaned_data['cor_primaria'],
                    cor_secundaria=form.cleaned_data['cor_secundaria'],
                    plano=plano_escolhido,
                    valor_mensal=tabela_valor.get(plano_escolhido, 147),
                    limite_profissionais=form.cleaned_data['limite_profissionais'],
                )

            messages.success(request, 'Cadastro realizado com sucesso! Bem-vindo ao EasySchedule.')
            login(request, user)
            return redirect('dashboard_home')
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


@login_required
def empresa_configuracoes(request):
    empresa, response = _get_configurable_empresa_or_redirect(request)
    if response:
        return response

    profissionais = list(
        Profissional.objects.filter(empresa=empresa).select_related('usuario').order_by('nome')
    )

    if request.method == 'POST':
        form = EmpresaConfiguracaoForm(request.POST, request.FILES, instance=empresa)
        if form.is_valid():
            form.save()

            modulo_updates = parse_profissional_modules_from_post(request.POST, profissionais)
            for profissional in profissionais:
                profissional.acessos_modulos = modulo_updates.get(profissional.pk, profissional.get_allowed_modules())
                profissional.save(update_fields=['acessos_modulos'])

            messages.success(request, 'Configuracoes da empresa atualizadas com sucesso.')
            return redirect('empresa_configuracoes')
    else:
        form = EmpresaConfiguracaoForm(instance=empresa)

    return render(request, 'empresas/empresa_configuracoes.html', {
        'form': form,
        'empresa': empresa,
        'profissionais': profissionais,
        'module_choices': profissional_module_choices(),
        'portal_agendamento_url': request.build_absolute_uri(reverse('cliente_empresa', args=[empresa.portal_token])),
        'portal_catalogo_url': request.build_absolute_uri(reverse('cliente_catalogo', args=[empresa.portal_token])),
        'portal_loja_url': request.build_absolute_uri(reverse('loja_produtos', args=[empresa.portal_token])),
    })


@login_required
def empresa_excluir_conta(request):
    empresa, response = _get_configurable_empresa_or_redirect(request)
    if response:
        return response

    if empresa.usuario_id != request.user.id:
        messages.error(request, 'Somente o administrador dono da empresa pode apagar esta conta.')
        return redirect('empresa_configuracoes')

    if request.method == 'POST':
        empresa_nome = empresa.nome
        delete_empresa_account(empresa)
        logout(request)
        messages.success(request, f'A conta {empresa_nome} foi apagada com todos os dados vinculados.')
        return redirect('login')

    return render(request, 'empresas/empresa_excluir_conta.html', {'empresa': empresa})
