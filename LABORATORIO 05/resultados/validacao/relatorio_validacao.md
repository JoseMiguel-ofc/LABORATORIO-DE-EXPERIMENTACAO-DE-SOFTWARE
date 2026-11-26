# Relatório de validação da coleta

Nenhum problema estrutural encontrado.

## Resumo

- Arquivo: `coleta.csv`
- Linhas: 140
- Primeira medição: 2026-11-19 19:38 UTC; última: 2026-11-26 05:08 UTC
- Endpoints fora do config.json: nenhum

## Valores faltantes

| verificação | linhas | % |
|---|---|---|
| endpoint vazio | 0 | 0.0% |
| latência ausente ou negativa | 0 | 0.0% |
| status vazio com erro registrado (falha sem resposta) | 0 | 0.0% |
| status vazio **sem** erro registrado | 0 | 0.0% |
| usuarios_online ausente | 0 | 0.0% |
| jogadores_top ausente | 0 | 0.0% |

Status vazio com erro preenchido é uma falha registrada (timeout, conexão recusada) e conta como indisponibilidade. `usuarios_online` e `jogadores_top` ficam vazios quando a fonte falhou naquela rodada.

## Duplicatas

- Linhas idênticas: 0
- Mesmo timestamp e endpoint: 0
- Rodadas com um endpoint medido duas vezes: 0

## Execuções do agendador

- Período avaliado: 2026-11-19 19:17 a 2026-11-26 04:17 UTC (154 horários de coleta)
- Rodadas observadas: 20; horários com pelo menos uma rodada: 20; **execuções puladas: 134**
- Maior sequência de horários seguidos sem coleta: 12 h
- Rodadas extras no mesmo horário (ex.: disparo manual): 0
- Rodadas incompletas (menos de 7 medições): 0
- Rodadas em que tudo falhou (provável problema do runner, não da Steam): 0
- Atraso do início da rodada em relação ao minuto 17: mediana 31.5 min, p90 51.8 min, máximo 56.3 min; acima de 30 min: 12

O atraso é medido contra o minuto 17 do próprio horário, porque o GitHub não informa qual disparo do `cron` originou cada execução: uma execução que começou com horas de atraso aparece como rodada daquele horário posterior, e os horários anteriores contam como pulados.

## Outliers de latência (só requisições com sucesso)

| endpoint | n | mediana_ms | Q3 + 1,5 IQR (ms) | outliers 1,5 IQR | extremos 3 IQR | máximo (ms) |
|---|---|---|---|---|---|---|
| GetNumberOfCurrentPlayers_570 | 20 | 70.1 | 230.6 | 1 | 0 | 296.2 |
| GetNumberOfCurrentPlayers_578080 | 20 | 90.4 | 211.1 | 1 | 0 | 248.9 |
| GetNumberOfCurrentPlayers_730 | 20 | 61.6 | 152.1 | 2 | 0 | 164.4 |
| GetServerInfo | 20 | 133.2 | 299.0 | 0 | 0 | 285.9 |
| PaginaLoja | 20 | 248.8 | 461.1 | 0 | 0 | 409.3 |
| ValveStats | 20 | 255.4 | 509.4 | 1 | 0 | 535.5 |
| appdetails | 20 | 133.7 | 268.6 | 0 | 0 | 252.8 |

Critério de Tukey por endpoint. Nada é removido aqui; a análise de robustez repete os testes com e sem esses valores.

## Cobertura

**20 de 154 horários com dados (13.0%).**

| grupo | horários | com coleta | cobertura |
|---|---|---|---|
| pico (14h-22h UTC) | 51 | 7 | 13.7% |
| fora do pico | 103 | 13 | 12.6% |
| janela candidata de manutenção | 3 | 0 | 0.0% |
| fora da janela | 151 | 20 | 13.2% |

| endpoint | medicoes | sucessos | sucesso entre medições | horários cobertos |
|---|---|---|---|---|
| GetNumberOfCurrentPlayers_570 | 20 | 20 | 100.0% | 13.0% |
| GetNumberOfCurrentPlayers_578080 | 20 | 20 | 100.0% | 13.0% |
| GetNumberOfCurrentPlayers_730 | 20 | 20 | 100.0% | 13.0% |
| GetServerInfo | 20 | 20 | 100.0% | 13.0% |
| PaginaLoja | 20 | 20 | 100.0% | 13.0% |
| appdetails | 20 | 20 | 100.0% | 13.0% |

Horário sem coleta não é falha da Steam: a taxa de sucesso usa como denominador só as medições feitas. `ValveStats` (fonte de usuários online) fica fora desta tabela.
