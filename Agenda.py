import os

# Passo 1. Quando coloco [] é pra criar uma lista vazia que vai guardar todos os agendamentos
agenda = []
# Sistema carrega o arquivo automaticamente ao iniciar
if os.path.exists("agenda_salva.txt"):
    with open("agenda_salva.txt", "r") as arquivo:
        for linha in arquivo:
            agenda.append(linha.strip())
    print ("Agenda anterior carregada com sucesso do arquivo!")

2# Passo 2. próximo passo é criar um loop (while True:) para o programa ficar rodando direto
while True:
    print("--- SISTEMA DE AGENDAMENTO DE CORTES---")
    print("1. Agendar novo cliente")
    print("2. Ver agenda")
    print("3. Cancelar agendamento")      
    print("4. Salvar Agendamento")   # <-- Nova opção
    print("5. Sair do sistema")     # O sair virou a opção 5

    # Recebemos a escolha do usuário com (opcao = input("escolher os numeros ou opcoes que coloquei anteriormente"))
    opcao = input ("Escolha uma opção (1-5): ")

    # se escolher 1: Vamos agendar
    if opcao == "1":
        cliente = input ("Digite o nome do cliente: ")
        horario = input ("Digite o horário (ex: 14:00): ")

        # criamos um texto organizando o agendamento
        agendamento_confirmado = f"Horário: {horario} - Cliente: {cliente}"
        
        # agora vamos guardar esse texto dentro da nossa lista (.append)
        agenda.append(agendamento_confirmado)
        print (f" Sucesso! Cliente {cliente} agendado para amanhã às {horario}!")

        # se escolher 2: Vamos mostrar a agenda
    elif opcao == "2":
        print ("\n--- CLIENTES AGENDADOS ---")
        if len(agenda) == 0:
            print("Nenhum cliente agendado para amanhã ainda. ")
            
        else:
            #Esse (for) vai passar por cada agendamento da lista e mostrar na tela
            for item in agenda:
                print(item)
        
        # se escolher a opção 3 vamos cancelar o agendamento
    elif opcao == "3":
        print("\n--- CANCELAR AGENDAMENTO ---")
        if len(agenda) == 0:
            print("A agenda está vazia, não a nada para cancelar.")
        else:
            # Perguntamos o nome do cliente que quer cancelar
            nome_cancelar = input("Digite o nome do cliente para cancelar: ")
            # Agora temos que criar uma variável para controlar se achamos o cliente ou não
            achou = False

            # Passamos pela lista procurando o nome do cliente agendado
            for item in agenda:
                if nome_cancelar in item:
                    agenda.remove(item)  # <-- aqui o python arranca o cliente da lista!
                    print(f" Agendamento de {nome_cancelar} foi cancelado com sucesso!")
                    achou = True
                    break  # para o "for" assim que acha e remove o cliente
            if achou == False:
                print (f"Cliente '{nome_cancelar}' não foi encontrado na agenda.")
        
        # se escolher a opção 4 salva os agendamentos
    elif opcao =="4":
        print("\n--- SALVANDO AGENDAMENTOS ---")
        if len(agenda) == 0:
            print("Não há agendamentos para salvar.")
        else:
            # O python vai criar ou abrir um arquivo chamado 'agenda_salva.txt'
            with open("agenda_salva.txt", "w") as arquivo:
                for item in agenda:
                    # Escreve cada cliente no arquivo e pula uma linda '\n'
                    arquivo.write(item +"\n")
            print ("Agenda salva com sucesso no arquivo 'agenda_salva.txt")
    
        # Se escolher o número 5: Encerra o programa
    elif opcao == "5":
        print ("Saindo do sistema... Bom Descanso")
        break # o break quebra o laço do 'while' e fecha o programa.
    
    else: 
        print ("Opção inválida! Digite de 1 a 5.")

