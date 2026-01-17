"""
Comando de gerenciamento para sincronizar manualmente com Google Sheets

COMO USAR:
    python manage.py sync_google_sheets

Este comando:
- Busca todos os cavalos na mesma ordem do admin
- Atualiza a planilha do Google Sheets
- Útil para sincronização inicial ou quando algo der errado
"""

from django.core.management.base import BaseCommand
from core.google_sheets import sync_cavalos_to_sheets


class Command(BaseCommand):
    help = 'Sincroniza a lista de cavalos com o Google Sheets'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando sincronização com Google Sheets...')
        
        success = sync_cavalos_to_sheets()
        
        if success:
            self.stdout.write(
                self.style.SUCCESS('✓ Sincronização concluída com sucesso!')
            )
        else:
            self.stdout.write(
                self.style.ERROR('✗ Erro na sincronização. Verifique os logs.')
            )
