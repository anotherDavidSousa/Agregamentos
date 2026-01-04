"""
Comando Django para importar cavalos, carretas e proprietarios de um arquivo Excel.

Uso:
    python manage.py importar_cavalos "D:\\Downloads\\cavalo.xlsx"
    
Ou sem especificar o caminho (usa o padrao):
    python manage.py importar_cavalos
"""

from django.core.management.base import BaseCommand
from core.models import Cavalo, Motorista, Carreta, Proprietario
import pandas as pd
import os
from django.db import transaction


class Command(BaseCommand):
    help = 'Importa cavalos, carretas e proprietarios de um arquivo Excel'

    def add_arguments(self, parser):
        parser.add_argument(
            'arquivo',
            nargs='?',
            type=str,
            default=r'D:\Downloads\cavalo.xlsx',
            help='Caminho do arquivo Excel com os dados'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa sem salvar no banco (apenas mostra o que seria importado)',
        )

    def handle(self, *args, **options):
        arquivo_path = options['arquivo']
        dry_run = options['dry_run']

        # Verificar se o arquivo existe
        if not os.path.exists(arquivo_path):
            self.stdout.write(
                self.style.ERROR(f'Arquivo nao encontrado: {arquivo_path}')
            )
            return

        self.stdout.write(f'Lendo arquivo: {arquivo_path}')

        try:
            # Ler o arquivo Excel
            df = pd.read_excel(arquivo_path)
            
            self.stdout.write(f'Total de linhas no Excel: {len(df)}')
            self.stdout.write(f'Colunas encontradas: {", ".join(df.columns.tolist())}')

            # Usar índices de coluna (A=0, B=1, E=4, F=5, G=6, I=8, J=9, K=10)
            # Ajustar se houver cabeçalho
            col_placa_cavalo = 0  # Coluna A
            col_nome_motorista = 1  # Coluna B
            col_placa_carreta = 4  # Coluna E
            col_tipo = 5  # Coluna F
            col_fluxo = 6  # Coluna G
            col_codigo_proprietario = 8  # Coluna I
            col_tipo_proprietario = 9  # Coluna J
            col_nome_proprietario = 10  # Coluna K

            # Verificar se tem cabeçalho (primeira linha pode ser cabeçalho)
            # Se a primeira linha não for numérica/texto de placa, pular
            primeira_linha = df.iloc[0]
            if not pd.isna(primeira_linha.iloc[col_placa_cavalo]):
                primeira_valor = str(primeira_linha.iloc[col_placa_cavalo]).strip().upper()
                # Se parece com cabeçalho, pular primeira linha
                if 'placa' in primeira_valor.lower() or len(primeira_valor) > 10:
                    df = df.iloc[1:].reset_index(drop=True)
                    self.stdout.write('Primeira linha (cabecalho) ignorada')

            # Contadores
            sucesso_cavalos = 0
            sucesso_carretas = 0
            sucesso_proprietarios = 0
            erros = 0
            atualizados = 0

            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        # Ler dados da linha
                        placa_cavalo = None
                        if col_placa_cavalo < len(row) and pd.notna(row.iloc[col_placa_cavalo]):
                            placa_cavalo = str(row.iloc[col_placa_cavalo]).strip().upper()
                            if placa_cavalo == '' or placa_cavalo == 'NAN':
                                placa_cavalo = None

                        if not placa_cavalo:
                            continue

                        nome_motorista = None
                        if col_nome_motorista < len(row) and pd.notna(row.iloc[col_nome_motorista]):
                            nome_motorista = str(row.iloc[col_nome_motorista]).strip()
                            if nome_motorista == '' or nome_motorista == 'NAN':
                                nome_motorista = None

                        placa_carreta = None
                        if col_placa_carreta < len(row) and pd.notna(row.iloc[col_placa_carreta]):
                            placa_carreta = str(row.iloc[col_placa_carreta]).strip().upper()
                            if placa_carreta == '' or placa_carreta == 'NAN':
                                placa_carreta = None

                        tipo_cavalo = None
                        if col_tipo < len(row) and pd.notna(row.iloc[col_tipo]):
                            tipo_str = str(row.iloc[col_tipo]).strip().lower()
                            if 'toco' in tipo_str:
                                tipo_cavalo = 'toco'
                            elif 'trucado' in tipo_str:
                                tipo_cavalo = 'trucado'

                        fluxo = None
                        if col_fluxo < len(row) and pd.notna(row.iloc[col_fluxo]):
                            fluxo_str = str(row.iloc[col_fluxo]).strip().lower()
                            if 'harsco' in fluxo_str or 'escor' in fluxo_str:
                                fluxo = 'escoria'
                            else:
                                fluxo = 'minerio'

                        codigo_proprietario = None
                        if col_codigo_proprietario < len(row) and pd.notna(row.iloc[col_codigo_proprietario]):
                            codigo_proprietario = str(row.iloc[col_codigo_proprietario]).strip()
                            if codigo_proprietario == '' or codigo_proprietario == 'NAN':
                                codigo_proprietario = None

                        tipo_proprietario = None
                        if col_tipo_proprietario < len(row) and pd.notna(row.iloc[col_tipo_proprietario]):
                            tipo_str = str(row.iloc[col_tipo_proprietario]).strip().upper()
                            if tipo_str in ['PF', 'PJ']:
                                tipo_proprietario = tipo_str

                        nome_proprietario = None
                        if col_nome_proprietario < len(row) and pd.notna(row.iloc[col_nome_proprietario]):
                            nome_proprietario = str(row.iloc[col_nome_proprietario]).strip()
                            if nome_proprietario == '' or nome_proprietario == 'NAN':
                                nome_proprietario = None

                        # Criar ou atualizar Proprietario
                        proprietario = None
                        if codigo_proprietario or nome_proprietario:
                            if codigo_proprietario:
                                proprietario, created = Proprietario.objects.get_or_create(
                                    codigo=codigo_proprietario,
                                    defaults={
                                        'nome_razao_social': nome_proprietario or '',
                                        'tipo': tipo_proprietario or 'PF',
                                        'status': 'sim'
                                    }
                                )
                                if not created:
                                    # Atualizar se necessário
                                    if nome_proprietario and proprietario.nome_razao_social != nome_proprietario:
                                        proprietario.nome_razao_social = nome_proprietario
                                    if tipo_proprietario and proprietario.tipo != tipo_proprietario:
                                        proprietario.tipo = tipo_proprietario
                                    proprietario.save()
                                    atualizados += 1
                                else:
                                    sucesso_proprietarios += 1
                            elif nome_proprietario:
                                # Buscar por nome se não tem código
                                proprietario = Proprietario.objects.filter(
                                    nome_razao_social__iexact=nome_proprietario
                                ).first()
                                if not proprietario:
                                    proprietario = Proprietario.objects.create(
                                        nome_razao_social=nome_proprietario,
                                        tipo=tipo_proprietario or 'PF',
                                        status='sim'
                                    )
                                    sucesso_proprietarios += 1

                        # Criar ou atualizar Carreta
                        carreta = None
                        if placa_carreta:
                            carreta, created = Carreta.objects.get_or_create(
                                placa=placa_carreta,
                                defaults={}
                            )
                            if created:
                                sucesso_carretas += 1
                            
                            # Se a carreta já está acoplada a outro cavalo, desacoplar
                            try:
                                cavalo_antigo = carreta.cavalo_acoplado
                                if cavalo_antigo and cavalo_antigo.placa != placa_cavalo:
                                    cavalo_antigo.carreta = None
                                    cavalo_antigo.save()
                            except Carreta.cavalo_acoplado.RelatedObjectDoesNotExist:
                                # Carreta não está acoplada, tudo bem
                                pass

                        # Buscar Motorista por nome
                        motorista = None
                        if nome_motorista:
                            motorista = Motorista.objects.filter(nome__iexact=nome_motorista).first()
                            if not motorista:
                                self.stdout.write(
                                    self.style.WARNING(f'Motorista nao encontrado: {nome_motorista} (linha {index + 2})')
                                )

                        # Criar ou atualizar Cavalo
                        cavalo, created = Cavalo.objects.get_or_create(
                            placa=placa_cavalo,
                            defaults={
                                'tipo': tipo_cavalo,
                                'fluxo': fluxo,
                                'situacao': 'ativo',
                                'proprietario': proprietario,
                                'carreta': carreta
                            }
                        )

                        if not created:
                            # Atualizar campos
                            atualizado = False
                            if tipo_cavalo and cavalo.tipo != tipo_cavalo:
                                cavalo.tipo = tipo_cavalo
                                atualizado = True
                            if fluxo and cavalo.fluxo != fluxo:
                                cavalo.fluxo = fluxo
                                atualizado = True
                            if cavalo.situacao != 'ativo':
                                cavalo.situacao = 'ativo'
                                atualizado = True
                            if proprietario and cavalo.proprietario != proprietario:
                                cavalo.proprietario = proprietario
                                atualizado = True
                            if carreta and cavalo.carreta != carreta:
                                cavalo.carreta = carreta
                                atualizado = True
                            
                            if atualizado:
                                cavalo.save()
                                atualizados += 1
                        else:
                            sucesso_cavalos += 1

                        # Associar motorista ao cavalo (se não estiver associado)
                        if motorista and not motorista.cavalo:
                            if not dry_run:
                                motorista.cavalo = cavalo
                                motorista.save()
                            else:
                                self.stdout.write(
                                    self.style.SUCCESS(f'[DRY-RUN] Associaria motorista {nome_motorista} ao cavalo {placa_cavalo}')
                                )

                        if not dry_run:
                            if created:
                                self.stdout.write(
                                    self.style.SUCCESS(f'Cavalo criado: {placa_cavalo}' + 
                                                     (f' (Motorista: {nome_motorista})' if nome_motorista else '') +
                                                     (f' (Carreta: {placa_carreta})' if placa_carreta else ''))
                                )
                            else:
                                self.stdout.write(
                                    self.style.WARNING(f'Cavalo atualizado: {placa_cavalo}')
                                )
                        else:
                            self.stdout.write(
                                self.style.SUCCESS(f'[DRY-RUN] Processaria: {placa_cavalo}')
                            )

                    except Exception as e:
                        erros += 1
                        self.stdout.write(
                            self.style.ERROR(f'Erro na linha {index + 2}: {str(e)}')
                        )
                        import traceback
                        self.stdout.write(traceback.format_exc())
                        continue

                if dry_run:
                    # Em dry-run, não commita a transação
                    transaction.set_rollback(True)

            # Resumo
            self.stdout.write('\n' + '='*50)
            self.stdout.write(self.style.SUCCESS('RESUMO DA IMPORTACAO:'))
            self.stdout.write(f'  [+] Cavalos criados: {sucesso_cavalos}')
            self.stdout.write(f'  [+] Carretas criadas: {sucesso_carretas}')
            self.stdout.write(f'  [+] Proprietarios criados: {sucesso_proprietarios}')
            self.stdout.write(f'  [+] Registros atualizados: {atualizados}')
            self.stdout.write(f'  [-] Erros: {erros}')
            if dry_run:
                self.stdout.write(self.style.WARNING('\n[AVISO] MODO DRY-RUN: Nenhum dado foi salvo!'))
            else:
                self.stdout.write(self.style.SUCCESS('\n[OK] Importacao concluida com sucesso!'))
                # Atualizar status dos proprietários
                self.stdout.write('Atualizando status dos proprietarios...')
                for proprietario in Proprietario.objects.all():
                    proprietario.atualizar_status_automatico()

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Erro ao processar arquivo: {str(e)}')
            )
            import traceback
            self.stdout.write(traceback.format_exc())

