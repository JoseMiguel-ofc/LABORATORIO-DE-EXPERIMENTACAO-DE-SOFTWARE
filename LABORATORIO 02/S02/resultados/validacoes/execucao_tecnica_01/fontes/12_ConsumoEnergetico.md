# Kata C — Consumo energético excedente

Identificador do trial: `ConsumoEnergetico`.

Implemente em Python, usando apenas a biblioteca padrão:

```python
def calcular_consumo_excedente(registros, franquia):
    ...
```

Uma administradora de condomínio recebe registros de consumo de energia (em kWh) de cada apartamento, coletados em diferentes leituras do mês. A função deve informar quantos kWh cada apartamento excedeu de sua franquia mensal.

## Contrato

- `registros` é uma lista de tuplas `(apartamento, consumo)`. `apartamento` é uma string; `consumo` e `franquia` são inteiros (não booleanos). Tipos diferentes estão fora do escopo e não precisam ser validados.
- Normalize cada apartamento com `apartamento.strip().lower()`. Não remova espaços internos nem acentos.
- Some os consumos de todos os registros do mesmo apartamento normalizado, mesmo quando não forem consecutivos.
- Considere somente apartamentos presentes nos registros, inclusive aqueles com consumo zero.
- Para cada total **maior** que `franquia`, retorne `(apartamento_normalizado, total - franquia)`.
- O retorno é uma **lista de tuplas**, ordenada pelo nome normalizado em ordem crescente, usando a ordenação padrão de strings do Python. Não inclua apartamentos que ficaram abaixo ou exatamente na franquia.
- Lista vazia retorna `[]`; franquia zero é permitida.
- Lance `ValueError` se `franquia < 0`, se qualquer consumo for negativo ou se qualquer nome ficar vazio após normalização. Valide também registros que não apareceriam na saída e a franquia quando a lista estiver vazia. A mensagem da exceção é livre.
- Não altere a lista recebida, inclusive em caso de erro. Chamadas não devem compartilhar estado.
- Não leia entrada interativa, arquivos ou rede; retorne o resultado, sem depender de impressões no terminal.

## Exemplos

```python
calcular_consumo_excedente([(" Ap101 ", 120), ("AP101", 130), ("Ap102", 90)], 200)
# [("ap101", 50)]

calcular_consumo_excedente([("B", 220), ("A", 150)], 100)
# [("a", 50), ("b", 120)]

calcular_consumo_excedente([], 0)
# []

calcular_consumo_excedente([("   ", 2)], 5)
# lança ValueError
```

## Entrega e conclusão

Copie o [modelo](modelos/ConsumoEnergetico.py) para `solucoes/INTEGRANTE__ConsumoEnergetico__TRATAMENTO.py` (caminho relativo a `LABORATORIO 02`). Preserve o nome e os parâmetros da função. Funções auxiliares são permitidas no mesmo arquivo.

O trial termina quando toda a suíte deste kata passar, dentro do limite de **35 minutos**. Execute os testes conforme o [guia da S01](../README.md). Se o tempo acabar, preserve a implementação parcial e registre a tentativa como censurada.
