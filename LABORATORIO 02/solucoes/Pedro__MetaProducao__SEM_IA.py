def calcular_deficit_producao(registros, meta):
    if meta < 0:
        raise ValueError("A meta não pode ser negativa!")

    totais = {}
    for item, quantidade in registros:
        if quantidade < 0:
            raise ValueError("A quantidade não pode ser negativa!")

        item = item.strip().lower()
        if not item:
            raise ValueError("O nome do item não pode ser vazio!")

        totais[item] = totais.get(item, 0) + quantidade

    resultado = []
    for item in sorted(totais):
        if totais[item] < meta:
            resultado.append((item, meta - totais[item]))

    return resultado
