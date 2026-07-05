from flask import Flask, render_template, request, jsonify, redirect, session
import pg8000.dbapi
import re

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_super_segura_aqui'

DATABASE_URL = "postgresql://neondb_owner:npg_rTPwGgzo6Cj8@ep-flat-butterfly-ac5vi3vd.sa-east-1.aws.neon.tech/neondb?sslmode=require"

def conectar_banco():
    padrao = r"postgresql://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^/:]+)(?::(?P<port>\d+))?/(?P<database>[^\?]+)"
    match = re.match(padrao, DATABASE_URL)
    dados = match.groupdict()
    
    return pg8000.dbapi.connect(
        user=dados['user'],
        password=dados['password'],
        host=dados['host'],
        port=int(dados['port']) if dados['port'] else 5432,
        database=dados['database'],
        ssl_context=True
    )

def inicializar_banco():
    conexao = conectar_banco()
    cursor = conexao.cursor()
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agendamentos (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL,
                whatsapp TEXT NOT NULL,
                servico TEXT NOT NULL,
                data TEXT NOT NULL,
                horario TEXT NOT NULL,
                valor REAL DEFAULT 0.0,
                vip INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assinantes (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL,
                whatsapp TEXT NOT NULL UNIQUE
            )
        ''')
        conexao.commit()
    finally:
        cursor.close()
        conexao.close()

# Inicializa o banco de dados garantindo encerramento da conexão inicial
inicializar_banco()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/horarios-ocupados', methods=['GET'])
def horarios_ocupados():
    data = request.args.get('data')
    if not data:
        return jsonify([])
        
    conexao = conectar_banco()
    cursor = conexao.cursor()
    try:
        cursor.execute("SELECT horario FROM agendamentos WHERE data = %s", (data,))
        vagas = cursor.fetchall()
        lista_ocupados = [vaga[0] for vaga in vagas] if vagas else []
        return jsonify(lista_ocupados)
    finally:
        cursor.close()
        conexao.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        senha = request.form.get('senha')
        if usuario == 'admin' and senha == 'admin123':
            session['admin_logado'] = True
            return redirect('/admin')
        else:
            return render_template('login.html', erro="Usuário ou senha incorretos!")
    return render_template('login.html')

@app.route('/sair')
def sair():
    session.pop('admin_logado', None)
    return redirect('/login')

@app.route('/salvar-agendamento', methods=['POST'])
def salvar_agendamento():
    dados = request.json
    nome_cliente = dados.get('nome')
    whatsapp_cliente = dados.get('whatsapp')
    servico_escolhido = dados.get('servico')
    horario_escolhido = dados.get('horario')
    data_escolhida = dados.get('data')

    conexao = conectar_banco()
    cursor = conexao.cursor()

    try:
        cursor.execute("SELECT id FROM agendamentos WHERE data = %s AND horario = %s", (data_escolhida, horario_escolhido))
        ja_ocupado = cursor.fetchone()

        if ja_ocupado:
            return jsonify({"status": "erro", "mensagem": "Este horário já foi preenchido!"}), 400

        valor_corte = 0.0
        if servico_escolhido:
            valores_encontrados = re.findall(r"R\$\s*(\d+[\d,.]*)", servico_escolhido)
            if valores_encontrados:
                valor_corte = float(valores_encontrados[0].replace(',', '.'))

        cursor.execute("SELECT id FROM assinantes WHERE whatsapp = %s", (whatsapp_cliente,))
        assinante_encontrado = cursor.fetchone()
        eh_assinante = 1 if assinante_encontrado else 0

        cursor.execute("""
            INSERT INTO agendamentos (nome, whatsapp, servico, data, horario, valor, vip)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (nome_cliente, whatsapp_cliente, servico_escolhido, data_escolhida, horario_escolhido, valor_corte, eh_assinante))

        conexao.commit()

        return jsonify({
            "status": "sucesso",
            "mensagem": "Agendamento gravado!",
            "vip": bool(eh_assinante),
            "nome": nome_cliente,
            "data": data_escolhida
        })
    finally:
        cursor.close()
        conexao.close()

@app.route('/admin')
def admin_painel():
    if 'admin_logado' not in session:
        return redirect('/login')

    conexao = conectar_banco()
    cursor = conexao.cursor()
    
    try:
        cursor.execute("SELECT nome, whatsapp, servico, data, horario, valor, vip FROM agendamentos ORDER BY data, horario")
        agendamentos_rows = cursor.fetchall()

        lista_agendamentos = []
        if agendamentos_rows:
            for row in agendamentos_rows:
                lista_agendamentos.append({
                    "nome": row[0],
                    "whatsapp": row[1],
                    "servico": row[2],
                    "data": row[3],
                    "horario": row[4],
                    "valor": f"R$ {row[5]:.2f}".replace('.', ','),
                    "vip": bool(row[6])
                })

        cursor.execute("SELECT SUM(valor) FROM agendamentos")
        resultado_faturamento = cursor.fetchone()
        faturamento_total = float(resultado_faturamento[0]) if resultado_faturamento and resultado_faturamento[0] is not None else 0.0

        cursor.execute("SELECT COUNT(*) FROM agendamentos")
        resultado_contagem = cursor.fetchone()
        total_atendimentos = resultado_contagem[0] if resultado_contagem else 0

        horarios_padrao = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00"]
        horarios_bloqueados = session.get('horarios_bloqueados_admin', [])

        return render_template(
            "admin.html",
            agendamentos=lista_agendamentos,
            faturamento=f"R$ {faturamento_total:.2f}".replace('.', ','),
            total_atendimentos=total_atendimentos,
            horarios_disponiveis_painel=horarios_padrao,
            horarios_bloqueados_admin=horarios_bloqueados
        )
    finally:
        cursor.close()
        conexao.close()

@app.route('/admin/cancelar-agendamento', methods=['POST'])
def cancelar_agendamento():
    if 'admin_logado' not in session:
        return jsonify({"status": "erro", "mensagem": "Não autorizado"}), 401
        
    dados = request.get_json()
    horario_cliente = dados.get('horario')
    data_cliente = dados.get('data')
    
    conexao = conectar_banco()
    cursor = conexao.cursor()
    try:
        cursor.execute("DELETE FROM agendamentos WHERE horario = %s AND data = %s", (horario_cliente, data_cliente))
        conexao.commit()
        return jsonify({"status": "sucesso", "mensagem": "Agendamento cancelado com sucesso!"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500
    finally:
        cursor.close()
        conexao.close()

@app.route('/admin/bloquear-horario', methods=['POST'])
def bloquear_horario():
    if 'admin_logado' not in session:
        return jsonify({"status": "erro", "mensagem": "Não autorizado"}), 401
    dados = request.get_json()
    horario = dados.get('horario')
    horarios_bloqueados = session.get('horarios_bloqueados_admin', [])
    if horario not in horarios_bloqueados:
        horarios_bloqueados.append(horario)
        session['horarios_bloqueados_admin'] = horarios_bloqueados
    return jsonify({"status": "sucesso", "mensagem": f"Horário {horario} blocked!"})

@app.route('/admin/desbloquear-horario', methods=['POST'])
def desbloquear_horario():
    if 'admin_logado' not in session:
        return jsonify({"status": "erro", "mensagem": "Não autorizado"}), 401
    dados = request.get_json()
    horario = dados.get('horario')
    horarios_bloqueados = session.get('horarios_bloqueados_admin', [])
    if horario in horarios_bloqueados:
        horarios_bloqueados.remove(horario)
        session['horarios_bloqueados_admin'] = horarios_bloqueados
    return jsonify({"status": "sucesso", "mensagem": f"Horário {horario} liberado!"})

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)