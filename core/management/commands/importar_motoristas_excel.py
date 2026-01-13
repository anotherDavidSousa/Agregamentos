"""
Comando para importar motoristas de um arquivo Excel.

Estrutura esperada:
- Coluna 1: Nome do motorista
- Coluna 2: CPF do motorista
- Coluna 3: Placa do cavalo que o motorista trabalha

Uso:
    python manage.py importar_motoristas_excel "D:\Downloads\motoristas.xlsx"
    
Ou em produção:
    python manage.py importar_motoristas_excel /caminho/para/arquivo.xlsx
"""

from django.core.management.base import BaseCommand
from django.db import transaction
import pandas as pd
import os
import re
from pathlib import Path
from core.models import Motorista, Cavalo


class Command(BaseCommand):
    help = 'Importa motoristas de um arquivo Excel (Nome, CPF, Cavalo)'

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

    def normalizar_cpf(self, cpf):
        """Remove formatação do CPF, deixando apenas números"""
        if not cpf:
            return None
        cpf_str = str(cpf).strip()
        # Remove tudo que não é número
        cpf_limpo = re.sub(r'[^0-9]', '', cpf_str)
        return cpf_limpo if cpf_limpo else None

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
                    self.style.ERROR('❌ Arquivo deve ter pelo menos 3 colunas (Nome, CPF, Cavalo)')
                )
                return

            # Verificar se primeira linha é cabeçalho
            primeira_linha = df.iloc[0]
            primeira_col = str(primeira_linha.iloc[0]).strip().lower() if pd.notna(primeira_linha.iloc[0]) else ''
            if 'nome' in primeira_col or 'cpf' in primeira_col or 'cavalo' in primeira_col:
                df = df.iloc[1:].reset_index(drop=True)
                self.stdout.write('ℹ️  Primeira linha (cabeçalho) ignorada')

            # Remover linhas onde todas as colunas estão vazias
            df = df[df.iloc[:, 0].notna() | df.iloc[:, 1].notna() | df.iloc[:, 2].notna()]
            
            total_linhas = len(df)
            self.stdout.write(f'📊 Total de linhas encontradas: {total_linhas}')

            motoristas_criados = 0
            motoristas_ignorados = 0
            motoristas_atualizados = 0
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
                        nome_raw = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
                        cpf_raw = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''
                        placa_cavalo_raw = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ''

                        # Validar nome
                        if not nome_raw or nome_raw.lower() in ['nan', 'none', '']:
                            continue

                        # Normalizar CPF e placa
                        cpf = self.normalizar_cpf(cpf_raw)
                        placa_cavalo = self.normalizar_placa(placa_cavalo_raw)

                        # Buscar motorista existente (por CPF ou nome)
                        motorista_existente = None
                        if cpf:
                            motorista_existente = Motorista.objects.filter(cpf=cpf).first()
                        
                        if not motorista_existente:
                            motorista_existente = Motorista.objects.filter(nome__iexact=nome_raw).first()

                        # Se motorista já existe, ignorar
                        if motorista_existente:
                            motoristas_ignorados += 1
                            self.stdout.write(
                                f'⏭️  Motorista já existe (ignorado): {nome_raw}'
                            )
                            continue

                        # Buscar cavalo pela placa
                        cavalo = None
                        if placa_cavalo:
                            cavalo = Cavalo.objects.filter(placa=placa_cavalo).first()
                            if not cavalo:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'⚠️  Cavalo não encontrado: {placa_cavalo} (linha {idx + 2})'
                                    )
                                )

                        # Criar motorista
                        if not dry_run:
                            motorista = Motorista.objects.create(
                                nome=nome_raw,
                                cpf=cpf,
                                cavalo=cavalo
                            )
                            motoristas_criados += 1
                            self.stdout.write(
                                f'✅ Motorista criado: {nome_raw}' +
                                (f' (CPF: {cpf})' if cpf else '') +
                                (f' (Cavalo: {placa_cavalo})' if placa_cavalo and cavalo else '')
                            )
                        else:
                            motoristas_criados += 1
                            self.stdout.write(
                                f'✅ Motorista seria criado: {nome_raw}' +
                                (f' (CPF: {cpf})' if cpf else '') +
                                (f' (Cavalo: {placa_cavalo})' if placa_cavalo else '')
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
            self.stdout.write(f'✅ Motoristas criados: {motoristas_criados}')
            self.stdout.write(f'⏭️  Motoristas ignorados (já existiam): {motoristas_ignorados}')
            
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
