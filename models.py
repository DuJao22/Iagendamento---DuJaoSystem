from database import db
from datetime import datetime, date, time
import json
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger('SistemaAgendamento')

class BaseModel:
    """Classe base para todos os modelos"""
    table_name = ""
    
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte o objeto para dicionário"""
        result = {}
        for key, value in self.__dict__.items():
            if key.startswith('_'):
                continue
            if isinstance(value, (date, datetime)):
                result[key] = value.isoformat() if value else None
            elif isinstance(value, time):
                result[key] = value.strftime('%H:%M') if value else None
            else:
                result[key] = value
        return result
    
    @classmethod
    def create(cls, **kwargs):
        """Cria um novo registro"""
        # Remover campos que não devem ser inseridos
        kwargs.pop('id', None)
        kwargs.pop('criado_em', None)
        
        if not kwargs:
            raise ValueError("Nenhum dado fornecido para criação")
        
        columns = ', '.join(kwargs.keys())
        placeholders = ', '.join(['?' for _ in kwargs])
        query = f"INSERT INTO {cls.table_name} ({columns}) VALUES ({placeholders})"
        
        record_id = db.execute_insert(query, tuple(kwargs.values()))
        return cls.find_by_id(record_id)
    
    @classmethod
    def find_by_id(cls, record_id: int):
        """Busca um registro por ID"""
        query = f"SELECT * FROM {cls.table_name} WHERE id = ?"
        rows = db.execute_query(query, (record_id,))
        if rows:
            return cls(**dict(rows[0]))
        return None
    
    @classmethod
    def find_all(cls) -> List['BaseModel']:
        """Busca todos os registros"""
        query = f"SELECT * FROM {cls.table_name}"
        rows = db.execute_query(query)
        return [cls(**dict(row)) for row in rows]
    
    @classmethod
    def find_where(cls, conditions: Dict[str, Any]) -> List['BaseModel']:
        """Busca registros com condições"""
        where_clause = ' AND '.join([f"{key} = ?" for key in conditions.keys()])
        query = f"SELECT * FROM {cls.table_name} WHERE {where_clause}"
        rows = db.execute_query(query, tuple(conditions.values()))
        return [cls(**dict(row)) for row in rows]
    
    @classmethod
    def find_one_where(cls, conditions: Dict[str, Any]):
        """Busca um registro com condições"""
        results = cls.find_where(conditions)
        return results[0] if results else None
    
    def save(self):
        """Salva alterações no registro"""
        if not hasattr(self, 'id') or not self.id:
            raise ValueError("Registro deve ter ID para ser atualizado")
        
        # Criar dicionário com todos os campos exceto id
        data = {k: v for k, v in self.__dict__.items() 
                if not k.startswith('_') and k != 'id'}
        
        if not data:
            return
        
        set_clause = ', '.join([f"{key} = ?" for key in data.keys()])
        query = f"UPDATE {self.table_name} SET {set_clause} WHERE id = ?"
        
        params = list(data.values()) + [self.id]
        db.execute_update(query, tuple(params))
    
    def delete(self):
        """Exclui o registro"""
        if not hasattr(self, 'id') or not self.id:
            raise ValueError("Registro deve ter ID para ser excluído")
        
        query = f"DELETE FROM {self.table_name} WHERE id = ?"
        db.execute_update(query, (self.id,))

class Paciente(BaseModel):
    """Modelo para pacientes da clínica"""
    table_name = "pacientes"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Campos padrão
        self.id = kwargs.get('id')
        self.cpf = kwargs.get('cpf', '')
        self.nome = kwargs.get('nome', '')
        self.data_nascimento = kwargs.get('data_nascimento')
        self.telefone = kwargs.get('telefone', '')
        self.email = kwargs.get('email', '')
        self.carteirinha = kwargs.get('carteirinha', '')
        self.tipo_atendimento = kwargs.get('tipo_atendimento', 'particular')
        self.criado_em = kwargs.get('criado_em')
    
    @classmethod
    def find_by_cpf(cls, cpf: str):
        """Busca paciente por CPF"""
        return cls.find_one_where({'cpf': cpf})
    
    def get_agendamentos(self) -> List['Agendamento']:
        """Retorna agendamentos do paciente"""
        return Agendamento.find_where({'paciente_id': self.id})
    
    def to_dict(self):
        data = super().to_dict()
        if self.data_nascimento:
            if isinstance(self.data_nascimento, str):
                # Se já é string, tentar converter para date para depois formatar
                try:
                    dt = datetime.strptime(self.data_nascimento, '%Y-%m-%d').date()
                    data['data_nascimento'] = dt.strftime('%d/%m/%Y')
                except:
                    data['data_nascimento'] = self.data_nascimento
            else:
                data['data_nascimento'] = self.data_nascimento.strftime('%d/%m/%Y')
        return data

class Local(BaseModel):
    """Modelo para locais de atendimento"""
    table_name = "locais"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.nome = kwargs.get('nome', '')
        self.endereco = kwargs.get('endereco', '')
        self.cidade = kwargs.get('cidade', '')
        self.telefone = kwargs.get('telefone', '')
        self.ativo = kwargs.get('ativo', True)
        self.criado_em = kwargs.get('criado_em')
    
    @classmethod
    def find_active(cls) -> List['Local']:
        """Busca locais ativos"""
        return cls.find_where({'ativo': 1})

class Especialidade(BaseModel):
    """Modelo para especialidades médicas"""
    table_name = "especialidades"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.nome = kwargs.get('nome', '')
        self.descricao = kwargs.get('descricao', '')
        self.ativo = kwargs.get('ativo', True)
        self.requer_anexo = kwargs.get('requer_anexo', False)
        self.criado_em = kwargs.get('criado_em')
    
    @classmethod
    def find_active(cls) -> List['Especialidade']:
        """Busca especialidades ativas"""
        return cls.find_where({'ativo': 1})
    
    def get_medicos(self) -> List['Medico']:
        """Retorna médicos desta especialidade"""
        return Medico.find_where({'especialidade_id': self.id})

class Medico(BaseModel):
    """Modelo para médicos da clínica"""
    table_name = "medicos"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.nome = kwargs.get('nome', '')
        self.crm = kwargs.get('crm', '')
        self.especialidade_id = kwargs.get('especialidade_id')
        self.ativo = kwargs.get('ativo', True)
        self.agenda_recorrente = kwargs.get('agenda_recorrente', False)
        self.data_abertura_agenda = kwargs.get('data_abertura_agenda')
        self.criado_em = kwargs.get('criado_em')
    
    @classmethod
    def find_active(cls) -> List['Medico']:
        """Busca médicos ativos"""
        return cls.find_where({'ativo': 1})
    
    def get_especialidade(self) -> Optional['Especialidade']:
        """Retorna a especialidade do médico"""
        if self.especialidade_id:
            return Especialidade.find_by_id(self.especialidade_id)
        return None
    
    def get_horarios(self) -> List['HorarioDisponivel']:
        """Retorna horários disponíveis do médico"""
        return HorarioDisponivel.find_where({'medico_id': self.id})
    
    def get_agendamentos(self) -> List['Agendamento']:
        """Retorna agendamentos do médico"""
        return Agendamento.find_where({'medico_id': self.id})
    
    def agenda_aberta(self, data_consulta: date = None) -> bool:
        """Verifica se a agenda do médico está aberta para uma data"""
        if not data_consulta:
            data_consulta = date.today()
        
        if not self.data_abertura_agenda:
            # Se não tem data configurada, considera agenda sempre aberta
            return True
        
        # Converter string para date se necessário
        if isinstance(self.data_abertura_agenda, str):
            try:
                data_abertura = datetime.strptime(self.data_abertura_agenda, '%Y-%m-%d').date()
            except:
                return True
        else:
            data_abertura = self.data_abertura_agenda
        
        # Agenda está aberta se a data de consulta for igual ou posterior à data de abertura
        return data_consulta >= data_abertura

class HorarioDisponivel(BaseModel):
    """Modelo para horários disponíveis dos médicos"""
    table_name = "horarios_disponiveis"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.medico_id = kwargs.get('medico_id')
        self.local_id = kwargs.get('local_id')
        self.dia_semana = kwargs.get('dia_semana', 0)
        self.hora_inicio = kwargs.get('hora_inicio')
        self.hora_fim = kwargs.get('hora_fim')
        self.duracao_consulta = kwargs.get('duracao_consulta', 30)
        self.ativo = kwargs.get('ativo', True)
        self.criado_em = kwargs.get('criado_em')
    
    def get_medico(self) -> Optional['Medico']:
        """Retorna o médico deste horário"""
        if self.medico_id:
            return Medico.find_by_id(self.medico_id)
        return None
    
    def get_local(self) -> Optional['Local']:
        """Retorna o local deste horário"""
        if self.local_id:
            return Local.find_by_id(self.local_id)
        return None
    
    def get_dia_semana_nome(self) -> str:
        """Retorna o nome do dia da semana"""
        dias = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        return dias[self.dia_semana] if 0 <= self.dia_semana < len(dias) else 'N/A'
    
    def to_dict(self):
        data = super().to_dict()
        medico = self.get_medico()
        local = self.get_local()
        
        data['medico_nome'] = medico.nome if medico else 'N/A'
        data['local_nome'] = local.nome if local else 'N/A'
        data['dia_semana_nome'] = self.get_dia_semana_nome()
        
        # Adicionar especialidade do médico
        if medico:
            especialidade = medico.get_especialidade()
            data['especialidade_nome'] = especialidade.nome if especialidade else 'N/A'
        else:
            data['especialidade_nome'] = 'N/A'
        
        # Formatar horários
        if self.hora_inicio:
            if isinstance(self.hora_inicio, str):
                data['hora_inicio'] = self.hora_inicio
            else:
                data['hora_inicio'] = self.hora_inicio.strftime('%H:%M')
        
        if self.hora_fim:
            if isinstance(self.hora_fim, str):
                data['hora_fim'] = self.hora_fim
            else:
                data['hora_fim'] = self.hora_fim.strftime('%H:%M')
        
        return data

class Agendamento(BaseModel):
    """Modelo para agendamentos médicos"""
    table_name = "agendamentos"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.paciente_id = kwargs.get('paciente_id')
        self.medico_id = kwargs.get('medico_id')
        self.especialidade_id = kwargs.get('especialidade_id')
        self.local_id = kwargs.get('local_id')
        self.data = kwargs.get('data')
        self.hora = kwargs.get('hora')
        self.observacoes = kwargs.get('observacoes', '')
        self.status = kwargs.get('status', 'agendado')
        self.anexo_nome = kwargs.get('anexo_nome', '')
        self.anexo_path = kwargs.get('anexo_path', '')
        self.criado_em = kwargs.get('criado_em')
        self.cancelado_em = kwargs.get('cancelado_em')
        self.motivo_cancelamento = kwargs.get('motivo_cancelamento', '')
    
    def get_paciente(self) -> Optional['Paciente']:
        """Retorna o paciente do agendamento"""
        if self.paciente_id:
            return Paciente.find_by_id(self.paciente_id)
        return None
    
    def get_medico(self) -> Optional['Medico']:
        """Retorna o médico do agendamento"""
        if self.medico_id:
            return Medico.find_by_id(self.medico_id)
        return None
    
    def get_especialidade(self) -> Optional['Especialidade']:
        """Retorna a especialidade do agendamento"""
        if self.especialidade_id:
            return Especialidade.find_by_id(self.especialidade_id)
        return None
    
    def get_local(self) -> Optional['Local']:
        """Retorna o local do agendamento"""
        if self.local_id:
            return Local.find_by_id(self.local_id)
        return None
    
    @classmethod
    def find_by_date(cls, data: date) -> List['Agendamento']:
        """Busca agendamentos por data"""
        return cls.find_where({'data': data.isoformat()})
    
    @classmethod
    def find_active_for_today(cls) -> List['Agendamento']:
        """Busca agendamentos ativos para hoje"""
        today = date.today().isoformat()
        query = f"SELECT * FROM {cls.table_name} WHERE data = ? AND status = 'agendado'"
        rows = db.execute_query(query, (today,))
        return [cls(**dict(row)) for row in rows]
    
    def cancelar(self, motivo: str = ''):
        """Cancela o agendamento"""
        self.status = 'cancelado'
        self.cancelado_em = datetime.utcnow().isoformat()
        self.motivo_cancelamento = motivo
        self.save()
    
    def to_dict(self):
        data = super().to_dict()
        
        # Buscar dados relacionados
        paciente = self.get_paciente()
        medico = self.get_medico()
        especialidade = self.get_especialidade()
        local = self.get_local()
        
        data['paciente_nome'] = paciente.nome if paciente else 'N/A'
        data['medico_nome'] = medico.nome if medico else 'N/A'
        data['especialidade_nome'] = especialidade.nome if especialidade else 'N/A'
        data['local_nome'] = local.nome if local else 'N/A'
        
        # Formatar data
        if self.data:
            if isinstance(self.data, str):
                try:
                    dt = datetime.strptime(self.data, '%Y-%m-%d').date()
                    data['data'] = dt.strftime('%d/%m/%Y')
                except:
                    data['data'] = self.data
            else:
                data['data'] = self.data.strftime('%d/%m/%Y')
        
        # Formatar hora
        if self.hora:
            if isinstance(self.hora, str):
                data['hora'] = self.hora
            else:
                data['hora'] = self.hora.strftime('%H:%M')
        
        # Formatar data de criação
        if self.criado_em:
            if isinstance(self.criado_em, str):
                try:
                    dt = datetime.fromisoformat(self.criado_em.replace('Z', '+00:00'))
                    data['criado_em'] = dt.strftime('%d/%m/%Y %H:%M')
                except:
                    data['criado_em'] = self.criado_em
        
        return data

class Conversa(BaseModel):
    """Modelo para manter estado das conversas do chatbot"""
    table_name = "conversas"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.session_id = kwargs.get('session_id', '')
        self.paciente_id = kwargs.get('paciente_id')
        self.estado = kwargs.get('estado', 'inicio')
        self.dados_temporarios = kwargs.get('dados_temporarios', '{}')
        self.criado_em = kwargs.get('criado_em')
        self.atualizado_em = kwargs.get('atualizado_em')
    
    @classmethod
    def find_by_session(cls, session_id: str):
        """Busca conversa por session ID"""
        return cls.find_one_where({'session_id': session_id})
    
    def get_dados(self) -> Dict[str, Any]:
        """Retorna dados temporários como dicionário"""
        if self.dados_temporarios:
            try:
                return json.loads(self.dados_temporarios)
            except:
                return {}
        return {}
    
    def set_dados(self, dados: Dict[str, Any]):
        """Define dados temporários a partir de dicionário"""
        self.dados_temporarios = json.dumps(dados)
        self.atualizado_em = datetime.utcnow().isoformat()

class Configuracao(BaseModel):
    """Modelo para configurações do sistema"""
    table_name = "configuracoes"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.chave = kwargs.get('chave', '')
        self.valor = kwargs.get('valor', '')
        self.descricao = kwargs.get('descricao', '')
        self.atualizado_em = kwargs.get('atualizado_em')
    
    @classmethod
    def get_valor(cls, chave: str, padrao: str = '') -> str:
        """Obtém valor de uma configuração"""
        config = cls.find_one_where({'chave': chave})
        return config.valor if config else padrao
    
    @classmethod
    def set_valor(cls, chave: str, valor: str, descricao: str = '') -> 'Configuracao':
        """Define valor de uma configuração"""
        config = cls.find_one_where({'chave': chave})
        if config:
            config.valor = valor
            config.atualizado_em = datetime.utcnow().isoformat()
            if descricao:
                config.descricao = descricao
            config.save()
        else:
            config = cls.create(
                chave=chave, 
                valor=valor, 
                descricao=descricao,
                atualizado_em=datetime.utcnow().isoformat()
            )
        return config

class ArquivoPaciente(BaseModel):
    """Modelo para arquivos anexados pelos pacientes"""
    table_name = "arquivos_pacientes"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.paciente_id = kwargs.get('paciente_id')
        self.agendamento_id = kwargs.get('agendamento_id')  # Opcional, pode ser None
        self.nome_original = kwargs.get('nome_original', '')
        self.nome_arquivo = kwargs.get('nome_arquivo', '')
        self.caminho_arquivo = kwargs.get('caminho_arquivo', '')
        self.tipo_arquivo = kwargs.get('tipo_arquivo', '')
        self.tamanho_arquivo = kwargs.get('tamanho_arquivo', 0)
        self.descricao = kwargs.get('descricao', '')
        self.criado_em = kwargs.get('criado_em')
    
    def get_paciente(self) -> Optional['Paciente']:
        """Retorna o paciente dono do arquivo"""
        if self.paciente_id:
            return Paciente.find_by_id(self.paciente_id)
        return None
    
    def get_agendamento(self) -> Optional['Agendamento']:
        """Retorna o agendamento relacionado ao arquivo (se houver)"""
        if self.agendamento_id:
            return Agendamento.find_by_id(self.agendamento_id)
        return None
    
    @classmethod
    def find_by_paciente(cls, paciente_id: int) -> List['ArquivoPaciente']:
        """Busca arquivos de um paciente"""
        return cls.find_where({'paciente_id': paciente_id})
    
    def to_dict(self):
        data = super().to_dict()
        
        # Buscar dados relacionados
        paciente = self.get_paciente()
        agendamento = self.get_agendamento()
        
        data['paciente_nome'] = paciente.nome if paciente else 'N/A'
        data['agendamento_data'] = agendamento.data if agendamento else None
        
        # Formatar tamanho do arquivo
        if self.tamanho_arquivo:
            if self.tamanho_arquivo < 1024:
                data['tamanho_formatado'] = f"{self.tamanho_arquivo} B"
            elif self.tamanho_arquivo < 1024 * 1024:
                data['tamanho_formatado'] = f"{self.tamanho_arquivo / 1024:.1f} KB"
            else:
                data['tamanho_formatado'] = f"{self.tamanho_arquivo / (1024 * 1024):.1f} MB"
        else:
            data['tamanho_formatado'] = "N/A"
        
        return data

class AgendamentoRecorrente(BaseModel):
    """Modelo para agendamentos recorrentes semanais"""
    table_name = "agendamentos_recorrentes"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = kwargs.get('id')
        self.paciente_id = kwargs.get('paciente_id')
        self.medico_id = kwargs.get('medico_id')
        self.especialidade_id = kwargs.get('especialidade_id')
        self.local_id = kwargs.get('local_id')
        self.dia_semana = kwargs.get('dia_semana', 0)
        self.hora = kwargs.get('hora')
        self.data_inicio = kwargs.get('data_inicio')
        self.data_fim = kwargs.get('data_fim')
        self.ativo = kwargs.get('ativo', True)
        self.observacoes = kwargs.get('observacoes', '')
        self.criado_em = kwargs.get('criado_em')
    
    def get_dia_semana_nome(self) -> str:
        """Retorna o nome do dia da semana"""
        dias = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        return dias[self.dia_semana] if 0 <= self.dia_semana < len(dias) else 'N/A'
    
    def to_dict(self):
        data = super().to_dict()
        data['dia_semana_nome'] = self.get_dia_semana_nome()
        
        # Formatar hora
        if self.hora:
            if isinstance(self.hora, str):
                data['hora'] = self.hora
            else:
                data['hora'] = self.hora.strftime('%H:%M')
        
        # Formatar datas
        if self.data_inicio:
            if isinstance(self.data_inicio, str):
                try:
                    dt = datetime.strptime(self.data_inicio, '%Y-%m-%d').date()
                    data['data_inicio'] = dt.strftime('%d/%m/%Y')
                except:
                    data['data_inicio'] = self.data_inicio
        
        if self.data_fim:
            if isinstance(self.data_fim, str):
                try:
                    dt = datetime.strptime(self.data_fim, '%Y-%m-%d').date()
                    data['data_fim'] = dt.strftime('%d/%m/%Y')
                except:
                    data['data_fim'] = 'Indefinido'
            else:
                data['data_fim'] = self.data_fim.strftime('%d/%m/%Y')
        else:
            data['data_fim'] = 'Indefinido'
        
        return data