"""
Comando para marcar todas as carretas atuais como "Agregamento"

COMO USAR:
    python manage.py marcar_carretas_agregamento

Este comando:
- Atualiza todas as carretas existentes
- Define classificacao='agregado' para todas
- Útil para inicializar o campo após adicionar a classificação
"""

from django.core.management.base import BaseCommand
from core.models import Carreta


class Command(BaseCommand):
    help = 'Marca todas as carretas atuais como "Agregamento"'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria feito sem realmente fazer as alterações',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Buscar todas as carretas
        carretas = Carreta.objects.all()
        total = carretas.count()
        
        if total == 0:
            self.stdout.write(
                self.style.WARNING('Nenhuma carreta encontrada no banco de dados.')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'[DRY RUN] Seriam atualizadas {total} carretas para "Agregamento"')
            )
            # Mostrar alguns exemplos
            for carreta in carretas[:5]:
                self.stdout.write(f'  - {carreta.placa or f"Carreta #{carreta.id}"}: {carreta.classificacao or "(sem classificação)"} → agregado')
            if total > 5:
                self.stdout.write(f'  ... e mais {total - 5} carretas')
            return
        
        # Confirmar ação
        self.stdout.write(f'Encontradas {total} carretas.')
        self.stdout.write('Todas serão marcadas como "Agregamento".')
        
        # Atualizar todas as carretas
        atualizadas = carretas.update(classificacao='agregado')
        
        self.stdout.write(
            self.style.SUCCESS(f'✓ {atualizadas} carretas atualizadas com sucesso!')
        )
        
        # Mostrar estatísticas
        self.stdout.write('\nEstatísticas:')
        for classificacao, label in Carreta.CLASSIFICACAO_CHOICES:
            count = Carreta.objects.filter(classificacao=classificacao).count()
            self.stdout.write(f'  - {label}: {count}')
