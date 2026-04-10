from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from .models import Agendamento, PlanoMensal
from .forms import AgendamentoForm, PlanoMensalForm
from datetime import datetime, timedelta, time
import json
from empresas.business_profiles import get_business_profile
from empresas.tenancy import get_active_empresa
from empresas.permissions import (
    PROFISSIONAL_ACCESS_AGENDAMENTOS,
    is_profissional_user,
    user_can_access_module,
)
from core.notifications import notify_booking_created
from produtos.models import VendaProduto


@login_required
def agendamentos_list(request):
    if not user_can_access_module(request.user, PROFISSIONAL_ACCESS_AGENDAMENTOS):
        messages.warning(request, 'Seu perfil nao possui acesso ao modulo de agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    agendamentos = Agendamento.objects.filter(empresa=empresa).select_related(
        'cliente',
        'servico',
        'profissional',
        'plano',
    )
    if is_profissional_user(request.user):
        agendamentos = agendamentos.filter(profissional=request.user.profissional_profile)
    return render(request, 'agendamentos/agendamentos_list.html', {'agendamentos': agendamentos})


@login_required
def agendamentos_form(request, pk=None):
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para visualizar a agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    if pk:
        agendamento = get_object_or_404(Agendamento, pk=pk, empresa=empresa)
        if agendamento.plano_id:
            return redirect('planos_edit', pk=agendamento.plano_id)
    else:
        agendamento = None

    profile = get_business_profile(empresa.tipo)
    termo_agendamento = profile['appointment_term_singular']

    if request.method == 'POST':
        form = AgendamentoForm(request.POST, instance=agendamento, empresa=empresa)
        if form.is_valid():
            try:
                is_new = agendamento is None
                agendamento = form.save(commit=False)
                agendamento.empresa = empresa
                agendamento.save()
                if is_new:
                    try:
                        notify_booking_created(agendamento)
                    except Exception:
                        pass
                return redirect('agendamentos_list')
            except ValidationError as e:
                form.add_error(None, str(e))
    else:
        form = AgendamentoForm(instance=agendamento, empresa=empresa)

    return render(request, 'agendamentos/agendamentos_form.html', {
        'form': form,
        'page_title': f"Editar {termo_agendamento}" if agendamento else f"Novo {termo_agendamento}",
        'page_subtitle': profile['appointment_page_hint'],
    })


@login_required
def planos_list(request):
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para visualizar a agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    planos = PlanoMensal.objects.filter(empresa=empresa).select_related(
        'cliente',
        'servico',
        'profissional',
    )
    return render(request, 'agendamentos/planos_list.html', {'planos': planos})


@login_required
def planos_form(request, pk=None):
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para visualizar a agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    plano = get_object_or_404(PlanoMensal, pk=pk, empresa=empresa) if pk else None
    profile = get_business_profile(empresa.tipo)

    if request.method == 'POST':
        form = PlanoMensalForm(request.POST, instance=plano, empresa=empresa)
        if form.is_valid():
            try:
                form.save()
                return redirect('planos_list')
            except ValidationError as exc:
                if hasattr(exc, 'message_dict'):
                    for field, messages in exc.message_dict.items():
                        for message in messages:
                            form.add_error(field if field in form.fields else None, message)
                else:
                    form.add_error(None, str(exc))
    else:
        form = PlanoMensalForm(instance=plano, empresa=empresa)

    return render(request, 'agendamentos/planos_form.html', {
        'form': form,
        'page_title': 'Editar plano mensal' if plano else 'Novo plano mensal',
        'page_subtitle': (
            f"Monte um pacote mensal com {profile['appointment_term_plural'].lower()} fixos por semana "
            "e um unico pagamento cobrindo o mes inteiro."
        ),
    })


@login_required
def planos_delete(request, pk):
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para visualizar a agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    plano = get_object_or_404(PlanoMensal, pk=pk, empresa=empresa)

    if request.method == 'POST':
        plano.delete()
        return redirect('planos_list')

    return render(request, 'agendamentos/planos_delete.html', {'plano': plano})


@login_required
def agendamentos_delete(request, pk):
    if is_profissional_user(request.user):
        messages.warning(request, 'Seu perfil possui acesso apenas para visualizar a agenda.')
        return redirect('dashboard_home')

    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    agendamento = get_object_or_404(Agendamento, pk=pk, empresa=empresa)

    if request.method == 'POST':
        agendamento.delete()
        return redirect('agendamentos_list')

    return render(request, 'agendamentos/agendamentos_delete.html', {'agendamento': agendamento})


@login_required
def agendamentos_api(request):
    if not user_can_access_module(request.user, PROFISSIONAL_ACCESS_AGENDAMENTOS):
        return JsonResponse([], safe=False)

    empresa = get_active_empresa(request)

    if not empresa:
        return JsonResponse([], safe=False)
    profissional_id = request.GET.get('profissional')
    status = request.GET.get('status')
    tipo_evento = (request.GET.get('tipo_evento') or 'geral').strip().lower()
    start = request.GET.get('start')
    end = request.GET.get('end')

    include_agendamentos = tipo_evento in ('', 'geral', 'agendamentos')
    include_produtos = tipo_evento in ('', 'geral', 'produtos')

    if tipo_evento not in ('', 'geral', 'agendamentos', 'produtos'):
        include_agendamentos = True
        include_produtos = True

    start_date = None
    end_date = None

    if start:
        start_value = parse_datetime(start)
        start_date = start_value.date() if start_value else parse_date(start[:10])

    if end:
        end_value = parse_datetime(end)
        end_date = end_value.date() if end_value else parse_date(end[:10])

    eventos = []

    status_colors = {
        'pendente': '#f59e0b',
        'confirmado': '#22c55e',
        'finalizado': '#38bdf8',
        'cancelado': '#ef4444',
    }

    if include_agendamentos:
        queryset = Agendamento.objects.filter(empresa=empresa).select_related(
            'cliente', 'servico', 'profissional'
        ).order_by('data', 'hora')

        if is_profissional_user(request.user):
            queryset = queryset.filter(profissional=request.user.profissional_profile)

        if profissional_id:
            queryset = queryset.filter(profissional_id=profissional_id)

        if status:
            queryset = queryset.filter(status=status)

        if start_date:
            queryset = queryset.filter(data__gte=start_date)

        if end_date:
            queryset = queryset.filter(data__lt=end_date)

        for ag in queryset:
            inicio = datetime.combine(ag.data, ag.hora)
            termino = inicio + timedelta(minutes=ag.servico.tempo or 30)
            eventos.append({
                'id': ag.id,
                'title': f'{ag.cliente.nome} - {ag.servico.nome}',
                'start': inicio.isoformat(),
                'end': termino.isoformat(),
                'editable': True,
                'color': status_colors.get(ag.status, ag.servico.cor or '#22c55e'),
                'extendedProps': {
                    'tipo_evento': 'agendamento',
                    'is_product_event': False,
                    'cliente': ag.cliente.nome,
                    'servico': ag.servico.nome,
                    'profissional': ag.profissional.nome if ag.profissional else '',
                    'valor': str(ag.servico.preco),
                    'status': ag.status,
                    'status_label': ag.get_status_display(),
                    'telefone': ag.cliente.telefone,
                    'observacoes': ag.observacoes or '',
                }
            })

    if include_produtos:
        vendas_qs = VendaProduto.objects.filter(empresa=empresa).select_related(
            'produto',
            'cliente',
            'agendamento__profissional',
        )

        if is_profissional_user(request.user):
            vendas_qs = vendas_qs.filter(
                Q(agendamento__profissional=request.user.profissional_profile)
                | Q(agendamento__isnull=True)
            )

        if profissional_id:
            vendas_qs = vendas_qs.filter(
                Q(agendamento__profissional_id=profissional_id)
                | Q(agendamento__isnull=True)
            )

        if start_date:
            vendas_qs = vendas_qs.filter(
                Q(data_entrega__isnull=False, data_entrega__gte=start_date)
                | Q(data_entrega__isnull=True, data_venda__gte=start_date)
            )

        if end_date:
            vendas_qs = vendas_qs.filter(
                Q(data_entrega__isnull=False, data_entrega__lt=end_date)
                | Q(data_entrega__isnull=True, data_venda__lt=end_date)
            )

        if status == 'pendente':
            vendas_qs = vendas_qs.filter(data_pagamento__isnull=True)
        elif status in ('confirmado', 'finalizado'):
            vendas_qs = vendas_qs.filter(data_pagamento__isnull=False)
        elif status == 'cancelado':
            vendas_qs = vendas_qs.none()

        for venda in vendas_qs.order_by('data_entrega', 'data_venda', 'criado_em'):
            data_evento = venda.data_entrega or venda.data_venda
            inicio = datetime.combine(data_evento, time(hour=9, minute=0))
            termino = inicio + timedelta(minutes=30)
            pendente = venda.data_pagamento is None
            status_raw = 'pendente' if pendente else 'pago'
            status_label = 'Pendente (produto)' if pendente else 'Pago (produto)'
            profissional_nome = ''
            if venda.agendamento_id and venda.agendamento and venda.agendamento.profissional:
                profissional_nome = venda.agendamento.profissional.nome

            eventos.append({
                'id': f'produto-{venda.id}',
                'title': f'Produto: {venda.produto.nome} - {venda.nome_cliente}',
                'start': inicio.isoformat(),
                'end': termino.isoformat(),
                'editable': False,
                'color': '#f59e0b' if pendente else '#0ea5e9',
                'extendedProps': {
                    'tipo_evento': 'produto',
                    'is_product_event': True,
                    'cliente': venda.nome_cliente,
                    'servico': f'Retirada/entrega de {venda.produto.nome}',
                    'profissional': profissional_nome,
                    'valor': str(venda.valor_venda),
                    'status': status_raw,
                    'status_label': status_label,
                    'telefone': venda.cliente.telefone if venda.cliente_id else '',
                    'observacoes': venda.observacoes or 'Sem observacoes.',
                }
            })

    return JsonResponse(eventos, safe=False)

@login_required
def mover_agendamento(request, pk):
    if request.method != 'POST':
        return JsonResponse({'status': 'erro', 'mensagem': 'Método não permitido.'}, status=405)

    if not user_can_access_module(request.user, PROFISSIONAL_ACCESS_AGENDAMENTOS):
        return JsonResponse({'status': 'erro', 'mensagem': 'Sem permissao para agenda.'}, status=403)

    empresa = get_active_empresa(request)

    if not empresa:
        return JsonResponse({'status': 'erro', 'mensagem': 'Empresa não selecionada.'}, status=400)

    agendamento = get_object_or_404(Agendamento, pk=pk, empresa=empresa)

    if is_profissional_user(request.user) and agendamento.profissional_id != request.user.profissional_profile.id:
        return JsonResponse({'status': 'erro', 'mensagem': 'Voce nao pode alterar agendamentos de outro profissional.'}, status=403)

    if agendamento.plano_id:
        return JsonResponse({
            'status': 'erro',
            'mensagem': 'Este atendimento faz parte de um plano mensal. Edite o pacote para alterar o horario.',
        }, status=400)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'erro', 'mensagem': 'JSON inválido.'}, status=400)

    try:
        data_evento = payload.get('data')

        if not data_evento:
            return JsonResponse({'status': 'erro', 'mensagem': 'Data inválida.'}, status=400)

        inicio = parse_datetime(data_evento)
        if inicio is None:
            try:
                inicio = datetime.fromisoformat(data_evento.replace('Z', '+00:00'))
            except ValueError:
                try:
                    inicio = datetime.strptime(data_evento[:16], '%Y-%m-%dT%H:%M')
                except ValueError:
                    return JsonResponse({'status': 'erro', 'mensagem': 'Data inválida.'}, status=400)

        if timezone.is_aware(inicio):
            inicio = timezone.localtime(inicio)

        inicio = inicio.replace(second=0, microsecond=0, tzinfo=None)
        agendamento.data = inicio.date()
        agendamento.hora = inicio.time()
        agendamento.save()
    except ValidationError as exc:
        return JsonResponse({'status': 'erro', 'mensagem': str(exc)}, status=400)

    return JsonResponse({'status': 'ok'})


VALID_STATUS_TRANSITIONS = {
    'pendente': ['confirmado', 'cancelado'],
    'confirmado': ['finalizado', 'cancelado'],
    'finalizado': [],
    'cancelado': [],
}


@login_required
def atualizar_status_agendamento(request, pk):
    if request.method != 'POST':
        return JsonResponse({'status': 'erro', 'mensagem': 'Método não permitido.'}, status=405)

    if not user_can_access_module(request.user, PROFISSIONAL_ACCESS_AGENDAMENTOS):
        return JsonResponse({'status': 'erro', 'mensagem': 'Sem permissao para agenda.'}, status=403)

    empresa = get_active_empresa(request)
    if not empresa:
        return JsonResponse({'status': 'erro', 'mensagem': 'Empresa não selecionada.'}, status=400)

    agendamento = get_object_or_404(Agendamento, pk=pk, empresa=empresa)

    if is_profissional_user(request.user) and agendamento.profissional_id != request.user.profissional_profile.id:
        return JsonResponse({'status': 'erro', 'mensagem': 'Sem permissão.'}, status=403)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'erro', 'mensagem': 'JSON inválido.'}, status=400)

    novo_status = payload.get('status', '').strip()
    allowed = VALID_STATUS_TRANSITIONS.get(agendamento.status, [])

    if novo_status not in allowed:
        return JsonResponse({
            'status': 'erro',
            'mensagem': f'Transição inválida de "{agendamento.status}" para "{novo_status}".',
        }, status=400)

    agendamento.status = novo_status
    agendamento.save(update_fields=['status'])

    return JsonResponse({
        'status': 'ok',
        'novo_status': novo_status,
        'novo_status_label': agendamento.get_status_display(),
    })
