# Kata D — Meta de produção

Identificador do trial: `MetaProducao`.

Implemente em Python, usando apenas a biblioteca padrão:

```python
def calcular_deficit_producao(registros, meta):
    ...
```

Uma fábrica recebe registros de quantidades produzidas de itens em diferentes turnos. A função deve informar quantas unidades faltam para cada item atingir a meta mínima de produção.

## Contrato

- `registros` é uma lista de tuplas `(item, quantidade)`. `item` é uma string; `quantidade` e `meta` são inteiros (não booleanos). Tipos diferentes estão fora do escopo e não precisam ser validados.
- Normalize cada item com `item.strip().lower()`. Não remova espaços internos nem acentos.
- Some as quantidades de todos os registros do mesmo item normalizado, mesmo quando não forem consecutivos.
- Considere somente itens presentes nos registros, inclusive aqueles com quantidade zero.
- Para cada total **menor** que `meta`, retorne `(item_normalizado, meta - total)`.
- O retorno é uma **lista de tuplas**, ordenada pelo nome normalizado em ordem crescente, usando a ordenação padrão de strings do Python. Não inclua itens que atingiram ou ultrapassaram a meta.
- Lista vazia retorna `[]`; meta zero é permitida.
- Lance `ValueError` se `meta < 0`, se qualquer quantidade for negativa ou se qualquer nome ficar vazio após normalização. Valide também registros que não apareceriam na saída e a meta quando a lista estiver vazia. A mensagem da exceção é livre.
- Não altere a lista recebida, inclusive em caso de erro. Chamadas não devem compartilhar estado.
- Não leia entrada interativa, arquivos ou rede; retorne o resultado, sem depender de impressões no terminal.

## Exemplos

```python
calcular_deficit_producao([(" Parafuso ", 40), ("PARAFUSO", 10), ("Porca", 80)], 60)
# [("parafuso", 10)]

calcular_deficit_producao([("B", 0), ("A", 20)], 40)
# [("a", 20), ("b", 40)]

calcular_deficit_producao([], 0)
# []

calcular_deficit_producao([("   ", 2)], 5)
# lança ValueError
```

## Entrega e conclusão

Copie o [modelo](modelos/MetaProducao.py) para `solucoes/INTEGRANTE__MetaProducao__TRATAMENTO.py` (caminho relativo a `LABORATORIO 02`). Preserve o nome e os parâmetros da função. Funções auxiliares são permitidas no mesmo arquivo.

O trial termina quando toda a suíte deste kata passar, dentro do limite de **35 minutos**. Execute os testes conforme o [guia da S01](../README.md). Se o tempo acabar, preserve a implementação parcial e registre a tentativa como censurada.
