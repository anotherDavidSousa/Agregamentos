from django.contrib import admin
from django.db.models import Case, When, Value, IntegerField, F, CharField
from .models import (
    Proprietario, Gestor, Cavalo, Carreta, Motorista, LogCarreta,
    MarcaCavalo, ModeloCavalo, MarcaCarreta, ModeloCarreta,
    DocumentoTransporte, UploadLog, HistoricoGestor
)


@admin.register(Proprietario)
class ProprietarioAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nome_razao_social', 'tipo', 'status', 'whatsapp', 'criado_em']
    list_filter = ['tipo', 'status', 'criado_em']
    search_fields = ['codigo', 'nome_razao_social', 'whatsapp']
    fieldsets = (
        ('Dados Básicos', {
            'fields': ('codigo', 'nome_razao_social', 'tipo', 'status', 'whatsapp', 'documento', 'observacoes')
        }),
        ('Informações do Sistema', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['criado_em', 'atualizado_em']
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Atualizar status automaticamente após salvar
        obj.atualizar_status_automatico()


@admin.register(Gestor)
class GestorAdmin(admin.ModelAdmin):
    list_display = ['nome', 'meta_faturamento', 'criado_em']
    search_fields = ['nome']
    fieldsets = (
        ('Dados Básicos', {
            'fields': ('nome', 'meta_faturamento')
        }),
        ('Informações do Sistema', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['criado_em', 'atualizado_em']


@admin.register(HistoricoGestor)
class HistoricoGestorAdmin(admin.ModelAdmin):
    list_display = ['gestor', 'cavalo', 'data_inicio', 'data_fim', 'criado_em']
    list_filter = ['gestor', 'data_inicio', 'data_fim']
    search_fields = ['gestor__nome', 'cavalo__placa']
    readonly_fields = ['criado_em']
    date_hierarchy = 'data_inicio'


@admin.register(Cavalo)
class CavaloAdmin(admin.ModelAdmin):
    list_display = [
        'placa', 
        'carreta_display', 
        'motorista_display', 
        'cpf_motorista', 
        'tipo', 
        'fluxo', 
        'codigo_proprietario', 
        'proprietario', 
        'situacao'
    ]
    list_filter = ['situacao', 'tipo', 'fluxo', 'classificacao', 'proprietario', 'gestor']
    search_fields = ['placa', 'proprietario__nome_razao_social', 'proprietario__codigo', 'motorista__nome', 'motorista__cpf']
    fieldsets = (
        ('Dados Básicos', {
            'fields': ('placa', 'ano', 'cor', 'fluxo', 'tipo', 'classificacao', 'situacao')
        }),
        ('Relacionamentos', {
            'fields': ('proprietario', 'gestor', 'carreta')
        }),
        ('Arquivos e Observações', {
            'fields': ('foto', 'documento', 'observacoes')
        }),
        ('Informações do Sistema', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['criado_em', 'atualizado_em']
    
    def get_queryset(self, request):
        """Aplica a mesma ordenação personalizada do template"""
        qs = super().get_queryset(request)
        qs = qs.select_related('motorista', 'carreta', 'proprietario', 'gestor')
        
        # Ordenação personalizada:
        # 1. Situação: ativo primeiro, depois parado
        # 2. Fluxo: escória primeiro, depois minério
        # 3. Tipo: toco primeiro, depois trucado
        # 4. Nome do motorista: alfabético
        qs = qs.annotate(
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
            # Nome do motorista para ordenação alfabética (usar string vazia se não tiver motorista)
            motorista_nome_ordem=Case(
                When(motorista__isnull=False, then=F('motorista__nome')),
                default=Value(''),
                output_field=CharField()
            )
        ).order_by(
            'ordem_situacao',  # Ativos primeiro
            'ordem_fluxo',      # Escória primeiro
            'ordem_tipo',       # Tocos primeiro
            'motorista_nome_ordem'  # Alfabético por nome do motorista
        )
        
        return qs
    
    def carreta_display(self, obj):
        """Exibe a placa da carreta"""
        return obj.carreta.placa if obj.carreta else '-'
    carreta_display.short_description = 'Carreta'
    
    def motorista_display(self, obj):
        """Exibe o nome do motorista"""
        return obj.motorista.nome if obj.motorista else '-'
    motorista_display.short_description = 'Motorista'
    
    def cpf_motorista(self, obj):
        """Exibe o CPF do motorista"""
        return obj.motorista.cpf if obj.motorista and obj.motorista.cpf else '-'
    cpf_motorista.short_description = 'CPF'
    
    def codigo_proprietario(self, obj):
        """Exibe o código do proprietário"""
        return obj.proprietario.codigo if obj.proprietario and obj.proprietario.codigo else '-'
    codigo_proprietario.short_description = 'Código do Proprietário'


@admin.register(Carreta)
class CarretaAdmin(admin.ModelAdmin):
    list_display = ['placa', 'marca', 'modelo', 'ano', 'tipo', 'local', 'cavalo_acoplado']
    list_filter = ['tipo', 'polietileno', 'localizador']
    search_fields = ['placa', 'marca', 'modelo', 'local']
    fieldsets = (
        ('Dados Básicos', {
            'fields': ('placa', 'marca', 'modelo', 'ano', 'cor')
        }),
        ('Lavagem', {
            'fields': ('ultima_lavagem', 'proxima_lavagem')
        }),
        ('Equipamentos', {
            'fields': ('polietileno', 'cones', 'localizador', 'lona_facil', 'step')
        }),
        ('Características', {
            'fields': ('tipo', 'classificacao')
        }),
        ('Localização e Arquivos', {
            'fields': ('local', 'foto', 'documento')
        }),
        ('Informações do Sistema', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['criado_em', 'atualizado_em', 'proxima_lavagem', 'local']

    def cavalo_acoplado(self, obj):
        """Mostra qual cavalo está acoplado a esta carreta"""
        cavalo = obj.get_cavalo()
        return cavalo.placa if cavalo else 'Nenhum'
    cavalo_acoplado.short_description = 'Cavalo Acoplado'


@admin.register(Motorista)
class MotoristaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'cpf', 'whatsapp', 'cavalo']
    list_filter = ['cavalo']
    search_fields = ['nome', 'cpf', 'whatsapp', 'cavalo__placa']
    fieldsets = (
        ('Dados Básicos', {
            'fields': ('nome', 'cpf', 'whatsapp', 'cavalo')
        }),
        ('Arquivos', {
            'fields': ('foto', 'documento')
        }),
        ('Informações do Sistema', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['criado_em', 'atualizado_em']


@admin.register(LogCarreta)
class LogCarretaAdmin(admin.ModelAdmin):
    list_display = ['tipo', 'placa_cavalo', 'carreta_anterior', 'carreta_nova', 'data_hora']
    list_filter = ['tipo', 'data_hora']
    search_fields = ['placa_cavalo', 'carreta_anterior', 'carreta_nova', 'descricao']
    readonly_fields = ['tipo', 'cavalo', 'carreta_anterior', 'carreta_nova', 'placa_cavalo', 'descricao', 'data_hora']
    date_hierarchy = 'data_hora'
    fieldsets = (
        ('Informações do Log', {
            'fields': ('tipo', 'cavalo', 'placa_cavalo', 'carreta_anterior', 'carreta_nova', 'descricao', 'data_hora')
        }),
    )

    def has_add_permission(self, request):
        """Impede criação manual de logs"""
        return False

    def has_change_permission(self, request, obj=None):
        """Impede edição de logs"""
        return False


@admin.register(MarcaCavalo)
class MarcaCavaloAdmin(admin.ModelAdmin):
    list_display = ['nome', 'ativo', 'data_cadastro']
    list_filter = ['ativo', 'data_cadastro']
    search_fields = ['nome']


@admin.register(ModeloCavalo)
class ModeloCavaloAdmin(admin.ModelAdmin):
    list_display = ['nome', 'marca', 'ativo', 'data_cadastro']
    list_filter = ['marca', 'ativo', 'data_cadastro']
    search_fields = ['nome', 'marca__nome']


@admin.register(MarcaCarreta)
class MarcaCarretaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'ativo', 'data_cadastro']
    list_filter = ['ativo', 'data_cadastro']
    search_fields = ['nome']


@admin.register(ModeloCarreta)
class ModeloCarretaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'marca', 'ativo', 'data_cadastro']
    list_filter = ['marca', 'ativo', 'data_cadastro']
    search_fields = ['nome', 'marca__nome']


@admin.register(DocumentoTransporte)
class DocumentoTransporteAdmin(admin.ModelAdmin):
    list_display = ['tipo_documento', 'filial', 'serie', 'numero_documento', 'data_documento', 'cavalo', 'gestor', 'total_frete']
    list_filter = ['tipo_documento', 'data_documento', 'gestor']
    search_fields = ['filial', 'serie', 'numero_documento', 'cavalo', 'carreta', 'motorista']
    date_hierarchy = 'data_documento'
    readonly_fields = ['created_at', 'updated_at']


@admin.register(UploadLog)
class UploadLogAdmin(admin.ModelAdmin):
    list_display = ['arquivo_nome', 'tipo_detectado', 'status', 'registros_processados', 'registros_duplicados', 'usuario', 'data_upload']
    list_filter = ['status', 'tipo_detectado', 'data_upload']
    search_fields = ['arquivo_nome', 'mensagem_erro']
    readonly_fields = ['data_upload']
    date_hierarchy = 'data_upload'

