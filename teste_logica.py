def limpar_preco (preco_texto):
    return int(preco_texto.replace("R$ ", ""))

agendamentos_brutos = [
    ["mateus", "R$ 25"],
    ["juan", "R$ 40"],
    ["john", "R$ 40"]
]

faturamento_total = 0

for agendamento in agendamentos_brutos:
    nome_sujo = agendamento[0]
    preco_sujo = agendamento[1]
    
    nome_limpo = nome_sujo.capitalize()
    
    preco_limpo = limpar_preco(preco_sujo)
    
    faturamento_total = faturamento_total + preco_limpo
    print("Cliente:", nome_limpo, "| Valor: R$", preco_limpo)
    
print("Faturamento Total usando Funções: R$", faturamento_total)
    
    