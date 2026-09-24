def calcular_consumo_excedente(registros, franquia):
    """Agrupa leituras e retorna o consumo excedente por apartamento."""
    if franquia < 0:
        raise ValueError("A franquia não pode ser negativa")

    totais = {}
    for apartamento, consumo in registros:
        nome = apartamento.strip().lower()
        if not nome or consumo < 0:
            raise ValueError("Apartamento vazio ou consumo negativo")
        totais[nome] = totais.get(nome, 0) + consumo

    return sorted(
        (nome, total - franquia)
        for nome, total in totais.items()
        if total > franquia
    )
