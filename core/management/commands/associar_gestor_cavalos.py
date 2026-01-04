"""
Comando Django para associar todos os cavalos a um gestor específico.

Uso:
    python manage.py associar_gestor_cavalos "David Sousa"
"""

from django.core.management.base import BaseCommand
from core.models import Cavalo, Gestor
from django.db import transaction


class Command(BaseCommand):
    help = 'Associa todos os cavalos a um gestor específico'

    def add_arguments(self, parser):
        parser.add_argument(
            'nome_gestor',
            nargs='?',
            type=str,
            default='David Sousa',
            help='Nome do gestor'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa sem salvar no banco (apenas mostra o que seria feito)',
        )

    def handle(self, *args, **options):
        nome_gestor = options['nome_gestor']
        dry_run = options['dry_run']

        # Buscar o gestor
        try:
            gestor = Gestor.objects.get(nome__iexact=nome_gestor)
            self.stdout.write(f'Gestor encontrado: {gestor.nome} (ID: {gestor.id})')
        except Gestor.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Gestor "{nome_gestor}" nao encontrado!')
            )
            self.stdout.write('Gestores disponiveis:')
            for g in Gestor.objects.all():
                self.stdout.write(f'  - {g.nome}')
            return
        except Gestor.MultipleObjectsReturned:
            gestor = Gestor.objects.filter(nome__iexact=nome_gestor).first()
            self.stdout.write(
                self.style.WARNING(f'Multiplos gestores encontrados. Usando: {gestor.nome} (ID: {gestor.id})')
            )

        # Buscar todos os cavalos
        cavalos = Cavalo.objects.all()
        total_cavalos = cavalos.count()
        
        self.stdout.write(f'Total de cavalos encontrados: {total_cavalos}')

        if total_cavalos == 0:
            self.stdout.write(self.style.WARNING('Nenhum cavalo encontrado!'))
            return

        # Contadores
        atualizados = 0
        ja_associados = 0
        erros = 0

        with transaction.atomic():
            for cavalo in cavalos:
                try:
                    if cavalo.gestor == gestor:
                        ja_associados += 1
                        continue
                    
                    if not dry_run:
                        cavalo.gestor = gestor
                        cavalo.save()
                        self.stdout.write(
                            self.style.SUCCESS(f'Cavalo {cavalo.placa} associado ao gestor {gestor.nome}')
                        )
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(f'[DRY-RUN] Associaria cavalo {cavalo.placa} ao gestor {gestor.nome}')
                        )
                    atualizados += 1

                except Exception as e:
                    erros += 1
                    self.stdout.write(
                        self.style.ERROR(f'Erro ao associar cavalo {cavalo.placa}: {str(e)}')
                    )
                    continue

            if dry_run:
                # Em dry-run, não commita a transação
                transaction.set_rollback(True)

        # Resumo
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('RESUMO DA ASSOCIACAO:'))
        self.stdout.write(f'  Gestor: {gestor.nome}')
        self.stdout.write(f'  Total de cavalos: {total_cavalos}')
        self.stdout.write(f'  [+] Associados/Atualizados: {atualizados}')
        self.stdout.write(f'  [-] Ja estavam associados: {ja_associados}')
        self.stdout.write(f'  [-] Erros: {erros}')
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[AVISO] MODO DRY-RUN: Nenhum dado foi salvo!'))
        else:
            self.stdout.write(self.style.SUCCESS('\n[OK] Associacao concluida com sucesso!'))

