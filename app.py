from flask import Flask, render_template, request, jsonify
import sqlite3

# --- Bloco do Banco de Dados entrando antes do app = Flask(--name--) ---
def iniciar_banco():
    conexao = sqlite3.connect("barbearia.db")
    cursor = conexao.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agendamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT ,
            nome TEXT NOT NULL,
            servico TEXT NOT NULL,
            horario TEXT NOT NULL
        )
    """)
    conexao.commit()
    conexao.close()
    
# Executa a criação do banco antes do servidor ligar    
iniciar_banco()

def pegar_horarios_ocupados():
    # 1. Ligamos para o banco de dados
    conexao = sqlite3.connect("barbearia.db")
    cursor = conexao.cursor()
    
    # 2. Fazer a query SQL para pegar apenas a coluna "horario" de todos os agendamentos
    cursor.execute("SELECT horario FROM agendamentos")
    linhas = cursor.fetchall()  # Puxa todas as linhas encontradas no banco
    
    conexao.close()
    
    # 3. Limpamos os dados usando o mesmo nome de variável (linha)
    horarios_ocupados = [linha[0] for linha in linhas]
    
    return horarios_ocupados
app = Flask(__name__)

# Rota 1: Entrega a página visual para o cliente
@app.route('/')
def home():
    # 1. ligamos a maquina pra descobrir quais horarios estao pegos.
    ocupados = pegar_horarios_ocupados()
    
    # 2. Entregamos o HTML e enviamos a lista junto com o nome 'horarios_bloqueados'
    return render_template('index.html', horarios_bloqueados=ocupados)

# Rota 2: A caixinha de correio que recebe os dados do agendamento para salvar
@app.route('/salvar-agendamento', methods=['POST'])
def salvar_agendamento():
    dados = request.json
    nome_cliente = dados.get('nome')
    servico_escolhido = dados.get('servico')
    horario_escolhido = dados.get('horario') 

    # Ligando o banco de dados
    conexao = sqlite3.connect("barbearia.db")
    cursor = conexao.cursor()
    
    # Usando o comando SQL INSERT INTO para injetar os dados nas colunas certas
    cursor.execute("""
        INSERT INTO agendamentos (nome, servico, horario)
        VALUES (?, ?, ?)
    """, (nome_cliente, servico_escolhido, horario_escolhido))
    
    # Salvando as alterções e fechando a conexão com segurança
    conexao.commit()
    conexao.close()
    print(f" Sucesso! {nome_cliente} gravado direto no Banco de Dados!")
    
    return jsonify({"status": "sucesso", "mensagem": "Agendamento gravado!"})

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)