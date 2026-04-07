from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from empresas.models import Empresa
from pessoa.models import Pessoa
from profissionais.models import Profissional
from servicos.models import Servico

from .models import PlanoMensal


class PlanoMensalFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="gestor-planos@example.com",
            email="gestor-planos@example.com",
            password="senha-forte-123",
        )
        self.empresa = Empresa.objects.create(
            usuario=self.user,
            nome="Studio Premium",
            tipo="manicure",
            cnpj="12312312312312",
        )
        self.cliente = Pessoa.objects.create(
            empresa=self.empresa,
            nome="Cliente Mensal",
            email="cliente-mensal@example.com",
            telefone="65999990000",
            documento="12345678900",
            data_nascimento=timezone.localdate() - timedelta(days=9000),
        )
        self.profissional = Profissional.objects.create(
            empresa=self.empresa,
            nome="Bruna",
            especialidade="Alongamento",
            telefone="65999995555",
            email="bruna@example.com",
            ativo=True,
        )
        self.servico = Servico.objects.create(
            empresa=self.empresa,
            nome="Manutencao premium",
            categoria="maos",
            preco=120,
            tempo=60,
            ativo=True,
        )

    def _next_month_reference(self):
        candidate = timezone.localdate().replace(day=28) + timedelta(days=4)
        return candidate.replace(day=1)

    def test_area_interna_cria_plano_mensal_e_quita_mes_inteiro(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("planos_form"),
            {
                "cliente": self.cliente.pk,
                "servico": self.servico.pk,
                "profissional": self.profissional.pk,
                "mes_referencia": self._next_month_reference().isoformat(),
                "dia_semana": "1",
                "hora": "10:00",
                "observacoes": "Plano fixo das tercas.",
                "registrar_pagamento_agora": "on",
                "metodo_pagamento_inicial": "pix",
            },
        )

        self.assertRedirects(response, reverse("planos_list"))

        plano = PlanoMensal.objects.get(empresa=self.empresa, cliente=self.cliente)
        self.assertEqual(plano.pagamento_status, "pago")
        self.assertGreater(plano.quantidade_encontros, 0)
        self.assertEqual(plano.agendamentos.count(), plano.quantidade_encontros)
        self.assertEqual(plano.agendamentos.filter(status="confirmado").count(), plano.quantidade_encontros)
        self.assertEqual(plano.agendamentos.filter(forma_pagamento="pix").count(), plano.quantidade_encontros)
