from rest_framework import serializers
from .models import Relatorio


class RelatorioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Relatorio
        fields = [
            'id',
            'nome',
            'descricao',
            'tipo',
            'data_inicio',
            'data_fim',
            'profissional',
            'servico',
            'cliente',
            'status',
            'filtros',
            'agrupar_por',
            'criado_em',
            'atualizado_em',
            'ativo',
        ]
        read_only_fields = ['id', 'criado_em', 'atualizado_em']
