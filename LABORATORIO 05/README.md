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
| `analise/` | Piloto e simulação de poder | A |
| `docs/` | Proposta (A) e ética (B) | A e B |
| `tests/` | Testes do coletor (sem rede) | B |

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
