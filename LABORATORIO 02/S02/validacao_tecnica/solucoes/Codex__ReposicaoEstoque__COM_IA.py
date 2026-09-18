def calcular_reposicao(registros, minimo):
    """Agrupa lotes e retorna os déficits dos produtos abaixo do mínimo."""
    if minimo < 0:
        raise ValueError("O mínimo não pode ser negativo")

    totais = {}
    for produto, quantidade in registros:
        nome = produto.strip().lower()
        if not nome or quantidade < 0:
            raise ValueError("Produto vazio ou quantidade negativa")
        totais[nome] = totais.get(nome, 0) + quantidade

    return sorted(
        (nome, minimo - total)
        for nome, total in totais.items()
        if total < minimo
    )
