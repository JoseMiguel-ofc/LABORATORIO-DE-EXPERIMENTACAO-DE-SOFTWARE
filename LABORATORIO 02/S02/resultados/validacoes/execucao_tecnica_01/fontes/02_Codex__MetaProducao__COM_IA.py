def calcular_deficit_producao(registros, meta):
    """Agrupa a produção dos turnos e retorna os déficits por item."""
    if meta < 0:
        raise ValueError("A meta não pode ser negativa")

    totais = {}
    for item, quantidade in registros:
        nome = item.strip().lower()
        if not nome or quantidade < 0:
            raise ValueError("Item vazio ou quantidade negativa")
        totais[nome] = totais.get(nome, 0) + quantidade

    return sorted(
        (nome, meta - total)
        for nome, total in totais.items()
        if total < meta
    )
