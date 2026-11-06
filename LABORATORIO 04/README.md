# Lab04: testes de hipótese por dentro

Comparação entre o **t de Welch** e o **Mann-Whitney** (par P1) por simulação,
com parâmetros tirados de dados reais: o tempo até o merge de PRs com e sem bot
de revisão.

**GitHub Project:** a preencher (colunas `Backlog`, `In Progress`, `In Review`,
`Done`; limite de WIP de 2 cartões em `In Progress` por pessoa).

**Dashboard publicado:** a preencher.

## Como executar

Na pasta `LABORATORIO 04`, prepare um ambiente com Python 3.12 ou 3.13
(esta entrega foi validada com Python 3.12.14):

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Depois, o dashboard completo disponível nesta sprint abre com um único comando:

```bash
.venv/bin/python -m streamlit run app.py
```

O dashboard abre em `http://localhost:8501`, lê o CSV versionado e não acessa a
API do GitHub. Para ver só o resumo dos dados: `.venv/bin/python -m src.dados`.
Se usar Python 3.13, troque somente o comando de criação do ambiente por
`python3.13 -m venv .venv`.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `app.py` | Dashboard com as 7 seções |
| `dados/prs.csv` | Amostra real coletada |
| `resultados/` | Resultados das simulações (a partir da Sprint 2) |
| `src/coleta.py` | Coleta dos dados reais (já executada) |
| `src/dados.py` | Leitura do CSV e resumo estatístico |
| `src/cenario.py` | Pergunta, hipóteses, previsão e parâmetros estimados dos dados |
| `src/simulacao.py` | Gerador reproduzível de dados lognormais |
| `src/testes.py` | Welch e Mann-Whitney, com estatísticas, p-valores e interpretação |
| `src/graficos.py` | G1 e G2 do dashboard |
| `src/exemplo.py` | Execução do exemplo da Sprint 1 pelo terminal |
| `tests/` | Verificações numéricas, reprodutibilidade, gráficos e integração do dashboard |

## Sprint 1 — pessoa B

O cenário compara tempos de merge de PRs com e sem revisão do bot. A alternativa
é bicaudal, pois a pergunta admite aumento ou redução do tempo, e α = 0,05.
Welch testa médias iguais; Mann-Whitney usa postos sob a hipótese de distribuições
iguais. Interpretar Mann-Whitney como teste de medianas exige condições adicionais
sobre as formas das distribuições.

Há dois usos distintos da lognormal:

- **`ajuste_real` (G1):** μ e σ de `log(horas)` estimados separadamente em cada
  grupo, usando desvio padrão amostral (`ddof=1`). Preserva as diferenças
  descritivas observadas; não é uma geração sob H₀.
- **`base` (exemplo e G2):** reúne os logaritmos dos 60 tempos, obtendo
  μ = 2,903374 e σ = 2,270152. Os dois grupos partem da mesma distribuição,
  com sorteios independentes. `efeito=0` representa H₀; `efeito=0.30` multiplica
  os tempos do grupo com bot por 1,30, alterando média e mediana populacionais
  nessa proporção. Valores negativos maiores que -1 representam redução.

O contrato do gerador é
`gerar(n, efeito, situacao, rng, *, cenario=None)`, retornando os arrays
`com_bot` e `sem_bot` em horas. `n` é o tamanho de **cada** grupo. Um gerador
`numpy.random.default_rng(42)` reproduz os resultados; se o mesmo objeto `rng`
for reutilizado, seu estado avança para a próxima amostra. `ajuste_real` exige
efeito zero, e as situações da Q3 ficam para a Sprint 2.

**Previsão registrada antes de medir poder:** Mann-Whitney pode ter vantagem
com n = 30 e forte assimetria, mas isso será verificado por simulações repetidas.
Um único exemplo não demonstra superioridade de um teste.

O G2 usa as **distribuições de referência aproximadas sob H₀**: t com os graus
de liberdade de Welch e normal padrão para o U padronizado em Z. Exibe a
região de rejeição bilateral, os limites críticos, a estatística observada e
as duas caudas do p-valor. Mann-Whitney usa `method="asymptotic"`, correção de
empates e `use_continuity=False`, mantendo a área `2*sf(abs(z))` coerente com
o p-valor apresentado. As probabilidades incluem as caudas até infinito;
a janela desenhada é finita.

Essas curvas não são uma medição da distribuição empírica da estatística para
os tempos lognormais assimétricos. A calibração do erro tipo I e o poder serão
avaliados na Sprint 2. Não rejeitar H₀ não prova igualdade, e p não é a
probabilidade de H₀ ser verdadeira.

### Executar e testar

Para rodar somente o exemplo, sem abrir o navegador:

```bash
.venv/bin/python -m src.exemplo
.venv/bin/python -m src.exemplo --n 30 --efeito 0
```

No exemplo padrão (`n=30`, `efeito=0.30`, semente 42), os resultados esperados,
arredondados, são **Welch: t = -0,839645, p = 0,407387** e
**Mann-Whitney: U = 468, p = 0,790147**. Nenhum rejeita sua H₀ a 5% nessa
realização, embora o efeito configurado seja diferente de zero.

Para conferir a sintaxe e executar os testes automatizados:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m compileall -q src app.py
.venv/bin/python -m pytest -q
```

Os testes verificam resultados analíticos/SciPy, empates, reprodução pela
semente, amostras independentes sob H₀, efeito no grupo correto, áreas do G2 e
interação com os controles do dashboard. A integração mantém G3/G4, aplicação
aos dados reais e conclusão final como etapas futuras.

Referências das implementações: [Welch no SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html)
e [Mann-Whitney no SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html).

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
