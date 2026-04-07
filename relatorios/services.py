from agendamentos.models import Agendamento
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from agendamentos.models import PlanoMensal


class RelatorioService:

    @staticmethod
    def periodo_previsao(relatorio, dias_padrao=30):
        hoje = timezone.localdate()
        data_inicio = relatorio.data_inicio or hoje
        if data_inicio < hoje:
            data_inicio = hoje

        data_fim = relatorio.data_fim or (data_inicio + timedelta(days=dias_padrao - 1))
        if data_fim < data_inicio:
            data_fim = data_inicio

        return data_inicio, data_fim

    @staticmethod
    def aplicar_filtros(relatorio):
        qs = Agendamento.objects.filter(empresa=relatorio.empresa)

        if relatorio.data_inicio:
            qs = qs.filter(data__gte=relatorio.data_inicio)

        if relatorio.data_fim:
            qs = qs.filter(data__lte=relatorio.data_fim)

        if relatorio.profissional:
            qs = qs.filter(profissional=relatorio.profissional)

        if relatorio.servico:
            qs = qs.filter(servico=relatorio.servico)

        if relatorio.cliente:
            qs = qs.filter(cliente=relatorio.cliente)

        if relatorio.status:
            qs = qs.filter(status=relatorio.status)

        return qs


    # 💰 FATURAMENTO
    @staticmethod
    def faturamento(relatorio):
        qs = RelatorioService.aplicar_filtros(relatorio).filter(status='finalizado')

        total = sum(a.servico.preco for a in qs)

        return {
            "total": float(total),
            "quantidade": qs.count()
        }


    # 📅 AGENDAMENTOS POR DIA
    @staticmethod
    def agendamentos_por_dia(relatorio):
        qs = RelatorioService.aplicar_filtros(relatorio)

        dados = qs.values('data').annotate(total=Count('id')).order_by('data')

        return list(dados)


    # 👨‍💼 PROFISSIONAIS
    @staticmethod
    def por_profissional(relatorio):
        qs = RelatorioService.aplicar_filtros(relatorio).filter(status='finalizado')

        dados = qs.values('profissional__nome').annotate(
            total=Count('id'),
            faturamento=Sum('servico__preco')
        ).order_by('-faturamento')

        return list(dados)


    # 📦 SERVIÇOS
    @staticmethod
    def por_servico(relatorio):
        qs = RelatorioService.aplicar_filtros(relatorio).filter(status='finalizado')

        dados = qs.values('servico__nome').annotate(
            total=Count('id'),
            faturamento=Sum('servico__preco')
        ).order_by('-total')

        return list(dados)


    # ❌ CANCELAMENTOS
    @staticmethod
    def cancelamentos(relatorio):
        qs = RelatorioService.aplicar_filtros(relatorio)

        total = qs.count()
        cancelados = qs.filter(status='cancelado').count()

        taxa = (cancelados / total * 100) if total > 0 else 0

        return {
            "total": total,
            "cancelados": cancelados,
            "taxa_cancelamento": round(taxa, 2)
        }


    @staticmethod
    def previsao_agendamentos(relatorio):
        data_inicio, data_fim = RelatorioService.periodo_previsao(relatorio)
        qs = RelatorioService.aplicar_filtros(relatorio).filter(
            data__gte=data_inicio,
            data__lte=data_fim,
        ).exclude(status='cancelado')

        contagem = {
            item['data']: item['total']
            for item in qs.values('data').annotate(total=Count('id'))
        }

        dados = []
        cursor = data_inicio
        while cursor <= data_fim:
            dados.append({
                'data': cursor,
                'total': contagem.get(cursor, 0),
            })
            cursor += timedelta(days=1)

        return dados


    @staticmethod
    def previsao_receita(relatorio):
        data_inicio, data_fim = RelatorioService.periodo_previsao(relatorio)

        agendamentos_qs = RelatorioService.aplicar_filtros(relatorio).filter(
            data__gte=data_inicio,
            data__lte=data_fim,
        ).exclude(status='cancelado')

        por_dia = list(
            agendamentos_qs.values('data').annotate(valor=Sum('servico__preco')).order_by('data')
        )

        total_agendamentos_previstos = sum(float(item['valor'] or 0) for item in por_dia)

        planos_qs = PlanoMensal.objects.filter(
            empresa=relatorio.empresa,
            pagamento_status='pendente',
        ).exclude(status='cancelado')

        if relatorio.data_inicio:
            planos_qs = planos_qs.filter(mes_referencia__gte=relatorio.data_inicio)
        if relatorio.data_fim:
            planos_qs = planos_qs.filter(mes_referencia__lte=relatorio.data_fim)

        planos_pendentes = list(
            planos_qs.values('mes_referencia').annotate(
                total=Sum('valor_mensal'),
                quantidade=Count('id'),
            ).order_by('mes_referencia')
        )

        total_planos_pendentes = sum(float(item['total'] or 0) for item in planos_pendentes)

        return {
            'periodo_inicio': data_inicio,
            'periodo_fim': data_fim,
            'por_dia': por_dia,
            'planos_pendentes': planos_pendentes,
            'total_agendamentos_previstos': round(total_agendamentos_previstos, 2),
            'total_planos_pendentes': round(total_planos_pendentes, 2),
            'total_previsto': round(total_agendamentos_previstos + total_planos_pendentes, 2),
        }


    # 🔥 EXECUTOR PRINCIPAL
    @staticmethod
    def executar(relatorio):
        if relatorio.tipo == 'faturamento':
            return RelatorioService.faturamento(relatorio)

        elif relatorio.tipo == 'agendamentos':
            return RelatorioService.agendamentos_por_dia(relatorio)

        elif relatorio.tipo == 'profissionais':
            return RelatorioService.por_profissional(relatorio)

        elif relatorio.tipo == 'clientes':
            return RelatorioService.por_servico(relatorio)

        elif relatorio.tipo == 'cancelamentos':
            return RelatorioService.cancelamentos(relatorio)

        elif relatorio.tipo == 'previsao_agendamentos':
            return RelatorioService.previsao_agendamentos(relatorio)

        elif relatorio.tipo == 'previsao_receita':
            return RelatorioService.previsao_receita(relatorio)

        return {}