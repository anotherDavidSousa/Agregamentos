# Sistema de Agregamento

Sistema Django para gerenciar motoristas, veículos (cavalos mecânicos), proprietários, gestores dos veículos, equipamentos e manutenções e itens das carretas.

## Instalação

1. Instale as dependências:
```bash
pip install -r requirements.txt
```

2. Execute as migrações:
```bash
python manage.py makemigrations
python manage.py migrate
```

3. Crie um superusuário (opcional):
```bash
python manage.py createsuperuser
```

4. Execute o servidor de desenvolvimento:
```bash
python manage.py runserver
```

5. Acesse o sistema:
- Interface web: http://127.0.0.1:8000/
- Admin Django: http://127.0.0.1:8000/admin/

## Funcionalidades

### 1. Proprietários
- Cadastro de proprietários (PF ou PJ)
- Upload de documentos
- Observações

### 2. Cavalos (Veículos)
- Cadastro de cavalos mecânicos
- Vinculação com proprietário
- Vinculação com gestor
- Agregação de carretas
- Controle de situação (Ativo, Quebrado, Desagregado)
- Fluxo (Escória, Minério)

### 3. Carretas
- Cadastro completo de carretas
- Controle de lavagem (última e próxima - calculada automaticamente a cada 30 dias)
- Equipamentos (Polietileno, Cones, Localizador, Lona Fácil, Step)
- Tipo e altura
- Lista de carretas disponíveis para agregamento

### 4. Motoristas
- Cadastro de motoristas
- Vinculação única com cavalo (ao atribuir a outro cavalo, remove automaticamente do anterior)

### 5. Gestores
- Cadastro de gestores
- Vinculação com cavalos

### 6. Logs Automáticos
O sistema cria logs automaticamente quando:
- Uma carreta é acoplada a um cavalo
- Uma carreta é desacoplada de um cavalo
- Uma carreta é trocada entre cavalos
- Um cavalo é desagregado (remove gestor e cria log)

Os logs podem ser filtrados por:
- Tipo (acoplamento, desacoplamento, troca, desagregação)
- Placa (cavalo ou carreta)
- Período (data início e data fim)

## Estrutura do Projeto

```
agregamento/
├── agregamento/          # Configurações do projeto
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                 # App principal
│   ├── models.py         # Modelos de dados
│   ├── views.py          # Views
│   ├── urls.py           # URLs do app
│   ├── admin.py          # Configuração do admin
│   └── signals.py        # Signals para logs automáticos
├── templates/            # Templates HTML
│   ├── base.html
│   └── core/
├── media/                # Arquivos de mídia (documentos)
└── manage.py
```

## Observações Importantes

1. **Nenhum campo é obrigatório**: Todos os cadastros podem ser salvos sem preencher todos os campos, permitindo completar os dados posteriormente.

2. **Relacionamentos**:
   - Um proprietário pode ter vários cavalos
   - Um cavalo pertence a apenas um proprietário
   - Um cavalo pode ter apenas uma carreta acoplada
   - Uma carreta pode estar acoplada a apenas um cavalo
   - Um motorista pode estar em apenas um cavalo por vez

3. **Desagregação**: Quando um cavalo tem situação "Desagregado", o gestor é automaticamente removido e um log é criado.

4. **Carretas Disponíveis**: Carretas que não estão acopladas a nenhum cavalo aparecem na lista de disponíveis.

5. **Cavalos Desagregados**: Cavalos sem carreta acoplada ou com situação "Desagregado" aparecem na lista de desagregados.

