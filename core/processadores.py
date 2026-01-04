import os
import pandas as pd
import re
import csv
import time
import threading
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from django.db import transaction
from .models import DocumentoTransporte, UploadLog, Cavalo


class ProcessadorCTECSV:
    """Processador para arquivos CSV de CTEs (Conhecimentos de Transporte)"""
    
    def __init__(self):
        self.ctes = []
    
    def processar_arquivo(self, arquivo_path):
        """Processa arquivo CSV de CTEs"""
        try:
            print(f"📄 Processando arquivo CSV de CTEs: {os.path.basename(arquivo_path)}")
            
            # Tentar diferentes encodings
            encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
            df = None
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(arquivo_path, encoding=encoding, dtype=str)
                    print(f"✅ Arquivo lido com encoding: {encoding}")
                    break
                except Exception as e:
                    continue
            
            if df is None:
                raise Exception("Não foi possível ler o arquivo CSV com nenhum encoding suportado")
            
            print(f"📊 Total de linhas encontradas: {len(df)}")
            
            # Processar cada linha
            for idx, row in df.iterrows():
                try:
                    cte = self._processar_linha_cte(row)
                    if cte:
                        self.ctes.append(cte)
                except Exception as e:
                    print(f"⚠️  Erro ao processar linha {idx+1}: {str(e)}")
                    continue
            
            print(f"✅ Total de CTEs processados: {len(self.ctes)}")
            return self.ctes
            
        except Exception as e:
            print(f"❌ Erro ao processar arquivo CSV: {str(e)}")
            raise
    
    def _processar_linha_cte(self, row):
        """Processa uma linha do CSV de CTE baseado na estrutura real do arquivo"""
        cte = {}
        
        # Converter row para lista se for Series ou dict
        if hasattr(row, 'values'):
            valores = list(row.values)
        elif isinstance(row, dict):
            valores = list(row.values())
        else:
            valores = list(row) if isinstance(row, (list, tuple)) else []
        
        # Se não tem valores suficientes, retornar vazio
        # Precisamos pelo menos até a coluna 31 (índice 31)
        if len(valores) < 32:
            return {}
        
        # Pular linhas que são totais (contém "TOTAL GERAL" ou "TOTAL DO GRUPO")
        primeiro_valor = str(valores[0]).strip() if len(valores) > 0 else ''
        ultimo_valor = str(valores[-1]).strip() if len(valores) > 0 else ''
        if 'TOTAL GERAL' in primeiro_valor or 'TOTAL GERAL' in ultimo_valor:
            return {}
        if 'TOTAL DO GRUPO' in primeiro_valor or 'TOTAL DO GRUPO' in ultimo_valor:
            return {}
        if 'TOTAL DA LINHA' in primeiro_valor or 'TOTAL DA LINHA' in ultimo_valor:
            return {}
        
        # Extrair Filial, Série e CTRC da coluna 18 (índice 18 no array do pandas)
        filial_serie_ctrc = str(valores[18]).strip() if len(valores) > 18 and str(valores[18]) != 'nan' else ''
        if filial_serie_ctrc and '/' in filial_serie_ctrc:
            partes = [p.strip() for p in filial_serie_ctrc.split('/')]
            if len(partes) >= 3:
                cte['filial'] = partes[0]
                cte['serie'] = partes[1]
                cte['ctrc'] = partes[2].replace('.', '')
            else:
                cte['filial'] = ''
                cte['serie'] = ''
                cte['ctrc'] = ''
        else:
            cte['filial'] = ''
            cte['serie'] = ''
            cte['ctrc'] = ''
        
        # Data/Hora - coluna 20 (índice 20 no array do pandas)
        data_hora_raw = valores[20] if len(valores) > 20 else None
        if pd.notna(data_hora_raw) and str(data_hora_raw).strip() and str(data_hora_raw).strip().lower() != 'nan':
            data_hora = str(data_hora_raw).strip()
            data_str = data_hora.split()[0] if ' ' in data_hora else data_hora
            if '/' in data_str and len(data_str.split('/')) == 3:
                partes = data_str.split('/')
                if len(partes[2]) == 2:
                    ano_int = int(partes[2])
                    ano = f"20{partes[2]}" if ano_int < 50 else f"19{partes[2]}"
                    data_str = f"{partes[0]}/{partes[1]}/{ano}"
            cte['data_hora'] = data_str
        else:
            cte['data_hora'] = ''
        
        # Cavalo - coluna 21 (índice 21)
        cte['cavalo'] = str(valores[21]).strip() if len(valores) > 21 and str(valores[21]) != 'nan' else ''
        
        # Carreta - coluna 22 (índice 22)
        cte['carreta'] = str(valores[22]).strip() if len(valores) > 22 and str(valores[22]) != 'nan' else ''
        
        # Motorista - coluna 23 (índice 23)
        cte['motorista'] = str(valores[23]).strip() if len(valores) > 23 and str(valores[23]) != 'nan' else ''
        
        # Tipo Frota - coluna 24 (índice 24)
        cte['tipo_frota'] = str(valores[24]).strip() if len(valores) > 24 and str(valores[24]) != 'nan' else ''
        
        # Pedágio - coluna 26 (índice 26)
        pedagio_raw = valores[26] if len(valores) > 26 else None
        if pedagio_raw is not None and str(pedagio_raw).strip() and str(pedagio_raw).strip().lower() not in ['nan', 'none', '']:
            pedagio_str = str(pedagio_raw).strip()
            if '.' in pedagio_str and ',' not in pedagio_str:
                partes_ponto = pedagio_str.split('.')
                if len(partes_ponto) == 2:
                    cte['pedagio'] = pedagio_str.replace('.', ',')
                else:
                    cte['pedagio'] = pedagio_str.replace('.', '', len(partes_ponto) - 2).replace('.', ',')
            elif ',' in pedagio_str:
                cte['pedagio'] = pedagio_str
            else:
                cte['pedagio'] = f"{pedagio_str},00"
        else:
            cte['pedagio'] = '0,00'
        
        # Total Frete - coluna 28 (índice 28)
        total_frete_raw = valores[28] if len(valores) > 28 else None
        if total_frete_raw is not None and str(total_frete_raw).strip() and str(total_frete_raw).strip().lower() not in ['nan', 'none', '']:
            total_frete_str = str(total_frete_raw).strip()
            if '.' in total_frete_str and ',' not in total_frete_str:
                partes_ponto = total_frete_str.split('.')
                if len(partes_ponto) == 2:
                    cte['total_frete'] = total_frete_str.replace('.', ',')
                else:
                    cte['total_frete'] = total_frete_str.replace('.', '', len(partes_ponto) - 2).replace('.', ',')
            elif ',' in total_frete_str:
                cte['total_frete'] = total_frete_str
            else:
                cte['total_frete'] = f"{total_frete_str},00"
        else:
            cte['total_frete'] = '0,00'
        
        # Nota Fiscal - coluna 30 (índice 30)
        nota_raw = valores[30] if len(valores) > 30 else None
        nota_str = ''
        if nota_raw is not None:
            nota_str = str(nota_raw).strip()
        if nota_str and nota_str.lower() != 'nan' and nota_str:
            cte['nota'] = nota_str
        else:
            cte['nota'] = ''
        
        # Tarifa - coluna 31 (índice 31)
        tarifa_raw = valores[31] if len(valores) > 31 else None
        if tarifa_raw is not None and str(tarifa_raw).strip() and str(tarifa_raw).strip().lower() not in ['nan', 'none', '']:
            tarifa_str = str(tarifa_raw).strip()
            if '.' in tarifa_str and ',' not in tarifa_str:
                partes_ponto = tarifa_str.split('.')
                if len(partes_ponto) == 2:
                    cte['tarifa'] = tarifa_str.replace('.', ',')
                else:
                    cte['tarifa'] = tarifa_str.replace('.', '', len(partes_ponto) - 2).replace('.', ',')
            elif ',' in tarifa_str:
                cte['tarifa'] = tarifa_str
            else:
                cte['tarifa'] = f"{tarifa_str},00"
        else:
            cte['tarifa'] = '0,00'
        
        # Remetente e Destinatário - coluna 2 (índice 2)
        rem_dest = str(valores[2]).strip() if len(valores) > 2 else ''
        if rem_dest:
            if 'DESTINATÁRIO :' in rem_dest or 'DESTINATÁRIO:' in rem_dest:
                partes = re.split(r'DESTINATÁRIO\s*:', rem_dest, flags=re.IGNORECASE)
                if len(partes) >= 2:
                    remetente_raw = partes[0].replace('REMETENTE :', '').replace('REMETENTE:', '').strip()
                    destinatario_raw = partes[1].strip()
                    cte['remetente'] = remetente_raw
                    cte['destinatario'] = destinatario_raw
                else:
                    cte['remetente'] = rem_dest
                    cte['destinatario'] = ''
            else:
                cte['remetente'] = rem_dest
                cte['destinatario'] = ''
        else:
            cte['remetente'] = ''
            cte['destinatario'] = ''
        
        # Filial/Série/CTRC concatenado
        cte['filial_serie_ctrc'] = f"{cte.get('filial', '')}/{cte.get('serie', '')}/{cte.get('ctrc', '')}"
        
        return cte


class ProcessadorOST:
    """Processador para arquivos Excel de OSTs (Ordem de Serviço de Transporte)"""
    
    def __init__(self):
        self.osts = []
        
        # Padrões de validação
        self.padrao_filial_serie = re.compile(r'Filial:(\d+)\s*/\s*Série:(\w+)\s*/\s*Nº:([0-9.]+)')
        self.padrao_data = re.compile(r'(\d{2}/\d{2}/\d{4})')
        
        # Mapeamento baseado na estrutura do arquivo
        self.estrutura_ost = {
            'filial_serie_numero': 1,
            'data': 5,
            'remetente': 13,
            'destinatario': 20,
            'motorista': 34,
            'cavalo': 37,
            'carreta': 38,
            'total_frete': 44,
            'pedagio': 46,
        }
    
    def processar_arquivo(self, arquivo_path):
        """Processa arquivo Excel de OSTs"""
        try:
            print(f"🚛 Processando arquivo OST: {os.path.basename(arquivo_path)}")
            
            df = self._ler_arquivo_excel(arquivo_path)
            dados = df.fillna('').values.tolist()
            
            print(f"📊 Arquivo carregado: {len(dados)} linhas encontradas")
            
            linhas_ost = self._encontrar_linhas_ost(dados)
            print(f"🔍 Encontradas {len(linhas_ost)} OSTs")
            
            for i, linha_num in enumerate(linhas_ost):
                ost = self._processar_ost_individual(dados, linha_num)
                if ost:
                    self.osts.append(ost)
            
            print(f"✅ Processamento concluído: {len(self.osts)} OSTs extraídas")
            return self.osts
            
        except Exception as e:
            print(f"❌ Erro ao processar arquivo: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def _ler_arquivo_excel(self, arquivo_path):
        """Lê arquivo Excel com diferentes engines"""
        extensao = Path(arquivo_path).suffix.lower()
        
        engines = ['xlrd', 'openpyxl'] if extensao == '.xls' else ['openpyxl', 'xlrd']
        
        for engine in engines:
            try:
                df = pd.read_excel(arquivo_path, engine=engine, header=None)
                return df
            except ImportError:
                continue
            except Exception:
                continue
        
        raise Exception("Não foi possível ler o arquivo com nenhum engine disponível")
    
    def _encontrar_linhas_ost(self, dados):
        """Encontra todas as linhas que contêm OSTs"""
        linhas_ost = []
        
        for i, linha in enumerate(dados):
            for celula in linha:
                if isinstance(celula, str) and self.padrao_filial_serie.search(celula):
                    linhas_ost.append(i)
                    break
        
        return linhas_ost
    
    def _processar_ost_individual(self, dados, linha_ost):
        """Processa uma OST individual"""
        try:
            linha = dados[linha_ost]
            
            while len(linha) <= max(self.estrutura_ost.values()):
                linha.append('')
            
            filial, serie, numero_ost = self._extrair_filial_serie_numero(
                linha[self.estrutura_ost['filial_serie_numero']]
            )
            
            data = self._extrair_data(linha[self.estrutura_ost['data']])
            
            remetente = self._limpar_campo(linha[self.estrutura_ost['remetente']], 'Remetente :')
            destinatario = self._limpar_campo(linha[self.estrutura_ost['destinatario']], 'Destinatário :')
            
            motorista = self._limpar_campo(linha[self.estrutura_ost['motorista']], 'Motorista :')
            
            cavalo = self._limpar_campo(linha[self.estrutura_ost['cavalo']])
            carreta = self._limpar_campo(linha[self.estrutura_ost['carreta']])
            
            total_frete = self._extrair_valor(linha[self.estrutura_ost['total_frete']], 'Total Frete:')
            pedagio = self._extrair_valor(linha[self.estrutura_ost['pedagio']], 'Pedágio:')
            
            ost = {
                'filial': filial,
                'serie': serie,
                'numero_ost': numero_ost,
                'data': data,
                'motorista': motorista,
                'cavalo': cavalo,
                'carreta': carreta,
                'pedagio': pedagio,
                'destinatario': destinatario,
                'remetente': remetente,
                'total_frete': total_frete,
                'tarifa': '0,00',
                'filial_serie_ost': f"{filial}/{serie}/{numero_ost}"
            }
            
            return ost
            
        except Exception as e:
            print(f"❌ Erro ao processar OST na linha {linha_ost+1}: {str(e)}")
            return None
    
    def _extrair_filial_serie_numero(self, valor):
        """Extrai filial, série e número da OST"""
        if not valor:
            return '', '', ''
        
        match = self.padrao_filial_serie.search(str(valor))
        if match:
            return match.group(1), match.group(2), match.group(3)
        
        return '', '', ''
    
    def _extrair_data(self, valor):
        """Extrai data do campo"""
        if not valor:
            return ''
        
        valor_str = str(valor)
        match = self.padrao_data.search(valor_str)
        if match:
            return match.group(1)
        
        return ''
    
    def _limpar_campo(self, valor, prefixo=''):
        """Remove prefixo e limpa o campo"""
        if not valor:
            return ''
        
        valor_str = str(valor).strip()
        if prefixo and valor_str.startswith(prefixo):
            valor_str = valor_str.replace(prefixo, '').strip()
        
        return valor_str
    
    def _extrair_valor(self, valor, prefixo=''):
        """Extrai valor monetário removendo prefixo"""
        if not valor:
            return '0,00'
        
        valor_str = str(valor).strip()
        if prefixo:
            valor_str = valor_str.replace(prefixo, '').strip()
        
        return self._processar_valor_com_virgula(valor_str)
    
    def _processar_valor_com_virgula(self, valor):
        """Processa valores monetários substituindo ponto por vírgula"""
        if valor is None or valor == '':
            return '0,00'
        
        valor_str = str(valor).strip().replace(' ', '')
        
        if ',' in valor_str:
            partes = valor_str.split(',')
            if len(partes) == 2:
                if len(partes[1]) == 1:
                    valor_str = f"{partes[0]},{partes[1]}0"
                elif len(partes[1]) > 2:
                    valor_str = f"{partes[0]},{partes[1][:2]}"
            return valor_str
        
        if '.' in valor_str:
            valor_str = valor_str.replace('.', ',')
            partes = valor_str.split(',')
            if len(partes) == 2:
                if len(partes[1]) == 1:
                    valor_str = f"{partes[0]},{partes[1]}0"
                elif len(partes[1]) > 2:
                    valor_str = f"{partes[0]},{partes[1][:2]}"
            return valor_str
        
        if valor_str.isdigit():
            return f"{valor_str},00"
        
        return valor_str


# Lock global para serializar escritas no banco SQLite
_db_lock = threading.Lock()


class ProcessadorArquivos:
    """Classe principal que coordena o processamento de arquivos CTE e OST"""
    
    def __init__(self):
        self.registros_processados = 0
        self.registros_duplicados = 0
        self.erros = []
    
    def detectar_tipo_arquivo(self, arquivo_path):
        """Detecta se é CTE ou OST baseado no conteúdo e extensão"""
        try:
            print(f"🔍 Detectando tipo do arquivo: {os.path.basename(arquivo_path)}")
            
            extensao = Path(arquivo_path).suffix.lower()
            if extensao not in ['.xls', '.xlsx', '.csv']:
                raise Exception(f"Extensão não suportada: {extensao}")
            
            conteudo = ""
            
            if extensao == '.csv':
                try:
                    with open(arquivo_path, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        linhas = []
                        for i, linha in enumerate(reader):
                            if i >= 50:
                                break
                            linhas.append(linha)
                        conteudo = ' '.join([str(cell) for linha in linhas for cell in linha if cell])
                except:
                    try:
                        with open(arquivo_path, 'r', encoding='latin-1') as f:
                            reader = csv.reader(f)
                            linhas = []
                            for i, linha in enumerate(reader):
                                if i >= 50:
                                    break
                                linhas.append(linha)
                            conteudo = ' '.join([str(cell) for linha in linhas for cell in linha if cell])
                    except:
                        pass
            else:
                try:
                    df = pd.read_excel(arquivo_path, engine='openpyxl', header=None, nrows=50)
                    conteudo = ' '.join([str(cell) for row in df.values for cell in row if pd.notna(cell)])
                except:
                    try:
                        df = pd.read_excel(arquivo_path, engine='xlrd', header=None, nrows=50)
                        conteudo = ' '.join([str(cell) for row in df.values for cell in row if pd.notna(cell)])
                    except:
                        pass
            
            nome_arquivo = os.path.basename(arquivo_path).upper()
            
            indicadores_cte = ['CTRC', 'CONHECIMENTO', 'REMETENTE', 'DESTINATÁRIO', 'CTE', 'FIL. / Ser. / CTRC']
            indicadores_ost = ['OST', 'ORDEM DE SERVIÇO', 'FILIAL:', 'SÉRIE:']
            
            conteudo_upper = conteudo.upper()
            pontos_cte = sum(1 for ind in indicadores_cte if ind in conteudo_upper)
            pontos_ost = sum(1 for ind in indicadores_ost if ind in conteudo_upper)
            
            pontos_cte += sum(1 for ind in indicadores_cte if ind in nome_arquivo)
            pontos_ost += sum(1 for ind in indicadores_ost if ind in nome_arquivo)
            
            if pontos_cte > pontos_ost:
                tipo = 'CTE'
            elif pontos_ost > pontos_cte:
                tipo = 'OST'
            else:
                if 'FILIAL:' in conteudo and 'SÉRIE:' in conteudo:
                    tipo = 'OST'
                elif any(word in nome_arquivo for word in ['CTE', 'CTRC', 'CONHECIMENTO']):
                    tipo = 'CTE'
                elif any(word in nome_arquivo for word in ['OST', 'ORDEM']):
                    tipo = 'OST'
                else:
                    tipo = 'CTE'
                    print("⚠️  Tipo não detectado claramente, assumindo CTE")
            
            print(f"✅ Tipo detectado: {tipo}")
            return tipo
            
        except Exception as e:
            print(f"❌ Erro na detecção: {str(e)}")
            raise Exception(f"Erro ao detectar tipo do arquivo: {str(e)}")
    
    def _obter_gestor_por_cavalo(self, placa_cavalo):
        """Obtém gestor baseado na placa do cavalo cadastrado.
        Retorna None se o cavalo estiver desagregado (situacao='desagregado')"""
        if not placa_cavalo:
            return None
        
        max_retries = 3
        tentativas = 0
        delay = 0.05
        
        while tentativas < max_retries:
            try:
                with _db_lock:
                    # Buscar cavalo ativo que não esteja desagregado
                    cavalo = Cavalo.objects.filter(
                        placa=placa_cavalo,
                        situacao='ativo'
                    ).first()
                    
                    # Se não encontrou ativo, verificar se existe mas está desagregado
                    if not cavalo:
                        cavalo = Cavalo.objects.filter(placa=placa_cavalo).first()
                
                # Retornar gestor apenas se o cavalo existir, estiver ativo e não desagregado
                if cavalo and cavalo.gestor:
                    # Verificar se está desagregado
                    if cavalo.situacao == 'desagregado':
                        return None
                    return cavalo.gestor
                
                return None
                
            except Exception as e:
                tentativas += 1
                error_msg = str(e).lower()
                if 'locked' in error_msg and tentativas < max_retries:
                    time.sleep(delay)
                    delay *= 1.5
                else:
                    print(f"Erro ao buscar gestor para cavalo {placa_cavalo}: {e}")
                    return None
        
        return None
    
    def processar_arquivo(self, arquivo_path, upload_log):
        """Processa arquivo Excel/CSV e salva no banco usando os processadores apropriados"""
        try:
            tipo = self.detectar_tipo_arquivo(arquivo_path)
            upload_log.tipo_detectado = tipo
            upload_log.save()
            
            extensao = Path(arquivo_path).suffix.lower()
            
            if tipo == 'CTE':
                # CTE pode ser CSV ou Excel, mas ambos usam ProcessadorCTECSV
                # Para Excel, precisamos converter para CSV temporariamente ou ler diretamente
                if extensao == '.csv':
                    processador_cte = ProcessadorCTECSV()
                    ctes = processador_cte.processar_arquivo(arquivo_path)
                    registros_salvos, registros_duplicados = self._salvar_ctes_no_django(ctes)
                else:
                    # Para Excel, tentar ler como CSV usando pandas
                    try:
                        # Ler Excel e converter para CSV temporário
                        df = pd.read_excel(arquivo_path, engine='openpyxl' if extensao == '.xlsx' else 'xlrd', dtype=str)
                        import tempfile
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp:
                            df.to_csv(tmp.name, index=False, encoding='utf-8')
                            processador_cte = ProcessadorCTECSV()
                            ctes = processador_cte.processar_arquivo(tmp.name)
                            registros_salvos, registros_duplicados = self._salvar_ctes_no_django(ctes)
                            os.unlink(tmp.name)
                    except Exception as e:
                        # Se falhar, tentar ler diretamente como CSV
                        processador_cte = ProcessadorCTECSV()
                        ctes = processador_cte.processar_arquivo(arquivo_path)
                        registros_salvos, registros_duplicados = self._salvar_ctes_no_django(ctes)
            else:
                processador_ost = ProcessadorOST()
                osts = processador_ost.processar_arquivo(arquivo_path)
                registros_salvos, registros_duplicados = self._salvar_osts_no_django(osts)
            
            upload_log.status = 'SUCESSO'
            upload_log.registros_processados = registros_salvos
            upload_log.registros_duplicados = registros_duplicados
            upload_log.save()
            
            return True, f"Processado com sucesso: {registros_salvos} registros, {registros_duplicados} duplicatas ignoradas"
            
        except Exception as e:
            upload_log.status = 'ERRO'
            upload_log.mensagem_erro = str(e)
            upload_log.save()
            return False, str(e)
    
    def _salvar_ctes_no_django(self, ctes):
        """Salva CTEs processados no modelo Django usando bulk insert com retry"""
        registros_salvos = 0
        registros_duplicados = 0
        
        documentos_para_inserir = []
        
        for cte in ctes:
            try:
                if self._e_duplicata_cte(cte):
                    registros_duplicados += 1
                    continue
                
                data_documento = self._converter_data_django(cte.get('data_hora'))
                gestor = self._obter_gestor_por_cavalo(cte.get('cavalo', ''))
                
                doc = DocumentoTransporte(
                    tipo_documento='CTE',
                    filial=cte.get('filial', ''),
                    serie=cte.get('serie', ''),
                    numero_documento=cte.get('ctrc', ''),
                    data_documento=data_documento,
                    motorista=cte.get('motorista', ''),
                    cavalo=cte.get('cavalo', ''),
                    carreta=cte.get('carreta', ''),
                    tipo_frota=cte.get('tipo_frota', ''),
                    remetente=cte.get('remetente', ''),
                    destinatario=cte.get('destinatario', ''),
                    nota_fiscal=cte.get('nota', ''),
                    pedagio=self._converter_decimal(cte.get('pedagio', '0,00')),
                    total_frete=self._converter_decimal(cte.get('total_frete', '0,00')),
                    tarifa=self._converter_decimal(cte.get('tarifa', '0,00')),
                    filial_serie_numero=cte.get('filial_serie_ctrc', ''),
                    gestor=gestor,
                )
                documentos_para_inserir.append(doc)
                
            except Exception as e:
                print(f"Erro ao preparar CTE: {str(e)}")
                continue
        
        if documentos_para_inserir:
            registros_salvos = self._bulk_insert_com_retry(documentos_para_inserir, batch_size=100)
        
        return registros_salvos, registros_duplicados
    
    def _salvar_osts_no_django(self, osts):
        """Salva OSTs processadas no modelo Django usando bulk insert com retry"""
        registros_salvos = 0
        registros_duplicados = 0
        
        documentos_para_inserir = []
        
        for ost in osts:
            try:
                if self._e_duplicata_ost(ost):
                    registros_duplicados += 1
                    continue
                
                data_documento = self._converter_data_django(ost.get('data'))
                gestor = self._obter_gestor_por_cavalo(ost.get('cavalo', ''))
                
                doc = DocumentoTransporte(
                    tipo_documento='OST',
                    filial=ost.get('filial', ''),
                    serie=ost.get('serie', ''),
                    numero_documento=ost.get('numero_ost', ''),
                    data_documento=data_documento,
                    motorista=ost.get('motorista', ''),
                    cavalo=ost.get('cavalo', ''),
                    carreta=ost.get('carreta', ''),
                    remetente=ost.get('remetente', ''),
                    destinatario=ost.get('destinatario', ''),
                    pedagio=self._converter_decimal(ost.get('pedagio', '0,00')),
                    total_frete=self._converter_decimal(ost.get('total_frete', '0,00')),
                    tarifa=self._converter_decimal(ost.get('tarifa', '0,00')),
                    filial_serie_numero=ost.get('filial_serie_ost', ''),
                    gestor=gestor,
                )
                documentos_para_inserir.append(doc)
                
            except Exception as e:
                print(f"Erro ao preparar OST: {str(e)}")
                continue
        
        if documentos_para_inserir:
            registros_salvos = self._bulk_insert_com_retry(documentos_para_inserir, batch_size=100)
        
        return registros_salvos, registros_duplicados
    
    def _bulk_insert_com_retry(self, documentos, batch_size=100, max_retries=5, retry_delay=0.1):
        """Insere documentos em lotes com retry logic para lidar com database locks do SQLite"""
        registros_salvos = 0
        
        for i in range(0, len(documentos), batch_size):
            lote = documentos[i:i + batch_size]
            salvo = False
            tentativas = 0
            delay = retry_delay
            
            while not salvo and tentativas < max_retries:
                try:
                    with _db_lock:
                        with transaction.atomic():
                            DocumentoTransporte.objects.bulk_create(lote, ignore_conflicts=True)
                            registros_salvos += len(lote)
                            salvo = True
                    
                except Exception as e:
                    tentativas += 1
                    error_msg = str(e).lower()
                    
                    if 'locked' in error_msg or 'database is locked' in error_msg:
                        if tentativas < max_retries:
                            time.sleep(delay)
                            delay *= 2
                            print(f"⚠️  Database locked, tentativa {tentativas}/{max_retries}...")
                        else:
                            print(f"❌ Erro ao salvar lote após {max_retries} tentativas: {str(e)}")
                            registros_salvos += self._salvar_individual_com_retry(lote)
                            salvo = True
                    else:
                        print(f"❌ Erro ao salvar lote: {str(e)}")
                        salvo = True
        
        return registros_salvos
    
    def _salvar_individual_com_retry(self, documentos, max_retries=3):
        """Salva documentos individualmente com retry (fallback quando bulk falha)"""
        salvos = 0
        for doc in documentos:
            tentativas = 0
            salvo = False
            delay = 0.05
            
            while not salvo and tentativas < max_retries:
                try:
                    with _db_lock:
                        with transaction.atomic():
                            doc.save()
                            salvos += 1
                            salvo = True
                except Exception as e:
                    tentativas += 1
                    error_msg = str(e).lower()
                    if 'locked' in error_msg and tentativas < max_retries:
                        time.sleep(delay)
                        delay *= 1.5
                    else:
                        print(f"Erro ao salvar documento individual: {str(e)}")
                        salvo = True
        
        return salvos
    
    def _e_duplicata_cte(self, cte):
        """Verifica se CTE já existe no banco"""
        return DocumentoTransporte.objects.filter(
            tipo_documento='CTE',
            filial=cte.get('filial', ''),
            serie=cte.get('serie', ''),
            numero_documento=cte.get('ctrc', ''),
            data_documento=self._converter_data_django(cte.get('data_hora'))
        ).exists()
    
    def _e_duplicata_ost(self, ost):
        """Verifica se OST já existe no banco"""
        return DocumentoTransporte.objects.filter(
            tipo_documento='OST',
            filial=ost.get('filial', ''),
            serie=ost.get('serie', ''),
            numero_documento=ost.get('numero_ost', ''),
            data_documento=self._converter_data_django(ost.get('data'))
        ).exists()
    
    def _converter_data_django(self, data_str):
        """Converte string de data para objeto date (formato DD/MM/YYYY)"""
        if not data_str:
            return None
        
        try:
            data_str = str(data_str).strip()
            if not data_str or data_str.lower() == 'nan':
                return None
            
            if '/' in data_str:
                data_parte = data_str.split()[0]
                partes = data_parte.split('/')
                if len(partes) == 3:
                    if len(partes[2]) == 4:
                        return datetime.strptime(data_parte, '%d/%m/%Y').date()
                    elif len(partes[2]) == 2:
                        ano_int = int(partes[2])
                        ano = f"20{partes[2]}" if ano_int < 50 else f"19{partes[2]}"
                        data_completa = f"{partes[0]}/{partes[1]}/{ano}"
                        return datetime.strptime(data_completa, '%d/%m/%Y').date()
            elif '-' in data_str:
                return datetime.strptime(data_str.split()[0], '%Y-%m-%d').date()
        except Exception as e:
            print(f"⚠️  Erro ao converter data '{data_str}': {e}")
        
        return None
    
    def _converter_decimal(self, valor_str):
        """Converte string de valor monetário para Decimal (formato brasileiro com vírgula)"""
        if not valor_str:
            return Decimal('0.00')
        
        try:
            valor_limpo = str(valor_str).strip().replace(' ', '')
            
            if not valor_limpo or valor_limpo.lower() == 'nan':
                return Decimal('0.00')
            
            if ',' in valor_limpo:
                valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
            elif '.' in valor_limpo:
                partes = valor_limpo.split('.')
                if len(partes) == 2:
                    valor_limpo = valor_limpo
                else:
                    valor_limpo = ''.join(partes[:-1]) + '.' + partes[-1]
            
            return Decimal(valor_limpo)
        except Exception as e:
            print(f"⚠️  Erro ao converter valor '{valor_str}' para Decimal: {e}")
            return Decimal('0.00')

