(function($) {
    'use strict';
    
    $(document).ready(function() {
        var tipoField = $('#id_tipo');
        var carretaField = $('#id_carreta');
        var classificacaoField = $('#id_classificacao');
        var helpTextId = 'bi-truck-help-text';
        
        // Mapeamento de classificação: cavalo -> carreta
        var classificacaoMap = {
            'agregado': 'agregado',
            'frota': 'frota',
            'terceiro': 'terceiro'
        };
        
        function handleBiTruck() {
            var tipoValue = tipoField.val();
            
            if (tipoValue === 'bi_truck') {
                // Se for Bi-truck, limpar e desabilitar o campo de carreta
                carretaField.val('').prop('disabled', true);
                
                // Adicionar um texto informativo se não existir
                var existingHelp = $('#' + helpTextId);
                if (existingHelp.length === 0) {
                    var helpText = $('<p></p>')
                        .attr('id', helpTextId)
                        .addClass('help')
                        .css({
                            'color': '#666',
                            'font-style': 'italic',
                            'margin-top': '5px'
                        })
                        .text('Bi-truck não possui carreta (S/Placa)');
                    carretaField.closest('.form-row, .field-carreta').find('label').after(helpText);
                }
            } else {
                // Se não for Bi-truck, habilitar o campo
                carretaField.prop('disabled', false);
                
                // Remover texto informativo
                $('#' + helpTextId).remove();
            }
        }
        
        function filtrarCarretas() {
            var tipoValue = tipoField.val();
            var classificacaoValue = classificacaoField.val();
            var selectedValue = carretaField.val();
            var selectedOptionHidden = false;
            var hasVisibleOptions = false;
            
            // Se for Bi-truck, não filtrar (já está desabilitado)
            if (tipoValue === 'bi_truck') {
                return;
            }
            
            // Determinar qual classificação de carreta é compatível
            var classificacaoCarretaEsperada = classificacaoMap[classificacaoValue] || null;
            
            // Filtrar opções do select de carreta
            carretaField.find('option').each(function() {
                var option = $(this);
                var optionValue = option.val();
                
                // Sempre mostrar a opção vazia (-------)
                if (!optionValue || optionValue === '') {
                    option.show();
                    hasVisibleOptions = true;
                    return;
                }
                
                // Obter a classificação da carreta do atributo data-classificacao
                var classificacaoCarreta = option.attr('data-classificacao');
                
                // Se não tem data-classificacao, tentar obter do objeto classificacoesCarretas (carregado via AJAX)
                if (!classificacaoCarreta && classificacoesCarretas[optionValue]) {
                    classificacaoCarreta = classificacoesCarretas[optionValue];
                    // Adicionar o atributo para uso futuro
                    option.attr('data-classificacao', classificacaoCarreta);
                }
                
                // Se ainda não tem, tentar obter via texto da opção (fallback)
                if (!classificacaoCarreta) {
                    var optionText = option.text();
                    // Procurar por padrões como "(Agregamento)", "(Frota)", "(Terceiro)"
                    if (optionText.indexOf('(Agregamento)') !== -1 || optionText.indexOf('(Agregado)') !== -1) {
                        classificacaoCarreta = 'agregado';
                    } else if (optionText.indexOf('(Frota)') !== -1) {
                        classificacaoCarreta = 'frota';
                    } else if (optionText.indexOf('(Terceiro)') !== -1) {
                        classificacaoCarreta = 'terceiro';
                    }
                }
                
                // Se não tem classificação do cavalo selecionada, ocultar todas as carretas
                if (!classificacaoValue) {
                    option.hide();
                    if (optionValue === selectedValue) {
                        selectedOptionHidden = true;
                    }
                } else {
                    // Se tem classificação, mostrar apenas carretas compatíveis
                    if (classificacaoCarreta === classificacaoCarretaEsperada) {
                        option.show();
                        hasVisibleOptions = true;
                    } else {
                        option.hide();
                        if (optionValue === selectedValue) {
                            selectedOptionHidden = true;
                        }
                    }
                }
            });
            
            // Se a opção selecionada foi ocultada, limpar seleção
            if (selectedOptionHidden) {
                carretaField.val('');
            }
        }
        
        // Carregar classificações das carretas via AJAX
        var classificacoesCarretas = {};
        function carregarClassificacoesCarretas() {
            // Fazer uma chamada AJAX para obter as classificações das carretas
            $.ajax({
                url: '/ajax/carretas/classificacoes/',
                method: 'GET',
                success: function(data) {
                    classificacoesCarretas = data;
                    // Adicionar data-classificacao nas opções
                    carretaField.find('option').each(function() {
                        var option = $(this);
                        var optionValue = option.val();
                        if (optionValue && classificacoesCarretas[optionValue]) {
                            option.attr('data-classificacao', classificacoesCarretas[optionValue]);
                        }
                    });
                    // Filtrar após carregar
                    filtrarCarretas();
                },
                error: function() {
                    // Se falhar, tentar filtrar mesmo assim usando texto da opção
                    console.warn('Erro ao carregar classificações das carretas');
                    filtrarCarretas();
                }
            });
        }
        
        // Executar ao carregar a página
        handleBiTruck();
        carregarClassificacoesCarretas();
        
        // Executar quando o tipo mudar
        tipoField.on('change', function() {
            handleBiTruck();
            if (tipoField.val() !== 'bi_truck') {
                filtrarCarretas();
            }
        });
        
        // Executar quando a classificação mudar
        classificacaoField.on('change', function() {
            filtrarCarretas();
        });
    });
})(django.jQuery);
