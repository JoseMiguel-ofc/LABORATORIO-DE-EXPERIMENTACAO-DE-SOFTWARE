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
| `coleta/laco.py` e `coleta/commitar.sh` | Laço de ~5h40 com uma rodada por hora e commit após cada rodada | B |
| `../.github/workflows/coleta.yml` | Agendamento no minuto 17 de cada hora e commit automático | B |
| `../.github/workflows/lab05-validacao.yml` | Validação do dataset a cada push e uma vez por dia | B |
| `dados/brutos/coleta.csv` | Dataset (commits do `github-actions[bot]`) | bot |
| `dados/downdetector_manual.csv` | Incidentes consultados manualmente no Downdetector | B |
| `scripts/validar_dados.py` | Faltantes, duplicatas, execuções puladas, outliers e cobertura | B |
| `resultados/validacao/` | Relatório de validação e cobertura por horário | B |
| `analise/piloto.ipynb` | Notebook executável de descrição das primeiras 24–48 horas | A |
| `analise/piloto.py` | Leitura do CSV, tabelas e gráficos do piloto | A |
| `analise/poder.py` | Planejamento prospectivo de H1 por Monte Carlo | A |
| `analise/analise.py` | Descrição, normalidade, H1–H3 e relatório da Sprint 2 | A |
| `analise/estatistica.py` | Mann–Whitney, Cliff, Spearman, Fisher, Shapiro e Holm | A |
| `analise/graficos_s2.py` | Figuras por hora, período e usuários | A |
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

## Sprint 2 — Pessoa A

Com o ambiente da pasta `LABORATORIO 05` já instalado:

```bash
.venv/bin/python -m analise.analise
```

No Windows/PowerShell, use `.venv\Scripts\python -m analise.analise`.
O comando lê o CSV disponível e gera o
[relatório exploratório](resultados/analise_sprint2/relatorio.md), tabelas e três
gráficos em `resultados/analise_sprint2/`. Não é necessário aguardar o fim da
coleta para executar; atualize os resultados sempre que o CSV mudar.

A entrega inclui:

- Estatística descritiva por endpoint, por período e por dia da semana UTC.
- Normalidade por Shapiro–Wilk, com indicação de grupos pequenos ou constantes.
- H1 por Mann–Whitney unilateral, com delta de Cliff e descrição das medianas.
- H2 por Spearman unilateral, com o coeficiente e a limitação do valor-p em
  amostras pequenas.
- H3 por Fisher unilateral, com tabela 2×2 e razão de chances de falha quando
  estimáveis.
- Valores-p brutos e ajustados por Holm nas famílias principal e secundária.
- Gráficos de latência por hora, boxplots pico × fora do pico e dispersão
  latência × usuários, separados por endpoint.
- Documentação das [ameaças de conclusão e construto](docs/ameacas_conclusao_construto.md)
  e da [justificativa dos testes](docs/metodo_analise_sprint2.md).

Uma observação por endpoint e hora UTC é selecionada pela primeira tentativa,
independentemente de sucesso ou falha. `ValveStats` é excluído da estatística dos
serviços. Dados faltantes não viram zero; falhas não entram na latência de
sucesso; outliers válidos são mantidos. Os metadados registram essas escolhas,
os filtros, versões e hashes do CSV, do código e dos artefatos.

Os valores-p desta etapa são **exploratórios**: a independência entre horas não
foi estabelecida, a cobertura tem lacunas e o agendamento mudou em 26/11/2026.
Holm controla a multiplicidade apenas sob referências de teste válidas e não
corrige a dependência temporal. A robustez por reamostragem e os intervalos
correspondentes são etapas posteriores.

### Escolher um recorte temporal

Para descrever uma fase separada, escolha os limites antes de interpretar os
valores-p e salve em outra pasta. Por exemplo, para incluir medições do dia
26/11 até antes do dia 27/11 em UTC:

```bash
.venv/bin/python -m analise.analise --inicio 2026-11-26T00:00:00Z --fim 2026-11-27T00:00:00Z --saida resultados/analise_sprint2_recorte
```

O início é inclusivo e o fim é exclusivo; ambos exigem fuso explícito. O exemplo
é um recorte de calendário, sem afirmar o instante exato da mudança do coletor.
Também existem `--entrada` e `--config`; consulte `--help`.

### Situação da execução de 26/11/2026

O CSV disponível tinha 189 linhas: 27 consultas auxiliares e 162 medições dos
seis serviços. A regra horária selecionou **156 medições, 26 por serviço**,
excluindo seis repetições na mesma hora. Não havia tentativa na janela candidata
de manutenção: H3 ficou **não estimável**, com motivo explícito. Ter zero falhas
nas tentativas observadas não comprova disponibilidade contínua nem ausência de
efeito de manutenção. O estado atual sempre deve ser conferido no manifesto.

Para testar a entrega:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q analise coleta scripts
```

Registro local: [VALIDACAO_SPRINT2_PESSOA_A.txt](VALIDACAO_SPRINT2_PESSOA_A.txt).

## Sprint 2 — Pessoa B

### Correção da coleta

Na primeira semana, o agendador do GitHub disparou o workflow só a cada 6 a 12
horas: 20 rodadas em 154 horários (13% de cobertura) e nenhuma na janela
candidata de manutenção. Desde 26/11/2026, cada execução de `coleta-steam` roda
`coleta/laco.py` por até ~5h40 e mede no minuto 17 de cada hora, com commit após
cada rodada. O `cron` só inicia a execução seguinte. O coletor, os endpoints e o
esquema do CSV não mudaram. Detalhes em
[docs/ameacas_interna_externa.md](docs/ameacas_interna_externa.md).

### Validar os dados

```bash
.venv/bin/python scripts/validar_dados.py                                  # relatório no terminal
.venv/bin/python scripts/validar_dados.py --saida resultados/validacao     # grava relatório e cobertura
.venv/bin/python scripts/validar_dados.py --ate 2026-12-20 --saida resultados/validacao   # até a data de corte
```

O relatório cobre valores faltantes, duplicatas, execuções puladas (horário de
coleta sem rodada), atraso em relação ao minuto 17, rodadas em que tudo falhou,
outliers de latência por endpoint (Tukey) e cobertura por grupo (pico, fora,
janela candidata de manutenção), com as definições da proposta. O script só
reprova (código 1) se o arquivo estiver quebrado. O workflow `lab05-validacao`
roda a validação a cada push e uma vez por dia e publica o relatório no resumo
da execução.

### Downdetector e data de corte

- Consulta manual ao Downdetector a cada dois dias, registrada em
  `dados/downdetector_manual.csv` conforme [docs/downdetector.md](docs/downdetector.md).
- Na data de corte: desativar o workflow `coleta-steam` em *Actions*, gerar o
  relatório com `--ate` e congelar o dataset na tag `dados-v1.0`.

### Testes

```bash
.venv/bin/python -m pytest -q tests/test_coletar.py tests/test_laco.py tests/test_validar_dados.py
```
