# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_adicionar_classificacao_carreta'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cavalo',
            name='classificacao',
            field=models.CharField(
                blank=True,
                choices=[
                    ('agregado', 'Agregado'),
                    ('frota', 'Frota'),
                    ('terceiro', 'Terceiro')
                ],
                max_length=20,
                null=True,
                verbose_name='Classificação'
            ),
        ),
    ]
