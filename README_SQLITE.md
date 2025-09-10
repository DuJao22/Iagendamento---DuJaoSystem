# Sistema de Agendamento Médico - SQLite3 Puro

## Visão Geral

O sistema foi totalmente convertido de PostgreSQL/SQLAlchemy para SQLite3 puro, oferecendo:
- **Performance**: Acesso direto ao banco sem overhead de ORM
- **Simplicidade**: Código mais simples e direto
- **Portabilidade**: Banco de dados em arquivo único
- **Preparação para SQLite Cloud**: Arquitetura pronta para migração

## Arquitetura do Banco de Dados

### Estrutura Principal
- **database.py**: Classe principal de gerenciamento do banco SQLite
- **models_sqlite.py**: Modelos Python puros (sem SQLAlchemy)
- **app_sqlite.py**: Aplicação Flask adaptada para SQLite
- **ai_service_sqlite.py**: Serviço de IA adaptado

### Tabelas Criadas
1. **locais** - Locais de atendimento
2. **especialidades** - Especialidades médicas
3. **medicos** - Cadastro de médicos
4. **pacientes** - Cadastro de pacientes
5. **horarios_disponiveis** - Horários de trabalho dos médicos
6. **agendamentos** - Agendamentos realizados
7. **conversas** - Estados do chatbot
8. **configuracoes** - Configurações do sistema
9. **agendamentos_recorrentes** - Agendamentos recorrentes

## Dados Iniciais

### Locais de Atendimento
- Contagem - Rua Principal, 123
- Belo Horizonte - Av. Central, 456

### Especialidades Médicas
- Clínica Geral
- Cardiologia
- Dermatologia
- Pediatria
- Ginecologia
- Ortopedia
- Psiquiatria
- Oftalmologia

### Médicos de Exemplo
- Dr. João Silva (Clínica Geral)
- Dra. Maria Santos (Cardiologia)
- Dr. Carlos Oliveira (Dermatologia)
- Dra. Ana Costa (Pediatria)
- Dr. Pedro Lima (Ginecologia)
- Dra. Julia Fernandes (Ortopedia)

## Funcionalidades Mantidas

### Chatbot com IA
- Processamento de linguagem natural com Google Gemini
- Conversação inteligente para agendamentos
- Detecção automática de intenções
- Cadastro de pacientes via chat
- Cancelamento e consulta de agendamentos

### Painel Administrativo
- Gestão completa de médicos e especialidades
- Configuração de horários de atendimento
- Visualização de estatísticas
- Configurações do sistema

## Como Usar

### Inicialização Automática
O banco é criado automaticamente na primeira execução em:
```
sistema_agendamento.db
```

### Conexão com o Banco
```python
from database import db

# Executar query
result = db.execute_query("SELECT * FROM pacientes")

# Inserir dados
id_novo = db.execute_insert("INSERT INTO pacientes (cpf, nome) VALUES (?, ?)", ("12345678901", "João Silva"))

# Atualizar dados
db.execute_update("UPDATE pacientes SET nome = ? WHERE id = ?", ("João Santos", 1))
```

### Usando os Modelos
```python
from models_sqlite import Paciente, Agendamento, Especialidade

# Buscar todos os pacientes
pacientes = Paciente.find_all()

# Buscar por CPF
paciente = Paciente.find_by_cpf("12345678901")

# Criar novo paciente
novo_paciente = Paciente.create(
    cpf="98765432100",
    nome="Maria Silva",
    telefone="31999887766"
)

# Buscar especialidades ativas
especialidades = Especialidade.find_active()
```

## Migração para SQLite Cloud

### Preparação Atual
O sistema está preparado para migração futura para SQLite Cloud:

1. **Código Agnóstico**: Todas as queries são compatíveis
2. **Conexão Configurável**: Facilmente alterável em `database.py`
3. **Estrutura Mantida**: Mesmo schema funciona na nuvem

### Passos para Migração

#### 1. Configurar SQLite Cloud
```python
# Em database.py, alterar:
class Database:
    def __init__(self, db_path: str = "libsql://[seu-database].turso.io"):
        # Usar cliente libsql para conexão remota
```

#### 2. Instalar Cliente
```bash
pip install libsql-client
```

#### 3. Atualizar Conexão
```python
import libsql_client

class Database:
    def __init__(self, db_url: str, auth_token: str = None):
        if db_url.startswith('libsql://'):
            # Conexão SQLite Cloud
            self.client = libsql_client.create_client(
                url=db_url,
                auth_token=auth_token
            )
        else:
            # Conexão local SQLite
            self.db_path = db_url
```

#### 4. Variáveis de Ambiente
```bash
# Para SQLite Cloud
DATABASE_URL=libsql://seu-database.turso.io
DATABASE_AUTH_TOKEN=sua-chave-de-autenticacao

# Para SQLite local (atual)
DATABASE_URL=sistema_agendamento.db
```

## Vantagens da Arquitetura Atual

### Performance
- **Queries Diretas**: Sem overhead de ORM
- **Cache Automático**: SQLite com otimizações nativas
- **Menor Latência**: Acesso direto ao arquivo

### Simplicidade
- **Código Limpo**: Modelos Python simples
- **Debuging Fácil**: Queries SQL visíveis
- **Manutenção Simples**: Menos abstrações

### Portabilidade
- **Arquivo Único**: Fácil backup e migração
- **Zero Configuração**: Não precisa servidor
- **Cross-Platform**: Funciona em qualquer SO

### Flexibilidade Futura
- **SQLite Cloud Ready**: Migração transparente
- **Queries Otimizáveis**: Controle total sobre SQL
- **Escalabilidade**: Preparado para crescimento

## Estrutura de Arquivos

```
sistema_agendamento/
├── database.py              # Gerenciador do banco SQLite
├── models_sqlite.py         # Modelos Python puros
├── app_sqlite.py           # Aplicação Flask principal
├── ai_service_sqlite.py    # Serviço de IA adaptado
├── main.py                 # Entry point atualizado
├── sistema_agendamento.db  # Banco SQLite (criado automaticamente)
└── templates/              # Templates HTML (mantidos)
```

## Compatibilidade

### Funcionalidades Mantidas
✅ Chatbot com IA Google Gemini
✅ Sistema de agendamentos completo
✅ Painel administrativo
✅ Cadastro de pacientes
✅ Configurações dinâmicas
✅ Logs do sistema

### Melhorias Implementadas
✅ Performance superior
✅ Código mais simples
✅ Menos dependências
✅ Preparação para nuvem
✅ Backup mais fácil

## Comandos Úteis

### Verificar Banco
```python
# Ver estatísticas
from models_sqlite import *
print("Pacientes:", len(Paciente.find_all()))
print("Especialidades:", len(Especialidade.find_all()))
print("Médicos:", len(Medico.find_all()))
```

### Backup do Banco
```bash
# Copiar arquivo do banco
cp sistema_agendamento.db backup_$(date +%Y%m%d_%H%M%S).db
```

### Reset do Sistema
```bash
# Remover banco para recriar
rm sistema_agendamento.db
# Reiniciar aplicação para recriar automaticamente
```

## Considerações de Produção

### Recomendações
1. **Backup Regular**: Automatizar backup do arquivo .db
2. **Logs**: Manter logs para auditoria
3. **Monitoramento**: Acompanhar performance
4. **Migração Gradual**: Testar SQLite Cloud em ambiente de teste

### Limitações Atuais
- Conexões simultâneas limitadas (SQLite padrão)
- Arquivo único pode crescer muito
- Backup durante operação pode travar

### Soluções Futuras com SQLite Cloud
- Múltiplas conexões simultâneas
- Backup automático na nuvem
- Escalabilidade automática
- Redundância geográfica

## Próximos Passos

1. **Teste Completo**: Validar todas as funcionalidades
2. **Performance**: Otimizar queries críticas
3. **SQLite Cloud**: Preparar migração para nuvem
4. **Backup**: Implementar rotina automática
5. **Monitoramento**: Adicionar métricas de uso