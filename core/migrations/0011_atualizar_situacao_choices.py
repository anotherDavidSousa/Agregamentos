# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_proprietario_codigo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cavalo',
            name='situacao',
            field=models.CharField(blank=True, choices=[('ativo', 'Ativo'), ('parado', 'Parado'), ('desagregado', 'Desagregado')], max_length=20, null=True),
        ),
    ]
