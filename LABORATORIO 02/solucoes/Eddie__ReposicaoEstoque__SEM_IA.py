def calcular_reposicao(registros, minimo):
    """Retorna, por produto normalizado, o déficit até o estoque mínimo."""
    if minimo < 0:
        raise ValueError("O estoque mínimo não pode ser negativo")

    totais = {}
    for produto, quantidade in registros:
        nome = produto.strip().lower()
        if not nome or quantidade < 0:
            raise ValueError("Produto vazio ou quantidade negativa")
        totais[nome] = totais.get(nome, 0) + quantidade

    return [
        (nome, minimo - total)
        for nome, total in sorted(totais.items())
        if total < minimo
    ]
