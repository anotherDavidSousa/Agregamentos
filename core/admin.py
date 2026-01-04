from django.contrib import admin
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
    list_display = ['placa', 'proprietario', 'gestor', 'situacao', 'tipo', 'carreta', 'fluxo']
    list_filter = ['situacao', 'tipo', 'fluxo', 'proprietario', 'gestor']
    search_fields = ['placa', 'proprietario__nome_razao_social']
    fieldsets = (
        ('Dados Básicos', {
            'fields': ('placa', 'ano', 'cor', 'fluxo', 'tipo', 'situacao')
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
            'fields': ('tipo',)
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

