"""
Comando para marcar todos os cavalos atuais como "Agregado"

COMO USAR:
    python manage.py marcar_cavalos_agregados

Este comando:
- Atualiza todos os cavalos existentes
- Define classificacao='agregado' para todos
- Útil para inicializar o campo após adicionar a classificação
"""

from django.core.management.base import BaseCommand
from core.models import Cavalo


class Command(BaseCommand):
    help = 'Marca todos os cavalos atuais como "Agregado"'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria feito sem realmente fazer as alterações',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Buscar todos os cavalos
        cavalos = Cavalo.objects.all()
        total = cavalos.count()
        
        if total == 0:
            self.stdout.write(
                self.style.WARNING('Nenhum cavalo encontrado no banco de dados.')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'[DRY RUN] Seriam atualizados {total} cavalos para "Agregado"')
            )
            # Mostrar alguns exemplos
            for cavalo in cavalos[:5]:
                self.stdout.write(f'  - {cavalo.placa or f"Cavalo #{cavalo.id}"}: {cavalo.classificacao or "(sem classificação)"} → agregado')
            if total > 5:
                self.stdout.write(f'  ... e mais {total - 5} cavalos')
            return
        
        # Confirmar ação
        self.stdout.write(f'Encontrados {total} cavalos.')
        self.stdout.write('Todos serão marcados como "Agregado".')
        
        # Atualizar todos os cavalos
        atualizados = cavalos.update(classificacao='agregado')
        
        self.stdout.write(
            self.style.SUCCESS(f'✓ {atualizados} cavalos atualizados com sucesso!')
        )
        
        # Mostrar estatísticas
        self.stdout.write('\nEstatísticas:')
        for classificacao, label in Cavalo.CLASSIFICACAO_CHOICES:
            count = Cavalo.objects.filter(classificacao=classificacao).count()
            self.stdout.write(f'  - {label}: {count}')
