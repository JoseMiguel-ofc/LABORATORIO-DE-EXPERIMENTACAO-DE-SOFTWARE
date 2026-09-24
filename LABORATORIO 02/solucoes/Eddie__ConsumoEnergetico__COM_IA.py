def calcular_consumo_excedente(registros, franquia):
    """Retorna os excedentes por apartamento conforme o enunciado do kata."""
    if franquia < 0:
        raise ValueError("A franquia não pode ser negativa")

    totais = {}
    for apartamento, consumo in registros:
        nome = apartamento.strip().lower()
        if not nome or consumo < 0:
            raise ValueError("Apartamento vazio ou consumo negativo")
        totais[nome] = totais.get(nome, 0) + consumo

    return [
        (nome, total - franquia)
        for nome, total in sorted(totais.items())
        if total > franquia
    ]
