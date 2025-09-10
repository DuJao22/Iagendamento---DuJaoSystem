#!/usr/bin/env python3
import sqlite3
import json
from datetime import datetime, date, time

# Conectar ao banco
conn = sqlite3.connect('sistema_agendamento.db')
conn.row_factory = sqlite3.Row  # Para acessar colunas por nome
cursor = conn.cursor()

print("=== ANÁLISE COMPLETA DO SISTEMA DE AGENDAMENTO ===\n")

# 1. Listar tabelas
print("1. TABELAS NO SISTEMA:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
for table in tables:
    print(f"   - {table['name']}")

print("\n" + "="*50)

# 2. Analisar médicos e especialidades
print("\n2. MÉDICOS E ESPECIALIDADES:")
cursor.execute("""
    SELECT m.id, m.nome, m.crm, e.nome as especialidade 
    FROM medicos m 
    JOIN especialidades e ON m.especialidade_id = e.id 
    WHERE m.ativo = 1
""")
medicos = cursor.fetchall()
for medico in medicos:
    print(f"   Dr(a). {medico['nome']} - {medico['especialidade']} (CRM: {medico['crm']})")

print("\n" + "="*50)

# 3. Analisar horários disponíveis
print("\n3. HORÁRIOS CONFIGURADOS:")
cursor.execute("""
    SELECT hd.*, m.nome as medico_nome, l.nome as local_nome,
           CASE hd.dia_semana 
               WHEN 0 THEN 'Segunda'
               WHEN 1 THEN 'Terça' 
               WHEN 2 THEN 'Quarta'
               WHEN 3 THEN 'Quinta'
               WHEN 4 THEN 'Sexta'
               WHEN 5 THEN 'Sábado'
               WHEN 6 THEN 'Domingo'
           END as dia_nome
    FROM horarios_disponiveis hd
    JOIN medicos m ON hd.medico_id = m.id
    JOIN locais l ON hd.local_id = l.id
    WHERE hd.ativo = 1
    ORDER BY m.nome, hd.dia_semana, hd.hora_inicio
""")
horarios = cursor.fetchall()

medico_atual = ""
for horario in horarios:
    if horario['medico_nome'] != medico_atual:
        medico_atual = horario['medico_nome']
        print(f"\n   {medico_atual} ({horario['local_nome']}):")
    
    print(f"     {horario['dia_nome']}: {horario['hora_inicio']} - {horario['hora_fim']} (duração: {horario['duracao_consulta']}min)")

print("\n" + "="*50)

# 4. Verificar agendamentos existentes
print("\n4. AGENDAMENTOS EXISTENTES:")
cursor.execute("""
    SELECT a.*, p.nome as paciente_nome, m.nome as medico_nome, 
           e.nome as especialidade_nome, l.nome as local_nome
    FROM agendamentos a
    JOIN pacientes p ON a.paciente_id = p.id
    JOIN medicos m ON a.medico_id = m.id  
    JOIN especialidades e ON a.especialidade_id = e.id
    JOIN locais l ON a.local_id = l.id
    ORDER BY a.data, a.hora
""")
agendamentos = cursor.fetchall()

if agendamentos:
    for ag in agendamentos:
        print(f"   {ag['data']} {ag['hora']} - {ag['paciente_nome']} com {ag['medico_nome']} ({ag['especialidade_nome']}) em {ag['local_nome']} - Status: {ag['status']}")
else:
    print("   Nenhum agendamento encontrado")

print("\n" + "="*50)

# 5. Análise de conflitos potenciais
print("\n5. ANÁLISE DE DISPONIBILIDADE HOJE:")
today = date.today()
today_str = today.strftime('%Y-%m-%d')
dia_semana_hoje = today.weekday()

print(f"   Data: {today_str} ({['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'][dia_semana_hoje]})")

# Buscar horários disponíveis para hoje
cursor.execute("""
    SELECT hd.*, m.nome as medico_nome, l.nome as local_nome, e.nome as especialidade_nome
    FROM horarios_disponiveis hd
    JOIN medicos m ON hd.medico_id = m.id
    JOIN locais l ON hd.local_id = l.id  
    JOIN especialidades e ON m.especialidade_id = e.id
    WHERE hd.dia_semana = ? AND hd.ativo = 1 AND m.ativo = 1
    ORDER BY hd.hora_inicio
""", (dia_semana_hoje,))

horarios_hoje = cursor.fetchall()

if horarios_hoje:
    print(f"   Médicos disponíveis hoje:")
    for h in horarios_hoje:
        # Verificar se há agendamentos para este médico hoje
        cursor.execute("""
            SELECT COUNT(*) as total 
            FROM agendamentos 
            WHERE medico_id = ? AND data = ? AND status = 'agendado'
        """, (h['medico_id'], today_str))
        
        agendados = cursor.fetchone()['total']
        
        print(f"     {h['medico_nome']} ({h['especialidade_nome']}) - {h['hora_inicio']}-{h['hora_fim']} em {h['local_nome']} - {agendados} agendamentos")
else:
    print(f"   Nenhum médico disponível hoje ({['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'][dia_semana_hoje]})")

print("\n" + "="*50)

# 6. Gerar slots de horário disponíveis para teste
print("\n6. SLOTS DE HORÁRIOS CALCULADOS PARA HOJE:")

def gerar_slots_horario(hora_inicio, hora_fim, duracao_minutos):
    """Gera lista de slots de horário"""
    slots = []
    inicio = datetime.strptime(hora_inicio, '%H:%M').time()
    fim = datetime.strptime(hora_fim, '%H:%M').time()
    
    hora_atual = datetime.combine(date.today(), inicio)
    hora_final = datetime.combine(date.today(), fim)
    
    while hora_atual < hora_final:
        slots.append(hora_atual.strftime('%H:%M'))
        hora_atual += timedelta(minutes=duracao_minutos)
    
    return slots

from datetime import timedelta

for h in horarios_hoje:
    slots = gerar_slots_horario(h['hora_inicio'], h['hora_fim'], h['duracao_consulta'])
    print(f"\n   {h['medico_nome']} ({h['especialidade_nome']}) em {h['local_nome']}:")
    
    # Verificar quais slots estão ocupados
    slots_disponiveis = []
    for slot in slots[:10]:  # Mostrar apenas primeiros 10 slots
        cursor.execute("""
            SELECT COUNT(*) as ocupado 
            FROM agendamentos 
            WHERE medico_id = ? AND data = ? AND hora = ? AND status = 'agendado'
        """, (h['medico_id'], today_str, slot))
        
        ocupado = cursor.fetchone()['ocupado']
        status = "🔴 OCUPADO" if ocupado else "🟢 DISPONÍVEL"
        slots_disponiveis.append((slot, not ocupado))
        print(f"     {slot} - {status}")

print("\n" + "="*80)
print("ANÁLISE CONCLUÍDA")
print("="*80)

conn.close()