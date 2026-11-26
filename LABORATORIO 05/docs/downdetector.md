# Consulta manual ao Downdetector

O Downdetector reúne relatos de usuários sobre problemas em serviços. Ele serve
de fonte independente da Valve para os incidentes do período da coleta: ajuda a
interpretar falhas e picos de latência e alimenta a discussão sobre a Lei de
Goodhart (página de status × percepção dos usuários) na Sprint 3.

A consulta é **manual**, sem script: os termos do Downdetector não permitem
raspagem automática.

## Protocolo

1. Abrir <https://downdetector.com/status/steam/> e
   <https://downdetector.com.br/fora-do-ar/steam/> (versão brasileira).
2. Ver o gráfico das últimas 24 horas e a lista de relatos e comentários.
   O gráfico só mostra 24 horas, então a consulta deve ser feita **ao menos a cada
   dois dias** até a data de corte. Incidentes antigos podem ser recuperados pelos
   comentários e por notícias, com a fonte anotada.
3. Registrar como incidente todo pico de relatos claramente acima da linha de
   base mostrada no gráfico. Mesmo sem incidente, anotar uma linha com
   `servico = nenhum` para registrar que a consulta foi feita naquele dia.
4. Converter os horários para UTC (Brasília = UTC−3).

## Colunas de `dados/downdetector_manual.csv`

| Coluna | Conteúdo | Exemplo |
|---|---|---|
| `data_consulta` | Dia da consulta (AAAA-MM-DD) | 2026-11-26 |
| `inicio_utc` | Início aproximado do pico de relatos, UTC | 2026-11-25T23:10Z |
| `fim_utc` | Fim aproximado, UTC | 2026-11-26T00:40Z |
| `servico` | `steam`, ou `nenhum` se não houve incidente | steam |
| `pico_relatos` | Maior número de relatos mostrado no gráfico | 1450 |
| `problema_mais_citado` | Categoria principal mostrada (login, loja, servidor...) | Login |
| `observacao` | Contexto (manutenção de terça, promoção, lançamento) | Coincide com a janela de terça |
| `fonte` | URL consultada | https://downdetector.com/status/steam/ |

Os números do Downdetector são relatos espontâneos, não medições: dependem de
quantas pessoas reclamaram e de como o site define a linha de base. Na análise,
servem para cruzar com as falhas medidas, não como variável dos testes.
