# Lab03 — Mineração de métricas DORA

Pipeline que seleciona repositórios populares do GitHub que usam GitHub Actions,
aplica os critérios de inclusão do laboratório e coleta os dados usados para
calcular as métricas DORA (deployment frequency, lead time, change failure rate
e tempo de recuperação).

## Como executar

Requer Python 3.12+ e um token do GitHub (um *fine-grained token* só com acesso
de leitura a repositórios públicos basta).

```bash
cd "LABORATORIO 03"
pip install -r requirements.txt
export GITHUB_TOKEN=ghp_...          # PowerShell: $env:GITHUB_TOKEN = "ghp_..."
python -m pipeline --config config.yaml
```

O token é lido da variável de ambiente indicada em `github.token_env` no
`config.yaml` e nunca é gravado em disco.

**Retomada** (`pipeline/api_client.py` e `pipeline/cache.py`). Toda resposta da API fica salva em `dados/cache/` (um JSON por
URL). Se a coleta parar por rate limit, queda de rede ou `Ctrl+C`, basta rodar
o mesmo comando de novo: o que já foi baixado vem do cache, sem gastar cota. Para
coletar tudo do zero, apague `dados/cache/`.

**Rate limit** (`pipeline/api_client.py`). O cliente lê `X-RateLimit-Remaining`/`X-RateLimit-Reset` e
espera sozinho quando a cota acaba; respostas 5xx são repetidas com backoff
exponencial (1 s, 2 s, 4 s, …).

## Configuração (`config.yaml`)

| Chave | Significado |
|---|---|
| `janela.inicio`, `janela.fim` | Janela de observação de 12 meses (datas inclusivas, UTC) |
| `busca.faixas_estrelas` | Faixas de estrelas consultadas separadamente, para contornar o limite de 1.000 resultados da Search API. Se o log avisar que uma faixa passou de 1.000, divida-a |
| `busca.filtro_extra` | Termos adicionais da busca (ex.: `archived:false`) |
| `filtros.releases`, `filtros.runs` | Mínimos de inclusão: 5 releases e 50 workflow runs válidos na janela |
| `amostra.tamanho` | Quantos repositórios aprovados buscar (`null` = avaliar todos os candidatos) |
| `amostra.semente` | Semente que embaralha os candidatos antes da avaliação |

## Etapas

1. **Busca** (`pipeline/busca.py`): consulta `GET /search/repositories` por faixa
   de estrelas e une os resultados sem duplicatas.
2. **Seleção** (`pipeline/funil.py`): os candidatos são embaralhados com a
   semente fixa e avaliados em ordem até a amostra atingir `amostra.tamanho`.
   Cada candidato passa pelos filtros na ordem abaixo e sai no primeiro em que
   falhar:
   1. responde na API;
   2. tem workflows do GitHub Actions (`total_count > 0`);
   3. tem ≥ 5 releases publicadas na janela (`draft = false`, sem pré-releases);
   4. tem ≥ 50 workflow runs válidos na janela (`event = push`, default branch,
      conclusão `success`, `failure`, `timed_out` ou `startup_failure`).
3. **Metadados** (`pipeline/metadados.py`): estrelas, linguagem e data de criação
   (da busca), idade em anos no fim da janela, e número de contribuidores pelo
   truque `per_page=1` + página `rel="last"` do cabeçalho `Link`.
4. **Coletas detalhadas**: os módulos `pipeline/releases.py` e `pipeline/runs.py`
   expõem `coletar(cliente, amostra, config)` e rodam só sobre a amostra
   aprovada. Enquanto não existirem, o pipeline avisa e pula a etapa.

## Saídas (`dados/`)

| Arquivo | Conteúdo |
|---|---|
| `candidatos.csv` | Todos os repositórios retornados pela busca |
| `repositorios.csv` | Amostra aprovada com metadados (colunas abaixo) |
| `descartes.csv` | Cada repositório descartado, a etapa e o motivo |
| `funil.csv` | Funil de seleção: quantos restaram em cada etapa e por quê |

Colunas de `repositorios.csv`:

| Coluna | Tipo | Unidade | Origem |
|---|---|---|---|
| `full_name` | texto | — | `full_name` da Search API (`dono/nome`) |
| `estrelas` | inteiro | estrelas | `stargazers_count` no momento da coleta |
| `linguagem` | texto | — | `language` (vazio se o GitHub não detectou) |
| `criado_em` | data ISO 8601 | UTC | `created_at` |
| `idade_anos` | decimal | anos | (`janela.fim` − `created_at`) / 365,25 |
| `contribuidores` | inteiro | pessoas | última página de `/contributors?per_page=1&anon=true`; vazio se a API recusar |
| `default_branch` | texto | — | `default_branch` |
| `url` | texto | — | `html_url` |
| `releases_janela` | inteiro | releases | releases publicadas na janela (critério do filtro 3) |
| `runs_validos_janela` | inteiro | execuções | soma de `total_count` de `/actions/runs` por conclusão válida (filtro 4) |

## Testes

```bash
pytest --cov=metricas --cov-report=term-missing
```

Os testes usam um cliente falso (`tests/conftest.py`) e não acessam a rede.

| Arquivo | O que cobre |
|---|---|
| `tests/test_dora.py` | Classificação Elite/High/Medium/Low nos limites de cada faixa e categoria geral (exemplo (4, 3, 3, 1) → High) |
| `tests/test_funil.py` | Filtros de inclusão, janela e tabela do funil |
| `tests/test_busca_metadados.py` | Faixas de estrelas, teto de 1.000, descarte sem Actions, contribuidores |
| `tests/test_main.py` | Seleção da amostra de ponta a ponta |

## Classificação DORA (`metricas/dora.py`)

Cortes fixos da RQ 07. Unidades de entrada: deploys por semana; lead time e tempo
de recuperação em **horas**; CFR como **fração** de 0 a 1. "1 por mês" equivale a
12 / (365/7) ≈ 0,23 deploys por semana. A categoria geral é a mediana dos pontos
(Elite = 4 … Low = 1) arredondada para baixo; métricas ausentes (ex.: repositório
sem episódios de falha) ficam fora da mediana.
