"""
Comando Django para sincronizar gestores dos documentos de transporte
com base nas placas dos cavalos.

Uso:
    python manage.py sincronizar_gestor_documentos
"""

from django.core.management.base import BaseCommand
from core.models import Cavalo, DocumentoTransporte
from django.db import transaction
from django.db.models import Q


class Command(BaseCommand):
    help = 'Sincroniza gestores dos documentos de transporte com base nas placas dos cavalos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa sem salvar no banco (apenas mostra o que seria feito)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        self.stdout.write('Sincronizando gestores dos documentos de transporte...')

        # Buscar todos os cavalos com gestor
        cavalos_com_gestor = Cavalo.objects.filter(
            gestor__isnull=False,
            placa__isnull=False
        ).exclude(placa='').select_related('gestor')

        self.stdout.write(f'Total de cavalos com gestor: {cavalos_com_gestor.count()}')

        # Criar um dicionário: placa -> gestor
        placa_gestor_map = {}
        for cavalo in cavalos_com_gestor:
            placa_normalizada = cavalo.placa.strip().upper()
            if placa_normalizada:
                placa_gestor_map[placa_normalizada] = cavalo.gestor

        self.stdout.write(f'Placas mapeadas: {len(placa_gestor_map)}')

        # Buscar todos os documentos de transporte que têm placa de cavalo
        documentos = DocumentoTransporte.objects.filter(
            cavalo__isnull=False
        ).exclude(cavalo='')

        total_documentos = documentos.count()
        self.stdout.write(f'Total de documentos de transporte com placa: {total_documentos}')

        # Contadores
        atualizados = 0
        ja_corretos = 0
        sem_gestor_no_cavalo = 0
        erros = 0

        with transaction.atomic():
            for documento in documentos:
                try:
                    placa_documento = documento.cavalo.strip().upper() if documento.cavalo else None
                    
                    if not placa_documento:
                        continue

                    # Buscar gestor correspondente à placa
                    gestor_correspondente = placa_gestor_map.get(placa_documento)

                    if not gestor_correspondente:
                        sem_gestor_no_cavalo += 1
                        continue

                    # Verificar se o gestor já está correto
                    if documento.gestor == gestor_correspondente:
                        ja_corretos += 1
                        continue

                    # Atualizar gestor do documento
                    if not dry_run:
                        documento.gestor = gestor_correspondente
                        documento.save(update_fields=['gestor'])
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Documento {documento.tipo_documento} {documento.filial}/{documento.serie}/{documento.numero_documento} '
                                f'(Placa: {placa_documento}) -> Gestor: {gestor_correspondente.nome}'
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'[DRY-RUN] Atualizaria documento {documento.tipo_documento} {documento.filial}/{documento.serie}/{documento.numero_documento} '
                                f'(Placa: {placa_documento}) -> Gestor: {gestor_correspondente.nome}'
                            )
                        )
                    atualizados += 1

                except Exception as e:
                    erros += 1
                    self.stdout.write(
                        self.style.ERROR(f'Erro ao processar documento ID {documento.id}: {str(e)}')
                    )
                    continue

            if dry_run:
                # Em dry-run, não commita a transação
                transaction.set_rollback(True)

        # Resumo
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('RESUMO DA SINCRONIZACAO:'))
        self.stdout.write(f'  Total de documentos processados: {total_documentos}')
        self.stdout.write(f'  [+] Atualizados: {atualizados}')
        self.stdout.write(f'  [-] Ja estavam corretos: {ja_corretos}')
        self.stdout.write(f'  [-] Sem gestor no cavalo correspondente: {sem_gestor_no_cavalo}')
        self.stdout.write(f'  [-] Erros: {erros}')
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[AVISO] MODO DRY-RUN: Nenhum dado foi salvo!'))
        else:
            self.stdout.write(self.style.SUCCESS('\n[OK] Sincronizacao concluida com sucesso!'))

