# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_atualizar_labels_classificacao'),
    ]

    operations = [
        migrations.AddField(
            model_name='carreta',
            name='situacao',
            field=models.CharField(blank=True, choices=[('ativo', 'Ativo'), ('parado', 'Parado')], default='ativo', max_length=20, null=True, verbose_name='Situação'),
        ),
    ]
