from agendamentos.models import Agendamento
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
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


    # 🛒 VENDAS — KPIs gerais
    @staticmethod
    def vendas_kpis(empresa, data_inicio=None, data_fim=None):
        from produtos.models import VendaProduto
        hoje = timezone.localdate()
        qs = VendaProduto.objects.filter(empresa=empresa)
        if data_inicio:
            qs = qs.filter(data_venda__gte=data_inicio)
        if data_fim:
            qs = qs.filter(data_venda__lte=data_fim)

        agg_total = qs.aggregate(total=Sum("valor_venda"), qtd=Count("id"))
        agg_recebidas = qs.filter(data_pagamento__isnull=False).aggregate(total=Sum("valor_venda"), qtd=Count("id"))
        agg_pendentes = qs.filter(data_pagamento__isnull=True).aggregate(total=Sum("valor_venda"), qtd=Count("id"))
        agg_atrasadas = qs.filter(data_pagamento__isnull=True, data_venda__lt=hoje).aggregate(total=Sum("valor_venda"), qtd=Count("id"))

        return {
            "total": round(float(agg_total["total"] or 0), 2),
            "quantidade": agg_total["qtd"] or 0,
            "recebidas_total": round(float(agg_recebidas["total"] or 0), 2),
            "recebidas_qtd": agg_recebidas["qtd"] or 0,
            "pendentes_total": round(float(agg_pendentes["total"] or 0), 2),
            "pendentes_qtd": agg_pendentes["qtd"] or 0,
            "atrasadas_total": round(float(agg_atrasadas["total"] or 0), 2),
            "atrasadas_qtd": agg_atrasadas["qtd"] or 0,
        }

    # 🏆 VENDAS — Produtos mais vendidos
    @staticmethod
    def produtos_mais_vendidos(empresa, data_inicio=None, data_fim=None, limit=8):
        from produtos.models import VendaProduto
        qs = VendaProduto.objects.filter(empresa=empresa)
        if data_inicio:
            qs = qs.filter(data_venda__gte=data_inicio)
        if data_fim:
            qs = qs.filter(data_venda__lte=data_fim)
        dados = list(
            qs.values("produto__nome")
            .annotate(total=Count("id"), valor=Sum("valor_venda"))
            .order_by("-total")[:limit]
        )
        return [{"nome": d["produto__nome"] or "—", "total": d["total"], "valor": round(float(d["valor"] or 0), 2)} for d in dados]

    # 👥 VENDAS — Clientes que mais compram
    @staticmethod
    def clientes_top_compradores(empresa, data_inicio=None, data_fim=None, limit=8):
        from produtos.models import VendaProduto
        qs = VendaProduto.objects.filter(empresa=empresa)
        if data_inicio:
            qs = qs.filter(data_venda__gte=data_inicio)
        if data_fim:
            qs = qs.filter(data_venda__lte=data_fim)
        dados = list(
            qs.values("cliente__nome", "cliente_nome_avulso")
            .annotate(total=Count("id"), valor=Sum("valor_venda"))
            .order_by("-total")[:limit]
        )
        result = []
        for d in dados:
            nome = d.get("cliente__nome") or d.get("cliente_nome_avulso") or "Cliente avulso"
            result.append({"nome": nome, "total": d["total"], "valor": round(float(d["valor"] or 0), 2)})
        return result

    # 📅 VENDAS — Previsão de recebimentos futuros
    @staticmethod
    def previsao_recebimentos_vendas(empresa, data_inicio=None, data_fim=None):
        from produtos.models import VendaProduto
        qs = VendaProduto.objects.filter(empresa=empresa, data_pagamento__isnull=True)
        if data_inicio:
            qs = qs.filter(data_venda__gte=data_inicio)
        if data_fim:
            qs = qs.filter(data_venda__lte=data_fim)
        agg = qs.aggregate(total=Sum("valor_venda"), qtd=Count("id"))
        por_mes = list(
            qs.annotate(mes=TruncMonth("data_venda"))
            .values("mes")
            .annotate(total=Sum("valor_venda"), qtd=Count("id"))
            .order_by("mes")[:12]
        )
        return {
            "total_pendente": round(float(agg["total"] or 0), 2),
            "qtd_pendente": agg["qtd"] or 0,
            "por_mes": [{"mes": str(d["mes"])[:7] if d["mes"] else None, "total": round(float(d["total"] or 0), 2), "qtd": d["qtd"]} for d in por_mes],
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