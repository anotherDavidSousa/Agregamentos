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
import time
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
            # Verificar e expandir se necessário (precisa ter pelo menos 13 colunas: A-M)
            try:
                current_cols = worksheet.col_count
                if current_cols < 13:
                    logger.info(f"Expandindo planilha existente de {current_cols} para 13 colunas...")
                    worksheet.resize(rows=worksheet.row_count, cols=13)
            except Exception as e:
                logger.warning(f"Erro ao expandir planilha existente: {str(e)}")
        except gspread.exceptions.WorksheetNotFound:
            logger.info(f"Aba '{worksheet_name}' não encontrada. Criando...")
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=13)
            # Criar cabeçalhos na primeira vez
            headers = [
                'PLACA', 'CARRETA', 'PLACA MG', 'CARRETA MG', 'MOTORISTA', 'CPF', 'TIPO', 'FLUXO',
                'CLASSIFICAÇÃO', 'CÓDIGO DO PROPRIETÁRIO', 'TIPO DO PROPRIETÁRIO', 'PROPRIETÁRIO', 'SITUAÇÃO'
            ]
            worksheet.update('A1:M1', [headers], value_input_option='RAW')
        
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
    - Coluna C: PLACA + MG (cavalo)
    - Coluna D: CARRETA + MG
    - Coluna E: MOTORISTA
    - Coluna F: CPF
    - Coluna G: TIPO
    - Coluna H: FLUXO
    - Coluna I: CLASSIFICAÇÃO
    - Coluna J: CÓDIGO DO PROPRIETÁRIO
    - Coluna K: TIPO DO PROPRIETÁRIO
    - Coluna L: PROPRIETÁRIO
    - Coluna M: SITUAÇÃO
    
    Retorna um dicionário com os dados do cavalo mapeados para as colunas corretas
    """
    return {
        'A': 'placa',           # PLACA (cavalo)
        'B': 'carreta',        # CARRETA
        'C': 'placa_mg',       # PLACA + MG (cavalo)
        'D': 'carreta_mg',     # CARRETA + MG
        'E': 'motorista',      # MOTORISTA
        'F': 'cpf',            # CPF
        'G': 'tipo',           # TIPO
        'H': 'fluxo',          # FLUXO
        'I': 'classificacao',  # CLASSIFICAÇÃO
        'J': 'codigo_proprietario',  # CÓDIGO DO PROPRIETÁRIO
        'K': 'tipo_proprietario',   # TIPO DO PROPRIETÁRIO
        'L': 'proprietario',   # PROPRIETÁRIO
        'M': 'situacao',       # SITUAÇÃO
    }


def _get_cavalo_row_data(cavalo):
    """
    Prepara os dados de uma linha do cavalo no formato da planilha
    Retorna um dicionário com os valores mapeados por coluna (A, B, C, D, E, F, etc.)
    """
    # Tratar motorista de forma segura (OneToOne reverso pode lançar exceção)
    try:
        motorista_nome = cavalo.motorista.nome if cavalo.motorista else '-'
        motorista_cpf = cavalo.motorista.cpf if cavalo.motorista and cavalo.motorista.cpf else '-'
    except Exception:
        motorista_nome = '-'
        motorista_cpf = '-'
    
    # Preparar placas com MG
    placa_cavalo = cavalo.placa or '-'
    placa_cavalo_mg = f"{placa_cavalo}MG" if placa_cavalo != '-' else '-'
    
    # Bi-truck não tem carreta, é um conjunto apenas com o caminhão
    if cavalo.tipo == 'bi_truck':
        placa_carreta = 'S/Placa'
        placa_carreta_mg = 'S/Placa'
    else:
        placa_carreta = cavalo.carreta.placa if cavalo.carreta else '-'
        placa_carreta_mg = f"{placa_carreta}MG" if placa_carreta != '-' else '-'
    
    # Retornar dicionário mapeado por coluna
    # Para tipo do proprietário, usar abreviação (PF ou PJ) ao invés do display completo
    tipo_proprietario = '-'
    if cavalo.proprietario and cavalo.proprietario.tipo:
        tipo_proprietario = cavalo.proprietario.tipo  # Retorna 'PF' ou 'PJ' diretamente
    
    return {
        'A': placa_cavalo,
        'B': placa_carreta,
        'C': placa_cavalo_mg,
        'D': placa_carreta_mg,
        'E': motorista_nome,
        'F': motorista_cpf,
        'G': cavalo.get_tipo_display() if cavalo.tipo else '-',
        'H': cavalo.get_fluxo_display() if cavalo.fluxo else '-',
        'I': cavalo.get_classificacao_display() if cavalo.classificacao else '-',
        'J': cavalo.proprietario.codigo if cavalo.proprietario and cavalo.proprietario.codigo else '-',
        'K': tipo_proprietario,  # PF ou PJ
        'L': cavalo.proprietario.nome_razao_social if cavalo.proprietario else '-',
        'M': cavalo.get_situacao_display() if cavalo.situacao else '-',
    }


def _get_insert_position(worksheet, cavalo):
    """
    Calcula a posição correta para inserir o cavalo na planilha
    Baseado na mesma ordenação do admin/template
    Retorna o número da linha onde deve ser inserido
    """
    try:
        from .models import Cavalo
        
        # Buscar todos os cavalos na ordem correta (mesma ordenação do template/admin)
        # Bi-trucks devem ser incluídos mesmo sem carreta
        # Outros tipos precisam ter carreta
        todos_cavalos = Cavalo.objects.select_related('motorista', 'carreta', 'proprietario', 'gestor').exclude(
            Q(situacao='desagregado')
        ).filter(
            Q(tipo='bi_truck') | Q(carreta__isnull=False)
        ).annotate(
            ordem_classificacao=Case(
                When(classificacao='agregado', then=Value(0)),
                When(classificacao='frota', then=Value(1)),
                When(classificacao='terceiro', then=Value(2)),
                default=Value(0),
                output_field=IntegerField()
            ),
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
                When(tipo='bi_truck', then=Value(0)),
                When(tipo='toco', then=Value(1)),
                When(tipo='trucado', then=Value(2)),
                default=Value(3),
                output_field=IntegerField()
            ),
            motorista_nome_ordem=Case(
                When(motorista__isnull=False, then=F('motorista__nome')),
                default=Value(''),
                output_field=CharField()
            ),
            ordem_terceiro=Case(
                When(classificacao='terceiro', then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            )
        ).order_by(
            'ordem_terceiro',
            'ordem_classificacao',
            'ordem_situacao',
            'ordem_fluxo',
            'ordem_tipo',
            'motorista_nome_ordem'
        )
        
        # Calcular a posição do cavalo atual na ordem
        classificacao_ordem = 0 if (cavalo.classificacao == 'agregado' or not cavalo.classificacao) else (1 if cavalo.classificacao == 'frota' else 2)
        terceiro_ordem = 1 if cavalo.classificacao == 'terceiro' else 0
        tipo_ordem = 0 if cavalo.tipo == 'bi_truck' else (1 if cavalo.tipo == 'toco' else (2 if cavalo.tipo == 'trucado' else 3))
        cavalo_ordem = (
            terceiro_ordem,
            classificacao_ordem,
            (0 if cavalo.situacao == 'ativo' else 1 if cavalo.situacao == 'parado' else 2),
            (0 if cavalo.fluxo == 'escoria' else 1 if cavalo.fluxo == 'minerio' else 2),
            tipo_ordem,
            (cavalo.motorista.nome if cavalo.motorista else '')
        )
        
        # Contar quantos cavalos vêm antes deste na ordem
        posicao = 1  # Começa na linha 2 (linha 1 é cabeçalho)
        for outro_cavalo in todos_cavalos:
            if outro_cavalo.pk == cavalo.pk:
                break
            outro_classificacao_ordem = 0 if (outro_cavalo.classificacao == 'agregado' or not outro_cavalo.classificacao) else (1 if outro_cavalo.classificacao == 'frota' else 2)
            outro_terceiro_ordem = 1 if outro_cavalo.classificacao == 'terceiro' else 0
            outro_tipo_ordem = 0 if outro_cavalo.tipo == 'bi_truck' else (1 if outro_cavalo.tipo == 'toco' else (2 if outro_cavalo.tipo == 'trucado' else 3))
            outro_ordem = (
                outro_terceiro_ordem,
                outro_classificacao_ordem,
                (0 if outro_cavalo.situacao == 'ativo' else 1 if outro_cavalo.situacao == 'parado' else 2),
                (0 if outro_cavalo.fluxo == 'escoria' else 1 if outro_cavalo.fluxo == 'minerio' else 2),
                outro_tipo_ordem,
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
        
        # Verificar se deve ser exibido
        # Bi-truck não tem carreta, mas deve ser exibido
        # Outros tipos precisam ter carreta
        deve_exibir = False
        if cavalo.tipo == 'bi_truck':
            # Bi-truck sempre deve ser exibido (mesmo sem carreta)
            deve_exibir = cavalo.situacao != 'desagregado'
        else:
            # Outros tipos precisam ter carreta
            deve_exibir = cavalo.carreta is not None and cavalo.situacao != 'desagregado'
        
        if not deve_exibir:
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
            # Atualizar linha existente - todas as colunas (A-M)
            row_data_dict = _get_cavalo_row_data(cavalo)
            
            # Verificar e expandir planilha se necessário (precisa ter pelo menos 13 colunas: A-M)
            try:
                current_cols = worksheet.col_count
                if current_cols < 13:
                    logger.info(f"Expandindo planilha de {current_cols} para 13 colunas...")
                    worksheet.resize(rows=worksheet.row_count, cols=13)
            except Exception as e:
                logger.warning(f"Erro ao expandir planilha: {str(e)}")
            
            # Atualizar cada coluna individualmente (incluindo C e D com placas + MG)
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
        # Bi-truck não tem carreta, mas deve ser exibido
        # Outros tipos precisam ter carreta
        deve_exibir = False
        if cavalo.tipo == 'bi_truck':
            # Bi-truck sempre deve ser exibido (mesmo sem carreta)
            deve_exibir = cavalo.situacao != 'desagregado'
        else:
            # Outros tipos precisam ter carreta
            deve_exibir = cavalo.carreta is not None and cavalo.situacao != 'desagregado'
        
        if not deve_exibir:
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
        
        # Verificar e expandir planilha se necessário (precisa ter pelo menos 13 colunas: A-M)
        try:
            current_cols = worksheet.col_count
            if current_cols < 13:
                logger.info(f"Expandindo planilha de {current_cols} para 13 colunas...")
                worksheet.resize(rows=worksheet.row_count, cols=13)
        except Exception as e:
            logger.warning(f"Erro ao expandir planilha: {str(e)}")
        
        # Preparar dados - criar lista completa com todas as colunas
        row_data_dict = _get_cavalo_row_data(cavalo)
        
        # Criar lista completa de valores (incluindo C e D com placas + MG)
        # Ordem: A, B, C (placa + MG), D (carreta + MG), E, F, G, H, I, J, K, L, M
        row_data_list = [
            row_data_dict.get('A', ''),
            row_data_dict.get('B', ''),
            row_data_dict.get('C', ''),  # Coluna C - Placa Cavalo + MG
            row_data_dict.get('D', ''),  # Coluna D - Placa Carreta + MG
            row_data_dict.get('E', ''),
            row_data_dict.get('F', ''),
            row_data_dict.get('G', ''),
            row_data_dict.get('H', ''),
            row_data_dict.get('I', ''),
            row_data_dict.get('J', ''),  # Coluna J - Código do Proprietário
            row_data_dict.get('K', ''),  # Coluna K - Tipo do Proprietário
            row_data_dict.get('L', ''),  # Coluna L - Proprietário
            row_data_dict.get('M', ''),  # Coluna M - Situação
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
        
        # Verificar e expandir planilha se necessário (precisa ter pelo menos 13 colunas: A-M)
        try:
            current_cols = worksheet.col_count
            if current_cols < 13:
                logger.info(f"Expandindo planilha de {current_cols} para 13 colunas...")
                worksheet.resize(rows=worksheet.row_count, cols=13)
        except Exception as e:
            logger.warning(f"Erro ao expandir planilha: {str(e)}")
        
        from .models import Cavalo
        
        # Buscar todos os cavalos na mesma ordem do admin/template
        # Bi-trucks devem ser incluídos mesmo sem carreta
        # Outros tipos precisam ter carreta
        cavalos = Cavalo.objects.select_related('motorista', 'carreta', 'proprietario', 'gestor').exclude(
            Q(situacao='desagregado')
        ).filter(
            Q(tipo='bi_truck') | Q(carreta__isnull=False)
        ).annotate(
            ordem_classificacao=Case(
                When(classificacao='agregado', then=Value(0)),
                When(classificacao='frota', then=Value(1)),
                When(classificacao='terceiro', then=Value(2)),
                default=Value(0),
                output_field=IntegerField()
            ),
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
                When(tipo='bi_truck', then=Value(0)),
                When(tipo='toco', then=Value(1)),
                When(tipo='trucado', then=Value(2)),
                default=Value(3),
                output_field=IntegerField()
            ),
            motorista_nome_ordem=Case(
                When(motorista__isnull=False, then=F('motorista__nome')),
                default=Value(''),
                output_field=CharField()
            ),
            ordem_terceiro=Case(
                When(classificacao='terceiro', then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            )
        ).order_by(
            'ordem_terceiro',
            'ordem_classificacao',
            'ordem_situacao',
            'ordem_fluxo',
            'ordem_tipo',
            'motorista_nome_ordem'
        )
        
        # Preparar cabeçalhos
        headers = [
            'PLACA', 'CARRETA', 'PLACA MG', 'CARRETA MG', 'MOTORISTA', 'CPF', 'TIPO', 'FLUXO',
            'CLASSIFICAÇÃO', 'CÓDIGO DO PROPRIETÁRIO', 'TIPO DO PROPRIETÁRIO', 'PROPRIETÁRIO', 'SITUAÇÃO'
        ]
        
        # Verificar cabeçalhos
        try:
            first_row = worksheet.row_values(1)
            if not first_row or len(first_row) < 13:
                # Atualizar todos os cabeçalhos incluindo C e D
                header_updates = []
                header_updates.append({'range': 'A1', 'values': [['PLACA']]})
                header_updates.append({'range': 'B1', 'values': [['CARRETA']]})
                header_updates.append({'range': 'C1', 'values': [['PLACA MG']]})
                header_updates.append({'range': 'D1', 'values': [['CARRETA MG']]})
                header_updates.append({'range': 'E1', 'values': [['MOTORISTA']]})
                header_updates.append({'range': 'F1', 'values': [['CPF']]})
                header_updates.append({'range': 'G1', 'values': [['TIPO']]})
                header_updates.append({'range': 'H1', 'values': [['FLUXO']]})
                header_updates.append({'range': 'I1', 'values': [['CLASSIFICAÇÃO']]})
                header_updates.append({'range': 'J1', 'values': [['CÓDIGO DO PROPRIETÁRIO']]})
                header_updates.append({'range': 'K1', 'values': [['TIPO DO PROPRIETÁRIO']]})
                header_updates.append({'range': 'L1', 'values': [['PROPRIETÁRIO']]})
                header_updates.append({'range': 'M1', 'values': [['SITUAÇÃO']]})
                worksheet.batch_update(header_updates, value_input_option='RAW')
        except Exception:
            pass
        
        # Preparar dados
        data_rows = []
        for cavalo in cavalos:
            row_data_dict = _get_cavalo_row_data(cavalo)
            # Criar lista completa com todas as colunas (incluindo C e D com placas + MG)
            row_data_list = [
                row_data_dict.get('A', ''),
                row_data_dict.get('B', ''),
                row_data_dict.get('C', ''),  # Coluna C - Placa Cavalo + MG
                row_data_dict.get('D', ''),  # Coluna D - Placa Carreta + MG
                row_data_dict.get('E', ''),
                row_data_dict.get('F', ''),
                row_data_dict.get('G', ''),
                row_data_dict.get('H', ''),
                row_data_dict.get('I', ''),
                row_data_dict.get('J', ''),  # Coluna J - Código do Proprietário
                row_data_dict.get('K', ''),  # Coluna K - Tipo do Proprietário
                row_data_dict.get('L', ''),  # Coluna L - Proprietário
                row_data_dict.get('M', ''),  # Coluna M - Situação
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
        # Limite do Google Sheets: 60 requisições de escrita por minuto
        # Usar append_rows em lotes para ser mais eficiente e respeitar o limite
        if data_rows:
            total_rows = len(data_rows)
            logger.info(f'Inserindo {total_rows} linhas na planilha...')
            
            # Inserir em lotes de 50 linhas por vez (com delay entre lotes)
            # Isso é mais eficiente que inserir linha por linha e respeita o limite de quota
            batch_size = 50
            for batch_start in range(0, total_rows, batch_size):
                batch_end = min(batch_start + batch_size, total_rows)
                batch_data = data_rows[batch_start:batch_end]
                
                # Inserir lote usando append_rows (adiciona no final)
                worksheet.append_rows(batch_data, value_input_option='RAW')
                
                logger.info(f"Progresso: {batch_end}/{total_rows} linhas inseridas")
                
                # Delay de 1.1 segundos entre lotes (exceto no último lote)
                # Isso garante que não excedemos 60 requisições por minuto
                if batch_end < total_rows:
                    time.sleep(1.1)
        
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
