from django.contrib import admin
from .models import Agendamento, PlanoMensal, NotificacaoProfissional


@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'servico', 'data', 'hora', 'status', 'profissional']
    list_filter = ['empresa', 'status', 'data']
    search_fields = ['cliente__nome', 'servico__nome']


@admin.register(PlanoMensal)
class PlanoMensalAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'servico', 'mes_referencia', 'status', 'pagamento_status']
    list_filter = ['empresa', 'status', 'pagamento_status']
    search_fields = ['cliente__nome', 'servico__nome']


@admin.register(NotificacaoProfissional)
class NotificacaoProfissionalAdmin(admin.ModelAdmin):
    list_display = ['profissional', 'titulo', 'lida', 'criada_em']
    list_filter = ['lida', 'criada_em', 'profissional__empresa']
    search_fields = ['profissional__nome', 'titulo', 'mensagem']

