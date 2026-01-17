"""
Módulo para sincronizar dados de Cavalos com Google Sheets

COMO FUNCIONA:
1. Quando um cavalo é salvo ou deletado, um signal é disparado
2. O signal chama a função específica (adicionar/atualizar/deletar) em background
3. A função busca a linha na planilha pela placa e atualiza apenas aquela linha
4. Preserva todas as formatações e colunas extras

CONFIGURAÇÃO NECESSÁRIA (no settings.py):
- GOOGLE_SHEETS_CREDENTIALS_PATH: caminho para o arquivo JSON da Service Account
- GOOGLE_SHEETS_SPREADSHEET_ID: ID da planilha do Google Sheets
- GOOGLE_SHEETS_WORKSHEET_NAME: nome da aba (padrão: 'Cavalos')
- GOOGLE_SHEETS_ENABLED: True/False para habilitar/desabilitar (padrão: False)
"""

import os
import threading
import logging
from django.conf import settings
from django.db.models import Case, When, Value, IntegerField, F, CharField, Q

logger = logging.getLogger(__name__)


def _get_worksheet():
    """
    Função auxiliar para obter a worksheet do Google Sheets
    Retorna a worksheet ou None se houver erro
    """
    try:
        # Verificar se está habilitado
        if not getattr(settings, 'GOOGLE_SHEETS_ENABLED', False):
            return None
        
        # Importar aqui para evitar erro se não tiver instalado
        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            logger.error("Biblioteca gspread não instalada. Execute: pip install gspread")
            return None
        
        # Verificar configurações
        credentials_path = getattr(settings, 'GOOGLE_SHEETS_CREDENTIALS_PATH', None)
        spreadsheet_id = getattr(settings, 'GOOGLE_SHEETS_SPREADSHEET_ID', None)
        worksheet_name = getattr(settings, 'GOOGLE_SHEETS_WORKSHEET_NAME', 'Cavalos')
        
        if not credentials_path or not spreadsheet_id:
            logger.error("Configurações do Google Sheets não encontradas no settings.py")
            return None
        
        # Verificar se arquivo de credenciais existe
        if not os.path.exists(credentials_path):
            logger.error(f"Arquivo de credenciais não encontrado: {credentials_path}")
            return None
        
        # Conectar ao Google Sheets
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
            # Criar cabeçalhos na primeira vez (com colunas extras vazias C e D)
            headers = [
                'PLACA', 'CARRETA', '', '', 'MOTORISTA', 'CPF', 'TIPO', 'FLUXO',
                'CLASSIFICAÇÃO', 'CÓDIGO DO PROPRIETÁRIO', 'PROPRIETÁRIO', 'SITUAÇÃO'
            ]
            worksheet.update('A1:L1', [headers], value_input_option='RAW')
        
        return worksheet
        
    except Exception as e:
        logger.error(f"Erro ao conectar ao Google Sheets: {str(e)}", exc_info=True)
        return None


def _find_row_by_placa(worksheet, placa):
    """
    Encontra o número da linha na planilha pela placa (coluna A)
    Retorna o número da linha (1-indexed) ou None se não encontrar
    """
    try:
        # Buscar todas as placas na coluna A (começando da linha 2, pois linha 1 é cabeçalho)
        placas = worksheet.col_values(1)  # Coluna A
        
        # Procurar a placa (ignorar linha 1 que é cabeçalho)
        for idx, placa_na_planilha in enumerate(placas[1:], start=2):  # Começa na linha 2
            if placa_na_planilha and placa_na_planilha.strip().upper() == placa.strip().upper():
                return idx
        
        return None
        
    except Exception as e:
        logger.error(f"Erro ao buscar placa na planilha: {str(e)}")
        return None


def _get_column_mapping():
    """
    Define o mapeamento de colunas do banco de dados para as colunas da planilha
    
    Estrutura da planilha:
    - Coluna A: PLACA (cavalo)
    - Coluna B: CARRETA
    - Coluna C: [Coluna extra do usuário - NÃO TOCAR]
    - Coluna D: [Coluna extra do usuário - NÃO TOCAR]
    - Coluna E: MOTORISTA
    - Coluna F: CPF
    - Coluna G: TIPO
    - Coluna H: FLUXO
    - Coluna I: CÓDIGO DO PROPRIETÁRIO
    - Coluna J: PROPRIETÁRIO
    - Coluna K: SITUAÇÃO
    
    Retorna um dicionário com os dados do cavalo mapeados para as colunas corretas
    """
    return {
        'A': 'placa',           # PLACA (cavalo)
        'B': 'carreta',        # CARRETA
        # 'C': None,            # Coluna extra do usuário - NÃO TOCAR
        # 'D': None,            # Coluna extra do usuário - NÃO TOCAR
        'E': 'motorista',      # MOTORISTA
        'F': 'cpf',            # CPF
        'G': 'tipo',           # TIPO
        'H': 'fluxo',          # FLUXO
        'I': 'codigo_proprietario',  # CÓDIGO DO PROPRIETÁRIO
        'J': 'proprietario',   # PROPRIETÁRIO
        'K': 'situacao',       # SITUAÇÃO
    }


def _get_cavalo_row_data(cavalo):
    """
    Prepara os dados de uma linha do cavalo no formato da planilha
    Retorna um dicionário com os valores mapeados por coluna (A, B, E, F, etc.)
    """
    # Tratar motorista de forma segura (OneToOne reverso pode lançar exceção)
    try:
        motorista_nome = cavalo.motorista.nome if cavalo.motorista else '-'
        motorista_cpf = cavalo.motorista.cpf if cavalo.motorista and cavalo.motorista.cpf else '-'
    except Exception:
        motorista_nome = '-'
        motorista_cpf = '-'
    
    # Retornar dicionário mapeado por coluna
    return {
        'A': cavalo.placa or '-',
        'B': cavalo.carreta.placa if cavalo.carreta else '-',
        # C e D são colunas extras do usuário - não preencher
        'E': motorista_nome,
        'F': motorista_cpf,
        'G': cavalo.get_tipo_display() if cavalo.tipo else '-',
        'H': cavalo.get_fluxo_display() if cavalo.fluxo else '-',
        'I': cavalo.get_classificacao_display() if cavalo.classificacao else '-',
        'J': cavalo.proprietario.codigo if cavalo.proprietario and cavalo.proprietario.codigo else '-',
        'K': cavalo.proprietario.nome_razao_social if cavalo.proprietario else '-',
        'L': cavalo.get_situacao_display() if cavalo.situacao else '-',
    }


def _get_insert_position(worksheet, cavalo):
    """
    Calcula a posição correta para inserir o cavalo na planilha
    Baseado na mesma ordenação do admin/template
    Retorna o número da linha onde deve ser inserido
    """
    try:
        from .models import Cavalo
        
        # Buscar todos os cavalos na ordem correta
        todos_cavalos = Cavalo.objects.select_related('motorista', 'carreta', 'proprietario', 'gestor').exclude(
            Q(carreta__isnull=True) | Q(situacao='desagregado')
        ).annotate(
            ordem_situacao=Case(
                When(situacao='ativo', then=Value(0)),
                When(situacao='parado', then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
            ),
            ordem_fluxo=Case(
                When(fluxo='escoria', then=Value(0)),
                When(fluxo='minerio', then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
            ),
            ordem_tipo=Case(
                When(tipo='toco', then=Value(0)),
                When(tipo='trucado', then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
            ),
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
        
        # Calcular a posição do cavalo atual na ordem
        cavalo_ordem = (
            (0 if cavalo.situacao == 'ativo' else 1 if cavalo.situacao == 'parado' else 2),
            (0 if cavalo.fluxo == 'escoria' else 1 if cavalo.fluxo == 'minerio' else 2),
            (0 if cavalo.tipo == 'toco' else 1 if cavalo.tipo == 'trucado' else 2),
            (cavalo.motorista.nome if cavalo.motorista else '')
        )
        
        # Contar quantos cavalos vêm antes deste na ordem
        posicao = 1  # Começa na linha 2 (linha 1 é cabeçalho)
        for outro_cavalo in todos_cavalos:
            if outro_cavalo.pk == cavalo.pk:
                break
            outro_ordem = (
                (0 if outro_cavalo.situacao == 'ativo' else 1 if outro_cavalo.situacao == 'parado' else 2),
                (0 if outro_cavalo.fluxo == 'escoria' else 1 if outro_cavalo.fluxo == 'minerio' else 2),
                (0 if outro_cavalo.tipo == 'toco' else 1 if outro_cavalo.tipo == 'trucado' else 2),
                (outro_cavalo.motorista.nome if outro_cavalo.motorista else '')
            )
            if outro_ordem < cavalo_ordem:
                posicao += 1
        
        return posicao + 1  # +1 porque linha 1 é cabeçalho
        
    except Exception as e:
        logger.error(f"Erro ao calcular posição de inserção: {str(e)}")
        # Se der erro, insere no final
        try:
            all_values = worksheet.get_all_values()
            return len([row for row in all_values[1:] if any(cell.strip() for cell in row)]) + 2
        except:
            return 2


def update_cavalo_in_sheets(cavalo_pk):
    """
    Atualiza um cavalo específico na planilha do Google Sheets
    
    Args:
        cavalo_pk: ID do cavalo a ser atualizado
    """
    try:
        from .models import Cavalo
        
        # Buscar o cavalo
        try:
            cavalo = Cavalo.objects.select_related('motorista', 'carreta', 'proprietario').get(pk=cavalo_pk)
        except Cavalo.DoesNotExist:
            logger.warning(f"Cavalo com ID {cavalo_pk} não encontrado")
            return False
        
        # Verificar se deve ser exibido (tem carreta e não está desagregado)
        if not cavalo.carreta or cavalo.situacao == 'desagregado':
            # Se não deve ser exibido, deletar da planilha se existir
            return delete_cavalo_from_sheets(cavalo.placa)
        
        # Obter worksheet
        worksheet = _get_worksheet()
        if not worksheet:
            return False
        
        # Buscar linha na planilha pela placa
        if not cavalo.placa:
            logger.warning(f"Cavalo {cavalo_pk} não tem placa")
            return False
        
        row_num = _find_row_by_placa(worksheet, cavalo.placa)
        
        if row_num:
            # Atualizar linha existente - apenas as colunas do banco de dados
            row_data_dict = _get_cavalo_row_data(cavalo)
            
            # Atualizar cada coluna individualmente (pulando C e D que são extras do usuário)
            updates = []
            for col, value in row_data_dict.items():
                updates.append({
                    'range': f'{col}{row_num}',
                    'values': [[value]]
                })
            
            # Fazer update em lote para todas as colunas de uma vez
            worksheet.batch_update(updates, value_input_option='RAW')
            logger.info(f"Cavalo {cavalo.placa} atualizado na linha {row_num} do Google Sheets (colunas: {', '.join(row_data_dict.keys())})")
            return True
        else:
            # Não encontrou na planilha, adicionar nova linha
            return add_cavalo_to_sheets(cavalo_pk)
        
    except Exception as e:
        logger.error(f"Erro ao atualizar cavalo no Google Sheets: {str(e)}", exc_info=True)
        return False


def add_cavalo_to_sheets(cavalo_pk):
    """
    Adiciona um novo cavalo na planilha do Google Sheets na posição correta
    
    Args:
        cavalo_pk: ID do cavalo a ser adicionado
    """
    try:
        from .models import Cavalo
        
        # Buscar o cavalo
        try:
            cavalo = Cavalo.objects.select_related('motorista', 'carreta', 'proprietario').get(pk=cavalo_pk)
        except Cavalo.DoesNotExist:
            logger.warning(f"Cavalo com ID {cavalo_pk} não encontrado")
            return False
        
        # Verificar se deve ser exibido
        if not cavalo.carreta or cavalo.situacao == 'desagregado':
            logger.info(f"Cavalo {cavalo.placa} não será adicionado (sem carreta ou desagregado)")
            return False
        
        if not cavalo.placa:
            logger.warning(f"Cavalo {cavalo_pk} não tem placa")
            return False
        
        # Verificar se já existe na planilha
        worksheet = _get_worksheet()
        if not worksheet:
            return False
        
        if _find_row_by_placa(worksheet, cavalo.placa):
            logger.info(f"Cavalo {cavalo.placa} já existe na planilha. Atualizando...")
            return update_cavalo_in_sheets(cavalo_pk)
        
        # Calcular posição de inserção
        row_num = _get_insert_position(worksheet, cavalo)
        
        # Preparar dados - criar lista completa com colunas vazias para C e D
        row_data_dict = _get_cavalo_row_data(cavalo)
        
            # Criar lista completa de valores (incluindo colunas vazias C e D)
            # Ordem: A, B, C (vazio), D (vazio), E, F, G, H, I, J, K, L
            row_data_list = [
                row_data_dict.get('A', ''),
                row_data_dict.get('B', ''),
                '',  # Coluna C - extra do usuário (vazia)
                '',  # Coluna D - extra do usuário (vazia)
                row_data_dict.get('E', ''),
                row_data_dict.get('F', ''),
                row_data_dict.get('G', ''),
                row_data_dict.get('H', ''),
                row_data_dict.get('I', ''),
                row_data_dict.get('J', ''),
                row_data_dict.get('K', ''),
                row_data_dict.get('L', ''),
            ]
        
        # Inserir linha na posição correta
        worksheet.insert_row(row_data_list, row_num, value_input_option='RAW')
        logger.info(f"Cavalo {cavalo.placa} adicionado na linha {row_num} do Google Sheets")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao adicionar cavalo no Google Sheets: {str(e)}", exc_info=True)
        return False


def delete_cavalo_from_sheets(placa):
    """
    Deleta um cavalo da planilha do Google Sheets pela placa
    
    Args:
        placa: Placa do cavalo a ser deletado
    """
    try:
        if not placa:
            return False
        
        worksheet = _get_worksheet()
        if not worksheet:
            return False
        
        # Buscar linha na planilha
        row_num = _find_row_by_placa(worksheet, placa)
        
        if row_num:
            # Deletar linha
            worksheet.delete_rows(row_num)
            logger.info(f"Cavalo {placa} deletado da linha {row_num} do Google Sheets")
            return True
        else:
            logger.info(f"Cavalo {placa} não encontrado na planilha para deletar")
            return False
        
    except Exception as e:
        logger.error(f"Erro ao deletar cavalo do Google Sheets: {str(e)}", exc_info=True)
        return False


def sync_cavalos_to_sheets():
    """
    Função de sincronização completa (mantida para compatibilidade)
    Usa apenas para sincronização manual via comando
    """
    try:
        worksheet = _get_worksheet()
        if not worksheet:
            return False
        
        from .models import Cavalo
        
        # Buscar todos os cavalos na mesma ordem do admin
        cavalos = Cavalo.objects.select_related('motorista', 'carreta', 'proprietario', 'gestor').exclude(
            Q(carreta__isnull=True) | Q(situacao='desagregado')
        ).annotate(
            ordem_situacao=Case(
                When(situacao='ativo', then=Value(0)),
                When(situacao='parado', then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
            ),
            ordem_fluxo=Case(
                When(fluxo='escoria', then=Value(0)),
                When(fluxo='minerio', then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
            ),
            ordem_tipo=Case(
                When(tipo='toco', then=Value(0)),
                When(tipo='trucado', then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
            ),
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
        
        # Preparar cabeçalhos (incluindo colunas extras vazias)
        headers = [
            'PLACA', 'CARRETA', '', '', 'MOTORISTA', 'CPF', 'TIPO', 'FLUXO',
            'CLASSIFICAÇÃO', 'CÓDIGO DO PROPRIETÁRIO', 'PROPRIETÁRIO', 'SITUAÇÃO'
        ]
        
        # Verificar cabeçalhos
        try:
            first_row = worksheet.row_values(1)
            if not first_row or len(first_row) < 11:
                # Atualizar apenas as colunas do banco de dados, preservando C e D se existirem
                header_updates = []
                header_updates.append({'range': 'A1', 'values': [['PLACA']]})
                header_updates.append({'range': 'B1', 'values': [['CARRETA']]})
                # C e D não são atualizados (preservados)
                header_updates.append({'range': 'E1', 'values': [['MOTORISTA']]})
                header_updates.append({'range': 'F1', 'values': [['CPF']]})
                header_updates.append({'range': 'G1', 'values': [['TIPO']]})
                header_updates.append({'range': 'H1', 'values': [['FLUXO']]})
                header_updates.append({'range': 'I1', 'values': [['CLASSIFICAÇÃO']]})
                header_updates.append({'range': 'J1', 'values': [['CÓDIGO DO PROPRIETÁRIO']]})
                header_updates.append({'range': 'K1', 'values': [['PROPRIETÁRIO']]})
                header_updates.append({'range': 'L1', 'values': [['SITUAÇÃO']]})
                worksheet.batch_update(header_updates, value_input_option='RAW')
        except Exception:
            pass
        
        # Preparar dados
        data_rows = []
        for cavalo in cavalos:
            row_data_dict = _get_cavalo_row_data(cavalo)
            # Criar lista completa com colunas vazias para C e D
            row_data_list = [
                row_data_dict.get('A', ''),
                row_data_dict.get('B', ''),
                '',  # Coluna C - extra do usuário
                '',  # Coluna D - extra do usuário
                row_data_dict.get('E', ''),
                row_data_dict.get('F', ''),
                row_data_dict.get('G', ''),
                row_data_dict.get('H', ''),
                row_data_dict.get('I', ''),
                row_data_dict.get('J', ''),
                row_data_dict.get('K', ''),
            ]
            data_rows.append(row_data_list)
        
        # Limpar linhas antigas (mantém cabeçalho)
        try:
            all_values = worksheet.get_all_values()
            existing_data_rows = len([row for row in all_values[1:] if any(cell.strip() for cell in row)])
            if existing_data_rows > 0:
                worksheet.delete_rows(2, existing_data_rows + 1)
        except Exception:
            pass
        
        # Adicionar novos dados
        if data_rows:
            for i, row_data in enumerate(data_rows, start=2):
                worksheet.insert_row(row_data, i, value_input_option='RAW')
        
        logger.info(f"Sincronização completa: {len(data_rows)} cavalos atualizados")
        return True
        
    except Exception as e:
        logger.error(f"Erro na sincronização completa: {str(e)}", exc_info=True)
        return False


def update_cavalo_async(cavalo_pk):
    """Executa atualização em background"""
    thread = threading.Thread(target=update_cavalo_in_sheets, args=(cavalo_pk,), daemon=True)
    thread.start()


def add_cavalo_async(cavalo_pk):
    """Executa adição em background"""
    thread = threading.Thread(target=add_cavalo_to_sheets, args=(cavalo_pk,), daemon=True)
    thread.start()


def delete_cavalo_async(placa):
    """Executa deleção em background"""
    thread = threading.Thread(target=delete_cavalo_from_sheets, args=(placa,), daemon=True)
    thread.start()
