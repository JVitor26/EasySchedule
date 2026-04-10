import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
import stripe

from agendamentos.models import Agendamento, PlanoMensal, SlotHold
from empresas.models import Empresa
from core.models import PasswordRecoveryCode, StripeWebhookEvent
from pessoa.models import Pessoa
from profissionais.models import Profissional
from produtos.models import Produto
from servicos.models import Servico


class HomepageRoutingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="empresa-home@example.com",
            email="empresa-home@example.com",
            password="senha-forte-123",
        )
        self.empresa = Empresa.objects.create(
            usuario=self.owner,
            nome="Barbearia Teste",
            tipo="barbearia",
            cnpj="12345678000100",
        )

    def test_root_home_renders_landing_page(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home.html")
        self.assertContains(response, "Bem-vindo ao EasySchedule")
        self.assertNotContains(response, "Nenhuma empresa publicada ainda.")

    def test_cliente_home_exige_link_da_empresa(self):
        response = self.client.get(reverse("cliente_home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/cliente_publico.html")
        self.assertContains(response, "Use o link da empresa")
        self.assertNotContains(response, self.empresa.nome)

    def test_login_redirect_goes_to_dashboard_for_company_owner(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": self.owner.username,
                "password": "senha-forte-123",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse("dashboard_home"), fetch_redirect_response=False)
        self.assertContains(response, "Agenda")


class PublicCustomerBookingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="empresa-publica@example.com",
            email="empresa-publica@example.com",
            password="senha-forte-123",
        )
        self.empresa = Empresa.objects.create(
            usuario=self.owner,
            nome="Barbearia Teste",
            tipo="barbearia",
            cnpj="12345678000100",
        )
        self.profissional = Profissional.objects.create(
            empresa=self.empresa,
            nome="Rafael",
            especialidade="Fade",
            telefone="65999999999",
            email="rafael@example.com",
            ativo=True,
        )
        self.servico = Servico.objects.create(
            empresa=self.empresa,
            nome="Corte completo",
            categoria="corte",
            descricao="Corte com finalizacao",
            preco=70,
            tempo=60,
            ativo=True,
        )
        self.produto = Produto.objects.create(
            empresa=self.empresa,
            nome="Pomada Premium",
            categoria="Finalizacao",
            descricao="Fixacao forte",
            preco="39.90",
            estoque=12,
            ativo=True,
            destaque_publico=True,
        )
        self.data_agendamento = timezone.localdate() + timedelta(days=3)

        cliente_existente = Pessoa.objects.create(
            empresa=self.empresa,
            nome="Cliente Existente",
            email="existente@example.com",
            telefone="65988887777",
            documento="12345678901",
            data_nascimento=timezone.localdate() - timedelta(days=9000),
        )
        Agendamento.objects.create(
            empresa=self.empresa,
            cliente=cliente_existente,
            servico=self.servico,
            profissional=self.profissional,
            data=self.data_agendamento,
            hora="09:00",
            status="confirmado",
        )

    def _next_month_reference(self):
        candidate = timezone.localdate().replace(day=28) + timedelta(days=4)
        return candidate.replace(day=1)

    def test_api_publica_retorna_apenas_horarios_disponiveis(self):
        response = self.client.get(
            reverse("cliente_horarios", args=[self.empresa.pk]),
            {
                "servico": self.servico.pk,
                "profissional": self.profissional.pk,
                "data": self.data_agendamento.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        values = [item["value"] for item in payload["slots"]]

        self.assertNotIn("09:00", values)
        self.assertNotIn("09:30", values)
        self.assertIn("10:00", values)

    def test_cliente_publico_consegue_cadastrar_e_agendar(self):
        response = self.client.post(
            reverse("cliente_empresa", args=[self.empresa.pk]),
            {
                "nome": "Joao Cliente",
                "email": "joao@example.com",
                "telefone": "(65) 99999-1111",
                "documento": "98765432100",
                "data_nascimento": "1995-05-10",
                "servico": self.servico.pk,
                "profissional": self.profissional.pk,
                "data": self.data_agendamento.isoformat(),
                "hora": "10:00",
                "observacoes": "Prefere corte baixo.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Horario solicitado com sucesso")
        self.assertTrue(Pessoa.objects.filter(empresa=self.empresa, email="joao@example.com").exists())
        self.assertTrue(
            Agendamento.objects.filter(
                empresa=self.empresa,
                data=self.data_agendamento,
                hora="10:00",
            ).exists()
        )
        agendamento = Agendamento.objects.get(
            empresa=self.empresa,
            data=self.data_agendamento,
            hora="10:00",
        )
        self.assertEqual(agendamento.pagamento_status, "pendente")
        self.assertEqual(agendamento.metodo_pagamento, "")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_cliente_publico_recebe_confirmacao_por_email_para_cliente_e_profissional(self):
        response = self.client.post(
            reverse("cliente_empresa", args=[self.empresa.pk]),
            {
                "nome": "Joao Cliente",
                "email": "joao@example.com",
                "telefone": "(65) 99999-1111",
                "documento": "98765432100",
                "data_nascimento": "1995-05-10",
                "servico": self.servico.pk,
                "profissional": self.profissional.pk,
                "data": self.data_agendamento.isoformat(),
                "hora": "10:00",
                "observacoes": "Prefere corte baixo.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)

        emails_por_destinatario = {
            email.to[0]: email
            for email in mail.outbox
            if email.to
        }
        self.assertIn("joao@example.com", emails_por_destinatario)
        self.assertIn("rafael@example.com", emails_por_destinatario)

        email_cliente = emails_por_destinatario["joao@example.com"]
        self.assertEqual(email_cliente.subject, f"Confirmacao do seu agendamento - {self.empresa.nome}")
        self.assertIn("Experiencia confirmada para voce.", email_cliente.body)
        self.assertTrue(email_cliente.alternatives)
        cliente_alternativa = email_cliente.alternatives[0]
        cliente_html = getattr(cliente_alternativa, "content", cliente_alternativa[0])
        cliente_mime = getattr(cliente_alternativa, "mimetype", cliente_alternativa[1])
        self.assertEqual(cliente_mime, "text/html")
        self.assertIn("Agendamento confirmado", cliente_html)
        self.assertIn(">BT</span>", cliente_html)
        self.assertIn("Barbearia", cliente_html)
        self.assertIn("#0b3a61", cliente_html)

        email_profissional = emails_por_destinatario["rafael@example.com"]
        self.assertEqual(email_profissional.subject, f"Novo agendamento recebido - {self.empresa.nome}")
        self.assertIn("Voce recebeu um novo agendamento.", email_profissional.body)
        self.assertIn("Cliente: Joao Cliente", email_profissional.body)
        self.assertTrue(email_profissional.alternatives)
        profissional_alternativa = email_profissional.alternatives[0]
        profissional_html = getattr(profissional_alternativa, "content", profissional_alternativa[0])
        profissional_mime = getattr(profissional_alternativa, "mimetype", profissional_alternativa[1])
        self.assertEqual(profissional_mime, "text/html")
        self.assertIn("Novo agendamento recebido", profissional_html)
        self.assertIn(">BT</span>", profissional_html)
        self.assertIn("Barbearia", profissional_html)
        self.assertIn("#0b3a61", profissional_html)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_cliente_publico_recebe_confirmacao_por_email_no_pacote_mensal(self):
        month_reference = self._next_month_reference()

        response = self.client.post(
            reverse("cliente_empresa", args=[self.empresa.pk]),
            {
                "nome": "Cliente Pacote",
                "email": "pacote@example.com",
                "telefone": "(65) 99999-5555",
                "documento": "99988877766",
                "data_nascimento": "1994-01-09",
                "tipo_reserva": "pacote_mensal",
                "servico": self.servico.pk,
                "profissional": self.profissional.pk,
                "mes_referencia": month_reference.isoformat(),
                "dia_semana": "0",
                "hora": "10:00",
                "observacoes": "Pacote das segundas.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)

        emails_por_destinatario = {
            email.to[0]: email
            for email in mail.outbox
            if email.to
        }
        self.assertIn("pacote@example.com", emails_por_destinatario)
        self.assertIn("rafael@example.com", emails_por_destinatario)

        email_cliente = emails_por_destinatario["pacote@example.com"]
        self.assertEqual(email_cliente.subject, f"Confirmacao do seu agendamento - {self.empresa.nome}")
        self.assertIn("Experiencia confirmada para voce.", email_cliente.body)
        self.assertTrue(email_cliente.alternatives)
        cliente_alternativa = email_cliente.alternatives[0]
        cliente_html = getattr(cliente_alternativa, "content", cliente_alternativa[0])
        cliente_mime = getattr(cliente_alternativa, "mimetype", cliente_alternativa[1])
        self.assertEqual(cliente_mime, "text/html")
        self.assertIn("Agendamento confirmado", cliente_html)
        self.assertIn(">BT</span>", cliente_html)
        self.assertIn("Barbearia", cliente_html)
        self.assertIn("#0b3a61", cliente_html)

        email_profissional = emails_por_destinatario["rafael@example.com"]
        self.assertEqual(email_profissional.subject, f"Novo agendamento recebido - {self.empresa.nome}")
        self.assertIn("Voce recebeu um novo agendamento.", email_profissional.body)
        self.assertIn("Cliente: Cliente Pacote", email_profissional.body)
        self.assertTrue(email_profissional.alternatives)
        profissional_alternativa = email_profissional.alternatives[0]
        profissional_html = getattr(profissional_alternativa, "content", profissional_alternativa[0])
        profissional_mime = getattr(profissional_alternativa, "mimetype", profissional_alternativa[1])
        self.assertEqual(profissional_mime, "text/html")
        self.assertIn("Novo agendamento recebido", profissional_html)
        self.assertIn(">BT</span>", profissional_html)
        self.assertIn("Barbearia", profissional_html)
        self.assertIn("#0b3a61", profissional_html)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_cliente_publico_email_html_usa_branding_personalizado_da_empresa(self):
        self.empresa.logo_url = "https://cdn.example.com/logo.png"
        self.empresa.cor_primaria = "#123abc"
        self.empresa.cor_secundaria = "#ff6600"
        self.empresa.save(update_fields=["logo_url", "cor_primaria", "cor_secundaria"])

        response = self.client.post(
            reverse("cliente_empresa", args=[self.empresa.pk]),
            {
                "nome": "Joao Cliente",
                "email": "joao@example.com",
                "telefone": "(65) 99999-1111",
                "documento": "98765432100",
                "data_nascimento": "1995-05-10",
                "servico": self.servico.pk,
                "profissional": self.profissional.pk,
                "data": self.data_agendamento.isoformat(),
                "hora": "10:00",
                "observacoes": "Prefere corte baixo.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)

        for email in mail.outbox:
            self.assertTrue(email.alternatives)
            alternativa = email.alternatives[0]
            html = getattr(alternativa, "content", alternativa[0])

            self.assertIn("https://cdn.example.com/logo.png", html)
            self.assertIn("#123abc", html)
            self.assertIn("#ff6600", html)
            self.assertNotIn(">BT</span>", html)

    def test_cliente_publico_recebe_confirmacao_por_whatsapp_com_mensagem_personalizada(self):
        self.empresa.logo_url = "https://cdn.example.com/logo.png"
        self.empresa.save(update_fields=["logo_url"])

        with patch("core.notifications._send_whatsapp") as whatsapp_mock, patch("core.notifications._send_email"):
            response = self.client.post(
                reverse("cliente_empresa", args=[self.empresa.pk]),
                {
                    "nome": "Joao Cliente",
                    "email": "joao@example.com",
                    "telefone": "(65) 99999-1111",
                    "documento": "98765432100",
                    "data_nascimento": "1995-05-10",
                    "servico": self.servico.pk,
                    "profissional": self.profissional.pk,
                    "data": self.data_agendamento.isoformat(),
                    "hora": "10:00",
                    "observacoes": "Prefere corte baixo.",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(whatsapp_mock.call_count, 2)

        mensagens_por_telefone = {
            call.args[0]: call.args[1]
            for call in whatsapp_mock.call_args_list
            if len(call.args) >= 2
        }

        self.assertIn("65999991111", mensagens_por_telefone)
        self.assertIn("65999999999", mensagens_por_telefone)

        mensagem_cliente = mensagens_por_telefone["65999991111"]
        self.assertIn("Barbearia Teste | Confirmacao de agendamento", mensagem_cliente)
        self.assertIn("Segmento: Barbearia", mensagem_cliente)
        self.assertIn("Status: Pendente", mensagem_cliente)
        self.assertIn("Logo: https://cdn.example.com/logo.png", mensagem_cliente)

        mensagem_profissional = mensagens_por_telefone["65999999999"]
        self.assertIn("Barbearia Teste | Novo agendamento recebido", mensagem_profissional)
        self.assertIn("Cliente: Joao Cliente", mensagem_profissional)
        self.assertIn("Status: Pendente", mensagem_profissional)
        self.assertIn("Logo: https://cdn.example.com/logo.png", mensagem_profissional)

    def test_api_hold_reserva_horario_temporariamente(self):
        response = self.client.post(
            reverse("cliente_slot_hold_api", args=[self.empresa.pk]),
            data=json.dumps({
                "servico": self.servico.pk,
                "profissional": self.profissional.pk,
                "data": self.data_agendamento.isoformat(),
                "hora": "10:00",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "sucesso")
        self.assertTrue(SlotHold.objects.filter(token=payload["hold_token"], status="active").exists())

    def test_hold_bloqueia_horario_para_outra_sessao(self):
        hold_response = self.client.post(
            reverse("cliente_slot_hold_api", args=[self.empresa.pk]),
            data=json.dumps({
                "servico": self.servico.pk,
                "profissional": self.profissional.pk,
                "data": self.data_agendamento.isoformat(),
                "hora": "10:00",
            }),
            content_type="application/json",
        )
        self.assertEqual(hold_response.status_code, 200)

        other_client = Client()
        slots_response = other_client.get(
            reverse("cliente_horarios", args=[self.empresa.pk]),
            {
                "servico": self.servico.pk,
                "profissional": self.profissional.pk,
                "data": self.data_agendamento.isoformat(),
            },
        )
        self.assertEqual(slots_response.status_code, 200)

        values = [item["value"] for item in slots_response.json()["slots"]]
        self.assertNotIn("10:00", values)

    def test_cliente_publico_consome_hold_ao_agendar(self):
        hold_response = self.client.post(
            reverse("cliente_slot_hold_api", args=[self.empresa.pk]),
            data=json.dumps({
                "servico": self.servico.pk,
                "profissional": self.profissional.pk,
                "data": self.data_agendamento.isoformat(),
                "hora": "10:00",
            }),
            content_type="application/json",
        )
        self.assertEqual(hold_response.status_code, 200)
        hold_token = hold_response.json()["hold_token"]

        response = self.client.post(
            reverse("cliente_empresa", args=[self.empresa.pk]),
            {
                "nome": "Cliente Hold",
                "email": "hold@example.com",
                "telefone": "(65) 99999-9998",
                "documento": "12312312399",
                "data_nascimento": "1990-10-10",
                "servico": self.servico.pk,
                "profissional": self.profissional.pk,
                "data": self.data_agendamento.isoformat(),
                "hora": "10:00",
                "slot_hold_token": hold_token,
                "observacoes": "Reserva com hold.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Horario solicitado com sucesso")

        hold = SlotHold.objects.get(token=hold_token)
        self.assertEqual(hold.status, "consumed")

    def test_cliente_publico_recebe_erro_quando_horario_esta_ocupado(self):
        response = self.client.post(
            reverse("cliente_empresa", args=[self.empresa.pk]),
            {
                "nome": "Joao Cliente",
                "email": "joao2@example.com",
                "telefone": "(65) 99999-2222",
                "documento": "11122233344",
                "data_nascimento": "1998-08-10",
                "servico": self.servico.pk,
                "profissional": self.profissional.pk,
                "data": self.data_agendamento.isoformat(),
                "hora": "09:00",
                "observacoes": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Esse horario acabou de ser ocupado")
        self.assertFalse(
            Agendamento.objects.filter(
                empresa=self.empresa,
                data=self.data_agendamento,
                hora="09:00",
                cliente__email="joao2@example.com",
            ).exists()
        )

    def test_cliente_publico_consegue_agendar_sem_email_documento_e_data_nascimento(self):
        response = self.client.post(
            reverse("cliente_empresa", args=[self.empresa.pk]),
            {
                "nome": "Cliente Basico",
                "email": "",
                "telefone": "(65) 99999-7777",
                "documento": "",
                "data_nascimento": "",
                "servico": self.servico.pk,
                "profissional": self.profissional.pk,
                "data": self.data_agendamento.isoformat(),
                "hora": "10:00",
                "observacoes": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Horario solicitado com sucesso")

        cliente = Pessoa.objects.get(empresa=self.empresa, telefone="65999997777")
        self.assertEqual(cliente.email, "")
        self.assertEqual(cliente.documento, "")
        self.assertIsNone(cliente.data_nascimento)

    def test_cliente_publico_cria_agendamento_com_pagamento_pendente(self):
        response = self.client.post(
            reverse("cliente_empresa", args=[self.empresa.pk]),
            {
                "nome": "Ana Cliente",
                "email": "ana@example.com",
                "telefone": "(65) 99999-3333",
                "documento": "55566677788",
                "data_nascimento": "1996-03-12",
                "servico": self.servico.pk,
                "profissional": self.profissional.pk,
                "data": self.data_agendamento.isoformat(),
                "hora": "10:00",
                "observacoes": "Pagamento via aplicativo.",
            },
        )

        self.assertEqual(response.status_code, 200)
        agendamento = Agendamento.objects.get(
            empresa=self.empresa,
            cliente__email="ana@example.com",
            data=self.data_agendamento,
            hora="10:00",
        )
        agendamento.refresh_from_db()

        self.assertEqual(agendamento.status, "pendente")
        self.assertEqual(agendamento.pagamento_status, "pendente")
        self.assertEqual(agendamento.metodo_pagamento, "")

    def test_api_publica_retorna_horarios_fixos_para_pacote_mensal(self):
        response = self.client.get(
            reverse("cliente_horarios", args=[self.empresa.pk]),
            {
                "tipo_reserva": "pacote_mensal",
                "servico": self.servico.pk,
                "profissional": self.profissional.pk,
                "mes_referencia": self._next_month_reference().isoformat(),
                "dia_semana": 0,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        values = [item["value"] for item in payload["slots"]]

        self.assertIn("10:00", values)
        self.assertIn("14:00", values)

    def test_cliente_publico_consegue_criar_pacote_mensal(self):
        month_reference = self._next_month_reference()

        response = self.client.post(
            reverse("cliente_empresa", args=[self.empresa.pk]),
            {
                "nome": "Cliente Pacote",
                "email": "pacote@example.com",
                "telefone": "(65) 99999-5555",
                "documento": "99988877766",
                "data_nascimento": "1994-01-09",
                "tipo_reserva": "pacote_mensal",
                "servico": self.servico.pk,
                "profissional": self.profissional.pk,
                "mes_referencia": month_reference.isoformat(),
                "dia_semana": "0",
                "hora": "10:00",
                "observacoes": "Pacote das segundas.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pacote mensal solicitado com sucesso")

        plano = PlanoMensal.objects.get(
            empresa=self.empresa,
            cliente__email="pacote@example.com",
            mes_referencia=month_reference,
        )
        self.assertGreater(plano.quantidade_encontros, 0)
        self.assertEqual(plano.agendamentos.count(), plano.quantidade_encontros)
        self.assertTrue(plano.agendamentos.filter(status="pendente").exists())
        self.assertEqual(plano.pagamento_status, "pendente")

    def test_cliente_publico_adiciona_e_lista_produtos_no_carrinho_da_empresa(self):
        add_response = self.client.post(
            reverse("api_carrinho_adicionar", args=[self.empresa.pk]),
            data=json.dumps({"produto_id": self.produto.pk, "quantidade": 2}),
            content_type="application/json",
        )

        self.assertEqual(add_response.status_code, 200)
        self.assertEqual(add_response.json()["status"], "sucesso")
        self.assertEqual(add_response.json()["total_itens"], 2)

        list_response = self.client.get(reverse("api_carrinho_listar", args=[self.empresa.pk]))

        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        self.assertEqual(payload["status"], "sucesso")
        self.assertEqual(payload["total_itens"], 2)
        self.assertEqual(len(payload["itens"]), 1)
        self.assertEqual(payload["itens"][0]["produto_id"], self.produto.pk)

    def test_catalogo_da_empresa_exibe_servicos_e_profissionais(self):
        response = self.client.get(reverse("cliente_catalogo", args=[self.empresa.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.servico.nome)
        self.assertContains(response, self.profissional.nome)

    def test_loja_da_empresa_exibe_produtos_ativos(self):
        response = self.client.get(reverse("loja_produtos", args=[self.empresa.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.produto.nome)


class PasswordRecoveryTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="empresa-segura@example.com",
            email="empresa-segura@example.com",
            password="senha-antiga-123",
        )
        self.empresa = Empresa.objects.create(
            usuario=self.owner,
            nome="Studio Seguranca",
            tipo="barbearia",
            cnpj="12312312312",
            whatsapp="65999990000",
        )
        self.profissional_user = User.objects.create_user(
            username="profissional@example.com",
            email="profissional@example.com",
            password="senha-antiga-123",
        )
        self.profissional = Profissional.objects.create(
            empresa=self.empresa,
            usuario=self.profissional_user,
            nome="Profissional Login",
            especialidade="Corte",
            telefone="65999991111",
            email="profissional@example.com",
            ativo=True,
        )
        self.cliente = Pessoa.objects.create(
            empresa=self.empresa,
            nome="Cliente Portal",
            email="cliente.portal@example.com",
            telefone="65999992222",
            documento="12345678900",
        )
        self.cliente.set_portal_password("senha-portal-antiga")
        self.cliente.save(update_fields=["portal_password", "portal_password_updated_at"])

    def test_recuperacao_de_senha_interna_por_email(self):
        response = self.client.post(
            reverse("password_recovery_request"),
            {
                "account_type": "internal",
                "identifier": "empresa-segura@example.com",
                "channel": "email",
            },
        )

        self.assertRedirects(response, reverse("password_recovery_confirm"))
        recovery = PasswordRecoveryCode.objects.get(account_type="internal", user=self.owner)

        confirm_response = self.client.post(
            reverse("password_recovery_confirm"),
            {
                "code": recovery.codigo,
                "new_password1": "nova-senha-456",
                "new_password2": "nova-senha-456",
            },
        )

        self.assertRedirects(confirm_response, reverse("login"))
        self.owner.refresh_from_db()
        recovery.refresh_from_db()

        self.assertTrue(self.owner.check_password("nova-senha-456"))
        self.assertIsNotNone(recovery.usado_em)

    def test_recuperacao_de_senha_interna_por_whatsapp_para_profissional(self):
        response = self.client.post(
            reverse("password_recovery_request"),
            {
                "account_type": "internal",
                "identifier": "(65) 99999-1111",
                "channel": "whatsapp",
            },
        )

        self.assertRedirects(response, reverse("password_recovery_confirm"))
        recovery = PasswordRecoveryCode.objects.get(account_type="internal", user=self.profissional_user)

        confirm_response = self.client.post(
            reverse("password_recovery_confirm"),
            {
                "code": recovery.codigo,
                "new_password1": "senha-prof-789",
                "new_password2": "senha-prof-789",
            },
        )

        self.assertRedirects(confirm_response, reverse("login"))
        self.profissional_user.refresh_from_db()
        self.assertTrue(self.profissional_user.check_password("senha-prof-789"))

    def test_login_do_portal_com_senha(self):
        response = self.client.post(
            reverse("portal_password_login_api", args=[self.empresa.pk]),
            data=json.dumps({
                "identifier": "cliente.portal@example.com",
                "password": "senha-portal-antiga",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session[f"portal_cliente_empresa_{self.empresa.pk}"], self.cliente.pk)
        self.assertEqual(response.json()["status"], "sucesso")

    def test_recuperacao_de_senha_do_portal_por_whatsapp(self):
        response = self.client.post(
            reverse("password_recovery_request"),
            {
                "account_type": "client",
                "empresa": self.empresa.pk,
                "identifier": "65999992222",
                "channel": "whatsapp",
            },
        )

        self.assertRedirects(response, reverse("password_recovery_confirm"))
        recovery = PasswordRecoveryCode.objects.get(account_type="client", cliente=self.cliente)

        confirm_response = self.client.post(
            reverse("password_recovery_confirm"),
            {
                "code": recovery.codigo,
                "new_password1": "nova-senha-portal",
                "new_password2": "nova-senha-portal",
            },
        )

        self.assertRedirects(confirm_response, reverse("cliente_empresa", args=[self.empresa.pk]))
        self.cliente.refresh_from_db()
        recovery.refresh_from_db()

        self.assertTrue(self.cliente.check_portal_password("nova-senha-portal"))
        self.assertEqual(self.client.session[f"portal_cliente_empresa_{self.empresa.pk}"], self.cliente.pk)
        self.assertIsNotNone(recovery.usado_em)


@override_settings(STRIPE_WEBHOOK_SECRET="whsec_test_secret")
class StripeWebhookTests(TestCase):
    @patch("core.views.stripe.Webhook.construct_event")
    def test_webhook_processa_evento_assinado(self, construct_event_mock):
        construct_event_mock.return_value = {
            "id": "evt_test_1",
            "type": "checkout.session.completed",
            "livemode": False,
            "data": {"object": {"id": "cs_test_1"}},
        }

        response = self.client.post(
            reverse("stripe_webhook"),
            data="{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=123,v1=signature",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"], "processed")
        self.assertEqual(StripeWebhookEvent.objects.count(), 1)

        event = StripeWebhookEvent.objects.get(event_id="evt_test_1")
        self.assertEqual(event.processing_status, "processed")
        self.assertEqual(event.event_type, "checkout.session.completed")

    @patch("core.views.stripe.Webhook.construct_event")
    def test_webhook_ignora_evento_duplicado(self, construct_event_mock):
        construct_event_mock.return_value = {
            "id": "evt_test_duplicado",
            "type": "checkout.session.completed",
            "livemode": False,
            "data": {"object": {"id": "cs_test_dup"}},
        }

        first_response = self.client.post(
            reverse("stripe_webhook"),
            data="{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=123,v1=signature",
        )
        second_response = self.client.post(
            reverse("stripe_webhook"),
            data="{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=123,v1=signature",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json()["result"], "duplicate")
        self.assertEqual(StripeWebhookEvent.objects.filter(event_id="evt_test_duplicado").count(), 1)

    @patch("core.views.stripe.Webhook.construct_event")
    def test_webhook_rejeita_assinatura_invalida(self, construct_event_mock):
        construct_event_mock.side_effect = stripe.error.SignatureVerificationError("bad", "signature")

        response = self.client.post(
            reverse("stripe_webhook"),
            data="{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="assinatura-invalida",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "erro")
        self.assertEqual(StripeWebhookEvent.objects.count(), 0)


class InfrastructureEndpointsTests(TestCase):
    def test_healthz_endpoint_retorna_ok(self):
        response = self.client.get(reverse("healthz"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["service"], "easyschedule")

    def test_readyz_endpoint_retorna_db_ok(self):
        response = self.client.get(reverse("readyz"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["checks"]["database"], "ok")

    def test_request_id_e_refletido_no_header(self):
        request_id = "req-teste-123"
        response = self.client.get(reverse("healthz"), HTTP_X_REQUEST_ID=request_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Request-ID"], request_id)
