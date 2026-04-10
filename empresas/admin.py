from django.contrib import admin
from .models import Empresa


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
	list_display = (
		"nome",
		"tipo",
		"plano",
		"limite_profissionais",
		"cor_primaria",
		"cor_secundaria",
		"valor_mensal",
		"data_cadastro",
	)
	list_filter = ("plano", "tipo")
	search_fields = ("nome", "cnpj", "usuario__username")
