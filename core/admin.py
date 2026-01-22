from django.contrib import admin
from django.db.models import Case, When, Value, IntegerField, F, CharField
from django import forms
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


class CavaloAdminForm(forms.ModelForm):
    """Formulário customizado para adicionar campo de motorista"""
    motorista = forms.ModelChoiceField(
        queryset=Motorista.objects.all().order_by('nome'),
        required=False,
        label='Motorista',
        help_text='Selecione um motorista para associar a este cavalo. Se o motorista já estiver associado a outro cavalo, a associação anterior será removida.',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = Cavalo
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Se estiver editando um cavalo existente, pré-selecionar o motorista atual
        if self.instance and self.instance.pk:
            # Recarregar o objeto do banco para garantir que temos o relacionamento atualizado
            try:
                cavalo = Cavalo.objects.select_related('motorista').get(pk=self.instance.pk)
                if cavalo.motorista:
                    self.fields['motorista'].initial = cavalo.motorista.pk
            except Cavalo.DoesNotExist:
                pass


@admin.register(Cavalo)
class CavaloAdmin(admin.ModelAdmin):
    form = CavaloAdminForm
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
            'fields': ('proprietario', 'gestor', 'motorista', 'carreta')
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
    
    class Media:
        js = ('admin/js/cavalo_admin.js',)
    
    def get_form(self, request, obj=None, **kwargs):
        """Customiza o formulário para adicionar validação"""
        form = super().get_form(request, obj, **kwargs)
        
        # Adicionar validação customizada se necessário
        return form
    
    def get_queryset(self, request):
        """Aplica a mesma ordenação personalizada do template"""
        qs = super().get_queryset(request)
        qs = qs.select_related('motorista', 'carreta', 'proprietario', 'gestor')
        
        # Ordenação personalizada:
        # 1. Classificação: Agregado=0, Frota=1, Terceiro=2
        # 2. Situação: ativo primeiro, depois parado (mas Terceiros sempre por último)
        # 3. Fluxo: escória primeiro, depois minério
        # 4. Tipo: toco primeiro, depois trucado
        # 5. Nome do motorista: alfabético
        # Estrutura: Agregados Ativos → Frota Ativos → Parados (exceto Terceiros) → Terceiros (todos)
        qs = qs.annotate(
            # Ordem de classificação: agregado=0, frota=1, terceiro=2
            ordem_classificacao=Case(
                When(classificacao='agregado', then=Value(0)),
                When(classificacao='frota', then=Value(1)),
                When(classificacao='terceiro', then=Value(2)),
                default=Value(0),  # Sem classificação = agregado (compatibilidade)
                output_field=IntegerField()
            ),
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
            # Ordem de tipo: bi-truck=0, toco=1, trucado=2
            ordem_tipo=Case(
                When(tipo='bi_truck', then=Value(0)),
                When(tipo='toco', then=Value(1)),
                When(tipo='trucado', then=Value(2)),
                default=Value(3),
                output_field=IntegerField()
            ),
            # Nome do motorista para ordenação alfabética (usar string vazia se não tiver motorista)
            motorista_nome_ordem=Case(
                When(motorista__isnull=False, then=F('motorista__nome')),
                default=Value(''),
                output_field=CharField()
            ),
            # Ordem especial: Terceiros sempre por último, independente de situação
            # 0 = não terceiro, 1 = terceiro
            ordem_terceiro=Case(
                When(classificacao='terceiro', then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            )
        ).order_by(
            'ordem_terceiro',      # Terceiros sempre por último (0 primeiro, 1 depois)
            'ordem_classificacao', # Agregado, depois Frota, depois Terceiro
            'ordem_situacao',      # Ativos primeiro (dentro de cada classificação)
            'ordem_fluxo',         # Escória primeiro
            'ordem_tipo',          # Tocos primeiro
            'motorista_nome_ordem'  # Alfabético por nome do motorista
        )
        
        return qs
    
    def carreta_display(self, obj):
        """Exibe a placa da carreta ou S/Placa para Bi-truck"""
        if obj.tipo == 'bi_truck':
            return 'S/Placa'
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
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Passa todas as carretas disponíveis - o JavaScript vai filtrar por classificação"""
        if db_field.name == 'carreta':
            from django.db.models import Q
            carretas_acopladas_ids = Cavalo.objects.exclude(carreta__isnull=True).values_list('carreta_id', flat=True)
            
            # Tentar obter o cavalo sendo editado
            cavalo_atual = None
            if hasattr(request.resolver_match, 'kwargs') and 'object_id' in request.resolver_match.kwargs:
                try:
                    cavalo_atual = Cavalo.objects.get(pk=request.resolver_match.kwargs['object_id'])
                except Cavalo.DoesNotExist:
                    pass
            
            # Se for Bi-truck, não mostrar nenhuma carreta (será desabilitado via JS)
            if cavalo_atual and cavalo_atual.tipo == 'bi_truck':
                kwargs['queryset'] = Carreta.objects.none()
            else:
                # Passar TODAS as carretas disponíveis (não acopladas) - o JavaScript vai filtrar por classificação
                kwargs['queryset'] = Carreta.objects.exclude(id__in=carretas_acopladas_ids)
                
                # Incluir a carreta atual se houver (mesmo que não esteja disponível, para não perder a referência)
                if cavalo_atual and cavalo_atual.carreta:
                    kwargs['queryset'] = kwargs['queryset'] | Carreta.objects.filter(pk=cavalo_atual.carreta.pk)
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def save_model(self, request, obj, form, change):
        """Garante que Bi-truck não tenha carreta e gerencia associação de motorista"""
        # Se for Bi-truck, garantir que não tenha carreta
        if obj.tipo == 'bi_truck':
            # Se tinha carreta antes, remover
            if obj.carreta:
                obj.carreta = None
        
        # Salvar o cavalo primeiro para ter o ID
        super().save_model(request, obj, form, change)
        
        # Gerenciar motorista após salvar o cavalo
        motorista_selecionado = form.cleaned_data.get('motorista')
        if motorista_selecionado:
            # Se o motorista já está associado a outro cavalo, remover a associação anterior
            if motorista_selecionado.cavalo and motorista_selecionado.cavalo.pk != obj.pk:
                motorista_anterior_cavalo = motorista_selecionado.cavalo
                motorista_selecionado.cavalo = None
                motorista_selecionado.save()
            # Associar motorista ao cavalo atual
            motorista_selecionado.cavalo = obj
            motorista_selecionado.save()
        else:
            # Se não selecionou motorista, remover associação atual se houver
            if obj.motorista:
                motorista_atual = obj.motorista
                motorista_atual.cavalo = None
                motorista_atual.save()


@admin.register(Carreta)
class CarretaAdmin(admin.ModelAdmin):
    list_display = ['placa', 'marca', 'modelo', 'ano', 'tipo', 'situacao', 'local', 'cavalo_acoplado']
    list_filter = ['tipo', 'polietileno', 'localizador', 'situacao', 'classificacao']
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
            'fields': ('tipo', 'classificacao', 'situacao')
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

