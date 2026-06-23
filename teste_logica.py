horarios_ocupados = []

with open('agendamentos.txt', 'r', encoding='utf-8') as arquivo:
    for linha in arquivo:
        if "Horário:" in linha:
            partes = linha.split("Horário: ")
            horario_limpo = partes[1].strip()
            horarios_ocupados.append(horario_limpo)
print("Horários que já foram agendados hoje:", horarios_ocupados)