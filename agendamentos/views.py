from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from .models import Agendamento, Pagamento, PlanoMensal
from .forms import AgendamentoForm, PlanoMensalForm
from datetime import datetime, timedelta
import json
from empresas.business_profiles import get_business_profile
from empresas.tenancy import get_active_empresa
from empresas.permissions import is_profissional_user


@login_required
def agendamentos_list(request):
    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    agendamentos = Agendamento.objects.filter(empresa=empresa).select_related(
        'cliente',
        'servico',
        'profissional',
        'pagamento',
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
                agendamento = form.save(commit=False)
                agendamento.empresa = empresa
                agendamento.save()
                Pagamento.sync_for_agendamento(agendamento)
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
    empresa = get_active_empresa(request)

    if not empresa:
        return JsonResponse([], safe=False)
    profissional_id = request.GET.get('profissional')
    status = request.GET.get('status')
    start = request.GET.get('start')
    end = request.GET.get('end')

    eventos = []
    queryset = Agendamento.objects.filter(empresa=empresa).select_related(
        'cliente', 'servico', 'profissional'
    ).order_by('data', 'hora')

    if is_profissional_user(request.user):
        queryset = queryset.filter(profissional=request.user.profissional_profile)

    if profissional_id:
        queryset = queryset.filter(profissional_id=profissional_id)

    if status:
        queryset = queryset.filter(status=status)

    if start:
        start_value = parse_datetime(start)
        start_date = start_value.date() if start_value else parse_date(start[:10])
        if start_date:
            queryset = queryset.filter(data__gte=start_date)

    if end:
        end_value = parse_datetime(end)
        end_date = end_value.date() if end_value else parse_date(end[:10])
        if end_date:
            queryset = queryset.filter(data__lt=end_date)

    status_colors = {
        'pendente': '#f59e0b',
        'confirmado': '#22c55e',
        'finalizado': '#38bdf8',
        'cancelado': '#ef4444',
    }

    for ag in queryset:
        inicio = datetime.combine(ag.data, ag.hora)
        termino = inicio + timedelta(minutes=ag.servico.tempo or 0)
        eventos.append({
            'id': ag.id,
            'title': f'{ag.cliente.nome} - {ag.servico.nome}',
            'start': inicio.isoformat(),
            'end': termino.isoformat(),
            'color': status_colors.get(ag.status, ag.servico.cor or '#22c55e'),
            'extendedProps': {
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

    return JsonResponse(eventos, safe=False)

@login_required
def mover_agendamento(request, pk):
    if request.method != 'POST':
        return JsonResponse({'status': 'erro', 'mensagem': 'Método não permitido.'}, status=405)

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
