def calcular_reposicao(registros, minimo):
    """Retorna os déficits por produto conforme o enunciado do kata."""
    if minimo < 0:
        raise ValueError("minimo não pode ser negativo")

    totais = {}
    ordem = []

    for produto, quantidade in registros:
        chave = produto.strip().lower()

        if not chave:
            raise ValueError("nome de produto vazio após normalização")

        if quantidade < 0:
            raise ValueError("quantidade não pode ser negativa")

        if chave not in totais:
            totais[chave] = 0
            ordem.append(chave)

        totais[chave] += quantidade

    resultado = [
        (chave, minimo - totais[chave])
        for chave in ordem
        if totais[chave] < minimo
    ]

    return sorted(resultado, key=lambda item: item[0])
