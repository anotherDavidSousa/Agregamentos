"""
Comando para atualizar cavalos existentes com carreta e proprietário de um arquivo Excel.

Estrutura esperada:
- Coluna 1: Placa do cavalo
- Coluna 2: Placa da carreta acoplada
- Coluna 3: Nome do proprietário cadastrado

Uso:
    python manage.py atualizar_cavalos_excel "D:\Downloads\cavalos_atualizar.xlsx"
    
Ou em produção:
    python manage.py atualizar_cavalos_excel /caminho/para/arquivo.xlsx
"""

from django.core.management.base import BaseCommand
from django.db import transaction
import pandas as pd
import os
from pathlib import Path
from core.models import Cavalo, Carreta, Proprietario


class Command(BaseCommand):
    help = 'Atualiza cavalos existentes com carreta e proprietário de um arquivo Excel'

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

    def normalizar_placa(self, placa):
        """Normaliza placa (maiúscula, sem espaços)"""
        if not placa:
            return None
        placa_str = str(placa).strip().upper()
        placa_limpa = placa_str.replace(' ', '').replace('-', '').replace('.', '')
        return placa_limpa if placa_limpa else None

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
            
            # Verificar se tem pelo menos 3 colunas
            if df.shape[1] < 3:
                self.stdout.write(
                    self.style.ERROR('❌ Arquivo deve ter pelo menos 3 colunas (Placa Cavalo, Placa Carreta, Nome Proprietário)')
                )
                return

            # Verificar se primeira linha é cabeçalho
            primeira_linha = df.iloc[0]
            primeira_col = str(primeira_linha.iloc[0]).strip().lower() if pd.notna(primeira_linha.iloc[0]) else ''
            if 'placa' in primeira_col or 'cavalo' in primeira_col or 'carreta' in primeira_col or 'proprietario' in primeira_col or 'proprietário' in primeira_col:
                df = df.iloc[1:].reset_index(drop=True)
                self.stdout.write('ℹ️  Primeira linha (cabeçalho) ignorada')

            # Remover linhas onde todas as colunas estão vazias
            df = df[df.iloc[:, 0].notna() | df.iloc[:, 1].notna() | df.iloc[:, 2].notna()]
            
            total_linhas = len(df)
            self.stdout.write(f'📊 Total de linhas encontradas: {total_linhas}')

            cavalos_atualizados = 0
            cavalos_nao_encontrados = 0
            carretas_nao_encontradas = 0
            proprietarios_nao_encontrados = 0
            erros = []

            if dry_run:
                self.stdout.write(
                    self.style.WARNING('\n🔍 MODO DRY-RUN - Nenhum dado será salvo\n')
                )

            # Processar cada linha
            with transaction.atomic():
                for idx, row in df.iterrows():
                    try:
                        # Extrair dados das colunas
                        placa_cavalo_raw = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
                        placa_carreta_raw = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''
                        nome_proprietario_raw = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ''

                        # Validar placa do cavalo (obrigatória)
                        if not placa_cavalo_raw or placa_cavalo_raw.lower() in ['nan', 'none', '']:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'⚠️  Linha {idx + 2} ignorada: placa do cavalo vazia'
                                )
                            )
                            continue

                        # Normalizar placas
                        placa_cavalo = self.normalizar_placa(placa_cavalo_raw)
                        placa_carreta = self.normalizar_placa(placa_carreta_raw)

                        # Buscar cavalo pela placa
                        cavalo = Cavalo.objects.filter(placa=placa_cavalo).first()
                        if not cavalo:
                            cavalos_nao_encontrados += 1
                            self.stdout.write(
                                self.style.ERROR(
                                    f'❌ Cavalo não encontrado: {placa_cavalo} (linha {idx + 2})'
                                )
                            )
                            continue

                        # Buscar carreta pela placa (se fornecida)
                        carreta = None
                        if placa_carreta:
                            carreta = Carreta.objects.filter(placa=placa_carreta).first()
                            if not carreta:
                                carretas_nao_encontradas += 1
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'⚠️  Carreta não encontrada: {placa_carreta} (linha {idx + 2})'
                                    )
                                )
                            else:
                                # Se a carreta já está acoplada a outro cavalo, desacoplar
                                try:
                                    cavalo_anterior = carreta.cavalo_acoplado
                                    if cavalo_anterior and cavalo_anterior.id != cavalo.id:
                                        if not dry_run:
                                            cavalo_anterior.carreta = None
                                            cavalo_anterior.save()
                                        self.stdout.write(
                                            self.style.WARNING(
                                                f'ℹ️  Carreta {placa_carreta} desacoplada do cavalo {cavalo_anterior.placa} (linha {idx + 2})'
                                            )
                                        )
                                except:
                                    # Carreta não está acoplada, tudo bem
                                    pass

                        # Buscar proprietário pelo nome (se fornecido)
                        proprietario = None
                        if nome_proprietario_raw and nome_proprietario_raw.lower() not in ['nan', 'none', '']:
                            proprietario = Proprietario.objects.filter(
                                nome_razao_social__iexact=nome_proprietario_raw
                            ).first()
                            if not proprietario:
                                proprietarios_nao_encontrados += 1
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'⚠️  Proprietário não encontrado: {nome_proprietario_raw} (linha {idx + 2})'
                                    )
                                )

                        # Atualizar cavalo
                        atualizado = False
                        mudancas = []

                        # Atualizar carreta
                        if carreta and cavalo.carreta != carreta:
                            if not dry_run:
                                cavalo.carreta = carreta
                            atualizado = True
                            mudancas.append(f'Carreta: {placa_carreta}')
                        elif not carreta and cavalo.carreta:
                            # Se não foi fornecida carreta mas o cavalo tem uma, não remove
                            pass

                        # Atualizar proprietário
                        if proprietario and cavalo.proprietario != proprietario:
                            if not dry_run:
                                cavalo.proprietario = proprietario
                            atualizado = True
                            mudancas.append(f'Proprietário: {nome_proprietario_raw}')

                        if atualizado:
                            if not dry_run:
                                cavalo.save()
                            cavalos_atualizados += 1
                            self.stdout.write(
                                f'✅ Cavalo atualizado: {placa_cavalo} - {", ".join(mudancas)}'
                            )
                        else:
                            self.stdout.write(
                                f'ℹ️  Cavalo {placa_cavalo} sem alterações necessárias'
                            )

                    except Exception as e:
                        erro_msg = f'Erro na linha {idx + 2}: {str(e)}'
                        erros.append(erro_msg)
                        self.stdout.write(
                            self.style.ERROR(f'❌ {erro_msg}')
                        )
                        continue

                if dry_run:
                    transaction.set_rollback(True)

            # Resumo
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS('📊 RESUMO DO PROCESSAMENTO'))
            self.stdout.write('='*60)
            self.stdout.write(f'✅ Cavalos atualizados: {cavalos_atualizados}')
            if cavalos_nao_encontrados > 0:
                self.stdout.write(
                    self.style.ERROR(f'❌ Cavalos não encontrados: {cavalos_nao_encontrados}')
                )
            if carretas_nao_encontradas > 0:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Carretas não encontradas: {carretas_nao_encontradas}')
                )
            if proprietarios_nao_encontrados > 0:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Proprietários não encontrados: {proprietarios_nao_encontrados}')
                )
            
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
