from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils.timezone import localdate
from pessoa.models import Pessoa
from profissionais.models import Profissional
from servicos.models import Servico
from agendamentos.models import Agendamento
from empresas.tenancy import get_active_empresa


@login_required
def dashboard_home(request):
    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')

    hoje = localdate()

    # 📊 TOTAIS
    total_clientes = Pessoa.objects.filter(empresa=empresa).count()
    total_profissionais = Profissional.objects.filter(empresa=empresa).count()
    total_servicos = Servico.objects.filter(empresa=empresa).count()
    total_agendamentos = Agendamento.objects.filter(empresa=empresa).count()
    profissionais = Profissional.objects.filter(empresa=empresa, ativo=True).order_by('nome')

    # 📅 AGENDAMENTOS DE HOJE
    agendamentos_hoje = Agendamento.objects.filter(
        empresa=empresa,
        data=hoje
    ).select_related('cliente', 'servico', 'profissional').order_by('hora')
    total_agendamentos_hoje = agendamentos_hoje.count()
    confirmados_hoje = agendamentos_hoje.filter(status='confirmado').count()
    pendentes_hoje = agendamentos_hoje.filter(status='pendente').count()

    # 💰 FATURAMENTO DO MÊS
    agendamentos_mes = Agendamento.objects.filter(
        empresa=empresa,
        data__month=hoje.month,
        data__year=hoje.year
    )

    faturamento_mes = agendamentos_mes.filter(
        status='finalizado'
    ).aggregate(total=Sum('servico__preco'))['total'] or 0

    total_atendimentos_mes = agendamentos_mes.count()

    context = {
        "hoje": hoje,
        "total_clientes": total_clientes,
        "total_profissionais": total_profissionais,
        "total_servicos": total_servicos,
        "total_agendamentos": total_agendamentos,
        "profissionais": profissionais,
        "status_choices": Agendamento.STATUS_CHOICES,
        "faturamento_mes": faturamento_mes,
        "total_atendimentos_mes": total_atendimentos_mes,
        "total_agendamentos_hoje": total_agendamentos_hoje,
        "confirmados_hoje": confirmados_hoje,
        "pendentes_hoje": pendentes_hoje,
        "agendamentos_hoje": agendamentos_hoje,
    }

    return render(request, 'dashboard/agenda_dashboard.html', context)
