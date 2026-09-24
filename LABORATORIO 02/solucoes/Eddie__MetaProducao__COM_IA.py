def calcular_deficit_producao(registros, meta):
    """Retorna os déficits por item conforme o enunciado do kata."""
    if meta < 0:
        raise ValueError("A meta não pode ser negativa")

    totais = {}
    for item, quantidade in registros:
        nome = item.strip().lower()
        if not nome or quantidade < 0:
            raise ValueError("Item vazio ou quantidade negativa")
        totais[nome] = totais.get(nome, 0) + quantidade

    return [
        (nome, meta - total)
        for nome, total in sorted(totais.items())
        if total < meta
    ]
