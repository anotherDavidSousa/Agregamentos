# 📊 Guia de Configuração - Sincronização com Google Sheets

Este guia explica como configurar a sincronização automática dos cavalos com o Google Sheets.

## 📋 Pré-requisitos

1. **Arquivo JSON da Service Account do Google**
   - Você já mencionou que tem este arquivo
   - Se não tiver, siga: https://developers.google.com/workspace/guides/create-credentials

2. **Planilha do Google Sheets criada**
   - Crie uma planilha no Google Sheets
   - Anote o ID da planilha (está na URL)

## 🔧 Passo a Passo

### 1. Instalar Dependências

```bash
pip install -r requirements.txt
```

Isso instalará:
- `gspread` - biblioteca para trabalhar com Google Sheets
- `google-auth` - autenticação do Google

### 2. Configurar Credenciais

1. Coloque o arquivo JSON da Service Account na pasta raiz do projeto
   - Exemplo: `D:\SCRIPTS\Agregamento\google_credentials.json`

2. Ou coloque em uma pasta específica:
   - Exemplo: `D:\SCRIPTS\Agregamento\credentials\service-account.json`

### 3. Configurar Variáveis de Ambiente

Adicione no seu arquivo `.env`:

```env
# Habilitar sincronização (True ou False)
GOOGLE_SHEETS_ENABLED=True

# Caminho para o arquivo JSON da Service Account
GOOGLE_SHEETS_CREDENTIALS_PATH=D:\SCRIPTS\Agregamento\google_credentials.json

# ID da planilha (pegar da URL)
GOOGLE_SHEETS_SPREADSHEET_ID=seu_id_aqui

# Nome da aba (opcional, padrão é 'Cavalos')
GOOGLE_SHEETS_WORKSHEET_NAME=Cavalos
```

**Como pegar o ID da planilha:**
- Abra sua planilha no Google Sheets
- A URL será algo como: `https://docs.google.com/spreadsheets/d/1ABC123xyz/edit`
- O ID é a parte `1ABC123xyz`

### 4. Compartilhar Planilha com Service Account

**IMPORTANTE:** Você precisa dar permissão de editor para o email da Service Account!

1. Abra o arquivo JSON da Service Account
2. Procure o campo `client_email` (algo como: `seu-projeto@exemplo.iam.gserviceaccount.com`)
3. Abra sua planilha no Google Sheets
4. Clique em "Compartilhar" (botão no canto superior direito)
5. Cole o email da Service Account
6. Dê permissão de "Editor"
7. Clique em "Enviar"

### 5. Testar Sincronização Manual

Execute o comando para testar:

```bash
python manage.py sync_google_sheets
```

Se tudo estiver correto, você verá:
```
✓ Sincronização concluída com sucesso!
```

### 6. Sincronização Automática

A sincronização automática já está configurada! 

Toda vez que você:
- ✅ Salvar um cavalo (criar ou editar)
- ✅ Deletar um cavalo

A planilha será atualizada automaticamente em background (não trava o sistema).

## 📊 Estrutura da Planilha

A planilha terá as seguintes colunas (na mesma ordem do admin):

1. **PLACA** - Placa do cavalo
2. **CARRETA** - Placa da carreta
3. **MOTORISTA** - Nome do motorista
4. **CPF** - CPF do motorista
5. **TIPO** - Toco ou Trucado
6. **FLUXO** - Escória ou Minério
7. **CÓDIGO DO PROPRIETÁRIO** - Código do proprietário
8. **PROPRIETÁRIO** - Nome do proprietário
9. **SITUAÇÃO** - Ativo, Parado ou Desagregado

**Ordenação:**
- Mesma ordem do admin e do template
- Tocos da Escória Ativos primeiro (alfabético por motorista)
- Trucados da Escória Ativos
- Tocos do Minério Ativos
- Trucados do Minério Ativos
- Cavalos Parados

## 🔍 Solução de Problemas

### Erro: "Arquivo de credenciais não encontrado"
- Verifique o caminho no `.env`
- Use caminho absoluto ou relativo ao projeto

### Erro: "Permission denied" ou "Access denied"
- Verifique se compartilhou a planilha com o email da Service Account
- Dê permissão de "Editor" (não apenas "Visualizador")

### Erro: "Spreadsheet not found"
- Verifique se o ID da planilha está correto
- O ID está na URL da planilha

### Sincronização não acontece automaticamente
- Verifique se `GOOGLE_SHEETS_ENABLED=True` no `.env`
- Reinicie o servidor Django após mudar configurações
- Verifique os logs do Django

### Planilha fica vazia
- Execute manualmente: `python manage.py sync_google_sheets`
- Verifique se há cavalos cadastrados no sistema
- Verifique os logs para erros

## 📝 Logs

Os logs da sincronização aparecem no console do Django quando você executa `runserver`.

Para ver logs mais detalhados, configure no `settings.py`:

```python
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'core.google_sheets': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}
```

## 🛠️ Manutenção

### Desabilitar Temporariamente

No `.env`, coloque:
```env
GOOGLE_SHEETS_ENABLED=False
```

### Sincronização Manual

Sempre que quiser forçar uma sincronização:
```bash
python manage.py sync_google_sheets
```

### Limpar Planilha

A planilha é limpa automaticamente antes de cada sincronização, então sempre terá os dados mais atualizados.

## ❓ Dúvidas?

Se tiver problemas, verifique:
1. Arquivo JSON da Service Account está no lugar certo
2. Planilha foi compartilhada com o email da Service Account
3. ID da planilha está correto
4. Variáveis no `.env` estão corretas
5. Dependências foram instaladas (`pip install -r requirements.txt`)
