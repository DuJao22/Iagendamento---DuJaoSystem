/**
 * Sistema de Chatbot Médico - João Layon
 * JavaScript para interface de chat
 */

class ChatBot {
    constructor() {
        this.chatContainer = document.getElementById('chatContainer');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.fileUploadInProgress = false;
        
        this.initializeEventListeners();
        this.scrollToBottom();
    }
    
    initializeEventListeners() {
        // Enviar mensagem com Enter
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.enviarMensagem();
            }
        });
        
        // Enviar mensagem com botão
        this.sendButton.addEventListener('click', () => {
            this.enviarMensagem();
        });
        
        // Auto-resize do input
        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = this.messageInput.scrollHeight + 'px';
        });

        // Botão de anexar arquivo
        const attachButton = document.getElementById('attachButton');
        const fileInput = document.getElementById('fileInput');
        
        if (attachButton && fileInput) {
            // Remover qualquer listener existente
            attachButton.removeEventListener('click', this.handleAttachClick);
            fileInput.removeEventListener('change', this.handleFileChange);
            
            // Criar funções bound para poder remover listeners
            this.handleAttachClick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (this.fileUploadInProgress) return;
                console.log('Attach button clicked');
                fileInput.click();
            };
            
            this.handleFileChange = (e) => {
                if (this.fileUploadInProgress) return;
                const file = e.target.files[0];
                if (file) {
                    this.fileUploadInProgress = true;
                    console.log('File selected:', file.name);
                    this.enviarArquivo(file).finally(() => {
                        this.fileUploadInProgress = false;
                    });
                }
                // Limpar o input para permitir upload do mesmo arquivo novamente
                e.target.value = '';
            };
            
            // Adicionar listeners únicos
            attachButton.addEventListener('click', this.handleAttachClick);
            fileInput.addEventListener('change', this.handleFileChange);
        }
    }
    
    async enviarMensagem(mensagemTexto = null) {
        const mensagem = mensagemTexto || this.messageInput.value.trim();
        
        if (!mensagem) return;
        
        // Limpar input
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';
        
        // Adicionar mensagem do usuário
        this.adicionarMensagem(mensagem, 'user');
        
        // Mostrar indicador de digitação
        this.mostrarTyping(true);
        
        // Desabilitar input
        this.toggleInput(false);
        
        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ mensagem: mensagem })
            });
            
            const resultado = await response.json();
            
            // Esconder indicador de digitação
            this.mostrarTyping(false);
            
            if (resultado.success) {
                // Adicionar resposta do bot
                this.adicionarMensagem(resultado.message, 'bot', resultado);
            } else {
                // Adicionar mensagem de erro
                this.adicionarMensagem(resultado.message || 'Erro ao processar mensagem.', 'bot', {tipo: 'erro'});
            }
            
        } catch (error) {
            console.error('Erro na comunicação:', error);
            this.mostrarTyping(false);
            this.adicionarMensagem('Erro de conexão. Verifique sua internet e tente novamente.', 'bot', {tipo: 'erro'});
        } finally {
            // Reabilitar input
            this.toggleInput(true);
            this.messageInput.focus();
        }
    }
    
    adicionarMensagem(texto, tipo, dados = {}) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${tipo}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Adicionar ícone para bot
        if (tipo === 'bot') {
            const icon = dados.tipo === 'erro' ? 
                '<i class="bi bi-exclamation-triangle text-warning me-2"></i>' :
                '<i class="bi bi-robot me-2"></i>';
            contentDiv.innerHTML = icon + this.formatarTexto(texto);
        } else {
            contentDiv.innerHTML = this.formatarTexto(texto);
        }
        
        messageDiv.appendChild(contentDiv);
        
        // Adicionar opções se existirem
        if (dados.tipo === 'locais') {
            this.adicionarOpcoesLocais(messageDiv);
        } else if (dados.tipo === 'especialidades') {
            if (dados.especialidades) {
                this.adicionarOpcoesEspecialidadesFiltradas(messageDiv, dados.especialidades);
            } else {
                this.adicionarOpcoesEspecialidades(messageDiv);
            }
        } else if (dados.tipo === 'horarios' && dados.horarios) {
            this.adicionarOpcoesHorarios(messageDiv, dados.horarios);
        } else if (dados.tipo === 'agendamentos_cancelamento' && dados.agendamentos) {
            this.adicionarOpcoesAgendamentos(messageDiv, dados.agendamentos);
        } else if (dados.tipo === 'opcoes_menu') {
            this.adicionarOpcoesMenu(messageDiv);
        }
        
        // Adicionar timestamp
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date().toLocaleTimeString('pt-BR', {
            hour: '2-digit',
            minute: '2-digit'
        });
        contentDiv.appendChild(timeDiv);
        
        this.chatContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    async adicionarOpcoesLocais(messageDiv) {
        try {
            const response = await fetch('/locais');
            const locais = await response.json();
            
            const optionsDiv = document.createElement('div');
            optionsDiv.className = 'options-container';
            
            locais.forEach(local => {
                const button = document.createElement('button');
                button.className = 'option-btn';
                button.innerHTML = `
                    <i class="bi bi-geo-alt-fill me-1"></i>
                    <strong>${local.nome}</strong><br>
                    <small>${local.cidade}</small>
                `;
                button.onclick = () => this.enviarMensagem(local.nome);
                optionsDiv.appendChild(button);
            });
            
            messageDiv.appendChild(optionsDiv);
        } catch (error) {
            console.error('Erro ao carregar locais:', error);
        }
    }

    async adicionarOpcoesEspecialidades(messageDiv) {
        try {
            const response = await fetch('/especialidades');
            const especialidades = await response.json();
            
            const optionsDiv = document.createElement('div');
            optionsDiv.className = 'options-container';
            
            especialidades.forEach(esp => {
                const button = document.createElement('button');
                button.className = 'option-btn';
                button.textContent = esp.nome;
                button.onclick = () => this.enviarMensagem(esp.nome);
                optionsDiv.appendChild(button);
            });
            
            messageDiv.appendChild(optionsDiv);
        } catch (error) {
            console.error('Erro ao carregar especialidades:', error);
        }
    }

    adicionarOpcoesEspecialidadesFiltradas(messageDiv, especialidades) {
        const optionsDiv = document.createElement('div');
        optionsDiv.className = 'options-container';
        
        especialidades.forEach(esp => {
            const button = document.createElement('button');
            button.className = 'option-btn';
            button.innerHTML = `
                <i class="bi bi-heart-pulse-fill me-1"></i>
                <strong>${esp.nome}</strong><br>
                <small>${esp.descricao || 'Especialidade médica'}</small>
            `;
            button.onclick = () => this.enviarMensagem(esp.nome);
            optionsDiv.appendChild(button);
        });
        
        messageDiv.appendChild(optionsDiv);
    }
    
    adicionarOpcoesHorarios(messageDiv, horarios) {
        const optionsDiv = document.createElement('div');
        optionsDiv.className = 'options-container';
        
        horarios.forEach((horario, index) => {
            const button = document.createElement('button');
            button.className = 'option-btn horario-btn';
            button.innerHTML = `
                <div class="horario-info">
                    <div class="horario-data">📅 ${horario.data_formatada} (${horario.dia_semana})</div>
                    <div class="horario-hora">🕐 ${horario.hora_formatada}</div>
                    <div class="horario-medico">👨‍⚕️ Dr(a). ${horario.medico}</div>
                    <div class="horario-especialidade">🩺 ${horario.especialidade}</div>
                    <div class="horario-local">📍 ${horario.local_nome}</div>
                    <div class="horario-duracao">⏱️ ${horario.duracao} min</div>
                </div>
            `;
            button.onclick = () => this.enviarMensagem(`${index + 1}`);
            optionsDiv.appendChild(button);
        });
        
        messageDiv.appendChild(optionsDiv);
    }
    
    adicionarOpcoesAgendamentos(messageDiv, agendamentos) {
        const optionsDiv = document.createElement('div');
        optionsDiv.className = 'options-container';
        
        agendamentos.forEach((agendamento, index) => {
            const button = document.createElement('button');
            button.className = 'option-btn';
            button.innerHTML = `
                <strong>${index + 1}</strong><br>
                ${agendamento.data} ${agendamento.hora}<br>
                <small>Dr(a). ${agendamento.medico}</small><br>
                <small>${agendamento.especialidade}</small>
            `;
            button.onclick = () => this.enviarMensagem(`${index + 1}`);
            optionsDiv.appendChild(button);
        });
        
        messageDiv.appendChild(optionsDiv);
    }
    
    adicionarOpcoesMenu(messageDiv) {
        const optionsDiv = document.createElement('div');
        optionsDiv.className = 'options-container';
        
        const opcoes = [
            { texto: '🩺 Agendar Consulta', valor: 'agendar' },
            { texto: '❌ Cancelar Consulta', valor: 'cancelar' },
            { texto: '📋 Consultar Agendamentos', valor: 'consultar' }
        ];
        
        opcoes.forEach(opcao => {
            const button = document.createElement('button');
            button.className = 'option-btn';
            button.textContent = opcao.texto;
            button.onclick = () => this.enviarMensagem(opcao.valor);
            optionsDiv.appendChild(button);
        });
        
        messageDiv.appendChild(optionsDiv);
    }
    
    formatarTexto(texto) {
        return texto
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>');
    }
    
    mostrarTyping(mostrar) {
        this.typingIndicator.style.display = mostrar ? 'flex' : 'none';
        if (mostrar) {
            this.scrollToBottom();
        }
    }
    
    toggleInput(ativo) {
        this.messageInput.disabled = !ativo;
        this.sendButton.disabled = !ativo;
        
        if (ativo) {
            this.sendButton.innerHTML = '<i class="bi bi-send"></i>';
        } else {
            this.sendButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
        }
    }
    
    scrollToBottom() {
        setTimeout(() => {
            this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
        }, 100);
    }
    
    async enviarArquivo(file) {
        try {
            // Validar tipo de arquivo
            const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'application/pdf', 
                                 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
            
            if (!allowedTypes.includes(file.type)) {
                this.adicionarMensagem('Tipo de arquivo não permitido. Aceitos: JPG, PNG, PDF, DOC, DOCX', 'bot', {tipo: 'erro'});
                return;
            }
            
            // Validar tamanho do arquivo (máximo 10MB)
            if (file.size > 10 * 1024 * 1024) {
                this.adicionarMensagem('Arquivo muito grande. Tamanho máximo: 10MB', 'bot', {tipo: 'erro'});
                return;
            }
            
            // Mostrar que o arquivo está sendo enviado
            this.adicionarMensagem(`📎 Enviando arquivo: ${file.name} (${this.formatarTamanho(file.size)})`, 'user');
            this.mostrarTyping(true);
            this.toggleInput(false);
            
            // Criar FormData para envio
            const formData = new FormData();
            formData.append('arquivo', file);
            
            const response = await fetch('/chat/upload', {
                method: 'POST',
                body: formData
            });
            
            const resultado = await response.json();
            
            this.mostrarTyping(false);
            
            if (resultado.success) {
                this.adicionarMensagem(resultado.message, 'bot', resultado);
            } else {
                this.adicionarMensagem(resultado.message || 'Erro ao enviar arquivo.', 'bot', {tipo: 'erro'});
            }
            
        } catch (error) {
            console.error('Erro no upload:', error);
            this.mostrarTyping(false);
            this.adicionarMensagem('Erro de conexão ao enviar arquivo. Tente novamente.', 'bot', {tipo: 'erro'});
        } finally {
            this.toggleInput(true);
            this.messageInput.focus();
            // Limpar o input de arquivo
            const fileInput = document.getElementById('fileInput');
            if (fileInput) fileInput.value = '';
        }
    }
    
    formatarTamanho(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
}

// Função global para quick actions
function enviarMensagem(mensagem) {
    if (window.chatBot) {
        window.chatBot.enviarMensagem(mensagem);
    }
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    window.chatBot = new ChatBot();
    
    // Status da API (para debugging)
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            console.log('Sistema João Layon Ativo:', data);
        })
        .catch(error => {
            console.log('Sistema funcionando em modo local');
        });
});