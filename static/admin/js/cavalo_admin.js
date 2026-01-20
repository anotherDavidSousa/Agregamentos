(function($) {
    'use strict';
    
    $(document).ready(function() {
        var tipoField = $('#id_tipo');
        var carretaField = $('#id_carreta');
        var classificacaoField = $('#id_classificacao');
        var helpTextId = 'bi-truck-help-text';
        
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
        
        // Executar ao carregar a página
        handleBiTruck();
        
        // Executar quando o tipo mudar
        tipoField.on('change', function() {
            handleBiTruck();
        });
    });
})(django.jQuery);
