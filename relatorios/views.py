from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from datetime import date as date_type
from .models import Relatorio
from .services import RelatorioService
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from empresas.tenancy import get_active_empresa
from empresas.permissions import is_profissional_user
from dashboard.models import DashboardPreference


def get_report_card_definitions(empresa):
    profile = empresa.business_profile
    appointment_term = profile.get('appointment_term_plural', 'Agendamentos')

    return [
        {
            'key': 'faturamento',
            'label': 'Faturamento',
            'description': 'Receita de atendimentos finalizados no período.',
            'group': 'left',
        },
        {
            'key': 'agendamentos',
            'label': appointment_term,
            'description': 'Quantidade de atendimentos registrados no período.',
            'group': 'left',
        },
        {
            'key': 'cancelamentos',
            'label': 'Cancelamentos',
            'description': 'Taxa de cancelamento e volume cancelado.',
            'group': 'left',
        },
        {
            'key': 'ticket',
            'label': 'Ticket médio',
            'description': 'Valor médio por atendimento finalizado.',
            'group': 'left',
        },
        {
            'key': 'previsao_agendamentos',
            'label': 'Previsão de agendamentos',
            'description': 'Quantidade prevista de atendimentos futuros.',
            'group': 'right',
        },
        {
            'key': 'previsao_receita',
            'label': 'Previsão de receita',
            'description': 'Valor previsto por agendamentos e planos pendentes.',
            'group': 'right',
        },
        {
            'key': 'planos_pendentes',
            'label': 'Planos pendentes',
            'description': 'Total de planos contratados ainda não pagos.',
            'group': 'right',
        },
        {
            'key': 'vendas_total',
            'label': 'Total de vendas',
            'description': 'Valor total de todas as vendas de produtos no período.',
            'group': 'vendas',
        },
        {
            'key': 'vendas_pendentes',
            'label': 'Vendas pendentes',
            'description': 'Vendas realizadas mas sem pagamento registrado.',
            'group': 'vendas',
        },
        {
            'key': 'vendas_atrasadas',
            'label': 'Vendas atrasadas',
            'description': 'Vendas antigas ainda sem pagamento (data da venda já passou).',
            'group': 'vendas',
        },
        {
            'key': 'previsao_recebimentos',
            'label': 'Previsão de recebimentos',
            'description': 'Total a receber de vendas com pagamento pendente.',
            'group': 'vendas',
        },
    ]



@login_required
def relatorio_page(request):
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para a area de agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    cards = get_report_card_definitions(empresa)
    valid_keys = {card['key'] for card in cards}
    default_keys = [card['key'] for card in cards]
    preference, _ = DashboardPreference.objects.get_or_create(empresa=empresa)

    if request.method == 'POST':
        selected_cards = [key for key in request.POST.getlist('report_cards') if key in valid_keys]
        preference.selected_report_cards = selected_cards or default_keys
        preference.save(update_fields=['selected_report_cards', 'updated_at'])
        return redirect('relatorio_page')

    selected_cards = [key for key in (preference.selected_report_cards or []) if key in valid_keys]
    if not selected_cards:
        selected_cards = default_keys

    cards_by_group = {
        'left': [card for card in cards if card['group'] == 'left'],
        'right': [card for card in cards if card['group'] == 'right'],
        'vendas': [card for card in cards if card['group'] == 'vendas'],
    }

    return render(request, 'relatorios/relatorio.html', {
        'cards_by_group': cards_by_group,
        'selected_report_cards': selected_cards,
    })

@login_required
def dashboard(request):
    if is_profissional_user(request.user):
        return JsonResponse({'detail': 'Perfil sem permissao para relatorios.'}, status=403)

    empresa = get_active_empresa(request)

    if not empresa:
        return JsonResponse({'detail': 'Empresa não selecionada.'}, status=400)

    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    relatorio_base = Relatorio(
        empresa=empresa,
        usuario=request.user,
        nome="Dashboard",
        tipo="agendamentos",
        data_inicio=data_inicio or None,
        data_fim=data_fim or None
    )

    dados = {
        "faturamento": RelatorioService.faturamento(relatorio_base),
        "agendamentos": RelatorioService.agendamentos_por_dia(relatorio_base),
        "profissionais": RelatorioService.por_profissional(relatorio_base),
        "servicos": RelatorioService.por_servico(relatorio_base),
        "cancelamentos": RelatorioService.cancelamentos(relatorio_base),
        "previsao_agendamentos": RelatorioService.previsao_agendamentos(relatorio_base),
        "previsao_receita": RelatorioService.previsao_receita(relatorio_base),
    }

    return JsonResponse(dados)


class ExecutarRelatorioView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if is_profissional_user(request.user):
            return Response({'detail': 'Perfil sem permissao para relatorios.'}, status=403)

        empresa = get_active_empresa(request)

        if not empresa:
            return Response({'detail': 'Empresa não selecionada.'}, status=400)

        relatorio = get_object_or_404(Relatorio, pk=pk, empresa=empresa)

        dados = RelatorioService.executar(relatorio)

        return Response(dados)


@login_required
def dashboard_vendas(request):
    if is_profissional_user(request.user):
        return JsonResponse({'detail': 'Perfil sem permissao para relatorios.'}, status=403)

    empresa = get_active_empresa(request)
    if not empresa:
        return JsonResponse({'detail': 'Empresa não selecionada.'}, status=400)

    def parse_date(value):
        if not value:
            return None
        try:
            return date_type.fromisoformat(value)
        except ValueError:
            return None

    data_inicio = parse_date(request.GET.get('data_inicio'))
    data_fim = parse_date(request.GET.get('data_fim'))

    dados = {
        'kpis': RelatorioService.vendas_kpis(empresa, data_inicio, data_fim),
        'produtos_mais_vendidos': RelatorioService.produtos_mais_vendidos(empresa, data_inicio, data_fim),
        'clientes_top': RelatorioService.clientes_top_compradores(empresa, data_inicio, data_fim),
        'previsao_recebimentos': RelatorioService.previsao_recebimentos_vendas(empresa, data_inicio, data_fim),
    }

    return JsonResponse(dados)