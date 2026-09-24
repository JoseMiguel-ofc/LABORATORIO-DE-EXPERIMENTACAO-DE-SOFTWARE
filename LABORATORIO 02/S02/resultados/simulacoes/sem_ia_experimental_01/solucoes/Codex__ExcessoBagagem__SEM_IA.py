def calcular_excesso(registros, franquia):
    """Agrupa volumes e retorna os excessos de peso por passageiro."""
    if franquia < 0:
        raise ValueError("A franquia não pode ser negativa")

    totais = {}
    for passageiro, peso in registros:
        nome = passageiro.strip().lower()
        if not nome or peso < 0:
            raise ValueError("Passageiro vazio ou peso negativo")
        totais[nome] = totais.get(nome, 0) + peso

    return sorted(
        (nome, total - franquia)
        for nome, total in totais.items()
        if total > franquia
    )
