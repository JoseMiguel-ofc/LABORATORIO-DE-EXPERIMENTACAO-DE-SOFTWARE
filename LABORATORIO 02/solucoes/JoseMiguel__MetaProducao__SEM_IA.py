def calcular_deficit_producao(registros, meta):
    """Retorna os déficits por item conforme o enunciado do kata."""
    if meta < 0:
        raise ValueError("meta não pode ser negativa")

    totais = {}

    for item, quantidade in registros:
        chave = item.strip().lower()

        if chave == "":
            raise ValueError("nome de item vazio após normalização")

        if quantidade < 0:
            raise ValueError("quantidade não pode ser negativa")

        totais[chave] = totais.get(chave, 0) + quantidade

    deficits = []

    for chave in sorted(totais):
        if totais[chave] < meta:
            deficits.append((chave, meta - totais[chave]))

    return deficits
