import tempfile
from io import BytesIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from empresas.models import Empresa

from .models import Produto


TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ProdutoFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="produtos@example.com",
            email="produtos@example.com",
            password="senha-forte-123",
        )
        self.empresa = Empresa.objects.create(
            usuario=self.user,
            nome="Loja Studio",
            tipo="barbearia",
            cnpj="99999999000100",
        )

    def tearDown(self):
        media_root = Path(TEST_MEDIA_ROOT)
        if media_root.exists():
            for file_path in media_root.rglob("*"):
                if file_path.is_file():
                    file_path.unlink()

    def _build_png_file(self, filename="produto.png"):
        image_buffer = BytesIO()
        Image.new("RGB", (4, 4), color=(12, 96, 180)).save(image_buffer, format="PNG")
        image_buffer.seek(0)
        return SimpleUploadedFile(filename, image_buffer.getvalue(), content_type="image/png")

    def test_empresa_consegue_cadastrar_produto_com_foto(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("produtos_form"),
            {
                "nome": "Pomada Modeladora",
                "categoria": "Finalizacao",
                "preco": "59.90",
                "estoque": "8",
                "descricao": "Fixacao premium para acabamento.",
                "especificacoes": "Frasco 120g | efeito seco",
                "ativo": "on",
                "destaque_publico": "on",
                "foto": self._build_png_file("pomada.png"),
            },
        )

        self.assertRedirects(response, reverse("produtos_list"))
        produto = Produto.objects.get(empresa=self.empresa, nome="Pomada Modeladora")
        self.assertTrue(produto.foto.name.endswith("pomada.png"))

    def test_produto_publico_aparece_no_portal_da_empresa(self):
        Produto.objects.create(
            empresa=self.empresa,
            nome="Shampoo Premium",
            categoria="Cuidados",
            descricao="Limpeza e hidratacao.",
            especificacoes="Frasco 250ml",
            preco="39.90",
            estoque=5,
            ativo=True,
            destaque_publico=True,
        )

        response = self.client.get(reverse("cliente_empresa", args=[self.empresa.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Produtos da empresa")
        self.assertContains(response, "Shampoo Premium")
