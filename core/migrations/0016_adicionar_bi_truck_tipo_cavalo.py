# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_adicionar_situacao_carreta'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cavalo',
            name='tipo',
            field=models.CharField(
                blank=True,
                choices=[
                    ('bi_truck', 'Bi-truck'),
                    ('toco', 'Toco'),
                    ('trucado', 'Trucado')
                ],
                max_length=20,
                null=True,
                verbose_name='Tipo'
            ),
        ),
    ]
