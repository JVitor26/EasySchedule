from django.contrib import admin
from .models import Empresa


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
	list_display = ("nome", "tipo", "plano", "limite_profissionais", "valor_mensal", "data_cadastro")
	list_filter = ("plano", "tipo")
	search_fields = ("nome", "cnpj", "usuario__username")
