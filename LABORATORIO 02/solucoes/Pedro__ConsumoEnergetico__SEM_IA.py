def calcular_consumo_excedente(registros, franquia):
    if franquia < 0:
        raise ValueError("A franquia não pode ser negativa!")

    totais = {}
    for apartamento, consumo in registros:
        if consumo < 0:
            raise ValueError("O consumo não pode ser negativo!")

        apartamento = apartamento.strip().lower()
        if not apartamento:
            raise ValueError("O nome do apartamento não pode ser vazio!")

        totais[apartamento] = totais.get(apartamento, 0) + consumo

    resultado = []
    for apartamento in sorted(totais):
        if totais[apartamento] > franquia:
            resultado.append((apartamento, totais[apartamento] - franquia))

    return resultado
