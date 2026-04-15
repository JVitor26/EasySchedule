from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from django.utils.timezone import localdate
from pessoa.models import Pessoa
from profissionais.models import Profissional
from servicos.models import Servico
from agendamentos.models import Agendamento, NotificacaoProfissional
from core.loyalty import build_reengagement_candidates, nps_score_from_queryset
from core.models import NPSResposta
from produtos.models import VendaProduto
from empresas.tenancy import get_active_empresa
from empresas.permissions import is_profissional_user, is_global_admin
from .models import DashboardPreference


def get_dashboard_card_definitions(empresa):
    profile = empresa.business_profile
    client_term = profile.get('client_term_plural', 'Clientes')
    professional_term = profile.get('professional_term_plural', 'Profissionais')
    service_term = profile.get('service_term_plural', 'Servicos')
    appointment_term = profile.get('appointment_term_plural', 'Agendamentos')

    return [
        {
            'key': 'total_clients',
            'label': client_term,
            'description': f'Base total de {client_term.lower()} cadastrados.',
            'group': 'left',
            'format': 'number',
        },
        {
            'key': 'total_professionals',
            'label': professional_term,
            'description': f'Pessoas ativas disponíveis para {appointment_term.lower()}.',
            'group': 'left',
            'format': 'number',
        },
        {
            'key': 'total_services',
            'label': service_term,
            'description': f'{service_term} cadastrados na operação.',
            'group': 'left',
            'format': 'number',
        },
        {
            'key': 'total_appointments',
            'label': appointment_term,
            'description': 'Total de atendimentos registrados no sistema.',
            'group': 'left',
            'format': 'number',
        },
        {
            'key': 'revenue_month',
            'label': 'Faturamento do mês',
            'description': 'Receita calculada a partir dos atendimentos finalizados.',
            'group': 'right',
            'format': 'currency',
        },
        {
            'key': 'appointments_month',
            'label': 'Atendimentos no mês',
            'description': 'Total de atendimentos agendados para este mês.',
            'group': 'right',
            'format': 'number',
        },
        {
            'key': 'today_appointments',
            'label': 'Agenda de hoje',
            'description': 'Atendimentos marcados para hoje.',
            'group': 'right',
            'format': 'number',
        },
        {
            'key': 'confirmed_today',
            'label': 'Confirmados hoje',
            'description': 'Atendimentos confirmados para hoje.',
            'group': 'right',
            'format': 'number',
        },
        {
            'key': 'pending_today',
            'label': 'Pendentes hoje',
            'description': 'Atendimentos em aberto para hoje.',
            'group': 'right',
            'format': 'number',
        },
        {
            'key': 'finalized_month',
            'label': 'Finalizados no mês',
            'description': 'Atendimentos concluídos neste mês.',
            'group': 'left',
            'format': 'number',
        },
        {
            'key': 'canceled_month',
            'label': 'Cancelados no mês',
            'description': 'Atendimentos cancelados neste mês.',
            'group': 'right',
            'format': 'number',
        },
        {
            'key': 'no_show_month',
            'label': 'No-show no mês',
            'description': 'Atendimentos sem comparecimento no mês.',
            'group': 'right',
            'format': 'number',
        },
        {
            'key': 'show_rate_month',
            'label': 'Taxa de comparecimento',
            'description': 'Percentual de comparecimento sobre a agenda do mês.',
            'group': 'right',
            'format': 'percent',
        },
        {
            'key': 'reactivation_candidates',
            'label': 'Reativações prontas',
            'description': 'Clientes sem retorno recente e sem próximos agendamentos.',
            'group': 'left',
            'format': 'number',
        },
        {
            'key': 'avg_ticket_month',
            'label': 'Ticket médio',
            'description': 'Valor médio por atendimento finalizado no mês.',
            'group': 'left',
            'format': 'currency',
        },
        {
            'key': 'nps_month',
            'label': 'NPS do mês',
            'description': 'Pontuação de satisfação calculada por promotores e detratores.',
            'group': 'right',
            'format': 'number',
        },
    ]


def get_selected_dashboard_cards(preference, cards):
    selected = preference.selected_cards if preference and preference.selected_cards else []
    selected = [key for key in selected if key in {card['key'] for card in cards}]
    if not selected:
        selected = [card['key'] for card in cards[:4]]
    return [card for card in cards if card['key'] in selected]


@login_required
def dashboard_home(request):
    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    hoje = localdate()
    profissional_logado = getattr(request.user, 'profissional_profile', None) if is_profissional_user(request.user) else None

    total_clients = Pessoa.objects.filter(empresa=empresa).count()
    total_professionals = Profissional.objects.filter(empresa=empresa).count()
    total_services = Servico.objects.filter(empresa=empresa).count()
    profissionais = Profissional.objects.filter(empresa=empresa, ativo=True).order_by('nome')

    agendamentos_base = Agendamento.objects.filter(empresa=empresa)
    if profissional_logado:
        agendamentos_base = agendamentos_base.filter(profissional=profissional_logado)
        profissionais = profissionais.filter(pk=profissional_logado.pk)

    total_appointments = agendamentos_base.count()

    agendamentos_hoje = agendamentos_base.filter(data=hoje).select_related('cliente', 'servico', 'profissional').order_by('hora')
    today_appointments = agendamentos_hoje.count()
    confirmed_today = agendamentos_hoje.filter(status='confirmado').count()
    pending_today = agendamentos_hoje.filter(status='pendente').count()

    agendamentos_mes = agendamentos_base.filter(data__month=hoje.month, data__year=hoje.year)

    revenue_month = agendamentos_mes.filter(status='finalizado').aggregate(total=Sum('servico__preco'))['total'] or 0
    appointments_month = agendamentos_mes.count()
    finalized_month = agendamentos_mes.filter(status='finalizado').count()
    canceled_month = agendamentos_mes.filter(status='cancelado').count()
    no_show_month = agendamentos_mes.filter(status='no_show').count()

    presence_base = appointments_month - canceled_month
    show_rate_month = 0
    if presence_base > 0:
        show_rate_month = round(((finalized_month + confirmed_today) / presence_base) * 100, 1)

    avg_ticket_month = 0
    if finalized_month > 0:
        avg_ticket_month = round(revenue_month / finalized_month, 2)

    product_revenue_month = (
        VendaProduto.objects.filter(
            empresa=empresa,
            data_pagamento__isnull=False,
            data_pagamento__month=hoje.month,
            data_pagamento__year=hoje.year,
        ).aggregate(total=Sum('valor_venda'))['total'] or 0
    )
    total_revenue_month = revenue_month + product_revenue_month

    nps_queryset = NPSResposta.objects.filter(
        empresa=empresa,
        criado_em__month=hoje.month,
        criado_em__year=hoje.year,
    )
    nps_month = nps_score_from_queryset(nps_queryset)
    reengagement = build_reengagement_candidates(empresa, days_without_return=35, limit=20)
    reactivation_candidates = len(reengagement)

    preference, _ = DashboardPreference.objects.get_or_create(empresa=empresa)
    cards = get_dashboard_card_definitions(empresa)
    selected_cards = get_selected_dashboard_cards(preference, cards)

    card_values = {
        'total_clients': total_clients,
        'total_professionals': total_professionals,
        'total_services': total_services,
        'total_appointments': total_appointments,
        'revenue_month': revenue_month,
        'appointments_month': appointments_month,
        'today_appointments': today_appointments,
        'confirmed_today': confirmed_today,
        'pending_today': pending_today,
        'finalized_month': finalized_month,
        'canceled_month': canceled_month,
        'no_show_month': no_show_month,
        'show_rate_month': show_rate_month,
        'reactivation_candidates': reactivation_candidates,
        'avg_ticket_month': avg_ticket_month,
        'nps_month': nps_month,
    }

    for card in selected_cards:
        card['value'] = card_values.get(card['key'], 0)

    notificacoes_profissional = []
    if profissional_logado:
        notificacoes_profissional = NotificacaoProfissional.objects.filter(
            profissional=profissional_logado,
            lida=False,
        )[:10]

    context = {
        'hoje': hoje,
        'dashboard_widgets': selected_cards,
        'total_agendamentos': total_appointments,
        'total_servicos': total_services,
        'total_atendimentos_mes': appointments_month,
        'total_faturamento_mes': total_revenue_month,
        'confirmados_hoje': confirmed_today,
        'pendentes_hoje': pending_today,
        'no_show_mes': no_show_month,
        'show_rate_month': show_rate_month,
        'avg_ticket_month': avg_ticket_month,
        'nps_month': nps_month,
        'reativacao_candidatos': reengagement,
        'profissionais': profissionais,
        'status_choices': Agendamento.STATUS_CHOICES,
        'agendamentos_hoje': agendamentos_hoje,
        'dashboard_cards': cards,
        'selected_card_keys': [card['key'] for card in selected_cards],
        'profissional_logado': profissional_logado,
        'notificacoes_profissional': notificacoes_profissional,
    }

    return render(request, 'dashboard/agenda_dashboard.html', context)


@login_required
def dashboard_settings(request):
    if not is_global_admin(request.user):
        messages.warning(request, 'Somente o administrador da empresa pode alterar os cards do dashboard.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    preference, _ = DashboardPreference.objects.get_or_create(empresa=empresa)
    cards = get_dashboard_card_definitions(empresa)
    valid_keys = {card['key'] for card in cards}

    if request.method == 'POST':
        selected_cards = [key for key in request.POST.getlist('cards') if key in valid_keys]
        if not selected_cards:
            selected_cards = [card['key'] for card in cards[:4]]
        preference.selected_cards = selected_cards
        preference.save()
        return redirect('dashboard_home')

    categories = {
        'left': [card for card in cards if card['group'] == 'left'],
        'right': [card for card in cards if card['group'] == 'right'],
    }

    return render(request, 'dashboard/dashboard_settings.html', {
        'cards_by_group': categories,
        'selected_card_keys': set(preference.selected_cards or []),
    })
