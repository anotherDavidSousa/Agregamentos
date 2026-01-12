"""
Comando para importar placas de cavalos e carretas de um arquivo Excel.

Uso:
    python manage.py importar_placas_excel "D:\Downloads\faturamento_veiculos_gestores_v7_agregados.xls"
    
Ou em produção:
    python manage.py importar_placas_excel /caminho/para/arquivo.xls
"""

from django.core.management.base import BaseCommand
from django.db import transaction
import pandas as pd
import os
from pathlib import Path
from core.models import Cavalo, Carreta


class Command(BaseCommand):
    help = 'Importa placas de cavalos e carretas de um arquivo Excel'

    def add_arguments(self, parser):
        parser.add_argument(
            'arquivo',
            type=str,
            help='Caminho completo para o arquivo Excel (.xls ou .xlsx)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa sem salvar no banco (apenas mostra o que seria feito)',
        )

    def handle(self, *args, **options):
        arquivo_path = options['arquivo']
        dry_run = options['dry_run']

        # Verificar se o arquivo existe
        if not os.path.exists(arquivo_path):
            self.stdout.write(
                self.style.ERROR(f'❌ Arquivo não encontrado: {arquivo_path}')
            )
            return

        # Verificar extensão
        extensao = Path(arquivo_path).suffix.lower()
        if extensao not in ['.xls', '.xlsx']:
            self.stdout.write(
                self.style.ERROR(f'❌ Formato não suportado: {extensao}. Use .xls ou .xlsx')
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f'📄 Processando arquivo: {os.path.basename(arquivo_path)}')
        )

        try:
            # Ler arquivo Excel
            # Tentar diferentes engines
            df = None
            engines = ['xlrd', 'openpyxl'] if extensao == '.xls' else ['openpyxl', 'xlrd']
            
            for engine in engines:
                try:
                    df = pd.read_excel(arquivo_path, engine=engine, header=None)
                    self.stdout.write(f'✅ Arquivo lido com engine: {engine}')
                    break
                except ImportError:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️  Engine {engine} não disponível, tentando próximo...')
                    )
                    continue
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️  Erro com engine {engine}: {str(e)}, tentando próximo...')
                    )
                    continue

            if df is None:
                self.stdout.write(
                    self.style.ERROR('❌ Não foi possível ler o arquivo com nenhum engine disponível')
                )
                return

            # Remover linhas vazias
            df = df.dropna(how='all')
            
            # Verificar se tem pelo menos 2 colunas
            if df.shape[1] < 2:
                self.stdout.write(
                    self.style.ERROR('❌ Arquivo deve ter pelo menos 2 colunas (Cavalo e Carreta)')
                )
                return

            # Extrair placas (primeira e segunda coluna)
            # Remover linhas onde ambas as colunas estão vazias
            df = df[df.iloc[:, 0].notna() | df.iloc[:, 1].notna()]
            
            total_linhas = len(df)
            self.stdout.write(f'📊 Total de linhas encontradas: {total_linhas}')

            cavalos_criados = 0
            cavalos_ignorados = 0
            carretas_criadas = 0
            carretas_ignoradas = 0
            erros = []

            if dry_run:
                self.stdout.write(
                    self.style.WARNING('\n🔍 MODO DRY-RUN - Nenhum dado será salvo\n')
                )

            # Processar cada linha
            for idx, row in df.iterrows():
                try:
                    # Extrair placas (remover espaços e converter para string)
                    placa_cavalo_raw = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
                    placa_carreta_raw = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''

                    # Limpar placas (remover caracteres especiais, converter para maiúscula)
                    placa_cavalo = placa_cavalo_raw.upper().replace(' ', '').replace('-', '').replace('.', '') if placa_cavalo_raw else ''
                    placa_carreta = placa_carreta_raw.upper().replace(' ', '').replace('-', '').replace('.', '') if placa_carreta_raw else ''

                    # Validar formato de placa (ABC1234 ou ABC1D23)
                    if placa_cavalo and len(placa_cavalo) >= 7:
                        # Processar cavalo
                        if not dry_run:
                            cavalo, created = Cavalo.objects.get_or_create(
                                placa=placa_cavalo,
                                defaults={
                                    'situacao': 'ativo',
                                }
                            )
                            if created:
                                cavalos_criados += 1
                                self.stdout.write(
                                    f'✅ Cavalo criado: {placa_cavalo}'
                                )
                            else:
                                cavalos_ignorados += 1
                                self.stdout.write(
                                    f'⏭️  Cavalo já existe: {placa_cavalo}'
                                )
                        else:
                            # Dry run - verificar se existe
                            if Cavalo.objects.filter(placa=placa_cavalo).exists():
                                cavalos_ignorados += 1
                                self.stdout.write(
                                    f'⏭️  Cavalo já existe (seria ignorado): {placa_cavalo}'
                                )
                            else:
                                cavalos_criados += 1
                                self.stdout.write(
                                    f'✅ Cavalo seria criado: {placa_cavalo}'
                                )

                    # Processar carreta
                    if placa_carreta and len(placa_carreta) >= 7:
                        if not dry_run:
                            carreta, created = Carreta.objects.get_or_create(
                                placa=placa_carreta,
                                defaults={}
                            )
                            if created:
                                carretas_criadas += 1
                                self.stdout.write(
                                    f'✅ Carreta criada: {placa_carreta}'
                                )
                            else:
                                carretas_ignoradas += 1
                                self.stdout.write(
                                    f'⏭️  Carreta já existe: {placa_carreta}'
                                )
                        else:
                            # Dry run - verificar se existe
                            if Carreta.objects.filter(placa=placa_carreta).exists():
                                carretas_ignoradas += 1
                                self.stdout.write(
                                    f'⏭️  Carreta já existe (seria ignorada): {placa_carreta}'
                                )
                            else:
                                carretas_criadas += 1
                                self.stdout.write(
                                    f'✅ Carreta seria criada: {placa_carreta}'
                                )

                except Exception as e:
                    erro_msg = f'Erro na linha {idx + 1}: {str(e)}'
                    erros.append(erro_msg)
                    self.stdout.write(
                        self.style.ERROR(f'❌ {erro_msg}')
                    )
                    continue

            # Resumo
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS('📊 RESUMO DO PROCESSAMENTO'))
            self.stdout.write('='*60)
            self.stdout.write(f'✅ Cavalos criados: {cavalos_criados}')
            self.stdout.write(f'⏭️  Cavalos ignorados (já existiam): {cavalos_ignorados}')
            self.stdout.write(f'✅ Carretas criadas: {carretas_criadas}')
            self.stdout.write(f'⏭️  Carretas ignoradas (já existiam): {carretas_ignoradas}')
            
            if erros:
                self.stdout.write(
                    self.style.ERROR(f'\n❌ Erros encontrados: {len(erros)}')
                )
                for erro in erros[:10]:  # Mostrar apenas os 10 primeiros erros
                    self.stdout.write(self.style.ERROR(f'  - {erro}'))
                if len(erros) > 10:
                    self.stdout.write(
                        self.style.ERROR(f'  ... e mais {len(erros) - 10} erros')
                    )
            
            if dry_run:
                self.stdout.write(
                    self.style.WARNING('\n⚠️  MODO DRY-RUN - Nenhum dado foi salvo')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('\n✅ Processamento concluído com sucesso!')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erro ao processar arquivo: {str(e)}')
            )
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
