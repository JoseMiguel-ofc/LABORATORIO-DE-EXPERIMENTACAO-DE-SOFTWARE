# Ameaças à validade interna e externa

Parte do Integrante B. As ameaças de conclusão e de construto ficam com o
Integrante A (proposta, seção 9). Os números vêm de
`python scripts/validar_dados.py --saida resultados/validacao`, executado em
26/11/2026 sobre a primeira semana (19/11 19:38 a 26/11 05:08 UTC). Na data de
corte, os números devem ser atualizados com o relatório do dataset congelado.

## Validade interna

### 1. Omissão e atraso das execuções pelo agendador do GitHub (a mais grave)

**O que aconteceu.** O `cron` "17 * * * *" deveria gerar uma rodada por hora.
Na primeira semana, o GitHub disparou o workflow só a cada 6 a 12 horas, sempre
atrasado: **20 rodadas em 154 horários (13,0% de cobertura)**, 134 execuções
puladas, até 12 horas seguidas sem coleta e atraso mediano de 31,5 min em relação
ao minuto 17 (p90 51,8 min). O GitHub documenta que eventos `schedule` podem
atrasar ou ser descartados em períodos de alta carga.

**Por que ameaça o resultado.**
- A amostra fica muito menor que a planejada. A simulação de poder da proposta
  supõe cobertura de 100%; com 13%, mesmo 56 dias equivaleriam a pouco mais de 7
  dias completos, abaixo do prazo de 42 dias estimado para 80% de poder.
- As omissões não são aleatórias por construção: dependem da carga do GitHub, que
  varia com o horário. Se o GitHub pula mais em certos horários, o equilíbrio
  entre pico e fora do pico muda. Na primeira semana, a cobertura foi parecida nos
  dois grupos (13,7% no pico e 12,6% fora), mas a janela candidata de manutenção
  teve **0 de 3 horários** cobertos: H3 ficaria sem dados.
- Quando a execução atrasa, o horário real da medição deixa de ser o horário
  planejado. O CSV guarda o horário real; a classificação em pico/fora e em
  janela usa esse horário real, não o agendado.

**Mitigação.**
- **Correção do workflow (26/11/2026):** cada execução passou a ficar ativa por
  até ~5h40 (`coleta/laco.py`) e coleta no minuto 17 de cada hora, sem depender de
  um disparo por hora. O `cron` continua ligado só para iniciar a execução seguinte;
  o `concurrency` mantém no máximo uma na fila, nunca duas em paralelo. Se o
  horário atual ainda não tem rodada quando a execução começa, ela coleta na hora.
- `scripts/validar_dados.py` mede a cobertura por horário e por grupo (pico, fora,
  janela), lista os horários pulados e a maior lacuna. O workflow
  `lab05-validacao` roda a cada push e uma vez por dia, e o relatório aparece no
  resumo da execução.
- A primeira semana é tratada como **período piloto**. A análise confirmatória
  deve usar os dados a partir da correção e reportar a cobertura de cada grupo.
- Se a cobertura continuar baixa, a alternativa é disparar o workflow de fora
  (por exemplo, com um serviço gratuito de cron chamando a API `workflow_dispatch`).

### 2. Falhas do próprio runner confundidas com falhas da Steam

Um problema de rede no runner do GitHub pode parecer indisponibilidade da Steam e
inflar a taxa de falhas de H3. **Mitigação:** cada falha guarda o motivo
(`HTTP 503`, `Timeout`, `ConnectionError`), e a validação aponta as rodadas em que
**todos** os alvos falharam. Como eles estão em três domínios diferentes
(`api.steampowered.com`, `store.steampowered.com` e `www.valvesoftware.com`), uma
falha simultânea em todos indica problema do runner, e essas rodadas devem sair da
análise de disponibilidade. Na primeira semana: 0 rodadas assim e 100% de sucesso
em todos os endpoints.

### 3. Rodadas extras e duplicatas

Disparos manuais (`workflow_dispatch`) ou duas execuções no mesmo horário criariam
observações repetidas de uma hora. **Mitigação:** o laço só coleta se o horário
ainda não tem rodada; a validação conta rodadas extras por horário e reprova
linhas com timestamp e endpoint repetidos. Na primeira semana: 0 extras e 0
duplicatas.

### 4. Cache e CDN

A página da loja e o `appdetails` podem ser servidos por cache de borda, então a
latência pode ser a do cache e não a do serviço. **Mitigação:** os testes são
feitos por endpoint, e os endpoints da Web API (`GetServerInfo`,
`GetNumberOfCurrentPlayers`) são interpretados separadamente dos da loja.

### 5. Eventos externos no período

Promoções, lançamentos, ataques DDoS ou quedas de rede podem coincidir com o pico
e explicar uma diferença no lugar do número de usuários. **Mitigação:** a consulta
manual ao Downdetector (`dados/downdetector_manual.csv`, protocolo em
`docs/downdetector.md`) registra os incidentes do período, e a robustez pode
repetir os testes sem os dias afetados.

### 6. Mudanças no instrumento durante a coleta

A forma de agendar mudou em 26/11 (execução única → laço). O coletor, os endpoints
e o esquema do CSV **não** mudaram, mas o horário das rodadas passou de aleatório
para o minuto 17. **Mitigação:** a data da mudança fica registrada aqui e no
histórico do Git; a análise pode comparar os dois períodos ou usar só o segundo.

## Validade externa

| Ameaça | Limite da generalização | Mitigação |
|---|---|---|
| **Medição a partir dos EUA.** Os runners `ubuntu-latest` do GitHub ficam em data centers da Microsoft Azure nos EUA. | A latência medida não representa a de um usuário no Brasil, que passa por outra rota e pode ser atendido por outros servidores. No teste local feito do Brasil em 19/11, as latências foram de 570 a 1.000 ms, contra uma mediana de 62 a 255 ms no runner. O resultado vale para um cliente em data center nos EUA. | Declarar a limitação em todas as conclusões. Opcional: o mesmo coletor numa VM gratuita da Oracle Cloud em São Paulo, como segunda origem. |
| **Só endpoints públicos.** Não foram medidos matchmaking, servidores de jogo, download de jogos, login nem Steam Guard. | Nada se afirma sobre a experiência dentro do jogo ou sobre downloads. | Restringir as conclusões à Web API e à loja. |
| **Jogos escolhidos.** `GetNumberOfCurrentPlayers` mede CS2, Dota 2 e PUBG. | Outros jogos podem ter outro padrão de uso. | São os jogos com mais jogadores simultâneos na Steam; o total de usuários online vem da Valve e cobre a plataforma inteira. |
| **Período curto e sazonal.** Algumas semanas entre novembro e dezembro, período que costuma ter a Black Friday e a promoção de outono da Steam (fim de novembro). | O uso nesse período pode ser maior que o típico; não cobre férias nem outros meses. | Informar as datas exatas do dataset (`dados-v1.0`) e registrar os eventos do período; não extrapolar para o ano todo. |
| **Uma requisição por vez, sem carga.** Cada medição é uma requisição isolada, com conexão nova. | Não representa o cliente da Steam, que reaproveita conexões, nem o comportamento sob carga. | Tratar o resultado como um SLI externo de latência e disponibilidade, não como teste de carga. |
