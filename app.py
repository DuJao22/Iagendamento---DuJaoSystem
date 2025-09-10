import os
import logging
import uuid
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_file
from werkzeug.utils import secure_filename
import mimetypes
from datetime import datetime, date, time
import json

# Importar novos modelos SQLite
from models import (
    Paciente, Local, Especialidade, Medico, HorarioDisponivel, 
    Agendamento, Conversa, Configuracao, AgendamentoRecorrente
)

# Configure logging com formato melhorado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console
        logging.FileHandler('sistema_agendamento.log', mode='a')  # Arquivo
    ]
)

# Logger específico para o sistema
logger = logging.getLogger('SistemaAgendamento')

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-joao-layon-2025")

# Configurações de upload
UPLOAD_FOLDER = 'uploads/anexos'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Criar diretório de uploads se não existir
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Configurar para funcionar atrás de proxy (Replit)
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Importar serviço de AI
from ai_service import chatbot_service

# Registrar funções para usar nos templates
@app.template_global()
def get_file_icon_template(filename):
    """Função para usar no template Jinja2"""
    return get_file_icon(filename)

# Função global para disponibilizar configurações em todos os templates
@app.context_processor
def inject_config():
    """Injeta configurações do sistema em todos os templates"""
    return {
        'nome_clinica': Configuracao.get_valor('nome_clinica', 'Clínica João Layon'),
        'nome_assistente': Configuracao.get_valor('nome_assistente', 'Assistente Virtual'),
        'telefone_clinica': Configuracao.get_valor('telefone_clinica', '(31) 3333-4444'),
        'email_admin': Configuracao.get_valor('email_admin', 'joao@gmail.com')
    }

# Decorator para proteger rotas administrativas
def requer_login_admin(f):
    """Decorator para proteger rotas administrativas"""
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logado'):
            flash('Acesso negado. Faça login como administrador.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def allowed_file(filename):
    """Verifica se o arquivo tem extensão permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_icon(filename):
    """Retorna o ícone Bootstrap apropriado para o tipo de arquivo"""
    if not filename:
        return 'bi-file-earmark'
    
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    if ext in ['jpg', 'jpeg', 'png', 'gif']:
        return 'bi-file-earmark-image'
    elif ext in ['pdf']:
        return 'bi-file-earmark-pdf'
    elif ext in ['doc', 'docx']:
        return 'bi-file-earmark-word'
    elif ext in ['xls', 'xlsx']:
        return 'bi-file-earmark-excel'
    elif ext in ['txt']:
        return 'bi-file-earmark-text'
    else:
        return 'bi-file-earmark'

@app.route('/')
def index():
    """Página principal do chatbot"""
    return render_template('chat.html')

@app.route('/agendamentos')
@requer_login_admin
def listar_agendamentos():
    """Lista todos os agendamentos com filtros (apenas administradores)"""
    # Obter parâmetros de filtro
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    status_filtro = request.args.get('status')
    local_filtro = request.args.get('local')
    
    # Buscar locais ativos para o dropdown
    locais = Local.find_active()
    
    # Esta página é apenas para administradores
    agendamentos = Agendamento.find_all()
    
    # Aplicar filtros
    agendamentos_filtrados = []
    for agendamento in agendamentos:
        # Filtro por data de início
        if data_inicio:
            if not agendamento.data or str(agendamento.data) < data_inicio:
                continue
        
        # Filtro por data fim
        if data_fim:
            if not agendamento.data or str(agendamento.data) > data_fim:
                continue
        
        # Filtro por status
        if status_filtro and agendamento.status != status_filtro:
            continue
        
        # Filtro por local
        if local_filtro and str(agendamento.local_id) != local_filtro:
            continue
            
        agendamentos_filtrados.append(agendamento)
    
    # Adicionar dados relacionados a cada agendamento
    for agendamento in agendamentos_filtrados:
        agendamento.paciente_rel = agendamento.get_paciente()
        agendamento.medico_rel = agendamento.get_medico()
        agendamento.especialidade_rel = agendamento.get_especialidade()
        agendamento.local_rel = agendamento.get_local()
    
    # Ordenar por data e hora
    agendamentos_filtrados.sort(key=lambda a: (a.data or '9999-12-31', a.hora or '00:00'))
    return render_template('agendamentos.html', agendamentos=agendamentos_filtrados, locais=locais, admin=True)

@app.route('/chat', methods=['POST'])
def processar_chat():
    """Processa mensagem do chatbot"""
    try:
        dados = request.get_json()
        mensagem = dados.get('mensagem', '').strip()
        
        if not mensagem:
            return jsonify({
                'success': False,
                'message': 'Mensagem vazia.'
            })
        
        # Obter ou criar sessão de conversa
        session_id = session.get('chat_session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            session['chat_session_id'] = session_id
        
        # Buscar conversa existente
        conversa = Conversa.find_by_session(session_id)
        if not conversa:
            conversa = Conversa.create(session_id=session_id, estado='inicio')
        
        # Atualizar timestamp da conversa
        conversa.atualizado_em = datetime.utcnow().isoformat()
        conversa.save()
        
        # Limpeza proativa de sessões abandonadas (5% das vezes)
        import random
        if random.randint(1, 20) == 1:
            try:
                from datetime import timedelta
                data_limite = (datetime.utcnow() - timedelta(hours=6)).isoformat()
                # Buscar conversas antigas para limpeza
                query = "SELECT * FROM conversas WHERE atualizado_em < ? AND estado != 'finalizado' LIMIT 5"
                from database import db
                rows = db.execute_query(query, (data_limite,))
                
                if rows:
                    # Deletar conversas antigas
                    for row in rows:
                        conversa_antiga = Conversa(**dict(row))
                        conversa_antiga.delete()
                    logger.info(f"Limpeza: {len(rows)} conversas abandonadas removidas")
            except Exception as cleanup_error:
                logger.warning(f"Erro na limpeza: {cleanup_error}")
        
        # Processar mensagem com IA
        resposta = chatbot_service.processar_mensagem(mensagem, conversa)
        
        # MELHORIA: Adicionar timestamp para cache busting em horários
        if resposta.get('tipo') in ['horarios', 'horarios_atualizados']:
            resposta['timestamp'] = datetime.utcnow().isoformat()
            resposta['cache_key'] = f"horarios_{datetime.utcnow().timestamp()}"
        
        # Salvar mudanças na conversa
        conversa.save()
        
        return jsonify(resposta)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        mensagem = dados.get('mensagem', '') if 'dados' in locals() else 'N/A'
        logger.error(f"Erro crítico no processamento do chat - Sessão: {session.get('chat_session_id', 'N/A')} - Mensagem: '{mensagem}' - Erro: {e}\n{error_details}")
        return jsonify({
            'success': False,
            'message': 'Erro interno do servidor. Nossa equipe foi notificada. Tente novamente em alguns minutos.',
            'error_id': f"ERR_{int(datetime.utcnow().timestamp())}"
        })

@app.route('/chat/upload', methods=['POST'])
def processar_upload_chat():
    """Processa upload de arquivo via chat"""
    try:
        if 'arquivo' not in request.files:
            return jsonify({
                'success': False,
                'message': 'Nenhum arquivo foi enviado.'
            })
        
        file = request.files['arquivo']
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': 'Nenhum arquivo foi selecionado.'
            })
        
        # Obter sessão de conversa
        session_id = session.get('chat_session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'message': 'Sessão não encontrada. Recarregue a página e tente novamente.'
            })
        
        # Buscar conversa existente
        conversa = Conversa.find_by_session(session_id)
        if not conversa:
            return jsonify({
                'success': False,
                'message': 'Conversa não encontrada. Inicie uma nova conversa.'
            })
        
        # Buscar dados da conversa
        dados = conversa.get_dados()
        agendamento_temp_id = dados.get('agendamento_temp_id')
        paciente_id = conversa.paciente_id
        
        # Se não há paciente cadastrado, solicitar cadastro primeiro
        if not paciente_id:
            return jsonify({
                'success': False,
                'message': 'Você precisa se identificar primeiro. Digite seu CPF para iniciar o atendimento.'
            })
        
        # Verificar se paciente existe
        paciente = Paciente.find_by_id(paciente_id)
        if not paciente:
            return jsonify({
                'success': False,
                'message': 'Paciente não encontrado. Digite seu CPF novamente para se identificar.'
            })
        
        # Variável para controlar se é um anexo de agendamento ou arquivo geral
        agendamento = None
        if agendamento_temp_id:
            agendamento = Agendamento.find_by_id(agendamento_temp_id)
        
        # Validar arquivo
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'message': f'Tipo de arquivo não permitido. Tipos aceitos: {", ".join(ALLOWED_EXTENSIONS)}'
            })
        
        # Salvar arquivo
        filename = secure_filename(file.filename)
        # Usar agendamento_id se disponível, senão usar paciente_id  
        file_prefix = f"{agendamento.id}" if agendamento else f"pac_{paciente_id}"
        unique_filename = f"{file_prefix}_{uuid.uuid4().hex[:8]}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        # Criar diretório se não existir
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Obter o tamanho do arquivo antes de salvar
        file.seek(0, 2)  # Ir para o final do arquivo
        tamanho_arquivo = file.tell()
        file.seek(0)  # Voltar para o início
        
        # Salvar arquivo
        file.save(file_path)
        
        # Importar modelo ArquivoPaciente
        from models import ArquivoPaciente
        
        # Criar registro do arquivo
        arquivo_paciente = ArquivoPaciente.create(
            paciente_id=paciente_id,
            agendamento_id=agendamento.id if agendamento else None,
            nome_original=filename,
            nome_arquivo=unique_filename,
            caminho_arquivo=unique_filename,  # Armazenar apenas o nome do arquivo, não o path completo
            tipo_arquivo=file.content_type or (file.filename.split('.')[-1] if '.' in file.filename else 'unknown'),
            tamanho_arquivo=tamanho_arquivo,
            descricao='Arquivo enviado via chat'
        )
        
        # Se há agendamento, atualizar também o registro do agendamento
        if agendamento:
            agendamento.anexo_nome = filename
            agendamento.anexo_path = unique_filename
            agendamento.status = 'pendente_confirmacao'
            agendamento.save()
            
            # Atualizar dados da conversa
            dados['anexo_recebido'] = True
            dados['anexo_nome'] = filename
            conversa.set_dados(dados)
            conversa.estado = 'confirmacao'
            conversa.save()
            
            logger.info(f"Arquivo anexado via chat - Agendamento: {agendamento.id}, Arquivo: {filename}")
            
            # Buscar dados para confirmação
            local = Local.find_by_id(dados.get('local_id'))
            especialidade = Especialidade.find_by_id(dados.get('especialidade_id'))
            
            return jsonify({
                'success': True,
                'message': f"✅ **Arquivo Recebido com Sucesso!**\n\n" +
                          f"📎 **Arquivo:** {filename}\n\n" +
                          f"📋 **Resumo do Agendamento**\n\n" +
                          f"👤 **Paciente:** {paciente.nome}\n" +
                          f"🩺 **Médico:** {dados.get('medico_nome', 'N/A')}\n" +
                          f"🏥 **Especialidade:** {especialidade.nome if especialidade else 'N/A'}\n" +
                          f"📍 **Local:** {local.nome if local else 'N/A'}\n" +
                          f"📅 **Data:** {dados.get('data_formatada', 'N/A')}\n" +
                          f"⏰ **Horário:** {dados.get('hora_formatada', 'N/A')}\n" +
                          f"📎 **Pedido Médico:** ✅ Anexado\n\n" +
                          f"Confirma o agendamento? Digite **'sim'** para confirmar ou **'não'** para cancelar:",
                'tipo': 'confirmacao',
                'proximo_estado': 'confirmacao'
            })
        else:
            # Arquivo geral do paciente (não relacionado a agendamento específico)
            logger.info(f"Arquivo geral anexado via chat - Paciente: {paciente.nome} ({paciente_id}), Arquivo: {filename}")
            
            return jsonify({
                'success': True,
                'message': f"✅ **Arquivo Salvo com Sucesso!**\n\n" +
                          f"📎 **Arquivo:** {filename}\n" +
                          f"👤 **Paciente:** {paciente.nome}\n" +
                          f"📁 **Local:** Arquivado em seu histórico pessoal\n\n" +
                          f"🗂️ **Seu arquivo foi salvo com segurança e está disponível para consultas futuras.**\n\n" +
                          f"✨ Posso ajudar em mais alguma coisa? Digite **'menu'** para ver as opções.",
                'tipo': 'confirmacao_arquivo',
                'proximo_estado': 'inicio'
            })
        
    except Exception as e:
        logger.error(f"Erro no upload via chat: {e}")
        return jsonify({
            'success': False,
            'message': 'Erro interno ao processar arquivo. Tente novamente.'
        })

@app.route('/download-arquivo/<int:arquivo_id>')
def download_arquivo_paciente(arquivo_id):
    """Download de arquivo do paciente"""
    try:
        from models import ArquivoPaciente
        arquivo = ArquivoPaciente.find_by_id(arquivo_id)
        
        if not arquivo:
            return jsonify({
                'success': False,
                'message': 'Arquivo não encontrado.'
            }), 404
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], arquivo.caminho_arquivo)
        
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'message': 'Arquivo não encontrado no servidor.'
            }), 404
        
        # Tentar determinar o tipo MIME
        import mimetypes
        mimetype = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=arquivo.nome_original or 'arquivo',
            mimetype=mimetype
        )
        
    except Exception as e:
        logger.error(f"Erro ao fazer download de arquivo: {e}")
        return jsonify({
            'success': False,
            'message': 'Erro ao fazer download do arquivo.'
        }), 500

@app.route('/especialidades')
def listar_especialidades():
    """API para listar especialidades ativas filtradas por local da sessão"""
    try:
        # Buscar local da sessão atual
        session_id = session.get('chat_session_id')
        local_id = None
        
        if session_id:
            conversa = Conversa.find_by_session(session_id)
            if conversa:
                dados = conversa.get_dados()
                local_id = dados.get('local_id') if dados else None
        
        if local_id:
            # Buscar especialidades que têm médicos com horários no local escolhido
            from database import db
            query = """
                SELECT DISTINCT e.* FROM especialidades e
                JOIN medicos m ON e.id = m.especialidade_id
                JOIN horarios_disponiveis h ON m.id = h.medico_id
                WHERE h.local_id = {} AND e.ativo = 1 AND m.ativo = 1 AND h.ativo = 1
            """.format(local_id)
            rows = db.execute_query(query)
            especialidades = [Especialidade(**dict(row)) for row in rows] if rows else []
        else:
            # Fallback para todas as especialidades se não tiver local
            especialidades = Especialidade.find_active()
            
        return jsonify([esp.to_dict() for esp in especialidades])
        
    except Exception as e:
        logger.error(f"Erro ao listar especialidades: {e}")
        # Fallback em caso de erro
        especialidades = Especialidade.find_active()
        return jsonify([esp.to_dict() for esp in especialidades])

@app.route('/locais')
def listar_locais():
    """API para listar locais ativos"""
    locais = Local.find_active()
    return jsonify([local.to_dict() for local in locais])

@app.route('/api/verificar-disponibilidade', methods=['POST'])
def verificar_disponibilidade():
    """API para verificar se um horário específico ainda está disponível"""
    try:
        dados = request.get_json()
        medico_id = dados.get('medico_id')
        data_str = dados.get('data')  # formato: YYYY-MM-DD
        hora_str = dados.get('hora')  # formato: HH:MM
        
        if not all([medico_id, data_str, hora_str]):
            return jsonify({'disponivel': False, 'motivo': 'Dados incompletos'})
        
        # Converter para objetos datetime
        from datetime import datetime
        data_agendamento = datetime.strptime(data_str, '%Y-%m-%d').date()
        hora_agendamento = datetime.strptime(hora_str, '%H:%M').time()
        
        # Verificar agendamento normal
        from database import db
        query = """
            SELECT * FROM agendamentos 
            WHERE medico_id = ? AND data = ? AND hora = ? AND status = 'agendado'
        """
        rows = db.execute_query(query, (medico_id, data_str, hora_str))
        
        if rows:
            return jsonify({
                'disponivel': False, 
                'motivo': 'Horário já ocupado por outro paciente',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Verificar agendamento recorrente
        dia_semana = data_agendamento.weekday()
        query_recorrente = """
            SELECT * FROM agendamentos_recorrentes 
            WHERE medico_id = ? AND dia_semana = ? AND hora = ? AND ativo = 1
            AND data_inicio <= ? AND (data_fim IS NULL OR data_fim >= ?)
        """
        rows_recorrentes = db.execute_query(query_recorrente, 
                                          (medico_id, dia_semana, hora_str, data_str, data_str))
        
        if rows_recorrentes:
            return jsonify({
                'disponivel': False, 
                'motivo': 'Horário bloqueado por agendamento recorrente',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        return jsonify({
            'disponivel': True, 
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Erro ao verificar disponibilidade: {e}")
        return jsonify({'disponivel': False, 'motivo': 'Erro interno'})

@app.route('/cancelar/<int:agendamento_id>', methods=['POST'])
@requer_login_admin
def cancelar_agendamento(agendamento_id):
    """Cancela um agendamento (admin)"""
    try:
        agendamento = Agendamento.find_by_id(agendamento_id)
        if not agendamento:
            flash('Agendamento não encontrado.', 'error')
            return redirect(url_for('listar_agendamentos'))
        
        agendamento.cancelar('Cancelado pela administração')
        
        flash('Agendamento cancelado com sucesso!', 'success')
        return redirect(url_for('listar_agendamentos'))
        
    except Exception as e:
        logging.error(f"Erro ao cancelar agendamento: {e}")
        flash('Erro ao cancelar agendamento. Tente novamente.', 'error')
        return redirect(url_for('listar_agendamentos'))

# Novas rotas para ações dos agendamentos
@app.route('/admin/agendamento/<int:agendamento_id>/concluir', methods=['POST'])
@requer_login_admin
def concluir_agendamento(agendamento_id):
    """Marca um agendamento como concluído (admin)"""
    try:
        agendamento = Agendamento.find_by_id(agendamento_id)
        if not agendamento:
            flash('Agendamento não encontrado.', 'error')
            return redirect(url_for('listar_agendamentos'))
        
        agendamento.status = 'concluido'
        agendamento.save()
        
        flash('Agendamento marcado como concluído!', 'success')
        return redirect(url_for('listar_agendamentos'))
        
    except Exception as e:
        logging.error(f"Erro ao concluir agendamento: {e}")
        flash('Erro ao concluir agendamento. Tente novamente.', 'error')
        return redirect(url_for('listar_agendamentos'))

@app.route('/admin/agendamento/<int:agendamento_id>/cancelar', methods=['POST'])
@requer_login_admin
def cancelar_agendamento_admin(agendamento_id):
    """Cancela um agendamento (admin)"""
    try:
        agendamento = Agendamento.find_by_id(agendamento_id)
        if not agendamento:
            flash('Agendamento não encontrado.', 'error')
            return redirect(url_for('listar_agendamentos'))
        
        agendamento.cancelar('Cancelado pela administração')
        
        flash('Agendamento cancelado com sucesso!', 'success')
        return redirect(url_for('listar_agendamentos'))
        
    except Exception as e:
        logging.error(f"Erro ao cancelar agendamento: {e}")
        flash('Erro ao cancelar agendamento. Tente novamente.', 'error')
        return redirect(url_for('listar_agendamentos'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Página de login do administrador"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '').strip()
        
        email_admin = Configuracao.get_valor('email_admin', 'joao@gmail.com')
        senha_admin = Configuracao.get_valor('senha_admin', '30031936Vo')
        
        if email == email_admin and senha == senha_admin:
            session['admin_logado'] = True
            session['admin_email'] = email
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Email ou senha incorretos.', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Logout do administrador"""
    session.pop('admin_logado', None)
    session.pop('admin_email', None)
    flash('Logout realizado com sucesso!', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin')
@requer_login_admin
def admin():
    """Página administrativa"""
    especialidades = Especialidade.find_all()
    # Adicionar contagem de médicos para cada especialidade
    for esp in especialidades:
        esp.medicos = esp.get_medicos()
    
    medicos = Medico.find_all()
    locais = Local.find_all()
    horarios_disponiveis = HorarioDisponivel.find_all()
    pacientes = Paciente.find_all()
    
    # Agrupar horários por médico para melhor visualização
    horarios_agrupados = {}
    for horario in horarios_disponiveis:
        medico = horario.get_medico()
        medico_nome = medico.nome if medico else 'Médico não encontrado'
        medico_id = horario.medico_id
        chave = f"{medico_id}_{medico_nome}"
        if chave not in horarios_agrupados:
            horarios_agrupados[chave] = {
                'medico_nome': medico_nome,
                'medico_id': medico_id,
                'horarios': []
            }
        horarios_agrupados[chave]['horarios'].append(horario)
    
    # Estatísticas
    total_pacientes = len(pacientes)
    agendamentos_todos = Agendamento.find_all()
    total_agendamentos = len(agendamentos_todos)
    agendamentos_hoje = len(Agendamento.find_active_for_today())
    total_especialidades = len(Especialidade.find_active())
    
    # Stats por especialidade para relatórios
    agendamentos_por_especialidade = []
    for esp in especialidades:
        agendamentos_esp = [a for a in agendamentos_todos if a.especialidade_id == esp.id]
        total = len(agendamentos_esp)
        agendados = len([a for a in agendamentos_esp if a.status == 'agendado'])
        concluidos = len([a for a in agendamentos_esp if a.status == 'concluido'])
        cancelados = len([a for a in agendamentos_esp if a.status == 'cancelado'])
        
        if total > 0:  # Só incluir especialidades com agendamentos
            agendamentos_por_especialidade.append({
                'especialidade': esp.nome,
                'total': total,
                'agendados': agendados,
                'concluidos': concluidos,
                'cancelados': cancelados
            })
    
    # Relatório de pacientes por especialidade 
    pacientes_especialidades = []
    for paciente in pacientes:
        # Buscar todas as especialidades que este paciente já consultou/agendou
        agendamentos_paciente = [a for a in agendamentos_todos if a.paciente_id == paciente.id]
        especialidades_ids = list(set([a.especialidade_id for a in agendamentos_paciente]))
        
        if especialidades_ids:  # Só incluir pacientes que têm agendamentos
            especialidades_nomes = []
            for esp_id in especialidades_ids:
                esp = Especialidade.find_by_id(esp_id)
                if esp:
                    especialidades_nomes.append(esp.nome)
            
            pacientes_especialidades.append({
                'nome': paciente.nome,
                'cpf': paciente.cpf,
                'especialidades': especialidades_nomes,
                'total_agendamentos': len(agendamentos_paciente)
            })
    
    return render_template('admin.html',
                         especialidades=especialidades,
                         medicos=medicos,
                         locais=locais,
                         horarios_disponiveis=horarios_disponiveis,
                         horarios_agrupados=horarios_agrupados,
                         pacientes=pacientes,
                         total_pacientes=total_pacientes,
                         total_agendamentos=total_agendamentos,
                         agendamentos_hoje=agendamentos_hoje,
                         total_especialidades=total_especialidades,
                         agendamentos_por_especialidade=agendamentos_por_especialidade,
                         pacientes_especialidades=pacientes_especialidades)

@app.route('/admin/config')
@requer_login_admin
def admin_config():
    """Página de configurações"""
    configuracoes = {}
    chaves_config = ['nome_clinica', 'nome_assistente', 'telefone_clinica', 'email_admin', 'horario_funcionamento', 'bloquear_especialidades_duplicadas', 'duracao_agendamento_recorrente']
    
    for chave in chaves_config:
        configuracoes[chave] = Configuracao.get_valor(chave, '')
    
    return render_template('admin_config.html', configuracoes=configuracoes, locais=Local.find_all())

@app.route('/admin/config', methods=['POST'])
@requer_login_admin
def salvar_config():
    """Salvar configurações"""
    try:
        nome_clinica = request.form.get('nome_clinica', '').strip()
        nome_assistente = request.form.get('nome_assistente', '').strip()
        telefone_clinica = request.form.get('telefone_clinica', '').strip()
        email_admin = request.form.get('email_admin', '').strip()
        senha_admin = request.form.get('senha_admin', '').strip()
        horario_funcionamento = request.form.get('horario_funcionamento', '').strip()
        bloquear_especialidades = request.form.get('bloquear_especialidades_duplicadas')
        duracao_recorrente = request.form.get('duracao_agendamento_recorrente', '').strip()
        
        if nome_clinica:
            Configuracao.set_valor('nome_clinica', nome_clinica)
        if nome_assistente:
            Configuracao.set_valor('nome_assistente', nome_assistente)
        if telefone_clinica:
            Configuracao.set_valor('telefone_clinica', telefone_clinica)
        if email_admin:
            Configuracao.set_valor('email_admin', email_admin)
        if senha_admin:
            Configuracao.set_valor('senha_admin', senha_admin)
        if horario_funcionamento:
            Configuracao.set_valor('horario_funcionamento', horario_funcionamento)
        
        # Configurações de checkbox
        Configuracao.set_valor('bloquear_especialidades_duplicadas', 'true' if bloquear_especialidades else 'false')
        
        if duracao_recorrente and duracao_recorrente.isdigit():
            Configuracao.set_valor('duracao_agendamento_recorrente', duracao_recorrente)
        
        flash('Configurações salvas com sucesso!', 'success')
        return redirect(url_for('admin_config'))
        
    except Exception as e:
        logging.error(f"Erro ao salvar configurações: {e}")
        flash('Erro ao salvar configurações. Tente novamente.', 'error')
        return redirect(url_for('admin_config'))

@app.route('/admin/especialidades', methods=['POST'])
@requer_login_admin
def admin_especialidades():
    """Cadastrar nova especialidade"""
    try:
        nome = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip()
        requer_anexo = request.form.get('requer_anexo') == '1'
        
        if not nome:
            flash('Nome da especialidade é obrigatório.', 'error')
            return redirect(url_for('admin'))
        
        # Verificar se já existe
        existe = Especialidade.find_one_where({'nome': nome})
        if existe:
            flash('Especialidade já existe.', 'error')
            return redirect(url_for('admin'))
        
        Especialidade.create(
            nome=nome, 
            descricao=descricao if descricao else None,
            requer_anexo=requer_anexo
        )
        
        flash(f'Especialidade "{nome}" cadastrada com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        logging.error(f"Erro ao cadastrar especialidade: {e}")
        flash('Erro ao cadastrar especialidade. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/medicos', methods=['POST'])
@requer_login_admin
def admin_medicos():
    """Cadastrar novo médico"""
    try:
        nome = request.form.get('nome', '').strip()
        crm = request.form.get('crm', '').strip()
        especialidade_id = request.form.get('especialidade_id', '').strip()
        
        if not all([nome, crm, especialidade_id]):
            flash('Todos os campos são obrigatórios.', 'error')
            return redirect(url_for('admin'))
        
        # Verificar se CRM já existe
        existe = Medico.find_one_where({'crm': crm})
        if existe:
            flash('CRM já cadastrado.', 'error')
            return redirect(url_for('admin'))
        
        # Verificar se especialidade existe
        especialidade = Especialidade.find_by_id(int(especialidade_id))
        if not especialidade:
            flash('Especialidade não encontrada.', 'error')
            return redirect(url_for('admin'))
        
        Medico.create(nome=nome, crm=crm, especialidade_id=int(especialidade_id))
        
        flash(f'Médico "{nome}" cadastrado com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        logging.error(f"Erro ao cadastrar médico: {e}")
        flash('Erro ao cadastrar médico. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/locais', methods=['POST'])
@requer_login_admin
def admin_locais():
    """Cadastrar novo local"""
    try:
        nome = request.form.get('nome', '').strip()
        endereco = request.form.get('endereco', '').strip()
        cidade = request.form.get('cidade', '').strip()
        telefone = request.form.get('telefone', '').strip()
        
        if not nome:
            flash('Nome do local é obrigatório.', 'error')
            return redirect(url_for('admin'))
        
        # Verificar se já existe
        existe = Local.find_one_where({'nome': nome})
        if existe:
            flash('Local já existe.', 'error')
            return redirect(url_for('admin'))
        
        Local.create(
            nome=nome,
            endereco=endereco if endereco else None,
            cidade=cidade if cidade else None,
            telefone=telefone if telefone else None
        )
        
        flash(f'Local "{nome}" cadastrado com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        logging.error(f"Erro ao cadastrar local: {e}")
        flash('Erro ao cadastrar local. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/horarios', methods=['POST'])
@requer_login_admin
def admin_horarios():
    """Cadastrar novo horário disponível"""
    try:
        medico_id = request.form.get('medico_id', '').strip()
        local_id = request.form.get('local_id', '').strip()
        dia_semana = request.form.get('dia_semana', '').strip()
        hora_inicio = request.form.get('hora_inicio', '').strip()
        hora_fim = request.form.get('hora_fim', '').strip()
        duracao_consulta = request.form.get('duracao_consulta', '30').strip()
        
        if not all([medico_id, local_id, dia_semana, hora_inicio, hora_fim]):
            flash('Todos os campos são obrigatórios.', 'error')
            return redirect(url_for('admin'))
        
        HorarioDisponivel.create(
            medico_id=int(medico_id),
            local_id=int(local_id),
            dia_semana=int(dia_semana),
            hora_inicio=hora_inicio,
            hora_fim=hora_fim,
            duracao_consulta=int(duracao_consulta)
        )
        
        flash('Horário cadastrado com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        logging.error(f"Erro ao cadastrar horário: {e}")
        flash('Erro ao cadastrar horário. Tente novamente.', 'error')
        return redirect(url_for('admin'))

# Log de sistema ativo (para debug) - Removido before_first_request depreciado
def log_sistema_ativo():
    """Log quando o sistema ficar ativo"""
    logger.info("Sistema João Layon Ativo: SQLite3 Version")
    stats = {
        'status': 'ativo',
        'versao': '2.0.0 - SQLite3 Pure',
        'desenvolvedor': 'João Layon',
        'preco_mensal': 'R$ 19,90',
        'total_pacientes': len(Paciente.find_all()),
        'total_agendamentos': len(Agendamento.find_all()),
        'agendamentos_hoje': len(Agendamento.find_active_for_today()),
        'especialidades': len(Especialidade.find_active())
    }
    print("Sistema João Layon Ativo:", stats)

# Executar log no carregamento do módulo
log_sistema_ativo()

# Rota para editar médico
@app.route('/admin/medico/<int:medico_id>/edit')
@requer_login_admin
def editar_medico(medico_id):
    """Página para editar médico"""
    medico = Medico.find_by_id(medico_id)
    if not medico:
        flash('Médico não encontrado.', 'error')
        return redirect(url_for('admin'))
    
    especialidades = Especialidade.find_all()
    return render_template('editar_medico.html', medico=medico, especialidades=especialidades)

# Rota para editar local
@app.route('/admin/local/<int:local_id>/edit')
@requer_login_admin
def editar_local(local_id):
    """Página para editar local"""
    local = Local.find_by_id(local_id)
    if not local:
        flash('Local não encontrado.', 'error')
        return redirect(url_for('admin'))
    
    return render_template('editar_local.html', local=local)

# Rota POST para salvar alterações do local
@app.route('/admin/local/<int:local_id>/edit', methods=['POST'])
@requer_login_admin
def salvar_local(local_id):
    """Salvar alterações do local"""
    try:
        local = Local.find_by_id(local_id)
        if not local:
            flash('Local não encontrado.', 'error')
            return redirect(url_for('admin'))
        
        nome = request.form.get('nome', '').strip()
        cidade = request.form.get('cidade', '').strip()
        endereco = request.form.get('endereco', '').strip()
        telefone = request.form.get('telefone', '').strip()
        
        if not nome or not cidade:
            flash('Nome e cidade são obrigatórios.', 'error')
            return redirect(url_for('editar_local', local_id=local_id))
        
        # Atualizar os dados
        local.nome = nome
        local.cidade = cidade
        local.endereco = endereco if endereco else None
        local.telefone = telefone if telefone else None
        local.save()
        
        flash(f'Local "{nome}" atualizado com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        logging.error(f"Erro ao atualizar local: {e}")
        flash('Erro ao salvar alterações. Tente novamente.', 'error')
        return redirect(url_for('editar_local', local_id=local_id))

# Rota para buscar detalhes do paciente (AJAX)
@app.route('/admin/paciente/<int:paciente_id>/detalhes')
@requer_login_admin
def detalhes_paciente(paciente_id):
    """API para buscar detalhes do paciente"""
    try:
        paciente = Paciente.find_by_id(paciente_id)
        if not paciente:
            return jsonify({'success': False, 'message': 'Paciente não encontrado'})
        
        # Buscar agendamentos do paciente
        agendamentos = Agendamento.find_where({'paciente_id': paciente_id})
        
        # Gerar HTML com os detalhes
        html = f"""
        <div class="row">
            <div class="col-md-6">
                <h6>Informações Pessoais</h6>
                <p><strong>Nome:</strong> {paciente.nome}</p>
                <p><strong>CPF:</strong> {paciente.cpf}</p>
                <p><strong>Telefone:</strong> {paciente.telefone or 'Não informado'}</p>
                <p><strong>Email:</strong> {paciente.email or 'Não informado'}</p>
                <p><strong>Data de Nascimento:</strong> {paciente.data_nascimento or 'Não informado'}</p>
            </div>
            <div class="col-md-6">
                <h6>Estatísticas</h6>
                <p><strong>Total de Agendamentos:</strong> {len(agendamentos)}</p>
                <p><strong>Agendamentos Ativos:</strong> {len([a for a in agendamentos if a.status == 'agendado'])}</p>
                <p><strong>Concluídos:</strong> {len([a for a in agendamentos if a.status == 'concluido'])}</p>
                <p><strong>Cancelados:</strong> {len([a for a in agendamentos if a.status == 'cancelado'])}</p>
            </div>
        </div>
        """
        
        if agendamentos:
            html += "<hr><h6>Últimos Agendamentos</h6><div class='table-responsive'><table class='table table-sm'>"
            html += "<thead><tr><th>Data</th><th>Hora</th><th>Especialidade</th><th>Status</th></tr></thead><tbody>"
            
            # Mostrar últimos 5 agendamentos
            for agendamento in sorted(agendamentos, key=lambda x: x.data or '0000-00-00', reverse=True)[:5]:
                status_class = {
                    'agendado': 'success',
                    'concluido': 'info', 
                    'cancelado': 'danger'
                }.get(agendamento.status, 'secondary')
                
                especialidade = Especialidade.find_by_id(agendamento.especialidade_id)
                especialidade_nome = especialidade.nome if especialidade else 'N/A'
                
                html += f"""
                <tr>
                    <td>{agendamento.data or 'N/A'}</td>
                    <td>{agendamento.hora or 'N/A'}</td>
                    <td>{especialidade_nome}</td>
                    <td><span class="badge bg-{status_class}">{agendamento.status.title()}</span></td>
                </tr>
                """
            html += "</tbody></table></div>"
        
        return jsonify({'success': True, 'html': html})
        
    except Exception as e:
        logging.error(f"Erro ao buscar detalhes do paciente: {e}")
        return jsonify({'success': False, 'message': 'Erro interno do servidor'})

# Rota para buscar histórico do paciente (AJAX)
@app.route('/admin/paciente/<int:paciente_id>/historico')
@requer_login_admin
def historico_paciente(paciente_id):
    """API para buscar histórico do paciente"""
    try:
        paciente = Paciente.find_by_id(paciente_id)
        if not paciente:
            return jsonify({'success': False, 'message': 'Paciente não encontrado'})
        
        # Buscar todos os agendamentos do paciente
        agendamentos = Agendamento.find_where({'paciente_id': paciente_id})
        
        # Ordenar por data (mais recente primeiro)
        agendamentos_ordenados = sorted(agendamentos, key=lambda x: x.data or '0000-00-00', reverse=True)
        
        # Gerar HTML com o histórico
        html = f"<h6>Histórico Completo - {paciente.nome}</h6>"
        
        if not agendamentos_ordenados:
            html += "<div class='alert alert-info'>Este paciente ainda não possui agendamentos.</div>"
        else:
            html += "<div class='table-responsive'><table class='table table-hover'>"
            html += "<thead><tr><th>Data</th><th>Hora</th><th>Especialidade</th><th>Médico</th><th>Status</th></tr></thead><tbody>"
            
            for agendamento in agendamentos_ordenados:
                status_class = {
                    'agendado': 'success',
                    'concluido': 'info', 
                    'cancelado': 'danger'
                }.get(agendamento.status, 'secondary')
                
                especialidade = Especialidade.find_by_id(agendamento.especialidade_id)
                especialidade_nome = especialidade.nome if especialidade else 'N/A'
                
                medico = Medico.find_by_id(agendamento.medico_id) if agendamento.medico_id else None
                medico_nome = medico.nome if medico else 'N/A'
                
                html += f"""
                <tr>
                    <td>{agendamento.data or 'N/A'}</td>
                    <td>{agendamento.hora or 'N/A'}</td>
                    <td>{especialidade_nome}</td>
                    <td>{medico_nome}</td>
                    <td><span class="badge bg-{status_class}">{agendamento.status.title()}</span></td>
                </tr>
                """
            html += "</tbody></table></div>"
        
        return jsonify({'success': True, 'html': html})
        
    except Exception as e:
        logging.error(f"Erro ao buscar histórico do paciente: {e}")
        return jsonify({'success': False, 'message': 'Erro interno do servidor'})

# Rotas de edição para admin
@app.route('/admin/especialidade/<int:especialidade_id>/edit', methods=['POST'])
@requer_login_admin
def editar_especialidade(especialidade_id):
    """Salvar alterações da especialidade"""
    try:
        especialidade = Especialidade.find_by_id(especialidade_id)
        if not especialidade:
            return jsonify({'success': False, 'message': 'Especialidade não encontrada.'})
        
        nome = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip()
        ativo = request.form.get('ativo') == 'true'
        requer_anexo = request.form.get('requer_anexo') == 'true'
        
        if not nome:
            return jsonify({'success': False, 'message': 'Nome é obrigatório.'})
        
        # Verificar se já existe outro com mesmo nome
        existe = Especialidade.find_one_where({'nome': nome})
        if existe and existe.id != especialidade_id:
            return jsonify({'success': False, 'message': 'Já existe outra especialidade com este nome.'})
        
        # Atualizar os dados
        especialidade.nome = nome
        especialidade.descricao = descricao if descricao else None
        especialidade.ativo = ativo
        especialidade.requer_anexo = requer_anexo
        especialidade.save()
        
        return jsonify({
            'success': True, 
            'message': f'Especialidade "{nome}" atualizada com sucesso!',
            'especialidade': {
                'id': especialidade.id,
                'nome': especialidade.nome,
                'descricao': especialidade.descricao,
                'ativo': especialidade.ativo,
                'requer_anexo': especialidade.requer_anexo
            }
        })
        
    except Exception as e:
        logging.error(f"Erro ao editar especialidade: {e}")
        return jsonify({'success': False, 'message': 'Erro interno do servidor.'})

@app.route('/admin/especialidade/<int:especialidade_id>/toggle', methods=['POST'])
@requer_login_admin
def toggle_especialidade(especialidade_id):
    """Toggle ativo/inativo da especialidade"""
    try:
        especialidade = Especialidade.find_by_id(especialidade_id)
        if not especialidade:
            return jsonify({'success': False, 'message': 'Especialidade não encontrada.'})
        
        especialidade.ativo = not especialidade.ativo
        especialidade.save()
        
        return jsonify({
            'success': True, 
            'ativo': especialidade.ativo,
            'message': f'Especialidade {"ativada" if especialidade.ativo else "desativada"} com sucesso!'
        })
        
    except Exception as e:
        logging.error(f"Erro ao alterar status da especialidade: {e}")
        return jsonify({'success': False, 'message': 'Erro interno do servidor.'})

@app.route('/admin/medico/<int:medico_id>/edit', methods=['POST'])
@requer_login_admin
def salvar_medico(medico_id):
    """Salvar alterações do médico"""
    try:
        medico = Medico.find_by_id(medico_id)
        if not medico:
            flash('Médico não encontrado.', 'error')
            return redirect(url_for('admin'))
        
        nome = request.form.get('nome', '').strip()
        crm = request.form.get('crm', '').strip()
        especialidade_id = request.form.get('especialidade_id', '').strip()
        data_abertura_agenda = request.form.get('data_abertura_agenda', '').strip()
        ativo = 'ativo' in request.form
        agenda_recorrente = 'agenda_recorrente' in request.form
        
        if not all([nome, crm, especialidade_id]):
            flash('Nome, CRM e especialidade são obrigatórios.', 'error')
            return redirect(url_for('editar_medico', medico_id=medico_id))
        
        # Verificar se CRM já existe em outro médico
        existe = Medico.find_one_where({'crm': crm})
        if existe and existe.id != medico_id:
            flash('CRM já cadastrado para outro médico.', 'error')
            return redirect(url_for('editar_medico', medico_id=medico_id))
        
        # Verificar se especialidade existe
        especialidade = Especialidade.find_by_id(int(especialidade_id))
        if not especialidade:
            flash('Especialidade não encontrada.', 'error')
            return redirect(url_for('editar_medico', medico_id=medico_id))
        
        # Atualizar os dados
        medico.nome = nome
        medico.crm = crm
        medico.especialidade_id = int(especialidade_id)
        medico.data_abertura_agenda = data_abertura_agenda if data_abertura_agenda else None
        medico.ativo = ativo
        medico.agenda_recorrente = agenda_recorrente
        medico.save()
        
        flash(f'Médico "{nome}" atualizado com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        logging.error(f"Erro ao atualizar médico: {e}")
        flash('Erro ao salvar alterações. Tente novamente.', 'error')
        return redirect(url_for('editar_medico', medico_id=medico_id))

@app.route('/admin/horario/<int:horario_id>/edit', methods=['POST'])
@requer_login_admin
def editar_horario(horario_id):
    """Salvar alterações do horário"""
    try:
        horario = HorarioDisponivel.find_by_id(horario_id)
        if not horario:
            return jsonify({'success': False, 'message': 'Horário não encontrado.'})
        
        medico_id = request.form.get('medico_id', '').strip()
        local_id = request.form.get('local_id', '').strip()
        dia_semana = request.form.get('dia_semana', '').strip()
        hora_inicio = request.form.get('hora_inicio', '').strip()
        hora_fim = request.form.get('hora_fim', '').strip()
        duracao_consulta = request.form.get('duracao_consulta', '30').strip()
        
        if not all([medico_id, local_id, dia_semana, hora_inicio, hora_fim]):
            return jsonify({'success': False, 'message': 'Todos os campos são obrigatórios.'})
        
        # Verificar se médico e local existem
        medico = Medico.find_by_id(int(medico_id))
        local = Local.find_by_id(int(local_id))
        
        if not medico:
            return jsonify({'success': False, 'message': 'Médico não encontrado.'})
        if not local:
            return jsonify({'success': False, 'message': 'Local não encontrado.'})
        
        # Atualizar os dados
        horario.medico_id = int(medico_id)
        horario.local_id = int(local_id)
        horario.dia_semana = int(dia_semana)
        horario.hora_inicio = hora_inicio
        horario.hora_fim = hora_fim
        horario.duracao_consulta = int(duracao_consulta)
        horario.save()
        
        return jsonify({
            'success': True,
            'message': 'Horário atualizado com sucesso!'
        })
        
    except Exception as e:
        logging.error(f"Erro ao editar horário: {e}")
        return jsonify({'success': False, 'message': 'Erro interno do servidor.'})

# Rotas de exclusão para admin
@app.route('/admin/especialidade/<int:especialidade_id>/delete', methods=['POST'])
@requer_login_admin
def deletar_especialidade(especialidade_id):
    """Deletar especialidade"""
    try:
        especialidade = Especialidade.find_by_id(especialidade_id)
        if not especialidade:
            flash('Especialidade não encontrada.', 'error')
            return redirect(url_for('admin'))
        
        especialidade.delete()
        flash('Especialidade excluída com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        logging.error(f"Erro ao deletar especialidade: {e}")
        flash('Erro ao excluir especialidade. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/medico/<int:medico_id>/delete', methods=['POST'])
@requer_login_admin
def deletar_medico(medico_id):
    """Deletar médico"""
    try:
        medico = Medico.find_by_id(medico_id)
        if not medico:
            flash('Médico não encontrado.', 'error')
            return redirect(url_for('admin'))
        
        # Verificar se o médico tem horários ou agendamentos associados
        horarios = HorarioDisponivel.find_where({'medico_id': medico_id})
        agendamentos = Agendamento.find_where({'medico_id': medico_id})
        
        if horarios or agendamentos:
            total_registros = len(horarios) + len(agendamentos)
            flash(f'Não é possível excluir este médico pois ele possui {len(horarios)} horário(s) e {len(agendamentos)} agendamento(s) associados. Delete primeiro os horários e agendamentos relacionados.', 'error')
            return redirect(url_for('admin'))
        
        medico.delete()
        flash(f'Dr(a). {medico.nome} foi excluído(a) com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        logging.error(f"Erro ao deletar médico: {e}")
        if "FOREIGN KEY constraint failed" in str(e):
            flash('Não é possível excluir este médico pois ele possui registros associados (horários ou agendamentos).', 'error')
        else:
            flash('Erro ao excluir médico. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/horario/<int:horario_id>/delete', methods=['POST'])
@requer_login_admin
def deletar_horario(horario_id):
    """Deletar horário"""
    try:
        horario = HorarioDisponivel.find_by_id(horario_id)
        if not horario:
            flash('Horário não encontrado.', 'error')
            return redirect(url_for('admin'))
        
        horario.delete()
        flash('Horário excluído com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        logging.error(f"Erro ao deletar horário: {e}")
        flash('Erro ao excluir horário. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/local/<int:local_id>/delete', methods=['POST'])
@requer_login_admin
def deletar_local(local_id):
    """Deletar local"""
    try:
        local = Local.find_by_id(local_id)
        if not local:
            flash('Local não encontrado.', 'error')
            return redirect(url_for('admin'))
        
        local.delete()
        flash('Local excluído com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        logging.error(f"Erro ao deletar local: {e}")
        flash('Erro ao excluir local. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/zerar-banco-dados', methods=['POST'])
@requer_login_admin
def zerar_banco_dados():
    """Zerar todo o banco de dados mantendo apenas locais"""
    try:
        # Verificar confirmação
        confirmacao = request.form.get('confirmacao', '')
        if confirmacao != 'APAGAR':
            flash('Operação cancelada. Confirmação inválida.', 'error')
            return redirect(url_for('admin_config'))
        
        # Conectar diretamente ao banco para desabilitar foreign keys temporariamente
        import sqlite3
        conn = sqlite3.connect('sistema_agendamento.db')
        conn.execute('PRAGMA foreign_keys = OFF')
        
        try:
            # Deletar em ordem para evitar problemas de chave estrangeira
            conn.execute('DELETE FROM agendamentos')
            conn.execute('DELETE FROM horarios_disponiveis')
            conn.execute('DELETE FROM medicos')
            conn.execute('DELETE FROM especialidades')
            conn.execute('DELETE FROM pacientes')
            conn.execute('DELETE FROM conversas')
            
            # Resetar contadores de ID
            conn.execute('DELETE FROM sqlite_sequence WHERE name IN ("agendamentos", "horarios_disponiveis", "medicos", "especialidades", "pacientes", "conversas")')
            
            conn.commit()
            
            # Contar o que restou
            cursor = conn.execute('SELECT COUNT(*) FROM locais')
            locais_count = cursor.fetchone()[0]
            
            flash(f'✅ Banco de dados zerado com sucesso! Mantidos {locais_count} locais.', 'success')
            logging.info(f"Banco de dados zerado pelo admin. {locais_count} locais mantidos.")
            
        finally:
            conn.execute('PRAGMA foreign_keys = ON')
            conn.close()
            
        return redirect(url_for('admin_config'))
        
    except Exception as e:
        logging.error(f"Erro ao zerar banco de dados: {e}")
        flash('Erro ao zerar banco de dados. Tente novamente.', 'error')
        return redirect(url_for('admin_config'))

# Rota para testar JavaScript console logs
@app.route('/log-test')
def log_test():
    """Rota para testar logs no console JavaScript"""
    stats = {
        'status': 'ativo',
        'versao': '2.0.0 - SQLite3 Pure',
        'desenvolvedor': 'João Layon',
        'preco_mensal': 'R$ 19,90',
        'total_pacientes': len(Paciente.find_all()),
        'total_agendamentos': len(Agendamento.find_all()),
        'agendamentos_hoje': len(Agendamento.find_active_for_today()),
        'especialidades': len(Especialidade.find_active())
    }
    
    html = f"""
    <script>
    console.log("Sistema João Layon Ativo:", {json.dumps(stats)});
    </script>
    <h1>Sistema Ativo - SQLite3</h1>
    <pre>{json.dumps(stats, indent=2)}</pre>
    """
    return html

# Rotas para anexos

@app.route('/anexar-arquivo/<int:agendamento_id>')
def pagina_anexo_paciente(agendamento_id):
    """Página para o paciente anexar arquivo"""
    try:
        agendamento = Agendamento.find_by_id(agendamento_id)
        if not agendamento:
            flash('Agendamento não encontrado.', 'error')
            return redirect(url_for('index'))
        
        # Adicionar dados relacionados
        agendamento.paciente_rel = agendamento.get_paciente()
        agendamento.medico_rel = agendamento.get_medico()
        agendamento.especialidade_rel = agendamento.get_especialidade()
        
        return render_template('anexar_arquivo.html', agendamento=agendamento)
        
    except Exception as e:
        logger.error(f"Erro ao carregar página de anexo: {e}")
        flash('Erro ao carregar página.', 'error')
        return redirect(url_for('index'))

@app.route('/upload-anexo-paciente/<int:agendamento_id>', methods=['POST'])
def upload_anexo_paciente(agendamento_id):
    """Upload de arquivo pelo paciente"""
    try:
        agendamento = Agendamento.find_by_id(agendamento_id)
        if not agendamento:
            flash('Agendamento não encontrado.', 'error')
            return redirect(url_for('index'))
        
        if 'arquivo' not in request.files:
            flash('Nenhum arquivo foi selecionado.', 'error')
            return redirect(url_for('pagina_anexo_paciente', agendamento_id=agendamento_id))
        
        file = request.files['arquivo']
        if file.filename == '':
            flash('Nenhum arquivo foi selecionado.', 'error')
            return redirect(url_for('pagina_anexo_paciente', agendamento_id=agendamento_id))
        
        if file and allowed_file(file.filename):
            # Gerar nome único para o arquivo
            filename = secure_filename(file.filename)
            unique_filename = f"{agendamento_id}_{uuid.uuid4().hex[:8]}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            
            # Salvar o arquivo
            file.save(file_path)
            
            # Atualizar banco de dados
            agendamento.anexo_nome = filename
            agendamento.anexo_path = unique_filename
            agendamento.save()
            
            flash(f'Arquivo "{filename}" foi enviado com sucesso! O administrador poderá visualizá-lo.', 'success')
            logger.info(f"Arquivo anexado pelo paciente ao agendamento {agendamento_id}: {filename}")
            
            return render_template('anexo_enviado.html', agendamento=agendamento, filename=filename)
            
        else:
            flash('Tipo de arquivo não permitido. Tipos aceitos: ' + ', '.join(ALLOWED_EXTENSIONS), 'error')
            return redirect(url_for('pagina_anexo_paciente', agendamento_id=agendamento_id))
            
    except Exception as e:
        logger.error(f"Erro ao fazer upload de anexo pelo paciente: {e}")
        flash('Erro ao enviar arquivo.', 'error')
        return redirect(url_for('pagina_anexo_paciente', agendamento_id=agendamento_id))

@app.route('/upload-anexo/<int:agendamento_id>', methods=['POST'])
@requer_login_admin
def upload_anexo(agendamento_id):
    """Upload de arquivo anexado ao agendamento (admin)"""
    try:
        agendamento = Agendamento.find_by_id(agendamento_id)
        if not agendamento:
            flash('Agendamento não encontrado.', 'error')
            return redirect(url_for('listar_agendamentos'))
        
        if 'arquivo' not in request.files:
            flash('Nenhum arquivo foi selecionado.', 'error')
            return redirect(url_for('listar_agendamentos'))
        
        file = request.files['arquivo']
        if file.filename == '':
            flash('Nenhum arquivo foi selecionado.', 'error')
            return redirect(url_for('listar_agendamentos'))
        
        if file and allowed_file(file.filename):
            # Gerar nome único para o arquivo
            filename = secure_filename(file.filename)
            unique_filename = f"{agendamento_id}_{uuid.uuid4().hex[:8]}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            
            # Salvar o arquivo
            file.save(file_path)
            
            # Atualizar banco de dados
            agendamento.anexo_nome = filename
            agendamento.anexo_path = unique_filename
            agendamento.save()
            
            flash(f'Arquivo "{filename}" foi anexado com sucesso!', 'success')
            logger.info(f"Arquivo anexado ao agendamento {agendamento_id}: {filename}")
            
        else:
            flash('Tipo de arquivo não permitido. Tipos aceitos: ' + ', '.join(ALLOWED_EXTENSIONS), 'error')
            
    except Exception as e:
        logger.error(f"Erro ao fazer upload de anexo: {e}")
        flash('Erro ao fazer upload do arquivo.', 'error')
    
    return redirect(url_for('listar_agendamentos'))

@app.route('/download-anexo/<int:agendamento_id>')
def download_anexo(agendamento_id):
    """Download de arquivo anexado ao agendamento"""
    try:
        logger.info(f"Tentativa de download - Agendamento ID: {agendamento_id}")
        agendamento = Agendamento.find_by_id(agendamento_id)
        
        if not agendamento:
            logger.error(f"Agendamento {agendamento_id} não encontrado")
            return jsonify({
                'success': False,
                'message': 'Agendamento não encontrado.'
            }), 404
            
        if not agendamento.anexo_path:
            logger.error(f"Agendamento {agendamento_id} sem anexo")
            return jsonify({
                'success': False,
                'message': 'Nenhum anexo encontrado para este agendamento.'
            }), 404
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], agendamento.anexo_path)
        logger.info(f"Verificando arquivo: {file_path}")
        
        if not os.path.exists(file_path):
            logger.error(f"Arquivo não existe: {file_path}")
            return jsonify({
                'success': False,
                'message': 'Arquivo não encontrado no servidor.'
            }), 404
        
        # Tentar determinar o tipo MIME
        mimetype = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=agendamento.anexo_nome or 'anexo',
            mimetype=mimetype
        )
        
    except Exception as e:
        logger.error(f"Erro ao fazer download de anexo: {e}")
        return jsonify({
            'success': False,
            'message': 'Erro ao fazer download do arquivo.'
        }), 500

@app.route('/remover-anexo/<int:agendamento_id>', methods=['POST'])
@requer_login_admin
def remover_anexo(agendamento_id):
    """Remove arquivo anexado ao agendamento"""
    try:
        agendamento = Agendamento.find_by_id(agendamento_id)
        if not agendamento:
            flash('Agendamento não encontrado.', 'error')
            return redirect(url_for('listar_agendamentos'))
        
        if agendamento.anexo_path:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], agendamento.anexo_path)
            
            # Remover arquivo do sistema de arquivos
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Limpar campos do banco de dados
            agendamento.anexo_nome = ''
            agendamento.anexo_path = ''
            agendamento.save()
            
            flash('Anexo removido com sucesso!', 'success')
            logger.info(f"Anexo removido do agendamento {agendamento_id}")
        else:
            flash('Nenhum anexo encontrado para remover.', 'error')
            
    except Exception as e:
        logger.error(f"Erro ao remover anexo: {e}")
        flash('Erro ao remover anexo.', 'error')
    
    return redirect(url_for('listar_agendamentos'))

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)