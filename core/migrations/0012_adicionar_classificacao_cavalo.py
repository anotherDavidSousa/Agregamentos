# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_atualizar_situacao_choices'),
    ]

    operations = [
        migrations.AddField(
            model_name='cavalo',
            name='classificacao',
            field=models.CharField(
                blank=True,
                choices=[
                    ('agregado', 'Agregado'),
                    ('frota', 'Frota Própria'),
                    ('terceiro', 'Terceirizado')
                ],
                max_length=20,
                null=True,
                verbose_name='Classificação'
            ),
        ),
    ]
