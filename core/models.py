from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta, date
from decimal import Decimal


class Proprietario(models.Model):
    TIPO_CHOICES = [
        ('PF', 'Pessoa Física'),
        ('PJ', 'Pessoa Jurídica'),
    ]
    
    STATUS_CHOICES = [
        ('sim', 'Sim'),
        ('nao', 'Não'),
    ]

    codigo = models.CharField(max_length=50, blank=True, null=True, unique=True, verbose_name='Código')
    nome_razao_social = models.CharField(max_length=255, blank=True, null=True)
    tipo = models.CharField(max_length=2, choices=TIPO_CHOICES, blank=True, null=True)
    status = models.CharField(max_length=3, choices=STATUS_CHOICES, default='sim', verbose_name='Status')
    whatsapp = models.CharField(max_length=20, blank=True, null=True, verbose_name='WhatsApp')
    documento = models.FileField(upload_to='proprietarios/documentos/', blank=True, null=True)
    observacoes = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    def atualizar_status_automatico(self):
        """Atualiza o status automaticamente baseado nos cavalos com carreta"""
        # Verificar se tem cavalos
        tem_cavalos = self.cavalos.exists()
        
        # Verificar se tem cavalos com carreta acoplada
        tem_cavalos_com_carreta = self.cavalos.filter(carreta__isnull=False).exists()
        
        # Se não tem cavalos ou nenhum tem carreta, desativar
        if not tem_cavalos or not tem_cavalos_com_carreta:
            if self.status != 'nao':
                self.status = 'nao'
                self.save(update_fields=['status'])
        else:
            # Se tem pelo menos um cavalo com carreta, ativar
            if self.status != 'sim':
                self.status = 'sim'
                self.save(update_fields=['status'])

    class Meta:
        verbose_name = 'Proprietário'
        verbose_name_plural = 'Proprietários'
        ordering = ['nome_razao_social']

    def __str__(self):
        return self.nome_razao_social or f'Proprietário #{self.id}'


class Gestor(models.Model):
    nome = models.CharField(max_length=255, blank=True, null=True)
    meta_faturamento = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='Meta de Faturamento')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Gestor'
        verbose_name_plural = 'Gestores'
        ordering = ['nome']

    def __str__(self):
        return self.nome or f'Gestor #{self.id}'


class Cavalo(models.Model):
    FLUXO_CHOICES = [
        ('escoria', 'Escória'),
        ('minerio', 'Minério'),
    ]

    SITUACAO_CHOICES = [
        ('ativo', 'Ativo'),
        ('parado', 'Parado'),
        ('desagregado', 'Desagregado'),
    ]

    TIPO_CHOICES = [
        ('bi_truck', 'Bi-truck'),
        ('toco', 'Toco'),
        ('trucado', 'Trucado'),
    ]

    CLASSIFICACAO_CHOICES = [
        ('agregado', 'Agregado'),
        ('frota', 'Frota'),
        ('terceiro', 'Terceiro'),
    ]

    placa = models.CharField(max_length=10, blank=True, null=True, unique=True)
    ano = models.IntegerField(blank=True, null=True)
    cor = models.CharField(max_length=50, blank=True, null=True)
    fluxo = models.CharField(max_length=20, choices=FLUXO_CHOICES, blank=True, null=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, blank=True, null=True, verbose_name='Tipo')
    classificacao = models.CharField(max_length=20, choices=CLASSIFICACAO_CHOICES, blank=True, null=True, verbose_name='Classificação')
    foto = models.ImageField(upload_to='cavalos/fotos/', blank=True, null=True, verbose_name='Foto')
    carreta = models.OneToOneField(
        'Carreta',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='cavalo_acoplado',
        verbose_name='Carreta Agregada'
    )
    situacao = models.CharField(max_length=20, choices=SITUACAO_CHOICES, blank=True, null=True)
    proprietario = models.ForeignKey(
        Proprietario,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='cavalos',
        verbose_name='Proprietário'
    )
    gestor = models.ForeignKey(
        Gestor,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='cavalos',
        verbose_name='Gestor'
    )
    documento = models.FileField(upload_to='cavalos/documentos/', blank=True, null=True)
    observacoes = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cavalo'
        verbose_name_plural = 'Cavalos'
        ordering = ['placa']

    def __str__(self):
        return self.placa or f'Cavalo #{self.id}'

    def save(self, *args, **kwargs):
        # Se a situação for desagregado, remove o gestor
        if self.situacao == 'desagregado' and self.gestor:
            # Criar log antes de remover
            from core.models import LogCarreta, HistoricoGestor
            if self.pk:  # Só cria log se já existe no banco
                LogCarreta.objects.create(
                    tipo='desagregacao',
                    cavalo=self,
                    descricao=f'Cavalo {self.placa} desagregado. Gestor {self.gestor.nome} removido.',
                    placa_cavalo=self.placa,
                )
                # Fechar histórico do gestor
                historico_aberto = HistoricoGestor.objects.filter(
                    gestor=self.gestor,
                    cavalo=self,
                    data_fim__isnull=True
                ).first()
                if historico_aberto:
                    from datetime import date
                    historico_aberto.data_fim = date.today()
                    historico_aberto.save()
            self.gestor = None
        super().save(*args, **kwargs)


class Carreta(models.Model):
    POLIETILENO_CHOICES = [
        ('sim', 'Sim'),
        ('nao', 'Não'),
        ('metade', 'Metade'),
        ('danificado', 'Danificado'),
    ]

    CONES_CHOICES = [
        ('sim', 'Sim'),
        ('nao', 'Não'),
    ]

    LOCALIZADOR_CHOICES = [
        ('sim', 'Sim'),
        ('nao', 'Não'),
        ('nao_funciona', 'Não Funciona'),
    ]

    LONA_FACIL_CHOICES = [
        ('sim', 'Sim'),
        ('nao', 'Não'),
    ]

    STEP_CHOICES = [
        ('sim', 'Sim'),
        ('nao', 'Não'),
    ]

    TIPO_CHOICES = [
        ('baixa', 'Baixa'),
        ('alta', 'Alta'),
        ('canguru', 'Canguru'),
        ('vanderleia', 'Vanderleia'),
    ]

    CLASSIFICACAO_CHOICES = [
        ('agregado', 'Agregamento'),
        ('frota', 'Frota'),
        ('terceiro', 'Terceiro'),
    ]

    SITUACAO_CHOICES = [
        ('ativo', 'Ativo'),
        ('parado', 'Parado'),
    ]

    placa = models.CharField(max_length=10, blank=True, null=True, unique=True)
    marca = models.CharField(max_length=100, blank=True, null=True)
    modelo = models.CharField(max_length=100, blank=True, null=True)
    ano = models.IntegerField(blank=True, null=True)
    cor = models.CharField(max_length=50, blank=True, null=True)
    ultima_lavagem = models.DateField(blank=True, null=True, verbose_name='Última Lavagem')
    proxima_lavagem = models.DateField(blank=True, null=True, verbose_name='Próxima Lavagem')
    polietileno = models.CharField(max_length=20, choices=POLIETILENO_CHOICES, blank=True, null=True)
    cones = models.CharField(max_length=10, choices=CONES_CHOICES, blank=True, null=True)
    localizador = models.CharField(max_length=20, choices=LOCALIZADOR_CHOICES, blank=True, null=True)
    lona_facil = models.CharField(max_length=10, choices=LONA_FACIL_CHOICES, blank=True, null=True)
    step = models.CharField(max_length=10, choices=STEP_CHOICES, blank=True, null=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, blank=True, null=True)
    classificacao = models.CharField(max_length=20, choices=CLASSIFICACAO_CHOICES, blank=True, null=True, verbose_name='Classificação')
    situacao = models.CharField(max_length=20, choices=SITUACAO_CHOICES, blank=True, null=True, verbose_name='Situação', default='ativo')
    local = models.CharField(max_length=255, blank=True, null=True, verbose_name='Local', help_text='Atualizado automaticamente por API')
    foto = models.ImageField(upload_to='carretas/fotos/', blank=True, null=True, verbose_name='Foto')
    documento = models.FileField(upload_to='carretas/documentos/', blank=True, null=True, verbose_name='Documento')
    observacoes = models.TextField(blank=True, null=True, verbose_name='Observações')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Carreta'
        verbose_name_plural = 'Carretas'
        ordering = ['placa']

    def __str__(self):
        return self.placa or f'Carreta #{self.id}'

    def calcular_proxima_lavagem(self):
        """Calcula a próxima lavagem baseada na última lavagem (30 dias)"""
        if self.ultima_lavagem:
            # Garantir que ultima_lavagem é um objeto date (não string)
            if isinstance(self.ultima_lavagem, str):
                from datetime import datetime
                try:
                    self.ultima_lavagem = datetime.strptime(self.ultima_lavagem, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    return None
            if isinstance(self.ultima_lavagem, date):
                self.proxima_lavagem = self.ultima_lavagem + timedelta(days=30)
        return self.proxima_lavagem

    def save(self, *args, **kwargs):
        # Converter string para date se necessário antes de calcular
        if self.ultima_lavagem and isinstance(self.ultima_lavagem, str):
            from datetime import datetime
            try:
                self.ultima_lavagem = datetime.strptime(self.ultima_lavagem, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                self.ultima_lavagem = None
        
        # Calcular próxima lavagem se necessário
        if self.ultima_lavagem and not self.proxima_lavagem:
            self.calcular_proxima_lavagem()
        super().save(*args, **kwargs)

    def get_cavalo(self):
        """Retorna o cavalo ao qual esta carreta está acoplada"""
        try:
            return Cavalo.objects.get(carreta=self)
        except Cavalo.DoesNotExist:
            return None
    
    @property
    def disponivel(self):
        """
        Verifica se a carreta está disponível (não acoplada E classificada como Agregado)
        Carretas Frota ou Terceiro nunca são consideradas disponíveis
        """
        # Carretas Frota ou Terceiro nunca são disponíveis
        if self.classificacao and self.classificacao in ['frota', 'terceiro']:
            return False
        # Verifica se existe algum cavalo com esta carreta
        return not Cavalo.objects.filter(carreta=self).exists()


class Motorista(models.Model):
    nome = models.CharField(max_length=255, blank=True, null=True)
    cpf = models.CharField(max_length=14, blank=True, null=True, verbose_name='CPF')
    whatsapp = models.CharField(max_length=20, blank=True, null=True, verbose_name='WhatsApp')
    foto = models.ImageField(upload_to='motoristas/fotos/', blank=True, null=True, verbose_name='Foto')
    documento = models.FileField(upload_to='motoristas/documentos/', blank=True, null=True, verbose_name='Documento')
    cavalo = models.OneToOneField(
        Cavalo,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='motorista',
        verbose_name='Cavalo'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Motorista'
        verbose_name_plural = 'Motoristas'
        ordering = ['nome']

    def __str__(self):
        return self.nome or f'Motorista #{self.id}'

    def save(self, *args, **kwargs):
        # Se o motorista está sendo atribuído a um cavalo, remove de outros cavalos
        if self.cavalo and self.pk:
            Motorista.objects.filter(cavalo=self.cavalo).exclude(pk=self.pk).update(cavalo=None)
        super().save(*args, **kwargs)


class LogCarreta(models.Model):
    TIPO_CHOICES = [
        ('acoplamento', 'Acoplamento'),
        ('desacoplamento', 'Desacoplamento'),
        ('troca', 'Troca de Carreta'),
        ('desagregacao', 'Desagregação'),
        ('motorista_adicionado', 'Motorista Adicionado'),
        ('motorista_removido', 'Motorista Removido'),
        ('motorista_alterado', 'Motorista Alterado'),
        ('proprietario_alterado', 'Proprietário Alterado'),
        ('troca_proprietario', 'Troca de Proprietário'),
    ]

    tipo = models.CharField(max_length=25, choices=TIPO_CHOICES)
    cavalo = models.ForeignKey(
        Cavalo,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='logs',
        verbose_name='Cavalo'
    )
    carreta_anterior = models.CharField(max_length=10, blank=True, null=True, verbose_name='Placa Carreta Anterior')
    carreta_nova = models.CharField(max_length=10, blank=True, null=True, verbose_name='Placa Carreta Nova')
    motorista_anterior = models.CharField(max_length=255, blank=True, null=True, verbose_name='Motorista Anterior')
    motorista_novo = models.CharField(max_length=255, blank=True, null=True, verbose_name='Motorista Novo')
    proprietario_anterior = models.CharField(max_length=255, blank=True, null=True, verbose_name='Proprietário Anterior')
    proprietario_novo = models.CharField(max_length=255, blank=True, null=True, verbose_name='Proprietário Novo')
    placa_cavalo = models.CharField(max_length=10, blank=True, null=True, verbose_name='Placa do Cavalo')
    descricao = models.TextField(blank=True, null=True)
    data_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log de Carreta'
        verbose_name_plural = 'Logs de Carretas'
        ordering = ['-data_hora']

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.placa_cavalo} - {self.data_hora.strftime("%d/%m/%Y %H:%M")}'


# Modelos para Marca e Modelo de Cavalos e Carretas
class MarcaCavalo(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name='Marca')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    data_cadastro = models.DateTimeField(auto_now_add=True, verbose_name='Data de Cadastro')
    
    class Meta:
        db_table = 'marcas_cavalo'
        ordering = ['nome']
        verbose_name = 'Marca de Cavalo'
        verbose_name_plural = 'Marcas de Cavalo'
    
    def __str__(self):
        return self.nome


class ModeloCavalo(models.Model):
    marca = models.ForeignKey(MarcaCavalo, on_delete=models.CASCADE, related_name='modelos', verbose_name='Marca')
    nome = models.CharField(max_length=100, verbose_name='Modelo')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    data_cadastro = models.DateTimeField(auto_now_add=True, verbose_name='Data de Cadastro')
    
    class Meta:
        db_table = 'modelos_cavalo'
        ordering = ['marca__nome', 'nome']
        unique_together = ['marca', 'nome']
        verbose_name = 'Modelo de Cavalo'
        verbose_name_plural = 'Modelos de Cavalo'
    
    def __str__(self):
        return f"{self.marca.nome} - {self.nome}"


class MarcaCarreta(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name='Marca')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    data_cadastro = models.DateTimeField(auto_now_add=True, verbose_name='Data de Cadastro')
    
    class Meta:
        db_table = 'marcas_carreta'
        ordering = ['nome']
        verbose_name = 'Marca de Carreta'
        verbose_name_plural = 'Marcas de Carreta'
    
    def __str__(self):
        return self.nome


class ModeloCarreta(models.Model):
    marca = models.ForeignKey(MarcaCarreta, on_delete=models.CASCADE, related_name='modelos', verbose_name='Marca')
    nome = models.CharField(max_length=100, verbose_name='Modelo')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    data_cadastro = models.DateTimeField(auto_now_add=True, verbose_name='Data de Cadastro')
    
    class Meta:
        db_table = 'modelos_carreta'
        ordering = ['marca__nome', 'nome']
        unique_together = ['marca', 'nome']
        verbose_name = 'Modelo de Carreta'
        verbose_name_plural = 'Modelos de Carreta'
    
    def __str__(self):
        return f"{self.marca.nome} - {self.nome}"


# Modelo para Documentos de Transporte (CTE e OST)
class DocumentoTransporte(models.Model):
    """Modelo unificado para CTEs e OSTs"""
    TIPO_DOCUMENTO_CHOICES = [
        ('CTE', 'CTE'),
        ('OST', 'OST'),
    ]

    tipo_documento = models.CharField(max_length=3, choices=TIPO_DOCUMENTO_CHOICES, verbose_name="Tipo de Documento")
    filial = models.CharField(max_length=50, blank=True, null=True, verbose_name="Filial")
    serie = models.CharField(max_length=50, blank=True, null=True, verbose_name="Série")
    numero_documento = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número do Documento")
    data_documento = models.DateField(blank=True, null=True, verbose_name="Data do Documento")
    
    # Dados do transporte
    motorista = models.CharField(max_length=200, blank=True, null=True, verbose_name="Motorista")
    cavalo = models.CharField(max_length=10, blank=True, null=True, verbose_name="Placa do Cavalo")
    carreta = models.CharField(max_length=10, blank=True, null=True, verbose_name="Placa da Carreta")
    tipo_frota = models.CharField(max_length=50, blank=True, null=True, verbose_name="Tipo de Frota")
    
    # Dados das empresas
    remetente = models.CharField(max_length=500, blank=True, null=True, verbose_name="Remetente")
    destinatario = models.CharField(max_length=500, blank=True, null=True, verbose_name="Destinatário")
    nota_fiscal = models.CharField(max_length=50, blank=True, null=True, verbose_name="Nota Fiscal")
    
    # Valores financeiros
    pedagio = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Pedágio")
    total_frete = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Total do Frete")
    tarifa = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Tarifa")
    
    # Campo auxiliar
    filial_serie_numero = models.CharField(max_length=200, blank=True, null=True, 
                                           verbose_name="Filial/Série/Número")
    
    # Relacionamento com gestor
    gestor = models.ForeignKey(Gestor, on_delete=models.SET_NULL, null=True, blank=True, 
                               related_name='documentos', verbose_name="Gestor")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")

    class Meta:
        verbose_name = "Documento de Transporte"
        verbose_name_plural = "Documentos de Transporte"
        ordering = ['-data_documento', '-created_at']
        indexes = [
            models.Index(fields=['tipo_documento', 'filial', 'serie', 'numero_documento']),
            models.Index(fields=['data_documento']),
            models.Index(fields=['motorista']),
            models.Index(fields=['cavalo']),
            models.Index(fields=['gestor']),
        ]

    def data_documento_formatada(self):
        """Retorna a data do documento formatada como dd/mm/yyyy"""
        if self.data_documento:
            return self.data_documento.strftime('%d/%m/%Y')
        return ''

    def __str__(self):
        return f"{self.tipo_documento} - {self.filial}/{self.serie}/{self.numero_documento}"


# Modelo para Log de Uploads
class UploadLog(models.Model):
    """Modelo para log de uploads de arquivos"""
    STATUS_CHOICES = [
        ('PROCESSANDO', 'Processando'),
        ('SUCESSO', 'Sucesso'),
        ('ERRO', 'Erro'),
    ]

    arquivo_nome = models.CharField(max_length=500, verbose_name="Nome do Arquivo")
    tipo_detectado = models.CharField(max_length=10, blank=True, null=True, verbose_name="Tipo Detectado")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PROCESSANDO', verbose_name="Status")
    registros_processados = models.IntegerField(default=0, verbose_name="Registros Processados")
    registros_duplicados = models.IntegerField(default=0, verbose_name="Registros Duplicados")
    mensagem_erro = models.TextField(blank=True, null=True, verbose_name="Mensagem de Erro")
    data_upload = models.DateTimeField(auto_now_add=True, verbose_name="Data do Upload")
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuário")

    class Meta:
        verbose_name = "Log de Upload"
        verbose_name_plural = "Logs de Upload"
        ordering = ['-data_upload']

    def __str__(self):
        return f"{self.arquivo_nome} - {self.status} - {self.data_upload.strftime('%d/%m/%Y %H:%M')}"


class HistoricoGestor(models.Model):
    """Rastreia quando um gestor foi atribuído/removido de um cavalo"""
    gestor = models.ForeignKey(
        Gestor,
        on_delete=models.CASCADE,
        related_name='historico',
        verbose_name='Gestor'
    )
    cavalo = models.ForeignKey(
        Cavalo,
        on_delete=models.CASCADE,
        related_name='historico_gestores',
        verbose_name='Cavalo'
    )
    data_inicio = models.DateField(verbose_name='Data de Início')
    data_fim = models.DateField(blank=True, null=True, verbose_name='Data de Fim')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Histórico de Gestor'
        verbose_name_plural = 'Históricos de Gestores'
        ordering = ['-data_inicio']
        indexes = [
            models.Index(fields=['gestor', 'data_inicio', 'data_fim']),
            models.Index(fields=['cavalo', 'data_inicio', 'data_fim']),
        ]

    def __str__(self):
        fim = f' até {self.data_fim.strftime("%d/%m/%Y")}' if self.data_fim else ' (ativo)'
        return f'{self.gestor.nome} - {self.cavalo.placa} - {self.data_inicio.strftime("%d/%m/%Y")}{fim}'


# Modelos para múltiplos documentos
class DocumentoProprietario(models.Model):
    """Modelo para armazenar múltiplos documentos de proprietários"""
    proprietario = models.ForeignKey(
        Proprietario,
        on_delete=models.CASCADE,
        related_name='documentos',
        verbose_name='Proprietário'
    )
    arquivo = models.FileField(upload_to='proprietarios/documentos/', verbose_name='Documento')
    descricao = models.CharField(max_length=255, blank=True, null=True, verbose_name='Descrição')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')
    
    class Meta:
        verbose_name = 'Documento do Proprietário'
        verbose_name_plural = 'Documentos dos Proprietários'
        ordering = ['-criado_em']
    
    def __str__(self):
        return f'{self.proprietario.nome_razao_social} - {self.descricao or "Documento"}'


class DocumentoMotorista(models.Model):
    """Modelo para armazenar múltiplos documentos de motoristas"""
    motorista = models.ForeignKey(
        Motorista,
        on_delete=models.CASCADE,
        related_name='documentos',
        verbose_name='Motorista'
    )
    arquivo = models.FileField(upload_to='motoristas/documentos/', verbose_name='Documento')
    descricao = models.CharField(max_length=255, blank=True, null=True, verbose_name='Descrição')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')
    
    class Meta:
        verbose_name = 'Documento do Motorista'
        verbose_name_plural = 'Documentos dos Motoristas'
        ordering = ['-criado_em']
    
    def __str__(self):
        return f'{self.motorista.nome} - {self.descricao or "Documento"}'


class DocumentoCavalo(models.Model):
    """Modelo para armazenar múltiplos documentos de cavalos"""
    cavalo = models.ForeignKey(
        Cavalo,
        on_delete=models.CASCADE,
        related_name='documentos',
        verbose_name='Cavalo'
    )
    arquivo = models.FileField(upload_to='cavalos/documentos/', verbose_name='Documento')
    descricao = models.CharField(max_length=255, blank=True, null=True, verbose_name='Descrição')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')
    
    class Meta:
        verbose_name = 'Documento do Cavalo'
        verbose_name_plural = 'Documentos dos Cavalos'
        ordering = ['-criado_em']
    
    def __str__(self):
        return f'{self.cavalo.placa} - {self.descricao or "Documento"}'


class DocumentoCarreta(models.Model):
    """Modelo para armazenar múltiplos documentos de carretas"""
    carreta = models.ForeignKey(
        Carreta,
        on_delete=models.CASCADE,
        related_name='documentos',
        verbose_name='Carreta'
    )
    arquivo = models.FileField(upload_to='carretas/documentos/', verbose_name='Documento')
    descricao = models.CharField(max_length=255, blank=True, null=True, verbose_name='Descrição')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')
    
    class Meta:
        verbose_name = 'Documento da Carreta'
        verbose_name_plural = 'Documentos das Carretas'
        ordering = ['-criado_em']
    
    def __str__(self):
        return f'{self.carreta.placa} - {self.descricao or "Documento"}'

