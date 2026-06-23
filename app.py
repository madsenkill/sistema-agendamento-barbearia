from flask import Flask, render_template, request, jsonify


def pegar_horarios_ocupados():
    horarios_ocupados = []
    with open('agendamentos.txt', 'r', encoding='utf-8') as arquivo:
        for linha in arquivo:
            if "Horário:" in linha:
                partes = linha.split("Horário: ")
                horario_limpo = partes[1].strip()
                horarios_ocupados.append(horario_limpo)
    
    return horarios_ocupados  # Esse "return" faz a máquina "cuspir" a lista prontinha para quem chamar ela!
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
    horario_escolhido = dados.get('horario') # <-- Pegando o horário novo!

    # Adicionando o horário na gravação do arquivo de texto
    with open('agendamentos.txt', 'a', encoding='utf-8') as arquivo:
        arquivo.write(f"Cliente: {nome_cliente} | Serviço: {servico_escolhido} | Horário: {horario_escolhido}\n")

    print(f"🚀 Agendamento salvo com sucesso: {nome_cliente} às {horario_escolhido}")
    return jsonify({"status": "sucesso", "mensagem": "Agendamento gravado!"})

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)