from django.contrib import admin

from .models import (
	AuditLog,
	ClienteFidelidade,
	FidelidadeMovimento,
	NPSResposta,
	ProgramaFidelidade,
	StripeWebhookEvent,
)


@admin.register(StripeWebhookEvent)
class StripeWebhookEventAdmin(admin.ModelAdmin):
	list_display = ("event_id", "event_type", "processing_status", "livemode", "criado_em")
	list_filter = ("processing_status", "event_type", "livemode")
	search_fields = ("event_id", "event_type")


@admin.register(ProgramaFidelidade)
class ProgramaFidelidadeAdmin(admin.ModelAdmin):
	list_display = ("empresa", "ativo", "pontos_por_real", "multiplicador_indicacao", "pontos_bonus_indicacao")
	list_filter = ("ativo",)
	search_fields = ("empresa__nome",)


@admin.register(ClienteFidelidade)
class ClienteFidelidadeAdmin(admin.ModelAdmin):
	list_display = ("empresa", "cliente", "pontos_disponiveis", "pontos_totais", "codigo_indicacao", "indicador")
	list_filter = ("empresa",)
	search_fields = ("empresa__nome", "cliente__nome", "codigo_indicacao", "indicador__nome")


@admin.register(FidelidadeMovimento)
class FidelidadeMovimentoAdmin(admin.ModelAdmin):
	list_display = ("empresa", "cliente_fidelidade", "origem", "pontos", "descricao", "criado_em")
	list_filter = ("empresa", "origem")
	search_fields = ("cliente_fidelidade__cliente__nome", "descricao", "referencia_id")


@admin.register(NPSResposta)
class NPSRespostaAdmin(admin.ModelAdmin):
	list_display = ("empresa", "cliente", "agendamento", "nota", "criado_em")
	list_filter = ("empresa", "nota")
	search_fields = ("empresa__nome", "cliente__nome", "comentario")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
	list_display = ("empresa", "acao", "entidade", "entidade_id", "ator_usuario", "ator_cliente", "endereco_ip", "criado_em")
	list_filter = ("empresa", "acao", "entidade")
	search_fields = ("empresa__nome", "acao", "entidade", "entidade_id", "ator_usuario__username", "ator_cliente__nome")
