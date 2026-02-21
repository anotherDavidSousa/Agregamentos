from django.shortcuts import render, redirect, get_object_or_404
from django.db import models
from django.db.models import Q, Count, Case, When, Value, IntegerField, F, CharField
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.views import LoginView
from django.views.generic import FormView
from django.contrib import messages
from django.core.files.storage import default_storage
from django.conf import settings
from datetime import datetime
from decimal import Decimal
import os
import threading
import time
from .models import Proprietario, Gestor, Cavalo, Carreta, Motorista, LogCarreta, UploadLog, HistoricoGestor, DocumentoTransporte
from .forms import UploadArquivoForm
from .processadores import ProcessadorArquivos
from django.http import JsonResponse


def custom_login(request):
    """View customizada de login"""
    if request.user.is_authenticated:
        return redirect('index')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Bem-vindo, {user.username}!')
            next_url = request.GET.get('next', 'index')
            return redirect(next_url)
        else:
            messages.error(request, 'Usuário ou senha incorretos.')
    
    return render(request, 'registration/login.html')


@login_required
def custom_logout(request):
    """View customizada de logout"""
    logout(request)
    messages.success(request, 'Você foi desconectado com sucesso.')
    return redirect('login')


@login_required
def index(request):
    """Página inicial com estatísticas"""
    # Parceiros ativos (proprietários com status ativo)
    parceiros_ativos = Proprietario.objects.filter(status='sim').count()
    
    # Cavalos com carreta acoplada (não contar os sem carreta)
    total_cavalos = Cavalo.objects.exclude(carreta__isnull=True).count()
    
    total_carretas = Carreta.objects.count()
    
    # Carretas disponíveis (sem cavalo acoplado)
    carretas_disponiveis = Carreta.objects.exclude(
        id__in=Cavalo.objects.exclude(carreta__isnull=True).values_list('carreta_id', flat=True)
    ).count()
    
    # Fluxos
    # Harsco/Escória
    veiculos_escoria = Cavalo.objects.filter(
        fluxo='escoria',
        carreta__isnull=False
    ).count()
    
    # Bemisa/Minério
    veiculos_minerio = Cavalo.objects.filter(
        fluxo='minerio',
        carreta__isnull=False
    ).count()
    
    # Outros fluxos (cavalos com carreta mas sem fluxo definido ou com fluxo diferente)
    outros_fluxos = Cavalo.objects.filter(
        carreta__isnull=False
    ).filter(
        Q(fluxo__isnull=True) | Q(fluxo='') | ~Q(fluxo__in=['escoria', 'minerio'])
    ).count()

    context = {
        'parceiros_ativos': parceiros_ativos,
        'total_cavalos': total_cavalos,
        'total_carretas': total_carretas,
        'carretas_disponiveis': carretas_disponiveis,
        'veiculos_escoria': veiculos_escoria,
        'veiculos_minerio': veiculos_minerio,
        'outros_fluxos': outros_fluxos,
    }
    return render(request, 'core/index.html', context)


# Views para Proprietários (Parceiros)
@login_required
def proprietario_list(request):
    # Primeiro, atualizar status de todos os parceiros
    proprietarios = Proprietario.objects.all()
    for proprietario in proprietarios:
        proprietario.atualizar_status_automatico()
    
    # Filtros de período
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    # Filtrar apenas parceiros ativos que têm cavalos com carreta
    parceiros_ativos = Proprietario.objects.filter(
        status='sim'
    ).prefetch_related('cavalos').annotate(
        cavalos_com_carreta_count=Count(
            'cavalos',
            filter=Q(cavalos__carreta__isnull=False)
        )
    ).filter(
        cavalos_com_carreta_count__gt=0
    )
    
    # Preparar dados para a tabela
    dados_parceiros = []
    for parceiro in parceiros_ativos:
        # Buscar cavalos com carreta acoplada e ativos
        cavalos_com_carreta = list(parceiro.cavalos.filter(
            carreta__isnull=False,
            situacao='ativo'
        ).order_by('placa')[:3])
        
        # Só adicionar se tiver pelo menos um cavalo com carreta
        if cavalos_com_carreta:
            # Preencher até 3 cavalos com placa e ID
            cavalos_data = []
            placas_cavalos = []
            for cavalo in cavalos_com_carreta[:3]:
                if cavalo.placa:
                    cavalos_data.append({
                        'placa': cavalo.placa,
                        'id': cavalo.pk
                    })
                    placas_cavalos.append(cavalo.placa.upper().strip())
            
            # Preencher até 3 cavalos
            while len(cavalos_data) < 3:
                cavalos_data.append({'placa': '', 'id': None})
            
            # Calcular faturamento total de todos os veículos do proprietário
            faturamento_total = Decimal('0.00')
            if placas_cavalos:
                # Buscar todos os documentos de transporte das placas dos cavalos
                documentos_query = DocumentoTransporte.objects.filter(
                    cavalo__in=placas_cavalos
                )
                
                # Aplicar filtro de período se fornecido
                if data_inicio:
                    try:
                        from datetime import datetime
                        data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                        documentos_query = documentos_query.filter(data_documento__gte=data_inicio_obj)
                    except:
                        pass
                
                if data_fim:
                    try:
                        from datetime import datetime
                        data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
                        documentos_query = documentos_query.filter(data_documento__lte=data_fim_obj)
                    except:
                        pass
                
                # Somar o total_frete de todos os documentos
                from django.db.models import Sum
                resultado = documentos_query.aggregate(total=Sum('total_frete'))
                if resultado['total']:
                    faturamento_total = resultado['total']
            
            # Limpar WhatsApp para link
            whatsapp_limpo = ''
            if parceiro.whatsapp:
                whatsapp_limpo = parceiro.whatsapp.replace(' ', '').replace('(', '').replace(')', '').replace('-', '')
            
            dados_parceiros.append({
                'parceiro': parceiro,
                'cavalo_1': cavalos_data[0],
                'cavalo_2': cavalos_data[1],
                'cavalo_3': cavalos_data[2],
                'whatsapp_limpo': whatsapp_limpo,
                'faturamento_total': faturamento_total,
            })
    
    return render(request, 'core/proprietario_list.html', {
        'dados_parceiros': dados_parceiros,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
    })


@login_required
def proprietario_detail(request, pk):
    proprietario = get_object_or_404(Proprietario, pk=pk)
    cavalos = proprietario.cavalos.all()
    return render(request, 'core/proprietario_detail.html', {
        'proprietario': proprietario,
        'cavalos': cavalos
    })


@login_required
def proprietario_create(request):
    if request.method == 'POST':
        # Processar formulário
        codigo = request.POST.get('codigo', '').strip() or None
        nome = request.POST.get('nome_razao_social', '')
        tipo = request.POST.get('tipo', '')
        status = request.POST.get('status', 'sim')
        whatsapp = request.POST.get('whatsapp', '')
        observacoes = request.POST.get('observacoes', '')
        documento = request.FILES.get('documento', None)
        
        proprietario = Proprietario.objects.create(
            codigo=codigo,
            nome_razao_social=nome,
            tipo=tipo,
            status=status,
            whatsapp=whatsapp,
            observacoes=observacoes,
            documento=documento
        )
        # Atualizar status automaticamente após criar
        proprietario.atualizar_status_automatico()
        return redirect('proprietario_detail', pk=proprietario.pk)
    return render(request, 'core/proprietario_form.html', {'form_type': 'create'})


@login_required
def proprietario_edit(request, pk):
    proprietario = get_object_or_404(Proprietario, pk=pk)
    if request.method == 'POST':
        codigo = request.POST.get('codigo', '').strip() or None
        proprietario.codigo = codigo
        proprietario.nome_razao_social = request.POST.get('nome_razao_social', '')
        proprietario.tipo = request.POST.get('tipo', '')
        proprietario.status = request.POST.get('status', 'sim')
        proprietario.whatsapp = request.POST.get('whatsapp', '')
        proprietario.observacoes = request.POST.get('observacoes', '')
        if 'documento' in request.FILES:
            proprietario.documento = request.FILES['documento']
        proprietario.save()
        # Atualizar status automaticamente após salvar
        proprietario.atualizar_status_automatico()
        return redirect('proprietario_detail', pk=proprietario.pk)
    return render(request, 'core/proprietario_form.html', {
        'proprietario': proprietario,
        'form_type': 'edit'
    })


# Views para Gestores
@login_required
def gestor_list(request):
    from django.db.models import Q, Count, Sum
    from datetime import datetime, date
    from decimal import Decimal
    from calendar import monthrange
    
    # Filtros
    gestor_filter = request.GET.get('gestor', '')
    periodo_inicio = request.GET.get('periodo_inicio', '')
    periodo_fim = request.GET.get('periodo_fim', '')
    
    # Se não há filtro de período, usar mês atual como padrão
    if not periodo_inicio and not periodo_fim:
        hoje = date.today()
        primeiro_dia_mes = date(hoje.year, hoje.month, 1)
        ultimo_dia_mes = date(hoje.year, hoje.month, monthrange(hoje.year, hoje.month)[1])
        periodo_inicio = primeiro_dia_mes.strftime('%Y-%m-%d')
        periodo_fim = ultimo_dia_mes.strftime('%Y-%m-%d')
    
    # Converter datas
    data_inicio = None
    data_fim = None
    if periodo_inicio:
        try:
            data_inicio = datetime.strptime(periodo_inicio, '%Y-%m-%d').date()
        except ValueError:
            pass
    if periodo_fim:
        try:
            data_fim = datetime.strptime(periodo_fim, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Buscar gestores
    gestores_query = Gestor.objects.all().order_by('nome')
    if gestor_filter:
        try:
            gestor_id = int(gestor_filter)
            gestores_query = gestores_query.filter(id=gestor_id)
        except ValueError:
            pass
    
    # Calcular dados para cada gestor
    dados_gestores = []
    for gestor in gestores_query:
        # Buscar cavalos agregados ATUAIS (com gestor ativo)
        cavalos_agregados = gestor.cavalos.filter(
            gestor=gestor,
            situacao='ativo'
        ).count()
        
        # Buscar históricos do gestor no período
        historicos = HistoricoGestor.objects.filter(gestor=gestor).select_related('cavalo')
        
        # Aplicar filtro de período
        if data_inicio and data_fim:
            # Período específico: buscar históricos que se sobrepõem ao período
            historicos = historicos.filter(
                Q(data_inicio__lte=data_fim) & 
                (Q(data_fim__gte=data_inicio) | Q(data_fim__isnull=True))
            )
        elif data_inicio:
            historicos = historicos.filter(
                Q(data_fim__gte=data_inicio) | Q(data_fim__isnull=True)
            )
        elif data_fim:
            historicos = historicos.filter(data_inicio__lte=data_fim)
        
        # Contar agregados únicos no período (min e max)
        agregados_no_periodo = historicos.values('cavalo').distinct().count()
        
        # Buscar todas as placas dos cavalos do gestor (atuais e históricos)
        placas_gestor = set()
        
        # Adicionar placas dos cavalos atuais
        for cavalo in gestor.cavalos.filter(gestor=gestor, situacao='ativo'):
            if cavalo.placa:
                placas_gestor.add(cavalo.placa.strip().upper())
        
        # Adicionar placas dos históricos
        for historico in historicos:
            if historico.cavalo and historico.cavalo.placa:
                placas_gestor.add(historico.cavalo.placa.strip().upper())
        
        # Buscar documentos de transporte que têm o gestor OU que têm placas dos cavalos do gestor
        # Como cavalo é CharField, precisamos usar Q com OR para cada placa
        q_placas = Q()
        if placas_gestor:
            for placa in placas_gestor:
                q_placas |= Q(cavalo__iexact=placa)
        
        documentos_query = DocumentoTransporte.objects.filter(
            Q(gestor=gestor) | q_placas
        )
        
        if data_inicio:
            documentos_query = documentos_query.filter(data_documento__gte=data_inicio)
        if data_fim:
            documentos_query = documentos_query.filter(data_documento__lte=data_fim)
        
        # Calcular faturamento total
        faturamento_total = documentos_query.aggregate(
            total=Sum('total_frete')
        )['total'] or Decimal('0.00')
        
        dados_gestores.append({
            'gestor': gestor,
            'agregados': cavalos_agregados,
            'min_periodo': agregados_no_periodo,
            'max_periodo': agregados_no_periodo,
            'meta_faturamento': gestor.meta_faturamento,
            'faturamento_alcancado': faturamento_total,
        })
    
    # Preparar lista de placas com faturamento (todas as placas de todos os gestores)
    lista_placas = []
    
    # Buscar todos os cavalos ativos com gestor (incluindo os sem motorista)
    if gestor_filter:
        # Se há filtro de gestor, buscar apenas cavalos desse gestor
        try:
            gestor_id = int(gestor_filter)
            cavalos = Cavalo.objects.filter(
                gestor_id=gestor_id,
                situacao='ativo',
                placa__isnull=False
            ).exclude(placa='').select_related('proprietario', 'gestor')
        except ValueError:
            cavalos = Cavalo.objects.none()
    else:
        # Sem filtro, buscar todos os cavalos com gestor
        cavalos = Cavalo.objects.filter(
            gestor__isnull=False,
            situacao='ativo',
            placa__isnull=False
        ).exclude(placa='').select_related('proprietario', 'gestor')
    
    for cavalo in cavalos:
        placa = cavalo.placa.strip().upper() if cavalo.placa else ''
        if not placa:
            continue
        
        # Buscar faturamento desta placa no período
        documentos_placa = DocumentoTransporte.objects.filter(
            cavalo__iexact=placa
        )
        
        if data_inicio:
            documentos_placa = documentos_placa.filter(data_documento__gte=data_inicio)
        if data_fim:
            documentos_placa = documentos_placa.filter(data_documento__lte=data_fim)
        
        faturamento_placa = documentos_placa.aggregate(
            total=Sum('total_frete')
        )['total'] or Decimal('0.00')
        
        # Buscar motorista de forma segura (pode não existir - OneToOneField reverso)
        motorista_nome = '-'
        try:
            # Tentar acessar o motorista através do relacionamento reverso
            motorista = Motorista.objects.filter(cavalo=cavalo).first()
            if motorista and motorista.nome:
                motorista_nome = motorista.nome
        except:
            pass
        
        lista_placas.append({
            'placa': placa,
            'motorista': motorista_nome,
            'parceiro': cavalo.proprietario.nome_razao_social if cavalo.proprietario else '-',
            'tipo': cavalo.get_tipo_display() if cavalo.tipo else '-',
            'fluxo': cavalo.get_fluxo_display() if cavalo.fluxo else '-',
            'faturamento_esperado': Decimal('0.00'),  # Será definido depois
            'faturamento': faturamento_placa,
        })
    
    # Ordenar por faturamento decrescente
    lista_placas.sort(key=lambda x: x['faturamento'], reverse=True)
    
    # Buscar todos os gestores para o select
    todos_gestores = Gestor.objects.all().order_by('nome')
    
    return render(request, 'core/gestor_list.html', {
        'dados_gestores': dados_gestores,
        'gestor_filter': gestor_filter,
        'periodo_inicio': periodo_inicio,
        'periodo_fim': periodo_fim,
        'todos_gestores': todos_gestores,
        'lista_placas': lista_placas,
    })


@login_required
def gestor_create(request):
    if request.method == 'POST':
        nome = request.POST.get('nome', '')
        Gestor.objects.create(nome=nome)
        return redirect('gestor_list')
    return render(request, 'core/gestor_form.html', {'form_type': 'create'})


@login_required
def gestor_edit(request, pk):
    gestor = get_object_or_404(Gestor, pk=pk)
    if request.method == 'POST':
        gestor.nome = request.POST.get('nome', '')
        gestor.save()
        return redirect('gestor_list')
    return render(request, 'core/gestor_form.html', {
        'gestor': gestor,
        'form_type': 'edit'
    })


# Views para Cavalos
@login_required
def cavalo_list(request):
    # Filtrar: não exibir cavalos sem carreta ou com situação desagregado
    cavalos = Cavalo.objects.select_related('motorista', 'carreta', 'gestor').exclude(
        Q(carreta__isnull=True) | Q(situacao='desagregado')
    )
    
    # Alterar situação para "parado" quando não tem motorista
    from django.db import transaction
    with transaction.atomic():
        cavalos_sem_motorista = cavalos.filter(motorista__isnull=True, situacao='ativo')
        for cavalo in cavalos_sem_motorista:
            cavalo.situacao = 'parado'
            cavalo.save(update_fields=['situacao'])
    
    # Filtros
    situacao_filter = request.GET.get('situacao', '')
    tipo_filter = request.GET.get('tipo', '')
    fluxo_filter = request.GET.get('fluxo', '')
    
    # Aplicar filtros
    if situacao_filter:
        if situacao_filter == 'parado':
            # Veículo parado (sem motorista)
            cavalos = cavalos.filter(situacao='parado')
        else:
            cavalos = cavalos.filter(situacao=situacao_filter)
    
    if tipo_filter:
        cavalos = cavalos.filter(tipo=tipo_filter)
    
    if fluxo_filter:
        cavalos = cavalos.filter(fluxo=fluxo_filter)
    
    # Ordenação personalizada:
    # 1. Classificação: Agregado=0, Frota=1, Terceiro=2
    # 2. Situação: ativo primeiro, depois parado (mas Terceiros sempre por último)
    # 3. Fluxo: escória primeiro, depois minério
    # 4. Tipo: toco primeiro, depois trucado
    # 5. Nome do motorista: alfabético
    # Estrutura: Agregados Ativos → Frota Ativos → Parados (exceto Terceiros) → Terceiros (todos)
    cavalos = cavalos.annotate(
        # Ordem de classificação: agregado=0, frota=1, terceiro=2
        ordem_classificacao=Case(
            When(classificacao='agregado', then=Value(0)),
            When(classificacao='frota', then=Value(1)),
            When(classificacao='terceiro', then=Value(2)),
            default=Value(0),  # Sem classificação = agregado (compatibilidade)
            output_field=IntegerField()
        ),
        # Ordem de situação: ativo=0, parado=1 (mas Terceiros sempre por último)
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
    
    # Contadores (apenas cavalos agregados, não apenas os filtrados)
    todos_cavalos_agregados = Cavalo.objects.filter(
        Q(classificacao='agregado') | Q(classificacao__isnull=True)
    )
    contador_trucado = todos_cavalos_agregados.filter(tipo='trucado').count()
    contador_toco = todos_cavalos_agregados.filter(tipo='toco').count()
    contador_parado = todos_cavalos_agregados.filter(Q(situacao='parado') | Q(situacao='desagregado')).count()
    contador_escoria = todos_cavalos_agregados.filter(fluxo='escoria').count()
    contador_minerio = todos_cavalos_agregados.filter(fluxo='minerio').count()
    
    return render(request, 'core/cavalo_list.html', {
        'cavalos': cavalos,
        'situacao_filter': situacao_filter,
        'tipo_filter': tipo_filter,
        'fluxo_filter': fluxo_filter,
        'contador_trucado': contador_trucado,
        'contador_toco': contador_toco,
        'contador_parado': contador_parado,
        'contador_escoria': contador_escoria,
        'contador_minerio': contador_minerio,
    })


@login_required
def cavalo_detail(request, pk):
    cavalo = get_object_or_404(Cavalo, pk=pk)
    logs = cavalo.logs.all()[:10]  # Últimos 10 logs
    return render(request, 'core/cavalo_detail.html', {
        'cavalo': cavalo,
        'logs': logs
    })


@login_required
def cavalo_create(request):
    if request.method == 'POST':
        cavalo = Cavalo.objects.create(
            placa=request.POST.get('placa', ''),
            ano=request.POST.get('ano') or None,
            cor=request.POST.get('cor', ''),
            fluxo=request.POST.get('fluxo', ''),
            tipo=request.POST.get('tipo', ''),
            classificacao=request.POST.get('classificacao', ''),
            situacao=request.POST.get('situacao', ''),
            proprietario_id=request.POST.get('proprietario') or None,
            gestor_id=request.POST.get('gestor') or None,
            observacoes=request.POST.get('observacoes', ''),
            documento=request.FILES.get('documento', None)
        )
        # Processar foto
        if 'foto' in request.FILES:
            cavalo.foto = request.FILES['foto']
        
        # Gerenciar carreta (se selecionada)
        # Bi-truck não tem carreta, é um conjunto apenas com o caminhão
        if cavalo.tipo == 'bi_truck':
            cavalo.carreta = None
        else:
            carreta_id = request.POST.get('carreta') or None
            # Se for "s_placa", não atribuir carreta (já tratado acima para bi-truck)
            if carreta_id and carreta_id != 's_placa':
                try:
                    carreta = Carreta.objects.get(pk=carreta_id)
                    # Validar compatibilidade de classificação
                    if cavalo.classificacao and carreta.classificacao:
                        if cavalo.classificacao != carreta.classificacao:
                            messages.error(request, f'Erro: A carreta selecionada é de "{carreta.get_classificacao_display()}" mas o cavalo é "{cavalo.get_classificacao_display()}". Eles devem ter a mesma classificação.')
                            proprietarios = Proprietario.objects.all()
                            gestores = Gestor.objects.all()
                            motoristas = Motorista.objects.all().order_by('nome')
                            carretas_acopladas_ids = Cavalo.objects.exclude(carreta__isnull=True).values_list('carreta_id', flat=True)
                            # Passar TODAS as carretas disponíveis (não acopladas) - o JavaScript vai filtrar por classificação
                            carretas_disponiveis = Carreta.objects.exclude(id__in=carretas_acopladas_ids)
                            return render(request, 'core/cavalo_form.html', {
                                'form_type': 'create',
                                'proprietarios': proprietarios,
                                'gestores': gestores,
                                'motoristas': motoristas,
                                'carretas_disponiveis': carretas_disponiveis,
                                'cavalo': None
                            })
                    cavalo.carreta = carreta
                except Carreta.DoesNotExist:
                    cavalo.carreta = None
            else:
                cavalo.carreta = None
        
        # Gerenciar motorista
        motorista_id = request.POST.get('motorista') or None
        if motorista_id:
            try:
                motorista = Motorista.objects.get(pk=motorista_id)
                # Se o motorista já está associado a outro cavalo, remover a associação anterior
                if motorista.cavalo and motorista.cavalo.pk != cavalo.pk:
                    motorista_anterior_cavalo = motorista.cavalo
                    motorista.cavalo = None
                    motorista.save()
                # Associar motorista ao cavalo atual
                motorista.cavalo = cavalo
                motorista.save()
            except Motorista.DoesNotExist:
                pass
        else:
            # Se não selecionou motorista, remover associação atual se houver
            if cavalo.motorista:
                motorista_atual = cavalo.motorista
                motorista_atual.cavalo = None
                motorista_atual.save()
        
        cavalo.save()
        return redirect('cavalo_detail', pk=cavalo.pk)
    
    proprietarios = Proprietario.objects.all()
    gestores = Gestor.objects.all()
    motoristas = Motorista.objects.all().order_by('nome')
    # Carretas que não estão acopladas a nenhum cavalo
    # Passar TODAS as carretas disponíveis (não acopladas) - o JavaScript vai filtrar por classificação
    carretas_acopladas_ids = Cavalo.objects.exclude(carreta__isnull=True).values_list('carreta_id', flat=True)
    carretas_disponiveis = Carreta.objects.exclude(id__in=carretas_acopladas_ids)
    return render(request, 'core/cavalo_form.html', {
        'form_type': 'create',
        'proprietarios': proprietarios,
        'gestores': gestores,
        'motoristas': motoristas,
        'carretas_disponiveis': carretas_disponiveis,
        'cavalo': None  # Para o template saber que é criação
    })


@login_required
def cavalo_edit(request, pk):
    cavalo = get_object_or_404(Cavalo, pk=pk)
    if request.method == 'POST':
        cavalo.placa = request.POST.get('placa', '')
        cavalo.ano = request.POST.get('ano') or None
        cavalo.cor = request.POST.get('cor', '')
        cavalo.fluxo = request.POST.get('fluxo', '')
        cavalo.tipo = request.POST.get('tipo', '')
        cavalo.classificacao = request.POST.get('classificacao', '')
        cavalo.situacao = request.POST.get('situacao', '')
        cavalo.proprietario_id = request.POST.get('proprietario') or None
        cavalo.gestor_id = request.POST.get('gestor') or None
        cavalo.observacoes = request.POST.get('observacoes', '')
        if 'documento' in request.FILES:
            cavalo.documento = request.FILES['documento']
        if 'foto' in request.FILES:
            cavalo.foto = request.FILES['foto']
        
        # Gerenciar carreta
        # Bi-truck não tem carreta, é um conjunto apenas com o caminhão
        if cavalo.tipo == 'bi_truck':
            # Se tinha carreta antes, remover
            if cavalo.carreta:
                try:
                    cavalo_anterior = cavalo.carreta.cavalo_acoplado
                    if cavalo_anterior and cavalo_anterior.pk != cavalo.pk:
                        cavalo_anterior.carreta = None
                        cavalo_anterior.save()
                except Cavalo.DoesNotExist:
                    pass
            cavalo.carreta = None
        else:
            carreta_id = request.POST.get('carreta') or None
            # Se for "s_placa", não atribuir carreta
            if carreta_id and carreta_id != 's_placa':
                try:
                    carreta = Carreta.objects.get(pk=carreta_id)
                    # Validar compatibilidade de classificação
                    if cavalo.classificacao and carreta.classificacao:
                        if cavalo.classificacao != carreta.classificacao:
                            messages.error(request, f'Erro: A carreta selecionada é de "{carreta.get_classificacao_display()}" mas o cavalo é "{cavalo.get_classificacao_display()}". Eles devem ter a mesma classificação.')
                            proprietarios = Proprietario.objects.all()
                            gestores = Gestor.objects.all()
                            motoristas = Motorista.objects.all().order_by('nome')
                            carretas_acopladas_ids = Cavalo.objects.exclude(carreta__isnull=True).exclude(pk=pk).values_list('carreta_id', flat=True)
                            # Passar TODAS as carretas disponíveis (não acopladas) - o JavaScript vai filtrar por classificação
                            carretas_disponiveis = Carreta.objects.exclude(id__in=carretas_acopladas_ids)
                            # Incluir a carreta atual se houver (mesmo que não esteja disponível, para não perder a referência)
                            if cavalo.carreta:
                                carretas_disponiveis = carretas_disponiveis | Carreta.objects.filter(pk=cavalo.carreta.pk)
                            return render(request, 'core/cavalo_form.html', {
                                'cavalo': cavalo,
                                'form_type': 'edit',
                                'proprietarios': proprietarios,
                                'gestores': gestores,
                                'motoristas': motoristas,
                                'carretas_disponiveis': carretas_disponiveis
                            })
                    
                    # Remove carreta do cavalo anterior se houver
                    try:
                        cavalo_anterior = carreta.cavalo_acoplado
                        if cavalo_anterior and cavalo_anterior.pk != cavalo.pk:
                            cavalo_anterior.carreta = None
                            cavalo_anterior.save()
                    except Cavalo.DoesNotExist:
                        pass
                    cavalo.carreta = carreta
                except Carreta.DoesNotExist:
                    cavalo.carreta = None
            else:
                # Se não selecionou carreta ou selecionou "s_placa", remover carreta atual se houver
                if cavalo.carreta:
                    try:
                        cavalo_anterior = cavalo.carreta.cavalo_acoplado
                        if cavalo_anterior and cavalo_anterior.pk != cavalo.pk:
                            cavalo_anterior.carreta = None
                            cavalo_anterior.save()
                    except Cavalo.DoesNotExist:
                        pass
                cavalo.carreta = None
        
        # Gerenciar motorista
        motorista_id = request.POST.get('motorista') or None
        if motorista_id:
            try:
                motorista = Motorista.objects.get(pk=motorista_id)
                # Se o motorista já está associado a outro cavalo, remover a associação anterior
                if motorista.cavalo and motorista.cavalo.pk != cavalo.pk:
                    motorista_anterior_cavalo = motorista.cavalo
                    motorista.cavalo = None
                    motorista.save()
                # Associar motorista ao cavalo atual
                motorista.cavalo = cavalo
                motorista.save()
            except Motorista.DoesNotExist:
                pass
        else:
            # Se não selecionou motorista, remover associação atual se houver
            if cavalo.motorista:
                motorista_atual = cavalo.motorista
                motorista_atual.cavalo = None
                motorista_atual.save()
        
        cavalo.save()
        return redirect('cavalo_detail', pk=cavalo.pk)
    
    proprietarios = Proprietario.objects.all()
    gestores = Gestor.objects.all()
    motoristas = Motorista.objects.all().order_by('nome')
    # Carretas disponíveis + a carreta atual do cavalo (se houver)
    # Passar TODAS as carretas disponíveis (não acopladas) - o JavaScript vai filtrar por classificação
    carretas_acopladas_ids = Cavalo.objects.exclude(carreta__isnull=True).exclude(pk=cavalo.pk).values_list('carreta_id', flat=True)
    carretas_disponiveis = Carreta.objects.exclude(id__in=carretas_acopladas_ids)
    # Incluir a carreta atual se houver (mesmo que não esteja disponível, para não perder a referência)
    if cavalo.carreta:
        carretas_disponiveis = carretas_disponiveis | Carreta.objects.filter(pk=cavalo.carreta.pk)
    return render(request, 'core/cavalo_form.html', {
        'cavalo': cavalo,
        'form_type': 'edit',
        'proprietarios': proprietarios,
        'gestores': gestores,
        'motoristas': motoristas,
        'carretas_disponiveis': carretas_disponiveis
    })


# Views para Carretas
@login_required
def carreta_list(request):
    carretas = Carreta.objects.select_related().all()
    disponivel_filter = request.GET.get('disponivel', '')
    carretas_acopladas_ids = Cavalo.objects.exclude(carreta__isnull=True).values_list('carreta_id', flat=True)
    if disponivel_filter == 'sim':
        # Apenas carretas Agregado (ou sem classificação) que não estão acopladas
        carretas = carretas.filter(
            models.Q(classificacao='agregado') | models.Q(classificacao__isnull=True)
        ).exclude(id__in=carretas_acopladas_ids)
    elif disponivel_filter == 'nao':
        carretas = carretas.filter(id__in=carretas_acopladas_ids)
    
    # Contadores para carretas agregadas
    carretas_agregadas = Carreta.objects.filter(
        models.Q(classificacao='agregado') | models.Q(classificacao__isnull=True)
    )
    contador_total_agregamento = carretas_agregadas.count()
    contador_disponiveis_agregamento = carretas_agregadas.exclude(id__in=carretas_acopladas_ids).count()
    contador_paradas_agregamento = carretas_agregadas.filter(situacao='parado').count()
    
    return render(request, 'core/carreta_list.html', {
        'carretas': carretas,
        'disponivel_filter': disponivel_filter,
        'contador_total_agregamento': contador_total_agregamento,
        'contador_disponiveis_agregamento': contador_disponiveis_agregamento,
        'contador_paradas_agregamento': contador_paradas_agregamento
    })


@login_required
def carreta_detail(request, pk):
    carreta = get_object_or_404(Carreta, pk=pk)
    return render(request, 'core/carreta_detail.html', {'carreta': carreta})


@login_required
def carreta_create(request):
    if request.method == 'POST':
        # Processar data de lavagem
        ultima_lavagem_str = request.POST.get('ultima_lavagem', '').strip()
        ultima_lavagem = None
        if ultima_lavagem_str:
            try:
                from datetime import datetime
                ultima_lavagem = datetime.strptime(ultima_lavagem_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                ultima_lavagem = None
        
        carreta = Carreta.objects.create(
            placa=request.POST.get('placa', ''),
            marca=request.POST.get('marca', ''),
            modelo=request.POST.get('modelo', ''),
            ano=request.POST.get('ano') or None,
            cor=request.POST.get('cor', ''),
            ultima_lavagem=ultima_lavagem,
            polietileno=request.POST.get('polietileno', ''),
            cones=request.POST.get('cones', ''),
            localizador=request.POST.get('localizador', ''),
            lona_facil=request.POST.get('lona_facil', ''),
            step=request.POST.get('step', ''),
            tipo=request.POST.get('tipo', ''),
            classificacao=request.POST.get('classificacao', ''),
            situacao=request.POST.get('situacao', 'ativo'),
            observacoes=request.POST.get('observacoes', ''),
        )
        # Processar arquivos
        if 'foto' in request.FILES:
            carreta.foto = request.FILES['foto']
        if 'documento' in request.FILES:
            carreta.documento = request.FILES['documento']
            carreta.save()
        return redirect('carreta_detail', pk=carreta.pk)
    return render(request, 'core/carreta_form.html', {'form_type': 'create'})


@login_required
def carreta_edit(request, pk):
    carreta = get_object_or_404(Carreta, pk=pk)
    if request.method == 'POST':
        carreta.placa = request.POST.get('placa', '')
        carreta.marca = request.POST.get('marca', '')
        carreta.modelo = request.POST.get('modelo', '')
        carreta.ano = request.POST.get('ano') or None
        carreta.cor = request.POST.get('cor', '')
        
        # Processar data de lavagem
        ultima_lavagem_str = request.POST.get('ultima_lavagem', '').strip()
        if ultima_lavagem_str:
            try:
                from datetime import datetime
                carreta.ultima_lavagem = datetime.strptime(ultima_lavagem_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                carreta.ultima_lavagem = None
        else:
            carreta.ultima_lavagem = None
        
        carreta.polietileno = request.POST.get('polietileno', '')
        carreta.cones = request.POST.get('cones', '')
        carreta.localizador = request.POST.get('localizador', '')
        carreta.lona_facil = request.POST.get('lona_facil', '')
        carreta.step = request.POST.get('step', '')
        carreta.tipo = request.POST.get('tipo', '')
        carreta.classificacao = request.POST.get('classificacao', '')
        carreta.situacao = request.POST.get('situacao', 'ativo')
        carreta.observacoes = request.POST.get('observacoes', '')
        # Processar arquivos
        if 'foto' in request.FILES:
            carreta.foto = request.FILES['foto']
        if 'documento' in request.FILES:
            carreta.documento = request.FILES['documento']
        carreta.save()
        return redirect('carreta_detail', pk=carreta.pk)
    return render(request, 'core/carreta_form.html', {
        'carreta': carreta,
        'form_type': 'edit'
    })


# Views para Motoristas
@login_required
def motorista_list(request):
    motoristas = Motorista.objects.select_related('cavalo', 'cavalo__carreta').filter(cavalo__isnull=False)
    return render(request, 'core/motorista_list.html', {'motoristas': motoristas})


@login_required
def motorista_create(request):
    if request.method == 'POST':
        motorista = Motorista.objects.create(
            nome=request.POST.get('nome', ''),
            cpf=request.POST.get('cpf', ''),
            whatsapp=request.POST.get('whatsapp', ''),
            cavalo_id=request.POST.get('cavalo') or None
        )
        # Processar arquivos
        if 'foto' in request.FILES:
            motorista.foto = request.FILES['foto']
        if 'documento' in request.FILES:
            motorista.documento = request.FILES['documento']
        motorista.save()
        return redirect('motorista_detail', pk=motorista.pk)
    
    cavalos = Cavalo.objects.all()
    return render(request, 'core/motorista_form.html', {
        'form_type': 'create',
        'cavalos': cavalos
    })


@login_required
def motorista_detail(request, pk):
    motorista = get_object_or_404(Motorista.objects.select_related('cavalo', 'cavalo__carreta'), pk=pk)
    return render(request, 'core/motorista_detail.html', {
        'motorista': motorista
    })


@login_required
def motorista_edit(request, pk):
    motorista = get_object_or_404(Motorista, pk=pk)
    if request.method == 'POST':
        motorista.nome = request.POST.get('nome', '')
        motorista.cpf = request.POST.get('cpf', '')
        motorista.whatsapp = request.POST.get('whatsapp', '')
        motorista.cavalo_id = request.POST.get('cavalo') or None
        # Processar arquivos
        if 'foto' in request.FILES:
            motorista.foto = request.FILES['foto']
        if 'documento' in request.FILES:
            motorista.documento = request.FILES['documento']
        motorista.save()
        return redirect('motorista_detail', pk=motorista.pk)
    
    cavalos = Cavalo.objects.all()
    return render(request, 'core/motorista_form.html', {
        'motorista': motorista,
        'form_type': 'edit',
        'cavalos': cavalos
    })


# Views para Logs
@login_required
def log_list(request):
    logs = LogCarreta.objects.all()
    
    # Filtros
    tipo_filter = request.GET.get('tipo', '')
    placa_filter = request.GET.get('placa', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    if tipo_filter:
        logs = logs.filter(tipo=tipo_filter)
    if placa_filter:
        logs = logs.filter(
            Q(placa_cavalo__icontains=placa_filter) |
            Q(carreta_anterior__icontains=placa_filter) |
            Q(carreta_nova__icontains=placa_filter) |
            Q(motorista_anterior__icontains=placa_filter) |
            Q(motorista_novo__icontains=placa_filter) |
            Q(proprietario_anterior__icontains=placa_filter) |
            Q(proprietario_novo__icontains=placa_filter)
        )
    if data_inicio:
        try:
            data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d')
            logs = logs.filter(data_hora__gte=data_inicio_obj)
        except ValueError:
            pass
    if data_fim:
        try:
            data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d')
            logs = logs.filter(data_hora__lte=data_fim_obj)
        except ValueError:
            pass
    
    # Paginação
    paginator = Paginator(logs, 50)
    page = request.GET.get('page')
    logs_page = paginator.get_page(page)
    
    return render(request, 'core/log_list.html', {
        'logs': logs_page,
        'tipo_filter': tipo_filter,
        'placa_filter': placa_filter,
        'data_inicio': data_inicio,
        'data_fim': data_fim
    })


# Views para Upload de Arquivos
class UploadView(LoginRequiredMixin, FormView):
    template_name = 'core/upload.html'
    form_class = UploadArquivoForm
    success_url = '/upload/'
    
    def form_valid(self, form):
        extensoes_validas = ['.xls', '.xlsx', '.csv']
        arquivos_processados = []
        arquivos_erro = []
        
        # Verificar se foi usado upload múltiplo ou único
        arquivo_unico = form.cleaned_data.get('arquivo')
        arquivos_multiplos = self.request.FILES.getlist('arquivos') if 'arquivos' in self.request.FILES else []
        
        # Lista de arquivos para processar
        lista_arquivos = []
        
        # Se houver arquivo único
        if arquivo_unico:
            lista_arquivos.append(arquivo_unico)
        
        # Se houver arquivos múltiplos
        if arquivos_multiplos:
            lista_arquivos.extend(arquivos_multiplos)
        
        # Se não houver nenhum arquivo
        if not lista_arquivos:
            messages.error(self.request, 'Nenhum arquivo foi selecionado.')
            return redirect('upload')
        
        # Processar cada arquivo
        for arquivo in lista_arquivos:
            nome_arquivo = arquivo.name
            extensao = os.path.splitext(nome_arquivo)[1].lower()
            
            if extensao not in extensoes_validas:
                arquivos_erro.append(f"{nome_arquivo} - Formato não suportado")
                continue
            
            try:
                # Salvar arquivo temporariamente (com timestamp para evitar conflitos)
                timestamp = int(time.time() * 1000)
                nome_seguro = f"{timestamp}_{nome_arquivo}"
                caminho_arquivo = os.path.join(settings.MEDIA_ROOT, 'uploads', nome_seguro)
                os.makedirs(os.path.dirname(caminho_arquivo), exist_ok=True)
                
                with open(caminho_arquivo, 'wb+') as destino:
                    for chunk in arquivo.chunks():
                        destino.write(chunk)
                
                # Criar log de upload
                upload_log = UploadLog.objects.create(
                    arquivo_nome=nome_arquivo,
                    status='PROCESSANDO',
                    usuario=self.request.user
                )
                
                # Processar arquivo em thread separada para não bloquear
                thread = threading.Thread(
                    target=self._processar_arquivo_background,
                    args=(caminho_arquivo, upload_log)
                )
                thread.daemon = True
                thread.start()
                
                arquivos_processados.append(nome_arquivo)
                
            except Exception as e:
                arquivos_erro.append(f"{nome_arquivo} - {str(e)}")
        
        # Mensagens de feedback
        if arquivos_processados:
            if len(arquivos_processados) == 1:
                messages.success(self.request, f'Arquivo {arquivos_processados[0]} enviado e será processado em breve. Acompanhe o status na tabela abaixo.')
            else:
                messages.success(self.request, f'{len(arquivos_processados)} arquivos enviados e serão processados em breve. Acompanhe o status na tabela abaixo.')
        
        if arquivos_erro:
            for erro in arquivos_erro:
                messages.warning(self.request, erro)
        
        return super().form_valid(form)
    
    def _processar_arquivo_background(self, caminho_arquivo, upload_log):
        """Processa arquivo em background"""
        try:
            processador = ProcessadorArquivos()
            sucesso, mensagem = processador.processar_arquivo(caminho_arquivo, upload_log)
            
            # Remover arquivo após processamento
            try:
                if os.path.exists(caminho_arquivo):
                    os.remove(caminho_arquivo)
            except:
                pass
                
        except Exception as e:
            upload_log.status = 'ERRO'
            upload_log.mensagem_erro = str(e)
            upload_log.save()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['upload_logs'] = UploadLog.objects.all()[:20]  # Últimos 20 uploads
        return context


@login_required
def historico_upload_view(request):
    """View para histórico completo de uploads"""
    upload_logs = UploadLog.objects.all().order_by('-data_upload')
    return render(request, 'core/historico_upload.html', {
        'upload_logs': upload_logs
    })


@login_required
def ajax_carretas_classificacoes(request):
    """Endpoint AJAX para obter classificações das carretas"""
    carretas = Carreta.objects.all().values('id', 'classificacao')
    classificacoes = {str(c['id']): c['classificacao'] or '' for c in carretas}
    return JsonResponse(classificacoes)




# ── API JWT ──────────────────────────────────────────────────────────
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView


@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    usuario = request.data.get('usuario')
    senha = request.data.get('senha')

    if not usuario or not senha:
        return Response(
            {'erro': 'Informe usuário e senha.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = authenticate(request, username=usuario, password=senha)

    if user is None:
        return Response(
            {'erro': 'Credenciais inválidas.'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    if not user.is_active:
        return Response(
            {'erro': 'Usuário desativado. Contate o administrador.'},
            status=status.HTTP_403_FORBIDDEN
        )

    refresh = RefreshToken.for_user(user)

    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'usuario': {
            'nome': user.get_full_name() or user.username,
            'email': user.email,
            'admin': user.is_staff,
        }
    })


api_refresh_token = TokenRefreshView.as_view()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_me(request):
    """Rota de teste — retorna os dados do usuário autenticado pelo token."""
    user = request.user
    return Response({
        'nome': user.get_full_name() or user.username,
        'email': user.email,
        'admin': user.is_staff,
    })
