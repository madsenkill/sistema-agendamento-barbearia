from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Rota 1: Entrega a página visual para o cliente
@app.route('/')
def home():
    return render_template('index.html')

# Rota 2: A caixinha de correio que recebe os dados do agendamento para salvar
@app.route('/salvar-agendamento', methods=['POST'])
def salvar_agendamento():
    # 1. Pega os dados enviados pelo JavaScript
    dados = request.json
    nome_cliente = dados.get('nome')
    servico_escolhido = dados.get('servico')

    # 2. Abre (ou cria) um arquivo de texto para salvar o agendamento
    # O modo 'a' significa 'append' (adicionar no final do arquivo sem apagar o que já existe)
    with open('agendamentos.txt', 'a', encoding='utf-8') as arquivo:
        arquivo.write(f"Cliente: {nome_cliente} | Serviço: {servico_escolhido}\n")

    print(f"🚀 Agendamento salvo com sucesso: {nome_cliente}") # Mostra no terminal do VS Code

    # 3. Responde para o JavaScript dizendo que deu tudo certo!
    return jsonify({"status": "sucesso", "mensagem": "Agendamento gravado!"})

if __name__ == '__main__':
    app.run(debug=True)