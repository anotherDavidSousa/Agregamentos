"""
Comando Django para importar motoristas de um arquivo Excel.

Uso:
    python manage.py importar_motoristas "D:\\Downloads\\motoristas.xlsx"
    
Ou sem especificar o caminho (usa o padrao):
    python manage.py importar_motoristas
"""

from django.core.management.base import BaseCommand
from core.models import Motorista
import pandas as pd
import os
from django.db import transaction


class Command(BaseCommand):
    help = 'Importa motoristas de um arquivo Excel'

    def add_arguments(self, parser):
        parser.add_argument(
            'arquivo',
            nargs='?',
            type=str,
            default=r'D:\Downloads\motoristas.xlsx',
            help='Caminho do arquivo Excel com os motoristas'
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
                self.style.ERROR(f'Arquivo não encontrado: {arquivo_path}')
            )
            return

        self.stdout.write(f'Lendo arquivo: {arquivo_path}')

        try:
            # Ler o arquivo Excel
            df = pd.read_excel(arquivo_path)
            
            self.stdout.write(f'Total de linhas no Excel: {len(df)}')
            self.stdout.write(f'Colunas encontradas: {", ".join(df.columns.tolist())}')

            # Normalizar nomes das colunas (remover espaços, converter para minúsculas)
            df.columns = df.columns.str.strip().str.lower()
            
            # Mapear colunas possíveis
            nome_col = None
            cpf_col = None
            whatsapp_col = None

            # Tentar encontrar as colunas
            for col in df.columns:
                col_lower = col.lower()
                if 'nome' in col_lower and nome_col is None:
                    nome_col = col
                elif 'cpf' in col_lower and cpf_col is None:
                    cpf_col = col
                elif 'whatsapp' in col_lower or 'whats' in col_lower or 'telefone' in col_lower or 'fone' in col_lower:
                    if whatsapp_col is None:
                        whatsapp_col = col

            if nome_col is None:
                self.stdout.write(
                    self.style.ERROR('Coluna "nome" não encontrada no arquivo!')
                )
                self.stdout.write(f'Colunas disponíveis: {", ".join(df.columns.tolist())}')
                return

            self.stdout.write(f'Coluna Nome: {nome_col}')
            if cpf_col:
                self.stdout.write(f'Coluna CPF: {cpf_col}')
            if whatsapp_col:
                self.stdout.write(f'Coluna WhatsApp: {whatsapp_col}')

            # Processar cada linha
            sucesso = 0
            erros = 0
            duplicados = 0
            ignorados = 0

            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        nome = str(row[nome_col]).strip() if pd.notna(row[nome_col]) else None
                        
                        if not nome or nome == 'nan' or nome == '':
                            ignorados += 1
                            continue

                        cpf = None
                        if cpf_col and pd.notna(row[cpf_col]):
                            cpf_str = str(row[cpf_col]).strip()
                            # Remover formatação do CPF (pontos, traços, espaços)
                            cpf = ''.join(filter(str.isdigit, cpf_str))
                            if cpf == '':
                                cpf = None

                        whatsapp = None
                        if whatsapp_col and pd.notna(row[whatsapp_col]):
                            whatsapp_str = str(row[whatsapp_col]).strip()
                            # Remover formatação do WhatsApp
                            whatsapp = ''.join(filter(lambda x: x.isdigit() or x in ['+', '-', '(', ')', ' '], whatsapp_str))
                            if whatsapp == '':
                                whatsapp = None

                        # Verificar se já existe motorista com mesmo CPF (se fornecido)
                        if cpf:
                            motorista_existente = Motorista.objects.filter(cpf=cpf).first()
                            if motorista_existente:
                                if not dry_run:
                                    # Atualizar dados existentes
                                    motorista_existente.nome = nome
                                    if whatsapp:
                                        motorista_existente.whatsapp = whatsapp
                                    motorista_existente.save()
                                    self.stdout.write(
                                        self.style.WARNING(f'Atualizado: {nome} (CPF: {cpf})')
                                    )
                                else:
                                    self.stdout.write(
                                        self.style.WARNING(f'[DRY-RUN] Atualizaria: {nome} (CPF: {cpf})')
                                    )
                                duplicados += 1
                                continue

                        # Verificar se já existe motorista com mesmo nome
                        motorista_existente = Motorista.objects.filter(nome__iexact=nome).first()
                        if motorista_existente:
                            if not dry_run:
                                # Atualizar dados existentes
                                if cpf:
                                    motorista_existente.cpf = cpf
                                if whatsapp:
                                    motorista_existente.whatsapp = whatsapp
                                motorista_existente.save()
                                self.stdout.write(
                                    self.style.WARNING(f'Atualizado: {nome}')
                                )
                            else:
                                self.stdout.write(
                                    self.style.WARNING(f'[DRY-RUN] Atualizaria: {nome}')
                                )
                            duplicados += 1
                            continue

                        # Criar novo motorista
                        if not dry_run:
                            Motorista.objects.create(
                                nome=nome,
                                cpf=cpf,
                                whatsapp=whatsapp
                            )
                            self.stdout.write(
                                self.style.SUCCESS(f'Criado: {nome}' + (f' (CPF: {cpf})' if cpf else ''))
                            )
                        else:
                            self.stdout.write(
                                self.style.SUCCESS(f'[DRY-RUN] Criaria: {nome}' + (f' (CPF: {cpf})' if cpf else ''))
                            )
                        sucesso += 1

                    except Exception as e:
                        erros += 1
                        self.stdout.write(
                            self.style.ERROR(f'Erro na linha {index + 2}: {str(e)}')
                        )
                        continue

                if dry_run:
                    # Em dry-run, não commita a transação
                    transaction.set_rollback(True)

            # Resumo
            self.stdout.write('\n' + '='*50)
            self.stdout.write(self.style.SUCCESS('RESUMO DA IMPORTACAO:'))
            self.stdout.write(f'  [+] Criados/Atualizados: {sucesso + duplicados}')
            self.stdout.write(f'  [+] Novos: {sucesso}')
            self.stdout.write(f'  [+] Atualizados: {duplicados}')
            self.stdout.write(f'  [-] Erros: {erros}')
            self.stdout.write(f'  [-] Ignorados (sem nome): {ignorados}')
            if dry_run:
                self.stdout.write(self.style.WARNING('\n[AVISO] MODO DRY-RUN: Nenhum dado foi salvo!'))
            else:
                self.stdout.write(self.style.SUCCESS('\n[OK] Importacao concluida com sucesso!'))

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Erro ao processar arquivo: {str(e)}')
            )
            import traceback
            self.stdout.write(traceback.format_exc())

