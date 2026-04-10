from django.contrib.auth.models import User
from django.test import TestCase

from empresas.models import Empresa
from servicos.forms import ServicoForm
from servicos.models import Servico


class ServicoFormCustomCategoryTests(TestCase):
	def setUp(self):
		self.owner = User.objects.create_user(
			username="empresa-servicos@example.com",
			email="empresa-servicos@example.com",
			password="senha-forte-123",
		)
		self.empresa = Empresa.objects.create(
			usuario=self.owner,
			nome="Studio Categorias",
			tipo="manicure",
			cnpj="98765432000199",
		)

	def test_form_permite_criar_categoria_personalizada(self):
		form = ServicoForm(
			{
				"nome": "Servico Especial",
				"categoria": ServicoForm.CUSTOM_CATEGORY_VALUE,
				"categoria_custom": "Ritual premium",
				"descricao": "Descricao teste",
				"preco": "120.00",
				"tempo": "75",
				"ativo": "on",
			},
			empresa=self.empresa,
		)

		self.assertTrue(form.is_valid(), form.errors)

		servico = form.save(commit=False)
		servico.empresa = self.empresa
		servico.save()

		self.assertEqual(servico.categoria, "Ritual premium")

	def test_form_exige_nome_da_categoria_personalizada(self):
		form = ServicoForm(
			{
				"nome": "Servico Especial",
				"categoria": ServicoForm.CUSTOM_CATEGORY_VALUE,
				"categoria_custom": "",
				"descricao": "Descricao teste",
				"preco": "120.00",
				"tempo": "75",
				"ativo": "on",
			},
			empresa=self.empresa,
		)

		self.assertFalse(form.is_valid())
		self.assertIn("categoria_custom", form.errors)

	def test_form_reutiliza_categorias_personalizadas_existentes_da_empresa(self):
		Servico.objects.create(
			empresa=self.empresa,
			nome="Servico Existente",
			categoria="Spa de cuticulas",
			descricao="",
			preco="89.90",
			tempo=50,
			ativo=True,
		)

		form = ServicoForm(empresa=self.empresa)
		values = [value for value, _label in form.fields["categoria"].choices]

		self.assertIn("Spa de cuticulas", values)
		self.assertIn(ServicoForm.CUSTOM_CATEGORY_VALUE, values)
