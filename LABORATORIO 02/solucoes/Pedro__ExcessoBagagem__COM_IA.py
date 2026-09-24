def calcular_excesso(registros, franquia):
    if franquia < 0:
        raise ValueError("A franquia nao pode ser negativa")

    totais = {}
    for passageiro, peso in registros:
        if peso < 0:
            raise ValueError("O peso nao pode ser negativo")

        passageiro_normalizado = passageiro.strip().lower()
        if not passageiro_normalizado:
            raise ValueError("O nome do passageiro nao pode ser vazio")

        totais[passageiro_normalizado] = totais.get(passageiro_normalizado, 0) + peso

    return [
        (passageiro, total - franquia)
        for passageiro, total in sorted(totais.items())
        if total > franquia
    ]
