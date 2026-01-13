"""
Comando para importar proprietários/parceiros de um arquivo Excel.

Estrutura esperada:
- Coluna 1: Código do proprietário (remover pontos, apenas números)
- Coluna 2: Nome do proprietário
- Coluna 3: Tipo (PF ou PJ)

Uso:
    python manage.py importar_proprietarios_excel "D:\Downloads\proprietarios.xlsx"
    
Ou em produção:
    python manage.py importar_proprietarios_excel /caminho/para/arquivo.xlsx
"""

from django.core.management.base import BaseCommand
from django.db import transaction
import pandas as pd
import os
import re
from pathlib import Path
from core.models import Proprietario


class Command(BaseCommand):
    help = 'Importa proprietários/parceiros de um arquivo Excel (Código, Nome, Tipo)'

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

    def normalizar_codigo(self, codigo):
        """Remove pontos e formatação, deixando apenas números"""
        if not codigo:
            return None
        codigo_str = str(codigo).strip()
        # Remove tudo que não é número
        codigo_limpo = re.sub(r'[^0-9]', '', codigo_str)
        return codigo_limpo if codigo_limpo else None

    def normalizar_tipo(self, tipo):
        """Normaliza tipo para PF ou PJ"""
        if not tipo:
            return None
        tipo_str = str(tipo).strip().upper()
        if tipo_str in ['PF', 'PESSOA FÍSICA', 'PESSOA FISICA', 'F', 'FÍSICA', 'FISICA']:
            return 'PF'
        elif tipo_str in ['PJ', 'PESSOA JURÍDICA', 'PESSOA JURIDICA', 'J', 'JURÍDICA', 'JURIDICA']:
            return 'PJ'
        return None

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
                    self.style.ERROR('❌ Arquivo deve ter pelo menos 3 colunas (Código, Nome, Tipo)')
                )
                return

            # Verificar se primeira linha é cabeçalho
            primeira_linha = df.iloc[0]
            primeira_col = str(primeira_linha.iloc[0]).strip().lower() if pd.notna(primeira_linha.iloc[0]) else ''
            if 'código' in primeira_col or 'codigo' in primeira_col or 'nome' in primeira_col or 'tipo' in primeira_col:
                df = df.iloc[1:].reset_index(drop=True)
                self.stdout.write('ℹ️  Primeira linha (cabeçalho) ignorada')

            # Remover linhas onde todas as colunas estão vazias
            df = df[df.iloc[:, 0].notna() | df.iloc[:, 1].notna() | df.iloc[:, 2].notna()]
            
            total_linhas = len(df)
            self.stdout.write(f'📊 Total de linhas encontradas: {total_linhas}')

            proprietarios_criados = 0
            proprietarios_ignorados = 0
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
                        codigo_raw = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
                        nome_raw = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''
                        tipo_raw = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ''

                        # Validar nome (obrigatório)
                        if not nome_raw or nome_raw.lower() in ['nan', 'none', '']:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'⚠️  Linha {idx + 2} ignorada: nome vazio'
                                )
                            )
                            continue

                        # Normalizar código e tipo
                        codigo = self.normalizar_codigo(codigo_raw)
                        tipo = self.normalizar_tipo(tipo_raw)

                        # Se não tem tipo válido, usar PF como padrão
                        if not tipo:
                            tipo = 'PF'
                            self.stdout.write(
                                self.style.WARNING(
                                    f'⚠️  Tipo inválido na linha {idx + 2}, usando PF como padrão'
                                )
                            )

                        # Buscar proprietário existente (por código ou nome)
                        proprietario_existente = None
                        if codigo:
                            proprietario_existente = Proprietario.objects.filter(codigo=codigo).first()
                        
                        if not proprietario_existente:
                            proprietario_existente = Proprietario.objects.filter(
                                nome_razao_social__iexact=nome_raw
                            ).first()

                        # Se proprietário já existe, ignorar
                        if proprietario_existente:
                            proprietarios_ignorados += 1
                            self.stdout.write(
                                f'⏭️  Proprietário já existe (ignorado): {nome_raw}' +
                                (f' (Código: {codigo})' if codigo else '')
                            )
                            continue

                        # Criar proprietário
                        if not dry_run:
                            proprietario = Proprietario.objects.create(
                                codigo=codigo,
                                nome_razao_social=nome_raw,
                                tipo=tipo,
                                status='sim'
                            )
                            proprietarios_criados += 1
                            self.stdout.write(
                                f'✅ Proprietário criado: {nome_raw}' +
                                (f' (Código: {codigo})' if codigo else '') +
                                f' (Tipo: {tipo})'
                            )
                        else:
                            proprietarios_criados += 1
                            self.stdout.write(
                                f'✅ Proprietário seria criado: {nome_raw}' +
                                (f' (Código: {codigo})' if codigo else '') +
                                f' (Tipo: {tipo})'
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
            self.stdout.write(f'✅ Proprietários criados: {proprietarios_criados}')
            self.stdout.write(f'⏭️  Proprietários ignorados (já existiam): {proprietarios_ignorados}')
            
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
