from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from empresas.models import Empresa
from pessoa.models import Pessoa
from profissionais.models import Profissional
from produtos.models import Produto, VendaProduto
from servicos.models import Servico

from .models import AgendaLock, Agendamento, PlanoMensal


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
        self.assertEqual(plano.metodo_pagamento, "pix")
        self.assertGreater(plano.quantidade_encontros, 0)
        self.assertEqual(plano.agendamentos.count(), plano.quantidade_encontros)
        self.assertEqual(plano.agendamentos.filter(status="confirmado").count(), plano.quantidade_encontros)
        self.assertEqual(plano.agendamentos.filter(metodo_pagamento="pix").count(), plano.quantidade_encontros)
        self.assertEqual(plano.agendamentos.filter(pagamento_status="pago").count(), plano.quantidade_encontros)

    def test_salvar_agendamento_cria_lock_de_agenda(self):
        data_agendamento = timezone.localdate() + timedelta(days=5)

        agendamento = Agendamento.objects.create(
            empresa=self.empresa,
            cliente=self.cliente,
            servico=self.servico,
            profissional=self.profissional,
            data=data_agendamento,
            hora="10:00",
            status="pendente",
        )

        self.assertIsNotNone(agendamento.pk)
        self.assertTrue(
            AgendaLock.objects.filter(
                empresa=self.empresa,
                profissional=self.profissional,
                data=data_agendamento,
            ).exists()
        )


class CalendarioEventosProdutosTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="gestor-calendario@example.com",
            email="gestor-calendario@example.com",
            password="senha-forte-123",
        )
        self.empresa = Empresa.objects.create(
            usuario=self.user,
            nome="Studio Calendario",
            tipo="manicure",
            cnpj="00011122233344",
        )
        self.cliente = Pessoa.objects.create(
            empresa=self.empresa,
            nome="Cliente Agenda",
            email="cliente-agenda@example.com",
            telefone="65999990001",
            documento="00011122233",
        )
        self.profissional = Profissional.objects.create(
            empresa=self.empresa,
            nome="Alice",
            especialidade="Design",
            telefone="65999990002",
            email="alice@example.com",
            ativo=True,
        )
        self.servico = Servico.objects.create(
            empresa=self.empresa,
            nome="Design de unhas",
            categoria="maos",
            preco=90,
            tempo=60,
            ativo=True,
        )
        self.produto = Produto.objects.create(
            empresa=self.empresa,
            nome="Kit tratamento",
            categoria="cuidados",
            preco=49.90,
            estoque=20,
            ativo=True,
        )
        self.data_agendamento = timezone.localdate() + timedelta(days=3)
        self.data_entrega = timezone.localdate() + timedelta(days=4)

        self.agendamento = Agendamento.objects.create(
            empresa=self.empresa,
            cliente=self.cliente,
            servico=self.servico,
            profissional=self.profissional,
            data=self.data_agendamento,
            hora="10:00",
            status="pendente",
        )
        self.venda = VendaProduto.objects.create(
            empresa=self.empresa,
            produto=self.produto,
            cliente=self.cliente,
            valor_venda="99.80",
            data_venda=timezone.localdate(),
            data_entrega=self.data_entrega,
            agendamento=self.agendamento,
            observacoes="Venda pendente para retirada.",
        )

        self.client.force_login(self.user)

    def test_api_calendario_retorna_agendamentos_e_produtos_no_modo_geral(self):
        response = self.client.get(reverse("agendamentos_api"), {"tipo_evento": "geral"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        tipos = {item.get("extendedProps", {}).get("tipo_evento") for item in payload}

        self.assertIn("agendamento", tipos)
        self.assertIn("produto", tipos)

    def test_api_calendario_filtra_apenas_produtos(self):
        response = self.client.get(reverse("agendamentos_api"), {"tipo_evento": "produtos"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload)
        self.assertTrue(all(item.get("extendedProps", {}).get("tipo_evento") == "produto" for item in payload))

    def test_api_calendario_filtra_apenas_agendamentos(self):
        response = self.client.get(reverse("agendamentos_api"), {"tipo_evento": "agendamentos"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload)
        self.assertTrue(all(item.get("extendedProps", {}).get("tipo_evento") == "agendamento" for item in payload))
