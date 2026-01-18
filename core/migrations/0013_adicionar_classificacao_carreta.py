# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_adicionar_classificacao_cavalo'),
    ]

    operations = [
        migrations.AddField(
            model_name='carreta',
            name='classificacao',
            field=models.CharField(
                blank=True,
                choices=[
                    ('agregado', 'Agregamento'),
                    ('frota', 'Frota'),
                    ('terceiro', 'Terceiro')
                ],
                max_length=20,
                null=True,
                verbose_name='Classificação'
            ),
        ),
    ]
