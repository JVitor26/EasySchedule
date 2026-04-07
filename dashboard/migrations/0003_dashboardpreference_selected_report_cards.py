from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0002_dashboardpreference'),
    ]

    operations = [
        migrations.AddField(
            model_name='dashboardpreference',
            name='selected_report_cards',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
