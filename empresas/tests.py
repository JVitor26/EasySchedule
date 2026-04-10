from datetime import date, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from agendamentos.models import Agendamento
from agendamentos.forms import AgendamentoForm
from empresas.models import Empresa
from pessoa.models import Pessoa
from profissionais.forms import ProfissionalForm
from profissionais.models import Profissional
from servicos.forms import ServicoForm
from servicos.models import Servico


class MultiEmpresaIsolationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin@example.com",
            email="admin@example.com",
            password="senha-forte-123",
        )

        self.user_a = User.objects.create_user(
            username="empresa-a@example.com",
            email="empresa-a@example.com",
            password="senha-forte-123",
        )
        self.user_b = User.objects.create_user(
            username="empresa-b@example.com",
            email="empresa-b@example.com",
            password="senha-forte-123",
        )

        self.empresa_a = Empresa.objects.create(
            usuario=self.user_a,
            nome="Empresa A",
            tipo="barbearia",
            cnpj="11111111111",
        )
        self.empresa_b = Empresa.objects.create(
            usuario=self.user_b,
            nome="Empresa B",
            tipo="manicure",
            cnpj="22222222222",
        )

        self.pessoa_a = Pessoa.objects.create(
            empresa=self.empresa_a,
            nome="Cliente A",
            email="cliente-a@example.com",
            telefone="65999990001",
            documento="11111111111",
            data_nascimento=date(1990, 1, 1),
            endereco="Rua A",
            observacoes="",
        )
        self.pessoa_b = Pessoa.objects.create(
            empresa=self.empresa_b,
            nome="Cliente B",
            email="cliente-b@example.com",
            telefone="65999990002",
            documento="22222222222",
            data_nascimento=date(1991, 2, 2),
            endereco="Rua B",
            observacoes="",
        )

        self.profissional_a = Profissional.objects.create(
            empresa=self.empresa_a,
            nome="Profissional A",
            especialidade="Corte",
            telefone="65999990003",
            email="prof-a@example.com",
            ativo=True,
        )
        self.profissional_b = Profissional.objects.create(
            empresa=self.empresa_b,
            nome="Profissional B",
            especialidade="Manicure",
            telefone="65999990004",
            email="prof-b@example.com",
            ativo=True,
        )

        self.servico_a = Servico.objects.create(
            empresa=self.empresa_a,
            nome="Servico A",
            categoria="Beleza",
            preco=100,
            tempo=60,
            ativo=True,
        )
        self.servico_b = Servico.objects.create(
            empresa=self.empresa_b,
            nome="Servico B",
            categoria="Saude",
            preco=150,
            tempo=45,
            ativo=True,
        )

        Agendamento.objects.create(
            empresa=self.empresa_a,
            cliente=self.pessoa_a,
            servico=self.servico_a,
            profissional=self.profissional_a,
            data=date(2026, 4, 10),
            hora=time(9, 0),
            status="confirmado",
        )
        Agendamento.objects.create(
            empresa=self.empresa_b,
            cliente=self.pessoa_b,
            servico=self.servico_b,
            profissional=self.profissional_b,
            data=date(2026, 4, 11),
            hora=time(10, 0),
            status="pendente",
        )

    def test_usuario_comum_ve_apenas_dados_da_propria_empresa(self):
        self.client.force_login(self.user_a)

        response = self.client.get(reverse("pessoa_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente A")
        self.assertNotContains(response, "Cliente B")

    def test_agendamento_form_bloqueia_relacoes_de_outra_empresa(self):
        self.client.force_login(self.user_a)

        response = self.client.post(
            reverse("agendamentos_form"),
            {
                "cliente": self.pessoa_b.pk,
                "servico": self.servico_b.pk,
                "profissional": self.profissional_b.pk,
                "data": "2026-04-12",
                "hora": "14:00",
                "observacoes": "Tentativa cruzada",
                "status": "confirmado",
                "forma_pagamento": "pix",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Agendamento.objects.filter(empresa=self.empresa_a).count(), 1)
        form = response.context["form"]
        self.assertIn("cliente", form.errors)
        self.assertIn("servico", form.errors)
        self.assertIn("profissional", form.errors)

    def test_admin_global_consegue_trocar_empresa_ativa(self):
        self.client.force_login(self.admin)

        switch_response = self.client.post(
            reverse("selecionar_empresa"),
            {
                "empresa_id": self.empresa_b.pk,
                "next": reverse("pessoa_list"),
            },
        )

        self.assertRedirects(switch_response, reverse("pessoa_list"))
        self.assertEqual(self.client.session["empresa_ativa_id"], self.empresa_b.pk)

        response = self.client.get(reverse("pessoa_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente B")
        self.assertNotContains(response, "Cliente A")

    def test_formularios_se_adaptam_ao_tipo_da_empresa(self):
        form_barbearia = ServicoForm(empresa=self.empresa_a)
        form_manicure = ProfissionalForm(empresa=self.empresa_b)
        form_agendamento = AgendamentoForm(empresa=self.empresa_a)

        categorias_barbearia = [value for value, _label in form_barbearia.fields["categoria"].choices]

        self.assertEqual(form_barbearia.fields["nome"].label, "Nome do servico")
        self.assertIn("corte", categorias_barbearia)
        self.assertIn("barba", categorias_barbearia)
        self.assertEqual(form_manicure.fields["nome"].label, "Nome da manicure")
        self.assertEqual(form_agendamento.fields["profissional"].label, "Barbeiro")


class CadastroEmpresaBrandingFieldsTests(TestCase):
    def test_pagina_cadastro_exibe_campos_de_branding_e_color_picker(self):
        response = self.client.get(reverse("cadastro_empresa"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_logo_url"')
        self.assertContains(response, 'id="id_cor_primaria"')
        self.assertContains(response, 'id="id_cor_secundaria"')
        self.assertContains(response, 'id="id_cor_primaria_picker"')
        self.assertContains(response, 'id="id_cor_secundaria_picker"')
        self.assertContains(response, 'type="color"')
        self.assertContains(response, 'id="brandingEmailPreviewHeader"')
        self.assertContains(response, 'id="brandingEmailPreviewMonogram"')
        self.assertContains(response, 'id="brandingEmailPreviewCompany"')
        self.assertContains(response, 'id="brandingEmailPreviewType"')
        self.assertContains(response, 'id="brandingWhatsappPreviewHeader"')
        self.assertContains(response, 'id="brandingWhatsappPreviewCustomer"')
        self.assertContains(response, 'id="brandingWhatsappPreviewProfessional"')
