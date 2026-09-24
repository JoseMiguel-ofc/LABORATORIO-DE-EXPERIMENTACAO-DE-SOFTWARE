def calcular_reposicao(registros, minimo):
    if minimo < 0:
        raise ValueError("O estoque minimo nao pode ser negativo")

    totais = {}
    for produto, quantidade in registros:
        if quantidade < 0:
            raise ValueError("A quantidade nao pode ser negativa")

        produto_normalizado = produto.strip().lower()
        if not produto_normalizado:
            raise ValueError("O nome do produto nao pode ser vazio")

        totais[produto_normalizado] = totais.get(produto_normalizado, 0) + quantidade

    return [
        (produto, minimo - total)
        for produto, total in sorted(totais.items())
        if total < minimo
    ]
