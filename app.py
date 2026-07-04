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

    # === [ALTERAÇÃO 1] Criamos a tabela para gerenciar horários bloqueados pelo admin ===
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bloqueios (
            horario TEXT UNIQUE
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
    
    # 2. Puxa horários de agendamentos de clientes
    cursor.execute("SELECT horario FROM agendamentos")
    linhas_agendamentos = cursor.fetchall()  
    
    # === [ALTERAÇÃO 2] Puxa também os horários que o Admin bloqueou manualmente ===
    cursor.execute("SELECT horario FROM bloqueios")
    linhas_bloqueios = cursor.fetchall()
    
    conexao.close()
    
    # Juntamos tudo na lista de horários indisponíveis para o cliente
    horarios_ocupados = [linha[0] for linha in linhas_agendamentos]
    horarios_bloqueados_admin = [linha[0] for linha in linhas_bloqueios]
    
    # Retorna a união dos dois (Agendados + Bloqueados)
    return list(set(horarios_ocupados + horarios_bloqueados_admin))

app = Flask(__name__)
app.secret_key = "sua_chave_secreta_aqui_mude_depois"

# Rota 1: Entrega a página visual para o cliente
@app.route('/')
def home():
    ocupados = pegar_horarios_ocupados()
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
    cursor.execute("INSERT INTO assinantes (nome, whatsapp) VALUES (?, ?)", (nome_vip, whatsapp_vip))
    conexao.commit()
    conexao.close()
    return f"Sucesso! {nome_vip} adicionado com o número {whatsapp_vip}!"

# Rota 3: Tela de Login do Admin
@app.route('/login', methods=['GET', 'POST'])
def login_admin():
    if request.method == 'POST':
        usuario_digitado = request.form.get('usuario')
        senha_digitada = request.form.get('senha')
        
        conexao = sqlite3.connect("barbearia.db")
        cursor = conexao.cursor()
        cursor.execute("SELECT * FROM admins WHERE usuario = ? AND senha = ?", (usuario_digitado, senha_digitada))
        admin_valido = cursor.fetchone()
        conexao.close()
        
        if admin_valido:
            session['admin_logado'] = usuario_digitado
            return redirect('/admin')
        else:
            return render_template('login.html', erro="Usuário ou senha incorretos!")
            
    return render_template('login.html')

# Rota de Logout para sair do painel com segurança
@app.route('/logout')
def logout_admin():
    session.pop('admin_logado', None)
    return redirect('/login')

# Rota 3.1: Tela do Painel Administrativo (COM FATURAMENTO, MÉTRICAS E HORÁRIOS)
@app.route('/admin')
def painel_admin():
    if 'admin_logado' not in session:
        return redirect('/login')
        
    conexao = sqlite3.connect("barbearia.db")
    cursor = conexao.cursor()
    
    # 1. Puxa os agendamentos
    cursor.execute("SELECT nome, whatsapp, servico, horario FROM agendamentos")
    agendamentos_rows = cursor.fetchall()
    
    lista_agendamentos = []
    faturamento_total = 0.0
    total_atendimentos = 0
    
    for row in agendamentos_rows:
        nome_cliente = row[0]
        whatsapp_cliente = row[1]
        servico_texto = row[2]
        horario_cliente = row[3]
        
        cursor.execute("SELECT * FROM assinantes WHERE whatsapp = ?", (whatsapp_cliente,))
        eh_vip = cursor.fetchone() is not None
        
        valor_servico = 0.0
        if eh_vip:
            valor_servico = 0.0
        else:
            try:
                if "R$" in servico_texto:
                    partes = servico_texto.split("R$")
                    valor_str = partes[1].split("/")[0].strip()
                    valor_str = valor_str.replace(",", ".")
                    valor_servico = float(valor_str)
            except Exception as e:
                print(f"Erro ao calcular valor do serviço '{servico_texto}': {e}")
                valor_servico = 0.0
        
        faturamento_total += valor_servico
        total_atendimentos += 1
        
        lista_agendamentos.append({
            "nome": nome_cliente,
            "whatsapp": whatsapp_cliente,
            "servico": servico_texto,
            "horario": horario_cliente,
            "vip": eh_vip
        })
        
    # === [ALTERAÇÃO 3] Listagem de horários que já estão bloqueados para gerenciar no painel ===
    cursor.execute("SELECT horario FROM bloqueios")
    bloqueados_rows = cursor.fetchall()
    lista_bloqueados = [b[0] for b in bloqueados_rows]
    
    conexao.close()
    
    faturamento_formatado = f"R$ {faturamento_total:.2f}".replace(".", ",")
    
    # Lista de horários padrão que a barbearia atende (para você escolher qual quer bloquear)
    horarios_padrao_barbearia = [
        "09:00", "10:00", "11:00", "12:00", "13:00", 
        "14:00", "15:00", "16:00", "17:00", "18:00", "19:00"
    ]
    
    return render_template(
        'admin.html', 
        agendamentos=lista_agendamentos, 
        faturamento=faturamento_formatado, 
        total_atendimentos=total_atendimentos,
        horarios_disponiveis_painel=horarios_padrao_barbearia,
        horarios_bloqueados_admin=lista_bloqueados
    )

# Rota 4: Botão mágico para tornar o cliente VIP direto pelo painel
@app.route('/admin/tornar-vip', methods=['POST'])
def tornar_vip_painel():
    dados = request.json
    nome_cliente = dados.get('nome')
    whatsapp_cliente = dados.get('whatsapp')
    
    conexao = sqlite3.connect("barbearia.db")
    cursor = conexao.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO assinantes (nome, whatsapp) VALUES (?, ?)", (nome_cliente, whatsapp_cliente))
        conexao.commit()
        resposta = {"status": "sucesso", "mensagem": f"{nome_cliente} agora é VIP!"}
    except Exception as e:
        resposta = {"status": "erro", "mensagem": str(e)}
    conexao.close()
    return jsonify(resposta)


# === [ALTERAÇÃO 4] Novas rotas para Bloquear e Liberar horários através do Painel ===
@app.route('/admin/bloquear-horario', methods=['POST'])
def bloquear_horario():
    if 'admin_logado' not in session:
        return jsonify({"status": "erro", "mensagem": "Não autorizado"}), 401
    
    dados = request.json
    horario = dados.get('horario')
    
    conexao = sqlite3.connect("barbearia.db")
    cursor = conexao.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO bloqueios (horario) VALUES (?)", (horario,))
        conexao.commit()
        resposta = {"status": "sucesso", "mensagem": f"Horário {horario} bloqueado!"}
    except Exception as e:
        resposta = {"status": "erro", "mensagem": str(e)}
    conexao.close()
    return jsonify(resposta)

@app.route('/admin/cancelar-agendamento', methods=['POST'])
def cancelar_agendamento():
    # Verifica se o usuário está logado como admin
    if 'admin' not in session:
        return jsonify({"status": "erro", "mensagem": "Não autorizado"}), 401

    dados = request.get_json()
    horario_cliente = dados.get('horario')

    if not horario_cliente:
        return jsonify({"status": "erro", "mensagem": "Horário inválido"}), 400

    try:
        conn = sqlite3.connect('barbearia.db')
        cursor = conn.cursor()
        
        # Deleta o agendamento daquele horário específico
        cursor.execute("DELETE FROM agendamentos WHERE horario = ?", (horario_cliente,))
        conn.commit()
        conn.close()
        
        return jsonify({"status": "sucesso", "mensagem": "Agendamento cancelado com sucesso!"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/admin/liberar-horario', methods=['POST'])
def liberar_horario():
    if 'admin_logado' not in session:
        return jsonify({"status": "erro", "mensagem": "Não autorizado"}), 401
    
    dados = request.json
    horario = dados.get('horario')
    
    conexao = sqlite3.connect("barbearia.db")
    cursor = conexao.cursor()
    try:
        cursor.execute("DELETE FROM bloqueios WHERE horario = ?", (horario,))
        conexao.commit()
        resposta = {"status": "sucesso", "mensagem": f"Horário {horario} liberado!"}
    except Exception as e:
        resposta = {"status": "erro", "mensagem": str(e)}
    conexao.close()
    return jsonify(resposta)


if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)