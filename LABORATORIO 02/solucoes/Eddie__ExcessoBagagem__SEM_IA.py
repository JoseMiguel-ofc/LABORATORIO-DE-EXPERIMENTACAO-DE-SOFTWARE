def calcular_excesso(registros, franquia):
    """Retorna, por passageiro normalizado, o peso acima da franquia."""
    if franquia < 0:
        raise ValueError("A franquia não pode ser negativa")

    totais = {}
    for passageiro, peso in registros:
        nome = passageiro.strip().lower()
        if not nome or peso < 0:
            raise ValueError("Passageiro vazio ou peso negativo")
        totais[nome] = totais.get(nome, 0) + peso

    return [
        (nome, total - franquia)
        for nome, total in sorted(totais.items())
        if total > franquia
    ]
