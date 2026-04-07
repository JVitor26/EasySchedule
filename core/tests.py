import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from agendamentos.models import Agendamento, Pagamento, PlanoMensal
from empresas.models import Empresa
from core.models import PasswordRecoveryCode
from pessoa.models import Pessoa
from profissionais.models import Profissional
from servicos.models import Servico


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
        self.assertTrue(Pagamento.objects.filter(agendamento=agendamento, status="pendente").exists())

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

    def test_cliente_publico_consegue_pagar_pelo_checkout(self):
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
        pagamento = Pagamento.objects.get(agendamento=agendamento)

        payment_response = self.client.post(
            reverse("cliente_pagamento", args=[pagamento.referencia_publica]),
            {
                "metodo": "pix",
                "nome_pagador": "Ana Cliente",
                "ultimos_digitos": "",
                "aceitar_termos": "on",
            },
        )

        self.assertEqual(payment_response.status_code, 200)
        pagamento.refresh_from_db()
        agendamento.refresh_from_db()

        self.assertEqual(pagamento.status, "pago")
        self.assertEqual(agendamento.status, "confirmado")
        self.assertEqual(agendamento.forma_pagamento, "pix")

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

    def test_cliente_publico_consegue_criar_e_pagar_pacote_mensal(self):
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

        payment_response = self.client.post(
            reverse("cliente_plano_pagamento", args=[plano.referencia_publica]),
            {
                "metodo": "pix",
                "nome_pagador": "Cliente Pacote",
                "ultimos_digitos": "",
                "aceitar_termos": "on",
            },
        )

        self.assertEqual(payment_response.status_code, 200)
        plano.refresh_from_db()

        self.assertEqual(plano.pagamento_status, "pago")
        self.assertEqual(plano.agendamentos.filter(status="confirmado").count(), plano.quantidade_encontros)
        self.assertEqual(plano.agendamentos.filter(forma_pagamento="pix").count(), plano.quantidade_encontros)


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
