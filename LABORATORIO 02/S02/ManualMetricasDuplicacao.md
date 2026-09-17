# Manual de Utilização - Métricas de Duplicação

## Objetivo

O script `metricas_duplicacao.py` mede duplicação de código entre as soluções dos katas do *Laboratório 02*. Essa métrica **não é exigida pelo enunciado oficial** (que cita apenas CK/PMD para Java e Radon como equivalente para Python, e Radon não calcula duplicação); foi incluída porque consta como artefato esperado na organização de tarefas da Sprint 2 do grupo.

## Como funciona

O script varre `LABORATORIO 02/solucoes/`, normaliza cada arquivo `.py` (remove linhas em branco e comentários puros, aplica `strip()`) e monta janelas deslizantes de linhas consecutivas (padrão: 4 linhas, ajustável com `--tamanho-bloco`). Um bloco é considerado duplicado quando a mesma sequência normalizada aparece mais de uma vez — dentro do mesmo arquivo ou entre arquivos diferentes. As ocorrências duplicadas são então agrupadas em regiões contínuas por arquivo.

É uma detecção simples baseada em texto (sem parsing/AST), similar em espírito ao CPD do PMD, mas sem tolerância a variações de nomes de variáveis — só captura duplicação **literal** (a menos de espaços e comentários).

## Requisitos

Nenhuma dependência externa; usa apenas a biblioteca padrão do Python.

## Uso

```bash
python metricas_duplicacao.py
```

Lê todos os `.py` de `LABORATORIO 02/solucoes/` e salva o resultado em `LABORATORIO 02/S02/resultados/metricas_duplicacao.csv`.

Outras opções:

```bash
python metricas_duplicacao.py --pasta OUTRA_PASTA --saida OUTRO_ARQUIVO.csv --tamanho-bloco 6
```

## Saída (`metricas_duplicacao.csv`)

| Coluna | Descrição |
|---|---|
| integrante, kata, tratamento | Extraídos do nome do arquivo (`integrante__kata__tratamento.py`); vazios se o nome não seguir o padrão |
| arquivo | Nome do arquivo analisado |
| linhas_comparaveis | Linhas normalizadas (sem brancos/comentários) usadas na comparação |
| linhas_duplicadas | Quantas dessas linhas fazem parte de pelo menos um bloco duplicado |
| percentual_duplicacao | `linhas_duplicadas / linhas_comparaveis`, em % |
| blocos_duplicados | Quantidade de regiões contínuas duplicadas encontradas no arquivo |
| arquivos_relacionados | Outros arquivos que compartilham algum bloco duplicado com este |

## Limitações

- Não entende sintaxe: renomear uma variável já quebra a detecção de um bloco como duplicado.
- Blocos menores que `--tamanho-bloco` linhas nunca são detectados.
- É uma métrica exploratória complementar a LOC/complexidade (`metricas_estaticas.py`), não uma medida de qualidade por si só.
