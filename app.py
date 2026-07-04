from flask import Flask, render_template, request, jsonify, session, redirect
import sqlite3

def iniciar_banco():
    # 1. Conectamos ou criamos o arquivo do banco de dados
    conexao = sqlite3.connect("barbearia.db")
    cursor = conexao.cursor()
    
    # 2. Criamos a tabela de agendamentos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agendamentos (
            nome TEXT, 
            whatsapp TEXT, 
            servico TEXT, 
            horario TEXT
        )
    """)
    
    # 3. Criamos a tabela VIP de assinantes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assinantes (
            nome TEXT, 
            whatsapp TEXT
        )
    """)
    
    # 4. Criamos a tabela de administradores para o painel login
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            usuario TEXT UNIQUE, 
            senha TEXT
        )
    """)
    
    # Inserimos um usuário administrador padrão se ele não existir
    try:
        cursor.execute("INSERT OR IGNORE INTO admins (usuario, senha) VALUES (?, ?)", ("admin", "admin123"))
    except Exception as e:
        print("Erro ao criar admin padrão:", e)
    
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
app.secret_key = "sua_chave_secreta_aqui_mude_depois" # <- Adicione essa linha aqui!

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
    whatsapp_cliente = dados.get('whatsapp')
    servico_escolhido = dados.get('servico')
    horario_escolhido = dados.get('horario')

    conexao = sqlite3.connect("barbearia.db")
    cursor = conexao.cursor()
    
    # Checando se é assinante
    cursor.execute("SELECT * FROM assinantes WHERE whatsapp = ?", (whatsapp_cliente,))
    assinante_encontrado = cursor.fetchone()
    
    # Criamos uma variável para avisar o site
    eh_assinante = False
    if assinante_encontrado:
        print(f"🔥 ATENÇÃO: O cliente {nome_cliente} é ASSINANTE VIP!")
        eh_assinante = True
    else:
        print(f"💰 CLIENTE AVULSO: {nome_cliente}")

    # Salva o agendamento
    cursor.execute("""
        INSERT INTO agendamentos (nome, whatsapp, servico, horario) 
        VALUES (?, ?, ?, ?)
    """, (nome_cliente, whatsapp_cliente, servico_escolhido, horario_escolhido))
    
    conexao.commit()
    conexao.close()
    
    # Enviamos a resposta dizendo se ele é VIP ou não!
    return jsonify({
        "status": "sucesso", 
        "mensagem": "Agendamento gravado!",
        "vip": eh_assinante,
        "nome": nome_cliente
    })

@app.route('/cadastrar-marcelo-vip')
def cadastrar_marcelo_vip():
    conexao = sqlite3.connect("barbearia.db")
    cursor = conexao.cursor()
    
    nome_vip = "Marcelo Assinante"
    whatsapp_vip = "21999999999"
    
    # Executamos o comando com os parâmetros na mesma linha para garantir o envio correto
    cursor.execute("INSERT INTO assinantes (nome, whatsapp) VALUES (?, ?)", (nome_vip, whatsapp_vip))
    
    conexao.commit()
    conexao.close()
    return f"Sucesso! {nome_vip} adicionado com o número {whatsapp_vip}!"

# Rota 3: Tela do Painel Administrativo
# Rota 3: Tela de Login do Admin
@app.route('/login', methods=['GET', 'POST'])
def login_admin():
    if request.method == 'POST':
        usuario_digitado = request.form.get('usuario')
        senha_digitada = request.form.get('senha')
        
        conexao = sqlite3.connect("barbearia.db")
        cursor = conexao.cursor()
        
        # Procura o admin no banco
        cursor.execute("SELECT * FROM admins WHERE usuario = ? AND senha = ?", (usuario_digitado, senha_digitada))
        admin_valido = cursor.fetchone()
        conexao.close()
        
        if admin_valido:
            session['admin_logado'] = usuario_digitado # Salva o carimbo na sessão!
            return redirect('/admin')
        else:
            return render_template('login.html', erro="Usuário ou senha incorretos!")
            
    return render_template('login.html')

# Rota de Logout para sair do painel com segurança
@app.route('/logout')
def logout_admin():
    session.pop('admin_logado', None) # Remove o carimbo
    return redirect('/login')

# Rota 3.1: Tela do Painel Administrativo (AGORA PROTEGIDA!)
@app.route('/admin')
def painel_admin():
    # Se o carimbo de login não estiver na sessão, barra o acesso!
    if 'admin_logado' not in session:
        return redirect('/login')
        
    conexao = sqlite3.connect("barbearia.db")
    cursor = conexao.cursor()
    
    cursor.execute("SELECT nome, whatsapp, servico, horario FROM agendamentos")
    agendamentos_rows = cursor.fetchall()
    
    lista_agendamentos = []
    for row in agendamentos_rows:
        cursor.execute("SELECT * FROM assinantes WHERE whatsapp = ?", (row[1],))
        eh_vip = cursor.fetchone() is not None
        
        lista_agendamentos.append({
            "nome": row[0],
            "whatsapp": row[1],
            "servico": row[2],
            "horario": row[3],
            "vip": eh_vip
        })
        
    conexao.close()
    return render_template('admin.html', agendamentos=lista_agendamentos)

# Rota 4: Botão mágico para tornar o cliente VIP direto pelo painel
@app.route('/admin/tornar-vip', methods=['POST'])
def tornar_vip_painel():
    dados = request.json
    nome_cliente = dados.get('nome')
    whatsapp_cliente = dados.get('whatsapp')
    
    conexao = sqlite3.connect("barbearia.db")
    cursor = conexao.cursor()
    
    try:
        # Insere o cliente na tabela de assinantes se ele já não estiver lá
        cursor.execute("INSERT OR IGNORE INTO assinantes (nome, whatsapp) VALUES (?, ?)", (nome_cliente, whatsapp_cliente))
        conexao.commit()
        resposta = {"status": "sucesso", "mensagem": f"{nome_cliente} agora é VIP!"}
    except Exception as e:
        resposta = {"status": "erro", "mensagem": str(e)}
        
    conexao.close()
    return jsonify(resposta)

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)