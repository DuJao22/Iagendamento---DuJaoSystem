/**
 * Sistema de Agendamento Médico por IA - João Layon
 * JavaScript para interface do usuário
 */

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('agendamentoForm');
    const btnAgendar = document.getElementById('btnAgendar');
    const textoAgendamento = document.getElementById('textoAgendamento');
    const resultadoModal = new bootstrap.Modal(document.getElementById('resultadoModal'));
    
    // Configurar formulário de agendamento
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            processarAgendamento();
        });
    }
    
    // Auto-resize do textarea
    if (textoAgendamento) {
        textoAgendamento.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
    }
    
    /**
     * Processa o agendamento via IA
     */
    async function processarAgendamento() {
        const texto = textoAgendamento.value.trim();
        
        if (!texto) {
            mostrarErro('Por favor, descreva como gostaria de agendar sua consulta.');
            return;
        }
        
        // Mostrar loading
        btnAgendar.disabled = true;
        btnAgendar.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processando...';
        
        try {
            const formData = new FormData();
            formData.append('texto_agendamento', texto);
            
            const response = await fetch('/agendar', {
                method: 'POST',
                body: formData
            });
            
            const resultado = await response.json();
            
            if (resultado.success) {
                mostrarSucesso(resultado.message);
                form.reset();
            } else {
                mostrarErro(resultado.message);
            }
            
        } catch (error) {
            console.error('Erro ao processar agendamento:', error);
            mostrarErro('Erro de conexão. Verifique sua internet e tente novamente.');
        } finally {
            // Restaurar botão
            btnAgendar.disabled = false;
            btnAgendar.innerHTML = '<i class="bi bi-calendar-plus me-2"></i>Processar Agendamento';
        }
    }
    
    /**
     * Mostra modal de sucesso
     */
    function mostrarSucesso(mensagem) {
        const modal = document.getElementById('resultadoModal');
        const modalTitle = document.getElementById('modalTitle');
        const modalMessage = document.getElementById('modalMessage');
        const verAgendamentos = document.getElementById('verAgendamentos');
        
        modalTitle.innerHTML = '<i class="bi bi-check-circle text-success me-2"></i>Agendamento Realizado!';
        modalMessage.innerHTML = mensagem.replace(/\n/g, '<br>');
        verAgendamentos.style.display = 'inline-block';
        
        // Adicionar classes de sucesso
        modal.querySelector('.modal-content').classList.remove('border-danger');
        modal.querySelector('.modal-content').classList.add('border-success');
        
        resultadoModal.show();
    }
    
    /**
     * Mostra modal de erro
     */
    function mostrarErro(mensagem) {
        const modal = document.getElementById('resultadoModal');
        const modalTitle = document.getElementById('modalTitle');
        const modalMessage = document.getElementById('modalMessage');
        const verAgendamentos = document.getElementById('verAgendamentos');
        
        modalTitle.innerHTML = '<i class="bi bi-exclamation-triangle text-warning me-2"></i>Ops! Algo não deu certo';
        modalMessage.innerHTML = mensagem;
        verAgendamentos.style.display = 'none';
        
        // Adicionar classes de erro
        modal.querySelector('.modal-content').classList.remove('border-success');
        modal.querySelector('.modal-content').classList.add('border-danger');
        
        resultadoModal.show();
    }
    
    /**
     * Adiciona sugestões de texto baseadas em exemplos
     */
    function adicionarSugestoes() {
        const sugestoes = [
            "Olá, sou Maria Silva. Gostaria de agendar uma consulta para amanhã às 15h.",
            "Boa tarde, João Santos aqui. Preciso marcar para segunda-feira de manhã, por volta das 10h.",
            "Oi, Ana Costa. Quero agendar para sexta-feira à tarde, preferencialmente às 16h.",
            "Bom dia, Carlos Oliveira. Preciso de uma consulta urgente para hoje, se possível às 14h."
        ];
        
        // Adicionar sugestão aleatória no placeholder ocasionalmente
        if (textoAgendamento && Math.random() > 0.7) {
            const sugestaoAleatoria = sugestoes[Math.floor(Math.random() * sugestoes.length)];
            setTimeout(() => {
                if (!textoAgendamento.value) {
                    textoAgendamento.placeholder = `Ex: ${sugestaoAleatoria}`;
                }
            }, 3000);
        }
    }
    
    // Inicializar sugestões
    adicionarSugestoes();
    
    /**
     * Adiciona atalhos de teclado
     */
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + Enter para enviar
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            if (textoAgendamento === document.activeElement) {
                e.preventDefault();
                processarAgendamento();
            }
        }
    });
    
    /**
     * Validação em tempo real
     */
    if (textoAgendamento) {
        textoAgendamento.addEventListener('input', function() {
            const texto = this.value.trim();
            const palavrasChave = ['consulta', 'agendar', 'marcar', 'horário', 'data'];
            const temPalavraChave = palavrasChave.some(palavra => 
                texto.toLowerCase().includes(palavra)
            );
            
            // Feedback visual sutil
            if (texto.length > 10 && temPalavraChave) {
                this.classList.remove('is-invalid');
                this.classList.add('is-valid');
            } else if (texto.length > 0) {
                this.classList.remove('is-valid');
                this.classList.add('is-invalid');
            } else {
                this.classList.remove('is-valid', 'is-invalid');
            }
        });
    }
    
    // Status da API (para debugging)
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            console.log('Sistema João Layon:', data);
        })
        .catch(error => {
            console.log('Sistema funcionando em modo offline');
        });
});

/**
 * Utilitário para formatação de datas em português
 */
function formatarDataPortugues(data) {
    const diasSemana = [
        'Domingo', 'Segunda-feira', 'Terça-feira', 'Quarta-feira',
        'Quinta-feira', 'Sexta-feira', 'Sábado'
    ];
    
    const meses = [
        'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ];
    
    const dataObj = new Date(data);
    const diaSemana = diasSemana[dataObj.getDay()];
    const dia = dataObj.getDate();
    const mes = meses[dataObj.getMonth()];
    const ano = dataObj.getFullYear();
    
    return `${diaSemana}, ${dia} de ${mes} de ${ano}`;
}

/**
 * Função para detectar suporte a voz (preparação para futuras versões)
 */
function verificarSuporteVoz() {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        console.log('Suporte a reconhecimento de voz detectado - Recurso futuro João Layon');
        return true;
    }
    return false;
}

// Verificar suporte no carregamento
verificarSuporteVoz();
