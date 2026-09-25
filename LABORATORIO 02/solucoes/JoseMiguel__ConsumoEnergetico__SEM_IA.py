def calcular_consumo_excedente(registros, franquia):
    """Retorna os excedentes por apartamento conforme o enunciado do kata."""
    if franquia < 0:
        raise ValueError("franquia não pode ser negativa")

    totais = {}

    for apartamento, consumo in registros:
        chave = apartamento.strip().lower()

        if chave == "":
            raise ValueError("nome de apartamento vazio após normalização")

        if consumo < 0:
            raise ValueError("consumo não pode ser negativo")

        totais[chave] = totais.get(chave, 0) + consumo

    excedentes = []

    for chave in sorted(totais):
        if totais[chave] > franquia:
            excedentes.append((chave, totais[chave] - franquia))

    return excedentes
