def calcular_excesso(registros, franquia):
    """Retorna os excessos por passageiro conforme o enunciado do kata."""
    if franquia < 0:
        raise ValueError("franquia não pode ser negativa")

    totais = {}
    ordem = []

    for passageiro, peso in registros:
        chave = passageiro.strip().lower()

        if not chave:
            raise ValueError("nome de passageiro vazio após normalização")

        if peso < 0:
            raise ValueError("peso não pode ser negativo")

        if chave not in totais:
            totais[chave] = 0
            ordem.append(chave)

        totais[chave] += peso

    resultado = [
        (chave, totais[chave] - franquia)
        for chave in ordem
        if totais[chave] > franquia
    ]

    return sorted(resultado, key=lambda item: item[0])
