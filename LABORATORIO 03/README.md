# Lab03 — Mineração de métricas DORA

Pipeline que seleciona repositórios populares do GitHub que usam GitHub Actions,
aplica os critérios de inclusão do laboratório e coleta os dados usados para
calcular as métricas DORA (deployment frequency, lead time, change failure rate
e tempo de recuperação).

**Estado da entrega da pessoa B — Sprint 1:** coleta de releases, tags e
commits, cálculo da frequência de releases e do lead time nas variantes (a)/(b),
e hipóteses H5/H6 no relatório. A coleta real depende de `pipeline/api_client.py`
da pessoa C, ausente nesta versão. Os testes usam exemplos controlados e não
exigem acesso à API. A janela em `config.yaml` é provisória, aguardando as datas
oficiais do professor.

## Como executar

Requer Python 3.12+ e um token do GitHub (um *fine-grained token* só com acesso
de leitura a repositórios públicos basta).

```bash
cd "LABORATORIO 03"
python3.12 -m venv .venv
source .venv/bin/activate          # PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
export GITHUB_TOKEN=ghp_...          # PowerShell: $env:GITHUB_TOKEN = "ghp_..."
python -m pipeline --config config.yaml
```

O token é lido da variável de ambiente indicada em `github.token_env` no
`config.yaml` e nunca é gravado em disco.

Antes da coleta real, integre o cliente da pessoa C e substitua `janela.inicio`,
`janela.fim` e a data de `busca.filtro_extra` pelas datas oficiais. A CLI explica
a dependência caso o cliente ainda esteja ausente.

**Infraestrutura prevista, pendente da pessoa C:** retomada por cache em
`dados/cache/`, paginação pelo cabeçalho `Link`, espera por rate limit e backoff
exponencial em respostas 5xx. Os módulos da pessoa B recebem esse cliente como
parâmetro; não criam outro cliente nem armazenam o token.

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
   aprovada. `releases.py` também chama `commits.py` e calcula frequência
   e lead time. A etapa `runs.py` ainda está pendente da pessoa C.

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
python -m compileall -q pipeline metricas tests
python -m pytest --cov=pipeline --cov=metricas --cov-report=term-missing --cov-fail-under=80
```

Os testes usam um cliente falso (`tests/conftest.py`) e não acessam a rede.
Não é necessário token para compilar ou executar os testes. O teste de integração
executa a CLI com o cliente da pessoa C simulado, passa pelo funil e confere os
quatro CSVs da pessoa B com os resultados esperados.
O registro da execução e seus limites estão em
[VALIDACAO_PESSOA_B.txt](VALIDACAO_PESSOA_B.txt).

| Arquivo | O que cobre |
|---|---|
| `tests/test_dora.py` | Classificação Elite/High/Medium/Low nos limites de cada faixa e categoria geral (exemplo (4, 3, 3, 1) → High) |
| `tests/test_funil.py` | Filtros de inclusão, janela e tabela do funil |
| `tests/test_busca_metadados.py` | Faixas de estrelas, teto de 1.000, descarte sem Actions, contribuidores |
| `tests/test_main.py` | Seleção da amostra de ponta a ponta |
| `tests/test_releases.py`, `test_commits.py` | Histórico, tags, paginação acima de 250 commits, erro 404 e CSVs |
| `tests/test_frequencia.py`, `test_lead_time.py` | Janela inclusiva; exemplo de 13 dias em (a) e 13, 5, 1 dias em (b); primeiras releases e comparações vazias |
| `tests/test_integracao_pessoa_b.py` | CLI com cliente simulado e comparação dos arquivos gerados com resultados esperados |

## Classificação DORA (`metricas/dora.py`)

Cortes fixos da RQ 07. Unidades de entrada: deploys por semana; lead time e tempo
de recuperação em **horas**; CFR como **fração** de 0 a 1. "1 por mês" equivale a
12 / (365/7) ≈ 0,23 deploys por semana. A categoria geral é a mediana dos pontos
(Elite = 4 … Low = 1) arredondada para baixo; métricas ausentes (ex.: repositório
sem episódios de falha) ficam fora da mediana.

## Entregas e decisões da pessoa B — Sprint 1

| Arquivo gerado em `dados/` | Conteúdo |
|---|---|
| `releases.csv` | Histórico, inclusive fora da janela, com flags, predecessora, estado da comparação e lead time por release |
| `tags.csv` | Tag, SHA, datas do commit apontado, inclusão na janela e estado da consulta |
| `commits.csv` | Um commit por comparação, mensagem, datas de autoria/integração e intervalos até a release |
| `metricas_entrega.csv` | Frequência de releases estáveis por semana, medianas de lead time (a)/(b) e contagens de diagnóstico e exclusões |

O lead time usa `commit.committer.date` como referência e preserva também
`commit.author.date` nos dados coletados. A variante (a) mede o commit mais antigo
de cada release; (b) agrega todos os commits das comparações. As saídas estão
em **horas**: o exemplo do PDF produz 312 h em (a), `[312, 120, 24]` h em (b),
com mediana de 120 h para (b). A primeira release da história e comparações
vazias não geram lead time; a predecessora anterior à janela é aproveitada.
Falhas 404 e outras indisponibilidades são contadas e não viram zeros.

A frequência considera releases publicadas, sem rascunhos nem pré-releases,
divididas pelas semanas da janela inclusiva, incluindo semanas sem release.
A coleta preserva as flags `draft`/`prerelease`, as tags e as datas dos commits
apontados por elas para os dados brutos da Sprint 1.

As hipóteses H5/H6 da pessoa B estão em
[RELATORIO_LAB03.md](RELATORIO_LAB03.md).
