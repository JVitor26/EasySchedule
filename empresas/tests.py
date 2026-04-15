from datetime import date, time
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from agendamentos.models import Agendamento
from agendamentos.forms import AgendamentoForm
from empresas.models import Empresa
from pessoa.models import Pessoa
from produtos.models import Produto, VendaProduto
from profissionais.forms import ProfissionalForm
from profissionais.models import Profissional
from servicos.forms import ServicoForm
from servicos.models import Servico
from empresas.permissions import PROFISSIONAL_ACCESS_CLIENTES, PROFISSIONAL_ACCESS_SERVICOS


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

    def test_profissional_form_cria_login_novo_usuario(self):
        form = ProfissionalForm(
            data={
                "criar_acesso": "on",
                "email_acesso": "novo.profissional@example.com",
                "senha_acesso": "SenhaForte123!",
                "senha_confirmacao_acesso": "SenhaForte123!",
                "nome": "Novo Profissional",
                "especialidade": "Corte",
                "telefone": "65999997777",
                "email": "",
                "cpf": "",
                "data_nascimento": "",
                "endereco": "",
                "ativo": "on",
                "observacoes": "",
            },
            empresa=self.empresa_a,
        )

        self.assertTrue(form.is_valid(), form.errors)
        profissional = form.save(commit=False)
        profissional.empresa = self.empresa_a
        profissional.usuario = form.provision_access_user()
        profissional.save()

        self.assertIsNotNone(profissional.usuario)
        self.assertEqual(profissional.usuario.username, "novo.profissional@example.com")
        self.assertTrue(profissional.usuario.check_password("SenhaForte123!"))

    def test_profissional_form_bloqueia_email_ja_existente(self):
        form = ProfissionalForm(
            data={
                "criar_acesso": "on",
                "email_acesso": "empresa-b@example.com",
                "senha_acesso": "SenhaForte123!",
                "senha_confirmacao_acesso": "SenhaForte123!",
                "nome": "Profissional Duplicado",
                "especialidade": "Corte",
                "telefone": "65999996666",
                "email": "",
                "cpf": "",
                "data_nascimento": "",
                "endereco": "",
                "ativo": "on",
                "observacoes": "",
            },
            empresa=self.empresa_a,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("email_acesso", form.errors)


class CadastroEmpresaBrandingFieldsTests(TestCase):
    def test_pagina_cadastro_exibe_campos_de_branding_e_color_picker(self):
        response = self.client.get(reverse("cadastro_empresa"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_logo"')
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


class EmpresaConfiguracoesTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="senha-forte-123",
        )
        self.empresa = Empresa.objects.create(
            usuario=self.owner,
            nome="Studio Central",
            tipo="barbearia",
            cnpj="12345678000199",
            whatsapp="65999990000",
            logo_url="https://cdn.example.com/old-logo.png",
            cor_primaria="#2255aa",
            cor_secundaria="#11aa88",
        )

        self.prof_user = User.objects.create_user(
            username="prof@example.com",
            email="prof@example.com",
            password="senha-forte-123",
        )
        self.profissional = Profissional.objects.create(
            empresa=self.empresa,
            usuario=self.prof_user,
            nome="Rafa",
            especialidade="Corte",
            telefone="65999993333",
            email="rafa@example.com",
            acessos_modulos=["agendamentos"],
        )

    def _build_png_file(self, filename="logo.png"):
        image_buffer = BytesIO()
        Image.new("RGB", (4, 4), color=(15, 76, 129)).save(image_buffer, format="PNG")
        image_buffer.seek(0)
        return SimpleUploadedFile(filename, image_buffer.getvalue(), content_type="image/png")

    def test_configuracoes_exibe_botao_para_apagar_conta(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("empresa_configuracoes"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Apagar conta")
        self.assertContains(response, reverse("empresa_excluir_conta"))

    def test_excluir_conta_exibe_card_de_confirmacao_irreversivel(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("empresa_excluir_conta"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Acao irreversivel")
        self.assertContains(response, "nao tem volta")
        self.assertContains(response, "Sim, apagar minha conta")

    def test_owner_can_update_empresa_and_profissional_modules(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("empresa_configuracoes"),
            {
                "nome": "Studio Premium",
                "tipo": "manicure",
                "whatsapp": "(65) 98888-7777",
                "plano": "start",
                "limite_profissionais": "5",
                "cor_primaria": "#0f4c81",
                "cor_secundaria": "#188fa7",
                "texto_cabecalho": "Agenda VIP da Studio Premium",
                f"acessos_{self.profissional.pk}": [
                    PROFISSIONAL_ACCESS_CLIENTES,
                    PROFISSIONAL_ACCESS_SERVICOS,
                ],
            },
        )

        self.assertRedirects(response, reverse("empresa_configuracoes"))

        self.empresa.refresh_from_db()
        self.profissional.refresh_from_db()

        self.assertEqual(self.empresa.nome, "Studio Premium")
        self.assertEqual(self.empresa.tipo, "manicure")
        self.assertEqual(self.empresa.whatsapp, "65988887777")
        self.assertEqual(self.empresa.plano, "start")
        self.assertEqual(self.empresa.limite_profissionais, 5)
        self.assertEqual(float(self.empresa.valor_mensal), 147.0)
        self.assertEqual(self.empresa.cor_primaria, "#0f4c81")
        self.assertEqual(self.empresa.cor_secundaria, "#188fa7")
        self.assertEqual(self.empresa.texto_cabecalho, "Agenda VIP da Studio Premium")
        self.assertIn(PROFISSIONAL_ACCESS_CLIENTES, self.profissional.acessos_modulos)
        self.assertIn(PROFISSIONAL_ACCESS_SERVICOS, self.profissional.acessos_modulos)

    def test_owner_can_upload_logo_file_in_configuracoes(self):
        self.client.force_login(self.owner)
        logo_file = self._build_png_file()

        response = self.client.post(
            reverse("empresa_configuracoes"),
            {
                "nome": self.empresa.nome,
                "tipo": self.empresa.tipo,
                "whatsapp": self.empresa.whatsapp,
                "plano": self.empresa.plano,
                "limite_profissionais": str(self.empresa.limite_profissionais),
                "cor_primaria": self.empresa.cor_primaria,
                "cor_secundaria": self.empresa.cor_secundaria,
                f"acessos_{self.profissional.pk}": self.profissional.acessos_modulos,
                "logo": logo_file,
            },
        )

        self.assertRedirects(response, reverse("empresa_configuracoes"))
        self.empresa.refresh_from_db()
        self.assertTrue(bool(self.empresa.logo))
        self.assertIn("empresas/logos/", self.empresa.logo.name)

    def test_owner_can_upgrade_plano_da_empresa(self):
        self.empresa.plano = Empresa.PLANO_SOLO
        self.empresa.limite_profissionais = 1
        self.empresa.valor_mensal = 97
        self.empresa.save(update_fields=["plano", "limite_profissionais", "valor_mensal"])

        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("empresa_configuracoes"),
            {
                "nome": self.empresa.nome,
                "tipo": self.empresa.tipo,
                "whatsapp": self.empresa.whatsapp,
                "plano": Empresa.PLANO_START,
                "limite_profissionais": "4",
                "cor_primaria": self.empresa.cor_primaria,
                "cor_secundaria": self.empresa.cor_secundaria,
                f"acessos_{self.profissional.pk}": self.profissional.acessos_modulos,
            },
        )

        self.assertRedirects(response, reverse("empresa_configuracoes"))
        self.empresa.refresh_from_db()
        self.assertEqual(self.empresa.plano, Empresa.PLANO_START)
        self.assertEqual(self.empresa.limite_profissionais, 4)
        self.assertEqual(float(self.empresa.valor_mensal), 147.0)

    def test_profissional_sem_modulo_clientes_e_bloqueado(self):
        self.profissional.acessos_modulos = ["agendamentos"]
        self.profissional.save(update_fields=["acessos_modulos"])

        self.client.force_login(self.prof_user)
        response = self.client.get(reverse("pessoa_list"))

        self.assertRedirects(response, reverse("dashboard_home"))

    def test_profissional_com_modulo_clientes_tem_acesso(self):
        self.profissional.acessos_modulos = ["agendamentos", PROFISSIONAL_ACCESS_CLIENTES]
        self.profissional.save(update_fields=["acessos_modulos"])

        self.client.force_login(self.prof_user)
        response = self.client.get(reverse("pessoa_list"))

        self.assertEqual(response.status_code, 200)

    def test_cabecalho_mostra_logo_da_empresa(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("dashboard_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://cdn.example.com/old-logo.png")
        self.assertContains(response, 'data-company-primary="#2255aa"')
        self.assertContains(response, 'data-company-secondary="#11aa88"')

    def test_owner_can_delete_full_company_account(self):
        cliente = Pessoa.objects.create(
            empresa=self.empresa,
            nome="Cliente Excluir",
            email="cliente.excluir@example.com",
            telefone="65999990001",
            documento="11111111111",
            data_nascimento=date(1990, 1, 1),
        )
        servico = Servico.objects.create(
            empresa=self.empresa,
            nome="Corte completo",
            categoria="Cabelo",
            preco=80,
            tempo=60,
        )
        produto = Produto.objects.create(
            empresa=self.empresa,
            nome="Pomada",
            preco=40,
            valor_venda=50,
            estoque=3,
        )
        venda = VendaProduto.objects.create(
            empresa=self.empresa,
            produto=produto,
            cliente=cliente,
            valor_venda=50,
            data_venda=date(2026, 4, 15),
        )

        owner_id = self.owner.pk
        prof_user_id = self.prof_user.pk
        empresa_id = self.empresa.pk

        self.client.force_login(self.owner)
        response = self.client.post(reverse("empresa_excluir_conta"))

        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(Empresa.objects.filter(pk=empresa_id).exists())
        self.assertFalse(User.objects.filter(pk__in=[owner_id, prof_user_id]).exists())
        self.assertFalse(Pessoa.objects.filter(pk=cliente.pk).exists())
        self.assertFalse(Servico.objects.filter(pk=servico.pk).exists())
        self.assertFalse(VendaProduto.objects.filter(pk=venda.pk).exists())
        self.assertFalse(Produto.objects.filter(pk=produto.pk).exists())

    def test_profissional_nao_pode_apagar_conta_da_empresa(self):
        self.client.force_login(self.prof_user)

        response = self.client.post(reverse("empresa_excluir_conta"))

        self.assertRedirects(response, reverse("dashboard_home"))
        self.assertTrue(Empresa.objects.filter(pk=self.empresa.pk).exists())
        self.assertEqual(User.objects.filter(pk__in=[self.owner.pk, self.prof_user.pk]).count(), 2)

    def test_admin_global_nao_apaga_conta_de_outro_dono(self):
        admin = User.objects.create_superuser(
            username="admin-global@example.com",
            email="admin-global@example.com",
            password="senha-forte-123",
        )

        self.client.force_login(admin)
        response = self.client.post(reverse("empresa_excluir_conta"))

        self.assertRedirects(response, reverse("empresa_configuracoes"))
        self.assertTrue(Empresa.objects.filter(pk=self.empresa.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.owner.pk).exists())
