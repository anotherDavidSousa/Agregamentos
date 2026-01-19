from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from datetime import date
from .models import Cavalo, LogCarreta, Proprietario, Motorista, HistoricoGestor


@receiver(pre_save, sender=Cavalo)
def log_mudanca_cavalo(sender, instance, **kwargs):
    """Cria logs automáticos quando há mudanças no cavalo (carreta, motorista, proprietário)"""
    if instance.pk:  # Só funciona para instâncias já salvas
        try:
            cavalo_antigo = Cavalo.objects.select_related('carreta', 'motorista', 'proprietario').get(pk=instance.pk)
            
            # Verificar mudanças na carreta
            carreta_antiga = cavalo_antigo.carreta
            carreta_nova = instance.carreta

            # Se não havia carreta e agora tem (acoplamento)
            if not carreta_antiga and carreta_nova:
                LogCarreta.objects.create(
                    tipo='acoplamento',
                    cavalo=instance,
                    carreta_nova=carreta_nova.placa if carreta_nova else None,
                    placa_cavalo=instance.placa,
                    descricao=f'Carreta {carreta_nova.placa if carreta_nova else "N/A"} acoplada ao cavalo {instance.placa}'
                )

            # Se havia carreta e agora não tem (desacoplamento)
            elif carreta_antiga and not carreta_nova:
                LogCarreta.objects.create(
                    tipo='desacoplamento',
                    cavalo=instance,
                    carreta_anterior=carreta_antiga.placa if carreta_antiga else None,
                    placa_cavalo=instance.placa,
                    descricao=f'Carreta {carreta_antiga.placa if carreta_antiga else "N/A"} desacoplada do cavalo {instance.placa}'
                )

            # Se trocou de carreta (troca)
            elif carreta_antiga and carreta_nova and carreta_antiga.pk != carreta_nova.pk:
                LogCarreta.objects.create(
                    tipo='troca',
                    cavalo=instance,
                    carreta_anterior=carreta_antiga.placa if carreta_antiga else None,
                    carreta_nova=carreta_nova.placa if carreta_nova else None,
                    placa_cavalo=instance.placa,
                    descricao=f'Troca de carreta no cavalo {instance.placa}: {carreta_antiga.placa if carreta_antiga else "N/A"} → {carreta_nova.placa if carreta_nova else "N/A"}'
                )

            # Verificar mudanças no motorista
            try:
                motorista_antigo = cavalo_antigo.motorista
            except Motorista.DoesNotExist:
                motorista_antigo = None
            
            # Buscar motorista novo através do relacionamento reverso
            try:
                motorista_novo = instance.motorista
            except Motorista.DoesNotExist:
                motorista_novo = None

            # Se não havia motorista e agora tem (motorista adicionado)
            if not motorista_antigo and motorista_novo:
                LogCarreta.objects.create(
                    tipo='motorista_adicionado',
                    cavalo=instance,
                    motorista_novo=motorista_novo.nome if motorista_novo else None,
                    placa_cavalo=instance.placa,
                    descricao=f'Motorista {motorista_novo.nome if motorista_novo else "N/A"} adicionado ao cavalo {instance.placa}'
                )

            # Se havia motorista e agora não tem (motorista removido)
            elif motorista_antigo and not motorista_novo:
                LogCarreta.objects.create(
                    tipo='motorista_removido',
                    cavalo=instance,
                    motorista_anterior=motorista_antigo.nome if motorista_antigo else None,
                    placa_cavalo=instance.placa,
                    descricao=f'Motorista {motorista_antigo.nome if motorista_antigo else "N/A"} removido do cavalo {instance.placa}'
                )

            # Se trocou de motorista (motorista alterado)
            elif motorista_antigo and motorista_novo and motorista_antigo.pk != motorista_novo.pk:
                LogCarreta.objects.create(
                    tipo='motorista_alterado',
                    cavalo=instance,
                    motorista_anterior=motorista_antigo.nome if motorista_antigo else None,
                    motorista_novo=motorista_novo.nome if motorista_novo else None,
                    placa_cavalo=instance.placa,
                    descricao=f'Troca de motorista no cavalo {instance.placa}: {motorista_antigo.nome if motorista_antigo else "N/A"} → {motorista_novo.nome if motorista_novo else "N/A"}'
                )

            # Verificar mudanças no gestor
            gestor_antigo = cavalo_antigo.gestor
            gestor_novo = instance.gestor

            # Se o gestor mudou, criar/atualizar histórico
            if gestor_antigo != gestor_novo:
                # Se tinha gestor e agora não tem (removido)
                if gestor_antigo and not gestor_novo:
                    # Fechar histórico anterior se existir
                    historico_aberto = HistoricoGestor.objects.filter(
                        gestor=gestor_antigo,
                        cavalo=instance,
                        data_fim__isnull=True
                    ).first()
                    if historico_aberto:
                        historico_aberto.data_fim = date.today()
                        historico_aberto.save()

                # Se não tinha gestor e agora tem (adicionado)
                elif not gestor_antigo and gestor_novo:
                    # Criar novo histórico
                    HistoricoGestor.objects.create(
                        gestor=gestor_novo,
                        cavalo=instance,
                        data_inicio=date.today()
                    )

                # Se trocou de gestor
                elif gestor_antigo and gestor_novo and gestor_antigo.pk != gestor_novo.pk:
                    # Fechar histórico do gestor antigo
                    historico_aberto = HistoricoGestor.objects.filter(
                        gestor=gestor_antigo,
                        cavalo=instance,
                        data_fim__isnull=True
                    ).first()
                    if historico_aberto:
                        historico_aberto.data_fim = date.today()
                        historico_aberto.save()
                    
                    # Criar novo histórico para o gestor novo
                    HistoricoGestor.objects.create(
                        gestor=gestor_novo,
                        cavalo=instance,
                        data_inicio=date.today()
                    )

            # Verificar mudanças no proprietário
            proprietario_antigo = cavalo_antigo.proprietario
            proprietario_novo = instance.proprietario

            # Se trocou de proprietário
            if proprietario_antigo != proprietario_novo:
                # Se ambos existem e são diferentes (troca de proprietário)
                if proprietario_antigo and proprietario_novo and proprietario_antigo.pk != proprietario_novo.pk:
                    LogCarreta.objects.create(
                        tipo='troca_proprietario',
                        cavalo=instance,
                        proprietario_anterior=proprietario_antigo.nome_razao_social if proprietario_antigo else None,
                        proprietario_novo=proprietario_novo.nome_razao_social if proprietario_novo else None,
                        placa_cavalo=instance.placa,
                        descricao=f'Troca de proprietário no cavalo {instance.placa}: {proprietario_antigo.nome_razao_social if proprietario_antigo else "N/A"} → {proprietario_novo.nome_razao_social if proprietario_novo else "N/A"}'
                    )
                # Se tinha proprietário e agora não tem
                elif proprietario_antigo and not proprietario_novo:
                    LogCarreta.objects.create(
                        tipo='proprietario_alterado',
                        cavalo=instance,
                        proprietario_anterior=proprietario_antigo.nome_razao_social if proprietario_antigo else None,
                        placa_cavalo=instance.placa,
                        descricao=f'Proprietário removido do cavalo {instance.placa}: {proprietario_antigo.nome_razao_social if proprietario_antigo else "N/A"}'
                    )
                # Se não tinha proprietário e agora tem
                elif not proprietario_antigo and proprietario_novo:
                    LogCarreta.objects.create(
                        tipo='proprietario_alterado',
                        cavalo=instance,
                        proprietario_novo=proprietario_novo.nome_razao_social if proprietario_novo else None,
                        placa_cavalo=instance.placa,
                        descricao=f'Proprietário adicionado ao cavalo {instance.placa}: {proprietario_novo.nome_razao_social if proprietario_novo else "N/A"}'
                    )

        except Cavalo.DoesNotExist:
            # Primeira vez que está sendo salvo, não há log
            pass


@receiver(post_save, sender=Cavalo)
def atualizar_status_parceiro_apos_salvar_cavalo(sender, instance, created, **kwargs):
    """Atualiza status do parceiro automaticamente quando um cavalo é salvo"""
    if instance.proprietario:
        instance.proprietario.atualizar_status_automatico()
    
    # Se é um novo cavalo com gestor, criar histórico
    if created and instance.gestor:
        HistoricoGestor.objects.create(
            gestor=instance.gestor,
            cavalo=instance,
            data_inicio=date.today()
        )
    
    # Sincronizar com Google Sheets (em background) - apenas este cavalo
    try:
        from .google_sheets import update_cavalo_async, add_cavalo_async
        if created:
            # Novo cavalo: adicionar
            add_cavalo_async(instance.pk)
        else:
            # Cavalo existente: atualizar
            update_cavalo_async(instance.pk)
    except Exception as e:
        # Não quebrar o fluxo se houver erro na sincronização
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Erro ao sincronizar com Google Sheets: {str(e)}")


@receiver(post_delete, sender=Cavalo)
def atualizar_status_parceiro_apos_deletar_cavalo(sender, instance, **kwargs):
    """Atualiza status do parceiro automaticamente quando um cavalo é deletado"""
    if instance.proprietario:
        instance.proprietario.atualizar_status_automatico()
    
    # Sincronizar com Google Sheets (em background) - deletar apenas este cavalo
    try:
        from .google_sheets import delete_cavalo_async
        if instance.placa:
            delete_cavalo_async(instance.placa)
    except Exception as e:
        # Não quebrar o fluxo se houver erro na sincronização
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Erro ao sincronizar com Google Sheets: {str(e)}")


@receiver(pre_save, sender=Motorista)
def log_mudanca_motorista(sender, instance, **kwargs):
    """Cria logs automáticos quando há mudanças no motorista relacionado ao cavalo"""
    # Armazenar o cavalo antigo para uso no post_save
    if instance.pk:  # Só funciona para instâncias já salvas
        try:
            motorista_antigo = Motorista.objects.select_related('cavalo').get(pk=instance.pk)
            instance._cavalo_antigo = motorista_antigo.cavalo
            cavalo_antigo = motorista_antigo.cavalo
            cavalo_novo = instance.cavalo

            # Se o motorista tinha um cavalo e agora não tem (removido)
            if cavalo_antigo and not cavalo_novo:
                LogCarreta.objects.create(
                    tipo='motorista_removido',
                    cavalo=cavalo_antigo,
                    motorista_anterior=motorista_antigo.nome if motorista_antigo else None,
                    placa_cavalo=cavalo_antigo.placa if cavalo_antigo else None,
                    descricao=f'Motorista {motorista_antigo.nome if motorista_antigo else "N/A"} removido do cavalo {cavalo_antigo.placa if cavalo_antigo else "N/A"}'
                )

            # Se o motorista não tinha cavalo e agora tem (adicionado)
            elif not cavalo_antigo and cavalo_novo:
                LogCarreta.objects.create(
                    tipo='motorista_adicionado',
                    cavalo=cavalo_novo,
                    motorista_novo=instance.nome if instance else None,
                    placa_cavalo=cavalo_novo.placa if cavalo_novo else None,
                    descricao=f'Motorista {instance.nome if instance else "N/A"} adicionado ao cavalo {cavalo_novo.placa if cavalo_novo else "N/A"}'
                )

            # Se trocou de cavalo (alterado)
            elif cavalo_antigo and cavalo_novo and cavalo_antigo.pk != cavalo_novo.pk:
                LogCarreta.objects.create(
                    tipo='motorista_alterado',
                    cavalo=cavalo_novo,
                    motorista_anterior=motorista_antigo.nome if motorista_antigo else None,
                    motorista_novo=instance.nome if instance else None,
                    placa_cavalo=cavalo_novo.placa if cavalo_novo else None,
                    descricao=f'Motorista {instance.nome if instance else "N/A"} transferido do cavalo {cavalo_antigo.placa if cavalo_antigo else "N/A"} para o cavalo {cavalo_novo.placa if cavalo_novo else "N/A"}'
                )

        except Motorista.DoesNotExist:
            # Primeira vez que está sendo salvo, não há log
            instance._cavalo_antigo = None
    else:
        # Nova instância, não há cavalo antigo
        instance._cavalo_antigo = None


@receiver(post_save, sender=Motorista)
def sincronizar_cavalo_apos_mudanca_motorista(sender, instance, created, **kwargs):
    """
    Sincroniza o cavalo relacionado no Google Sheets quando o motorista é associado/removido
    Também sincroniza o cavalo antigo se o motorista foi transferido
    """
    try:
        from .google_sheets import update_cavalo_async
        
        # Obter o cavalo antigo (armazenado no pre_save)
        cavalo_antigo = getattr(instance, '_cavalo_antigo', None)
        cavalo_novo = instance.cavalo
        
        # Se o motorista tem um cavalo novo associado, sincronizar esse cavalo
        if cavalo_novo:
            update_cavalo_async(cavalo_novo.pk)
        
        # Se havia um cavalo anterior diferente do atual, sincronizar o antigo também
        if cavalo_antigo and cavalo_antigo != cavalo_novo:
            update_cavalo_async(cavalo_antigo.pk)
        
    except Exception as e:
        # Não quebrar o fluxo se houver erro na sincronização
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Erro ao sincronizar cavalo após mudança de motorista: {str(e)}")

