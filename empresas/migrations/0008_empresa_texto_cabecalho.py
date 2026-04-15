from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("empresas", "0007_empresa_portal_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="empresa",
            name="texto_cabecalho",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
    ]
