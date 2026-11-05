# Lab04: testes de hipótese por dentro

Comparação entre o **t de Welch** e o **Mann-Whitney** (par P1) por simulação,
com parâmetros tirados de dados reais: o tempo até o merge de PRs com e sem bot
de revisão.

**GitHub Project:** a preencher (colunas `Backlog`, `In Progress`, `In Review`,
`Done`; limite de WIP de 2 cartões em `In Progress` por pessoa).

**Dashboard publicado:** a preencher.

## Como executar

Na pasta `LABORATORIO 04` (testado com Python 3.13):

```bash
pip install -r requirements.txt && streamlit run app.py
```

O dashboard abre em `http://localhost:8501`, lê o CSV versionado e não acessa a
API do GitHub. Para ver só o resumo dos dados: `python -m src.dados`.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `app.py` | Dashboard com as 7 seções |
| `dados/prs.csv` | Amostra real coletada |
| `resultados/` | Resultados das simulações (a partir da Sprint 2) |
| `src/coleta.py` | Coleta dos dados reais (já executada) |
| `src/dados.py` | Leitura do CSV e resumo estatístico |
| `src/graficos.py` | Gráficos do dashboard |

## Dados reais

**Origem:** PRs mergeados de [grafana/grafana](https://github.com/grafana/grafana)
entre 01/05/2026 e 31/10/2026, obtidos pela API de busca do GitHub em 05/11/2026.

**Bot:** o revisor do GitHub Copilot (`copilot-pull-request-reviewer[bot]`). Ele
foi escolhido porque, nesse repositório, atua em parte dos PRs do mesmo período.
Outros candidatos foram descartados: em `novuhq/novu` e `appwrite/appwrite` o
CodeRabbit quase não aparece em 2026, e em `langflow-ai/langflow` quase todos os
PRs têm bot.

**Grupos:**

- `com_bot`: o bot enviou uma revisão no PR. População de 467 PRs.
- `sem_bot`: o bot não revisou nem comentou. População de 5.778 PRs.

Os PRs em que o bot só comentou ficam fora dos dois grupos.

**Filtros:** saem PRs de autores bot e backports, que são cópias automáticas de um
PR já revisado.

**Amostra:** 30 PRs por grupo, sorteados com semente 42, 5 por mês de merge. Assim
os dois grupos cobrem o mesmo período. A população foi listada em janelas semanais
porque a busca corta em 1.000 resultados e não ordena por data de merge. Pegar os
primeiros resultados favoreceria PRs abertos há pouco, que são os de merge rápido.

**Variável:** `horas`, o tempo entre `criado_em` e `mergeado_em`, calculado em
`src/dados.py`.

Para repetir a coleta, use `python -m src.coleta`. Leva cerca de 15 minutos sem
token. Como o sorteio depende do estado atual da API, o resultado pode mudar; a
amostra do estudo é a versionada em `dados/prs.csv`.

### Resumo da amostra

| Grupo | n | Mediana (h) | Média (h) | Desvio (h) | Assimetria | Outliers | Máximo (h) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Com bot | 30 | 31,00 | 111,80 | 187,95 | 2,96 | 3 | 886,96 |
| Sem bot | 30 | 17,04 | 101,66 | 210,63 | 3,27 | 3 | 1.016,68 |

A assimetria é forte nos dois grupos: a média é de 3,6 a 6 vezes a mediana.

### Parâmetros para a simulação

Lognormal ajustada por `parametros_lognormal()`, com μ e σ de `log(horas)`:

| Grupo | μ | σ | Mediana da lognormal (h) |
|---|---:|---:|---:|
| Com bot | 3,390 | 1,965 | 29,65 |
| Sem bot | 2,417 | 2,477 | 11,21 |

A lognormal ajustada reproduz bem a mediana, mas exagera a cauda: a média simulada
foi de 207 h no grupo com bot (real: 112 h) e de 235 h no grupo sem bot (real:
102 h). Isso pesa na escolha dos parâmetros da simulação, porque o t de Welch
compara médias.

### Limitações

- **Não há sorteio do tratamento:** quem pede a revisão do bot decide em cada PR, e
  essa escolha pode estar ligada ao tamanho ou à complexidade do PR. Uma diferença
  entre os grupos é uma associação, não um efeito causal do bot.
- **Tempo em rascunho:** o cálculo inclui o período em que o PR ficou como draft.
- **Só PRs mergeados:** PRs fechados sem merge não entram.
- **Um único repositório:** o resultado vale para o grafana/grafana.
