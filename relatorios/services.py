from agendamentos.models import Agendamento
from django.db.models import Sum, Count
from collections import defaultdict


class RelatorioService:

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

        return {}