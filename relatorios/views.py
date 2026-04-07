from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import Relatorio
from .services import RelatorioService
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from empresas.tenancy import get_active_empresa



@login_required
def relatorio_page(request):
    empresa = get_active_empresa(request)

    if not empresa:
        return redirect('cadastro_empresa')
    
    return render(request, 'relatorios/relatorio.html')

@login_required
def dashboard(request):
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
    }

    return JsonResponse(dados)


class ExecutarRelatorioView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        empresa = get_active_empresa(request)

        if not empresa:
            return Response({'detail': 'Empresa não selecionada.'}, status=400)

        relatorio = get_object_or_404(Relatorio, pk=pk, empresa=empresa)

        dados = RelatorioService.executar(relatorio)

        return Response(dados)
    
    
