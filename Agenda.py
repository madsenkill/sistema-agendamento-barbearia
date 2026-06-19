# Passo 1. Quando coloco [] é pra criar uma lista vazia que vai guardar todos os agendamentos
agenda = []

# Passo 2. próximo passo é criar um loop (while True:) para o programa ficar rodando direto
while True:
    print("--- SISTEMA DE AGENDAMENTO DE CORTES---")
    print("1. Agendar novo cliente")
    print("2. Ver agenda")
    print("3. Sair do sistema")

    # Recebemos a escolha do usuário com (opcao = input("escolher os numeros ou opcoes que coloquei anteriormente"))
    opcao = input ("Escolha uma opção (1-3): ")

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
            
    # Se escolher o número 3: Encerra o programa
    elif opcao == "3":
        print ("Saindo do sistema... Bom Descanso")
        break # o break quebra o laço do 'while' e fecha o programa.
    
    else: 
        print ("Opção inválida! Digite 1, 2 ou 3.")

