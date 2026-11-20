# Lab05: latência e disponibilidade da Steam

Experimento em software real: latência e disponibilidade dos serviços públicos da
Steam, medidas de fora, com coleta automática de hora em hora pelo GitHub Actions.

**Pergunta:** a latência e a disponibilidade dos serviços públicos da Steam variam
conforme o número de usuários online e a janela de manutenção semanal?

## Estrutura

| Caminho | Conteúdo | Responsável |
|---|---|---|
| `coleta/config.json` | Endpoints, User-Agent, timeout e pausa | B |
| `coleta/coletar.py` | Uma rodada de medição por execução, gravada no CSV | B |
| `../.github/workflows/coleta.yml` | Agendamento no minuto 17 de cada hora e commit automático | B |
| `dados/brutos/coleta.csv` | Dataset (commits do `github-actions[bot]`) | bot |
| `analise/piloto.ipynb` | Notebook executável de descrição das primeiras 24–48 horas | A |
| `analise/piloto.py` | Leitura do CSV, tabelas e gráficos do piloto | A |
| `analise/poder.py` | Planejamento prospectivo de H1 por Monte Carlo | A |
| `resultados/` | Relatórios parciais reais e planejamento sintético identificado | A |
| `docs/` | Proposta (A) e ética (B) | A e B |
| `tests/` | Testes do coletor e das análises, sem rede | A e B |

## Esquema do CSV

`timestamp, endpoint, status, latencia_ms, usuarios_online, erro, jogadores_top`

| Coluna | Escala | Descrição |
|---|---|---|
| `timestamp` | intervalar | Início da requisição, UTC, ISO 8601 |
| `endpoint` | nominal | Nome do alvo em `config.json` |
| `status` | nominal | Código HTTP; vazio quando não houve resposta |
| `latencia_ms` | razão | Tempo até a resposta completa, com conexão nova (DNS + TCP + TLS) |
| `usuarios_online` | razão | Usuários online segundo a Valve, igual na rodada toda |
| `erro` | nominal | Vazio se deu certo; senão `HTTP 5xx`, `Timeout`, `ConnectionError`... |
| `jogadores_top` | razão | Soma dos jogadores atuais de CS2, Dota 2 e PUBG (aproximação pela API) |

A linha `ValveStats` é a própria consulta de usuários online, não um dos serviços
estudados; a análise deve deixá-la de fora.

## Como executar

Na pasta `LABORATORIO 05`, com Python 3.12 ou 3.13:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest -q                         # testes (sem rede)
.venv\Scripts\python coleta/coletar.py --saida teste.csv  # uma rodada real, fora do dataset
```

Não rode o coletor localmente sem `--saida`: o dataset deve ter uma única origem
de medição (o runner do GitHub).

## Coleta automática

1. O workflow `coleta-steam` roda no minuto 17 de cada hora (UTC) a partir da
   branch `main` e também pode ser disparado em *Actions → coleta-steam → Run workflow*.
2. Os endpoints usados não exigem chave. Se algum dia for preciso, a chave vai em
   *Settings → Secrets and variables → Actions* com o nome `STEAM_API_KEY`, e o
   endpoint ganha `"usa_chave": true` no `config.json`.
3. As primeiras 24 a 48 horas formam a coleta piloto.

Regras de ética: [docs/etica.md](docs/etica.md).

## Sprint 1 — Pessoa A

A [proposta](docs/proposta.md) contém os três critérios adotados para escolher a
Steam com evidências e fontes, GQM no template de Basili, H1–H3, definições das
métricas e suas escalas, plano de análise e primeira classificação nas sete
categorias da disciplina.

O piloto está em coleta. O notebook e o comando abaixo já funcionam com uma
janela parcial e informam essa condição no relatório. Para concluir a etapa
empírica, execute novamente depois das primeiras 24–48 horas. A contagem de
horas com dados e os percentuais de sucesso usam denominadores diferentes:
hora sem coleta não é falha da Steam; sucesso entre requisições observadas não
representa uptime global.

### Preparar o ambiente no macOS/Linux

Na raiz do repositório:

```bash
cd "LABORATORIO 05"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Se o terminal já estiver em `LABORATORIO 05`, comece pelo segundo comando.
No VS Code, selecione o Python de `LABORATORIO 05/.venv` como kernel do notebook.

### Gerar o piloto e executar o notebook

Na pasta `LABORATORIO 05`:

```bash
.venv/bin/python -m analise.piloto --horas 48
.venv/bin/python -m analise.executar_notebook
```

O primeiro comando gera tabelas, figura e manifesto em `resultados/piloto/`.
O segundo executa todas as células de `analise/piloto.ipynb` com o Python do
ambiente e salva os resultados no próprio notebook. Para uma janela de 24 horas,
use `--horas 24` no comando e `HORAS = 24` na célula de parâmetros do notebook.
As janelas começam na primeira medição do CSV e têm fim exclusivo.

No Windows/PowerShell, substitua `.venv/bin/python` por `.venv\Scripts\python`.
Os comandos de análise apenas leem o CSV; não disparam o coletor.

### Planejar por quantos dias coletar

```bash
.venv/bin/python -m analise.poder
```

O comando usa **10.000 repetições por configuração**, semente 42 e gera
`poder.csv`, `poder_resumo.csv` e `poder_metadados.json` em
`resultados/planejamento/`. Há progresso a cada configuração; o cálculo pode
levar alguns minutos. Os metadados registram premissas, versões e hashes.

São cenários **sintéticos prospectivos**, com durações de 7 a 56 dias,
aumentos de latência de 0%, 10%, 20% e 30%, dispersões em log de 0,5 e 1,0 e
autocorrelação AR(1) de 0 ou 0,5. Nenhuma linha do CSV da Steam ou dos PRs do
Lab04 é usada como se fosse amostra desses cenários. O reaproveitamento do
Lab04 é o procedimento de simulação em lotes, sementes comuns e IC de Wilson.

O modelo assume oito horas de pico por dia (14:00–22:00 UTC) e uma observação
por hora para **um** endpoint. O Mann–Whitney é unilateral, `pico > fora`.
O resumo planeja um aumento de **20%** e busca o primeiro dia **avaliado** com
taxa de pelo menos 80%, informando também o IC de Monte Carlo. Isso não estima
o mínimo exato nem garante poder no estudo real.

O cenário com autocorrelação é um diagnóstico: o teste independente pode
estar descalibrado. Sua taxa de rejeição não recomenda uma duração. H2
(correlação) e H3 (falhas na manutenção) exigem dimensionamento próprio; 28
dias incluem quatro terças, mas isso não garante eventos suficientes para H3.
O piloto servirá para rever as premissas antes de fechar o período da coleta.

Para uma sensibilidade conservadora à família de três hipóteses planejada na
proposta (limiar de Bonferroni, sem simular o procedimento de Holm inteiro):

```bash
.venv/bin/python -m analise.poder --alfa 0.016666666666666666 --saida resultados/planejamento_familia
```

Para conferir rapidamente a execução, salvando em outra pasta:

```bash
.venv/bin/python -m analise.poder --reps 100 --dias 7 14 --saida resultados/diagnostico
```

O resultado reduzido serve apenas para testar o comando.

As duas grades completas já foram executadas e estão em
`resultados/planejamento/` e `resultados/planejamento_familia/`. Para o efeito
planejado de 20%, o cenário independente com dispersão logarítmica 1,0
superou 80% nos primeiros prazos avaliados de **42 dias** (α = 5%) e **56 dias**
(α = 5%/3). Com 28 dias, as estimativas foram 70,21% e 52,09%, respectivamente.
Esses números justificam revisar o prazo com o piloto; não garantem poder no
dataset real nem dimensionam as outras hipóteses. A [proposta](docs/proposta.md)
registra os cenários, intervalos e a referência prospectiva de oito semanas.

### Testar a entrega

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q analise coleta
```

Os testes usam dados controlados: conferem falhas, ausências, fusos, janela do
piloto, exclusão da consulta auxiliar, reprodutibilidade, resultados de referência
do SciPy e os limites da recomendação de duração. O workflow `lab05-analise`
executa os testes e o notebook em Python 3.12 quando estas alterações estiverem
no GitHub.

Registro da execução local: [VALIDACAO_SPRINT1_PESSOA_A.txt](VALIDACAO_SPRINT1_PESSOA_A.txt).
