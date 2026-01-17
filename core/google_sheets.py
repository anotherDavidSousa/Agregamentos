"""
Módulo para sincronizar dados de Cavalos com Google Sheets

COMO FUNCIONA:
1. Quando um cavalo é salvo ou deletado, um signal é disparado
2. O signal chama a função de sincronização em background (thread)
3. A função busca todos os cavalos na mesma ordem do admin
4. Atualiza a planilha do Google Sheets com os dados

CONFIGURAÇÃO NECESSÁRIA (no settings.py):
- GOOGLE_SHEETS_CREDENTIALS_PATH: caminho para o arquivo JSON da Service Account
- GOOGLE_SHEETS_SPREADSHEET_ID: ID da planilha do Google Sheets
- GOOGLE_SHEETS_WORKSHEET_NAME: nome da aba (padrão: 'Cavalos')
- GOOGLE_SHEETS_ENABLED: True/False para habilitar/desabilitar (padrão: False)

COMO USAR:
1. Coloque o arquivo JSON da Service Account na pasta do projeto
2. Configure as variáveis no settings.py
3. Compartilhe a planilha com o email da Service Account (dá permissão de editor)
4. Execute: python manage.py sync_google_sheets (para sincronização manual)
"""

import os
import threading
import logging
from django.conf import settings
from django.db.models import Case, When, Value, IntegerField, F, CharField, Q

logger = logging.getLogger(__name__)


def sync_cavalos_to_sheets():
    """
    Função principal que sincroniza todos os cavalos com o Google Sheets
    
    Esta função:
    1. Busca todos os cavalos na mesma ordem do admin
    2. Prepara os dados no formato correto
    3. Atualiza a planilha do Google Sheets
    
    Retorna True se sucesso, False se erro
    """
    try:
        # Verificar se está habilitado
        if not getattr(settings, 'GOOGLE_SHEETS_ENABLED', False):
            logger.info("Sincronização com Google Sheets está desabilitada")
            return False
        
        # Importar aqui para evitar erro se não tiver instalado
        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            logger.error("Biblioteca gspread não instalada. Execute: pip install gspread")
            return False
        
        # Verificar configurações
        credentials_path = getattr(settings, 'GOOGLE_SHEETS_CREDENTIALS_PATH', None)
        spreadsheet_id = getattr(settings, 'GOOGLE_SHEETS_SPREADSHEET_ID', None)
        worksheet_name = getattr(settings, 'GOOGLE_SHEETS_WORKSHEET_NAME', 'Cavalos')
        
        if not credentials_path or not spreadsheet_id:
            logger.error("Configurações do Google Sheets não encontradas no settings.py")
            return False
        
        # Verificar se arquivo de credenciais existe
        if not os.path.exists(credentials_path):
            logger.error(f"Arquivo de credenciais não encontrado: {credentials_path}")
            return False
        
        # Conectar ao Google Sheets
        logger.info("Conectando ao Google Sheets...")
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        client = gspread.authorize(creds)
        
        # Abrir planilha
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        # Tentar abrir aba, criar se não existir
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
        except gspread.exceptions.WorksheetNotFound:
            logger.info(f"Aba '{worksheet_name}' não encontrada. Criando...")
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=20)
        
        # Buscar cavalos na mesma ordem do admin
        from .models import Cavalo
        
        cavalos = Cavalo.objects.select_related('motorista', 'carreta', 'proprietario', 'gestor').exclude(
            Q(carreta__isnull=True) | Q(situacao='desagregado')
        ).annotate(
            # Ordem de situação: ativo=0, parado=1
            ordem_situacao=Case(
                When(situacao='ativo', then=Value(0)),
                When(situacao='parado', then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
            ),
            # Ordem de fluxo: escória=0, minério=1
            ordem_fluxo=Case(
                When(fluxo='escoria', then=Value(0)),
                When(fluxo='minerio', then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
            ),
            # Ordem de tipo: toco=0, trucado=1
            ordem_tipo=Case(
                When(tipo='toco', then=Value(0)),
                When(tipo='trucado', then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
            ),
            # Nome do motorista para ordenação alfabética
            motorista_nome_ordem=Case(
                When(motorista__isnull=False, then=F('motorista__nome')),
                default=Value(''),
                output_field=CharField()
            )
        ).order_by(
            'ordem_situacao',
            'ordem_fluxo',
            'ordem_tipo',
            'motorista_nome_ordem'
        )
        
        # Preparar dados para a planilha
        # Cabeçalhos (mesma ordem das colunas do admin)
        headers = [
            'PLACA',
            'CARRETA',
            'MOTORISTA',
            'CPF',
            'TIPO',
            'FLUXO',
            'CÓDIGO DO PROPRIETÁRIO',
            'PROPRIETÁRIO',
            'SITUAÇÃO'
        ]
        
        # Dados dos cavalos
        rows = [headers]  # Primeira linha são os cabeçalhos
        
        for cavalo in cavalos:
            row = [
                cavalo.placa or '-',
                cavalo.carreta.placa if cavalo.carreta else '-',
                cavalo.motorista.nome if cavalo.motorista else '-',
                cavalo.motorista.cpf if cavalo.motorista and cavalo.motorista.cpf else '-',
                cavalo.get_tipo_display() if cavalo.tipo else '-',
                cavalo.get_fluxo_display() if cavalo.fluxo else '-',
                cavalo.proprietario.codigo if cavalo.proprietario and cavalo.proprietario.codigo else '-',
                cavalo.proprietario.nome_razao_social if cavalo.proprietario else '-',
                cavalo.get_situacao_display() if cavalo.situacao else '-',
            ]
            rows.append(row)
        
        # Limpar planilha e adicionar novos dados
        logger.info(f"Sincronizando {len(rows) - 1} cavalos para o Google Sheets...")
        
        # Limpar tudo primeiro
        worksheet.clear()
        
        # Adicionar dados (máximo de 1000 linhas por vez para evitar timeout)
        batch_size = 1000
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            # Calcular range (A1:Z1000)
            end_col = chr(64 + len(headers))  # A=65, B=66, etc.
            start_row = i + 1
            end_row = i + len(batch)
            range_name = f'A{start_row}:{end_col}{end_row}'
            
            worksheet.update(range_name, batch, value_input_option='RAW')
            logger.info(f"Atualizadas linhas {start_row} a {end_row}")
        
        logger.info("Sincronização com Google Sheets concluída com sucesso!")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao sincronizar com Google Sheets: {str(e)}", exc_info=True)
        return False


def sync_cavalos_async():
    """
    Executa a sincronização em uma thread separada (não bloqueia a requisição)
    
    Use esta função nos signals para não travar o Django quando salvar um cavalo
    """
    thread = threading.Thread(target=sync_cavalos_to_sheets, daemon=True)
    thread.start()
    logger.info("Sincronização com Google Sheets iniciada em background")
