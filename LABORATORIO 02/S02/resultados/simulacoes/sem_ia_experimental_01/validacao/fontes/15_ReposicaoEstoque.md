# Kata A — Reposição de estoque

Identificador do trial: `ReposicaoEstoque`.

Implemente em Python, usando apenas a biblioteca padrão:

```python
def calcular_reposicao(registros, minimo):
    ...
```

Uma loja recebe registros de quantidades disponíveis em diferentes lotes. A função deve informar quantas unidades faltam para cada produto atingir o estoque mínimo.

## Contrato

- `registros` é uma lista de tuplas `(produto, quantidade)`. `produto` é uma string; `quantidade` e `minimo` são inteiros (não booleanos). Tipos diferentes estão fora do escopo e não precisam ser validados.
- Normalize cada produto com `produto.strip().lower()`. Não remova espaços internos nem acentos.
- Some as quantidades de todos os registros do mesmo produto normalizado, mesmo quando não forem consecutivos.
- Considere somente produtos presentes nos registros, inclusive aqueles com quantidade zero.
- Para cada total **menor** que `minimo`, retorne `(produto_normalizado, minimo - total)`.
- O retorno é uma **lista de tuplas**, ordenada pelo nome normalizado em ordem crescente, usando a ordenação padrão de strings do Python. Não inclua produtos que atingiram ou ultrapassaram o mínimo.
- Lista vazia retorna `[]`; mínimo zero é permitido.
- Lance `ValueError` se `minimo < 0`, se qualquer quantidade for negativa ou se qualquer nome ficar vazio após normalização. Valide também registros que não apareceriam na saída e o mínimo quando a lista estiver vazia. A mensagem da exceção é livre.
- Não altere a lista recebida, inclusive em caso de erro. Chamadas não devem compartilhar estado.
- Não leia entrada interativa, arquivos ou rede; retorne o resultado, sem depender de impressões no terminal.

## Exemplos

```python
calcular_reposicao([(" Arroz ", 2), ("ARROZ", 3), ("Feijao", 8)], 7)
# [("arroz", 2)]

calcular_reposicao([("B", 0), ("A", 2)], 4)
# [("a", 2), ("b", 4)]

calcular_reposicao([], 0)
# []

calcular_reposicao([("   ", 2)], 5)
# lança ValueError
```

## Entrega e conclusão

Copie o [modelo](modelos/ReposicaoEstoque.py) para `solucoes/INTEGRANTE__ReposicaoEstoque__TRATAMENTO.py` (caminho relativo a `LABORATORIO 02`). Preserve o nome e os parâmetros da função. Funções auxiliares são permitidas no mesmo arquivo.

O trial termina quando toda a suíte deste kata passar, dentro do limite de **35 minutos**. Execute os testes conforme o [guia da S01](../README.md). Se o tempo acabar, preserve a implementação parcial e registre a tentativa como censurada.
