import sqlite3
import os
import logging
from datetime import datetime, date, time
import json
from typing import Optional, List, Dict, Any

logger = logging.getLogger('SistemaAgendamento')

class Database:
    """Classe principal para gerenciar conexão SQLite3"""
    
    def __init__(self, db_path: str = "sistema_agendamento.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Inicializa o banco de dados e cria as tabelas"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                self._create_tables(conn)
                self._populate_initial_data(conn)
            logger.info(f"Banco de dados SQLite inicializado: {self.db_path}")
        except Exception as e:
            logger.error(f"Erro ao inicializar banco de dados: {e}")
            raise
    
    def _add_missing_columns(self, conn):
        """Adiciona colunas que podem estar faltantes em tabelas existentes"""
        try:
            # Verificar e adicionar coluna requer_anexo na tabela especialidades
            cursor = conn.execute("PRAGMA table_info(especialidades)")
            colunas = [row[1] for row in cursor.fetchall()]
            if 'requer_anexo' not in colunas:
                conn.execute("ALTER TABLE especialidades ADD COLUMN requer_anexo BOOLEAN DEFAULT 0")
                logger.info("Coluna 'requer_anexo' adicionada à tabela especialidades")
            
            # Verificar e adicionar colunas anexo na tabela agendamentos
            cursor = conn.execute("PRAGMA table_info(agendamentos)")
            colunas = [row[1] for row in cursor.fetchall()]
            if 'anexo_nome' not in colunas:
                conn.execute("ALTER TABLE agendamentos ADD COLUMN anexo_nome TEXT")
                logger.info("Coluna 'anexo_nome' adicionada à tabela agendamentos")
            if 'anexo_path' not in colunas:
                conn.execute("ALTER TABLE agendamentos ADD COLUMN anexo_path TEXT")
                logger.info("Coluna 'anexo_path' adicionada à tabela agendamentos")
            
            # Verificar e adicionar coluna data_abertura_agenda na tabela medicos
            cursor = conn.execute("PRAGMA table_info(medicos)")
            colunas = [row[1] for row in cursor.fetchall()]
            if 'data_abertura_agenda' not in colunas:
                conn.execute("ALTER TABLE medicos ADD COLUMN data_abertura_agenda DATE")
                logger.info("Coluna 'data_abertura_agenda' adicionada à tabela medicos")
            
        except Exception as e:
            logger.error(f"Erro ao adicionar colunas faltantes: {e}")

    def _create_tables(self, conn):
        """Cria todas as tabelas necessárias"""
        # Adicionar colunas faltantes se necessário
        self._add_missing_columns(conn)
        
        # Tabela de locais
        conn.execute('''
            CREATE TABLE IF NOT EXISTS locais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                endereco TEXT,
                cidade TEXT,
                telefone TEXT,
                ativo BOOLEAN DEFAULT 1,
                criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela de especialidades
        conn.execute('''
            CREATE TABLE IF NOT EXISTS especialidades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                descricao TEXT,
                ativo BOOLEAN DEFAULT 1,
                requer_anexo BOOLEAN DEFAULT 0,
                criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela de médicos
        conn.execute('''
            CREATE TABLE IF NOT EXISTS medicos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                crm TEXT UNIQUE,
                especialidade_id INTEGER NOT NULL,
                ativo BOOLEAN DEFAULT 1,
                agenda_recorrente BOOLEAN DEFAULT 0,
                criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (especialidade_id) REFERENCES especialidades (id)
            )
        ''')
        
        # Tabela de pacientes
        conn.execute('''
            CREATE TABLE IF NOT EXISTS pacientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cpf TEXT NOT NULL UNIQUE,
                nome TEXT NOT NULL,
                data_nascimento DATE,
                telefone TEXT,
                email TEXT,
                carteirinha TEXT,
                tipo_atendimento TEXT DEFAULT 'particular',
                criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela de horários disponíveis
        conn.execute('''
            CREATE TABLE IF NOT EXISTS horarios_disponiveis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medico_id INTEGER NOT NULL,
                local_id INTEGER NOT NULL,
                dia_semana INTEGER NOT NULL,
                hora_inicio TIME NOT NULL,
                hora_fim TIME NOT NULL,
                duracao_consulta INTEGER DEFAULT 30,
                ativo BOOLEAN DEFAULT 1,
                criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (medico_id) REFERENCES medicos (id),
                FOREIGN KEY (local_id) REFERENCES locais (id)
            )
        ''')
        
        # Tabela de agendamentos
        conn.execute('''
            CREATE TABLE IF NOT EXISTS agendamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id INTEGER NOT NULL,
                medico_id INTEGER NOT NULL,
                especialidade_id INTEGER NOT NULL,
                local_id INTEGER NOT NULL,
                data DATE NOT NULL,
                hora TIME NOT NULL,
                observacoes TEXT,
                status TEXT DEFAULT 'agendado',
                anexo_nome TEXT,
                anexo_path TEXT,
                criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                cancelado_em DATETIME,
                motivo_cancelamento TEXT,
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id),
                FOREIGN KEY (medico_id) REFERENCES medicos (id),
                FOREIGN KEY (especialidade_id) REFERENCES especialidades (id),
                FOREIGN KEY (local_id) REFERENCES locais (id)
            )
        ''')
        
        # Tabela de conversas do chatbot
        conn.execute('''
            CREATE TABLE IF NOT EXISTS conversas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL UNIQUE,
                paciente_id INTEGER,
                estado TEXT DEFAULT 'inicio',
                dados_temporarios TEXT,
                criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
            )
        ''')
        
        # Tabela de configurações
        conn.execute('''
            CREATE TABLE IF NOT EXISTS configuracoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT NOT NULL UNIQUE,
                valor TEXT,
                descricao TEXT,
                atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela de agendamentos recorrentes
        conn.execute('''
            CREATE TABLE IF NOT EXISTS agendamentos_recorrentes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id INTEGER NOT NULL,
                medico_id INTEGER NOT NULL,
                especialidade_id INTEGER NOT NULL,
                local_id INTEGER NOT NULL,
                dia_semana INTEGER NOT NULL,
                hora TIME NOT NULL,
                data_inicio DATE NOT NULL,
                data_fim DATE,
                ativo BOOLEAN DEFAULT 1,
                observacoes TEXT,
                criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id),
                FOREIGN KEY (medico_id) REFERENCES medicos (id),
                FOREIGN KEY (especialidade_id) REFERENCES especialidades (id),
                FOREIGN KEY (local_id) REFERENCES locais (id)
            )
        ''')
        
        # Tabela de arquivos dos pacientes
        conn.execute('''
            CREATE TABLE IF NOT EXISTS arquivos_pacientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id INTEGER NOT NULL,
                agendamento_id INTEGER,
                nome_original TEXT NOT NULL,
                nome_arquivo TEXT NOT NULL,
                caminho_arquivo TEXT NOT NULL,
                tipo_arquivo TEXT,
                tamanho_arquivo INTEGER DEFAULT 0,
                descricao TEXT,
                criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id),
                FOREIGN KEY (agendamento_id) REFERENCES agendamentos (id)
            )
        ''')
        
        conn.commit()
    
    def _populate_initial_data(self, conn):
        """Popula dados iniciais se não existirem"""
        
        # Verificar se já existem dados
        cursor = conn.execute("SELECT COUNT(*) FROM locais")
        if cursor.fetchone()[0] > 0:
            return
        
        # Inserir locais iniciais
        locais_iniciais = [
            ("Contagem", "Rua Principal, 123", "Contagem", "(31) 3333-4444"),
            ("Belo Horizonte", "Av. Central, 456", "Belo Horizonte", "(31) 2222-5555")
        ]
        
        conn.executemany('''
            INSERT INTO locais (nome, endereco, cidade, telefone)
            VALUES (?, ?, ?, ?)
        ''', locais_iniciais)
        
        # Inserir especialidades iniciais
        especialidades_iniciais = [
            ("Clínica Geral", "Consultas gerais e check-ups"),
            ("Cardiologia", "Especialista em coração"),
            ("Dermatologia", "Cuidados com a pele"),
            ("Pediatria", "Especialista em crianças"),
            ("Ginecologia", "Saúde da mulher"),
            ("Ortopedia", "Ossos e articulações"),
            ("Psiquiatria", "Saúde mental"),
            ("Oftalmologia", "Cuidados com os olhos")
        ]
        
        conn.executemany('''
            INSERT INTO especialidades (nome, descricao)
            VALUES (?, ?)
        ''', especialidades_iniciais)
        
        # Inserir médicos de exemplo
        medicos_iniciais = [
            ("Dr. João Silva", "12345-SP", 1),
            ("Dra. Maria Santos", "23456-SP", 2),
            ("Dr. Carlos Oliveira", "34567-SP", 3),
            ("Dra. Ana Costa", "45678-SP", 4),
            ("Dr. Pedro Lima", "56789-SP", 5),
            ("Dra. Julia Fernandes", "67890-SP", 6)
        ]
        
        conn.executemany('''
            INSERT INTO medicos (nome, crm, especialidade_id)
            VALUES (?, ?, ?)
        ''', medicos_iniciais)
        
        # Inserir horários de exemplo para Dr. João Silva (Clínica Geral)
        conn.executemany('''
            INSERT INTO horarios_disponiveis (medico_id, local_id, dia_semana, hora_inicio, hora_fim, duracao_consulta)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', [
            (1, 1, 0, "08:00", "17:00", 30),  # Segunda
            (1, 1, 1, "08:00", "17:00", 30),  # Terça
            (1, 1, 2, "08:00", "17:00", 30),  # Quarta
            (1, 1, 3, "08:00", "17:00", 30),  # Quinta
            (1, 1, 4, "08:00", "17:00", 30),  # Sexta
        ])
        
        # Inserir horários para Dra. Ana Costa (Pediatria) - ESSENCIAL para Neuro Pediatra
        conn.executemany('''
            INSERT INTO horarios_disponiveis (medico_id, local_id, dia_semana, hora_inicio, hora_fim, duracao_consulta)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', [
            (4, 2, 0, "09:00", "16:00", 30),  # Segunda - Belo Horizonte
            (4, 2, 1, "09:00", "16:00", 30),  # Terça
            (4, 2, 2, "09:00", "16:00", 30),  # Quarta
            (4, 2, 3, "09:00", "16:00", 30),  # Quinta
            (4, 2, 4, "09:00", "16:00", 30),  # Sexta
        ])
        
        # Inserir horários para Dra. Maria Santos
        horarios_maria = [
            (2, 1, 0, "08:00", "12:00", 30),  # Segunda em Contagem
            (2, 1, 1, "08:00", "12:00", 30),  # Terça em Contagem
            (2, 2, 2, "13:00", "17:00", 30),  # Quarta em BH
            (2, 2, 3, "13:00", "17:00", 30),  # Quinta em BH
        ]
        
        conn.executemany('''
            INSERT INTO horarios_disponiveis (medico_id, local_id, dia_semana, hora_inicio, hora_fim, duracao_consulta)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', horarios_maria)
        
        # Horários para outros médicos (em Contagem, segunda a sexta)
        for medico_id in range(3, 7):
            for dia_semana in range(5):
                conn.execute('''
                    INSERT INTO horarios_disponiveis (medico_id, local_id, dia_semana, hora_inicio, hora_fim, duracao_consulta)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (medico_id, 1, dia_semana, "08:00", "18:00", 30))
        
        # Inserir configurações iniciais
        configuracoes_iniciais = [
            ('nome_clinica', 'Clínica João Layon', 'Nome da clínica exibido no sistema'),
            ('nome_assistente', 'Assistente Virtual', 'Nome do assistente de agendamentos'),
            ('telefone_clinica', '(31) 3333-4444', 'Telefone principal da clínica'),
            ('email_admin', 'joao@gmail.com', 'Email do administrador'),
            ('senha_admin', '30031936Vo', 'Senha do administrador'),
            ('horario_funcionamento', 'Segunda a Sexta, 8h às 18h', 'Horário de funcionamento da clínica'),
            ('bloquear_especialidades_duplicadas', 'false', 'Impedir paciente ter agendamentos em especialidades iguais'),
            ('duracao_agendamento_recorrente', '4', 'Duração em semanas para agendamentos recorrentes')
        ]
        
        conn.executemany('''
            INSERT INTO configuracoes (chave, valor, descricao)
            VALUES (?, ?, ?)
        ''', configuracoes_iniciais)
        
        conn.commit()
        logger.info("Dados iniciais inseridos no banco SQLite")
    
    def get_connection(self):
        """Retorna uma nova conexão com o banco"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row  # Para acessar colunas por nome
        return conn
    
    def execute_query(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Executa uma query SELECT e retorna os resultados"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()
    
    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """Executa uma query INSERT e retorna o ID inserido"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.lastrowid
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Executa uma query UPDATE/DELETE e retorna o número de linhas afetadas"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount

# Instância global do banco
db = Database()