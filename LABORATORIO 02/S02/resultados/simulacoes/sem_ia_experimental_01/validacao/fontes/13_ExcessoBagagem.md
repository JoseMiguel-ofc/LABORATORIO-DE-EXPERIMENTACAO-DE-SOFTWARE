# Kata B — Excesso de bagagem

Identificador do trial: `ExcessoBagagem`.

Implemente em Python, usando apenas a biblioteca padrão:

```python
def calcular_excesso(registros, franquia):
    ...
```

Uma transportadora recebe registros de pesos de volumes de diferentes passageiros. A função deve informar quantos quilogramas cada passageiro excedeu de sua franquia.

## Contrato

- `registros` é uma lista de tuplas `(passageiro, peso)`. `passageiro` é uma string; `peso` e `franquia` são inteiros (não booleanos). Tipos diferentes estão fora do escopo e não precisam ser validados.
- Normalize cada passageiro com `passageiro.strip().lower()`. Não remova espaços internos nem acentos.
- Some os pesos de todos os registros do mesmo passageiro normalizado, mesmo quando não forem consecutivos.
- Considere somente passageiros presentes nos registros, inclusive aqueles com peso zero.
- Para cada total **maior** que `franquia`, retorne `(passageiro_normalizado, total - franquia)`.
- O retorno é uma **lista de tuplas**, ordenada pelo nome normalizado em ordem crescente, usando a ordenação padrão de strings do Python. Não inclua passageiros que ficaram abaixo ou exatamente na franquia.
- Lista vazia retorna `[]`; franquia zero é permitida.
- Lance `ValueError` se `franquia < 0`, se qualquer peso for negativo ou se qualquer nome ficar vazio após normalização. Valide também registros que não apareceriam na saída e a franquia quando a lista estiver vazia. A mensagem da exceção é livre.
- Não altere a lista recebida, inclusive em caso de erro. Chamadas não devem compartilhar estado.
- Não leia entrada interativa, arquivos ou rede; retorne o resultado, sem depender de impressões no terminal.

## Exemplos

```python
calcular_excesso([(" Ana ", 2), ("ANA", 3), ("Bruno", 8)], 7)
# [("bruno", 1)]

calcular_excesso([("B", 6), ("A", 8)], 4)
# [("a", 4), ("b", 2)]

calcular_excesso([], 0)
# []

calcular_excesso([("   ", 2)], 5)
# lança ValueError
```

## Entrega e conclusão

Copie o [modelo](modelos/ExcessoBagagem.py) para `solucoes/INTEGRANTE__ExcessoBagagem__TRATAMENTO.py` (caminho relativo a `LABORATORIO 02`). Preserve o nome e os parâmetros da função. Funções auxiliares são permitidas no mesmo arquivo.

O trial termina quando toda a suíte deste kata passar, dentro do limite de **35 minutos**. Execute os testes conforme o [guia da S01](../README.md). Se o tempo acabar, preserve a implementação parcial e registre a tentativa como censurada.
