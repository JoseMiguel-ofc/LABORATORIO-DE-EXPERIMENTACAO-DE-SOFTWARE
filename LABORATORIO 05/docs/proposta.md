# Lab05 — Proposta de estudo dos serviços públicos da Steam

**Entrega:** Sprint 1 · **Responsável:** Pessoa A — Método e Análise  
**Versão:** proposta inicial, 19/11/2026  
**Situação:** coleta piloto em andamento; hipóteses e critérios definidos antes da análise confirmatória.

## 1. Software e critérios de escolha

O objeto do estudo é a plataforma Steam, operada pela Valve, observada por meio
de seis endpoints públicos já configurados em
[`coleta/config.json`](../coleta/config.json). O estudo caracteriza o acesso
externo a esses endpoints; o funcionamento de todos os serviços da plataforma
fica fora do alcance de uma única origem de medição.

Foram **adotados** três critérios para esta proposta: relevância e volume de
uso, observabilidade pública e viabilidade de coleta automatizada e ética.

| Critério adotado | Evidência e fonte | Justificativa para o estudo |
|---|---|---|
| **Relevância e volume de uso** | A [página oficial Steam Charts](https://store.steampowered.com/charts/), consultada em **19/11/2026**, exibiu **38.143.246** no indicador *Peak Online*. | Uma plataforma com milhões de usuários simultâneos é um objeto relevante para caracterizar latência e disponibilidade em horários distintos. O valor é o pico exibido no painel na consulta; não é apresentado como recorde histórico nem como medição do nosso coletor. |
| **Observabilidade pública** | A Valve publica contagens agregadas em [Steam Charts](https://store.steampowered.com/charts/) e em sua [página de estatísticas](https://www.valvesoftware.com/en/about/stats). A documentação Steamworks descreve [`GetServerInfo`](https://partner.steamgames.com/doc/webapi/ISteamWebAPIUtil) e [`GetNumberOfCurrentPlayers`](https://partner.steamgames.com/doc/webapi/ISteamUserStats). Fontes consultadas em **19/11/2026**. | Há fontes oficiais para o contexto de utilização e endpoints acessíveis externamente, permitindo medir tempo de resposta, status e falhas sem acesso à infraestrutura interna. |
| **Viabilidade de coleta automatizada e ética** | O coletor existente faz uma rodada por hora, usa pausa mínima de 1 segundo entre requisições, timeout de 15 segundos e identificação acadêmica. O [protocolo de ética](etica.md) documenta as regras e os [termos da Steam Web API](https://steamcommunity.com/dev/apiterms), consultados em **19/11/2026**. | A coleta é pequena, reproduzível, baseada em dados agregados e pode ser realizada sem contas de jogadores, autenticação pessoal ou dados pessoais. Mudanças nas permissões das fontes exigem reavaliação do protocolo. |

As contagens da página são dinâmicas. Uma contagem do CSV obtida em outro
instante pode diferir do painel consultado. Serão conservados o timestamp e a
fonte de cada observação, sem substituir o dado bruto por valores do painel.

`GetNumberOfCurrentPlayers` mede jogadores ativos de um **aplicativo**. A soma
de CS2, Dota 2 e PUBG, registrada em `jogadores_top`, é uma variável auxiliar
dos três jogos monitorados e não representa todos os usuários da Steam. O
preditor principal de uso será `usuarios_online`, da fonte oficial agregada.
[Fonte: documentação oficial de ISteamUserStats](https://partner.steamgames.com/doc/webapi/ISteamUserStats).

## 2. Pergunta de pesquisa e delimitação

**A latência e a disponibilidade observadas dos serviços públicos da Steam
variam conforme o período do dia, o número de usuários online e uma janela
operacional candidata de manutenção semanal?**

O ponto de vista é o de um usuário externo que realiza uma requisição HTTP
simples. A origem será o runner do GitHub Actions usado pelo coletor; mudanças
de runner, região, rota, DNS e conexão podem influenciar os resultados. A
latência inclui acesso pela rede e o recebimento da resposta. Não será
interpretada como tempo de processamento interno da Steam.

O **endpoint primário** será `GetServerInfo`, escolhido antes dos testes por
ter uma resposta pequena e não depender da contagem de um jogo. Os outros cinco
endpoints serão analisados separadamente como resultados secundários:

| Endpoint | Papel na proposta |
|---|---|
| `GetServerInfo` | Primário: análise principal de latência, associação com uso e disponibilidade. |
| `GetNumberOfCurrentPlayers_730` | Secundário: consulta agregada do CS2. |
| `GetNumberOfCurrentPlayers_570` | Secundário: consulta agregada do Dota 2. |
| `GetNumberOfCurrentPlayers_578080` | Secundário: consulta agregada do PUBG. |
| `PaginaLoja` | Secundário: acesso à página pública do CS2 na loja. |
| `appdetails` | Secundário: acesso aos detalhes públicos do CS2. |

A linha `ValveStats` é a consulta auxiliar de usuários online. Ela será
excluída das análises de latência e disponibilidade dos seis serviços. Linhas
da mesma rodada compartilham contexto e contagem de usuários: não serão
tratadas como seis réplicas independentes do mesmo serviço.

## 3. GQM no template de Basili

O plano segue o encadeamento **Goal → Questions → Metrics**, com o objetivo
explicitado nos cinco campos do template de Basili, Caldiera e Rombach.
[Fonte: *The Goal Question Metric Approach*](https://www.cs.umd.edu/~basili/publications/technical/T89.pdf).

| Campo do objetivo | Definição |
|---|---|
| **Objeto — analisar** | Os serviços públicos da Steam representados pelos seis endpoints configurados. |
| **Propósito — com o propósito de** | Caracterizar o comportamento observado e identificar associações com período, uso e janela candidata de manutenção. |
| **Foco de qualidade — com respeito a** | Latência de resposta HTTP e disponibilidade observada das requisições. |
| **Ponto de vista — do ponto de vista de** | Um usuário externo dos serviços, representado pela origem de medição no GitHub Actions. |
| **Contexto — no contexto de** | Medição externa automatizada, horária, em ambiente real, sem controle do tráfego ou da infraestrutura da Steam. |

**Objetivo completo:** analisar os serviços públicos da Steam com o propósito
de caracterizar seu comportamento, com respeito à latência e à disponibilidade,
do ponto de vista de um usuário externo, no contexto de medição horária em
ambiente real pelo GitHub Actions.

| Questão GQM | Métricas necessárias | Resultado planejado |
|---|---|---|
| **Q1.** A latência é maior no período previamente definido como pico? | Latência das respostas bem-sucedidas, timestamp, período pico/fora do pico e endpoint. | Quantidade de observações, mediana, IQR, p95, diferença e razão das medianas; teste direcional H1 e delta de Cliff. |
| **Q2.** A latência aumenta quando há mais usuários online? | Pares válidos de `usuarios_online` e latência bem-sucedida do mesmo endpoint e rodada. | Dispersão, coeficiente de Spearman, incerteza e teste direcional H2, com verificação de dependência temporal. |
| **Q3.** Há mais falhas na janela operacional candidata de manutenção? | Janela candidata, sucesso/falha de cada tentativa, número de tentativas observadas e endpoint. | Tabela 2×2, disponibilidade por grupo, diferença de proporções, razão de chances e teste direcional H3 quando os dados permitirem. |

As métricas de Q1 a Q3 serão reportadas por endpoint. O teste primário de cada
questão usará `GetServerInfo`; comparações adicionais serão identificadas como
secundárias e consideradas no controle de multiplicidade.

## 4. Definições operacionais anteriores aos testes

### 4.1 Período candidato de pico

Será classificado como **pico** o intervalo **14:00 ≤ hora < 22:00 UTC**, todos
os dias. Os demais horários serão **fora do pico**. O limite final é exclusivo:
21:59 UTC pertence ao pico e 22:00 UTC pertence ao grupo fora do pico.

Essa janela de oito horas é uma **hipótese operacional de trabalho** para
avaliar H1. Ela não é uma afirmação de que a Valve comprovou esse intervalo
como pico, e não será escolhida novamente para maximizar um resultado
estatístico. O piloto poderá motivar uma revisão documentada antes da coleta
confirmatória; eventual busca posterior do horário de maior latência será
exploratória.

### 4.2 Janela candidata de manutenção

Será usada a categoria **terça-feira, 15:00 ≤ hora < 18:00 no fuso
`America/Los_Angeles`**. A conversão partirá do timestamp UTC e respeitará o
horário de verão da base de fusos. No período de inverno do hemisfério norte,
essa janela corresponde a 23:00 UTC de terça até 02:00 UTC de quarta.

Esse intervalo é uma **janela candidata definida pelo estudo**, não um horário
garantido ou uma anotação de manutenção efetivamente ocorrida. A orientação
oficial informa que manutenções podem ocorrer em horário comercial e que o
impacto varia entre serviços. Uma falha dentro da janela não comprova sua
causa, e manutenção pode ocorrer fora dela.
[Fonte: Steam Support — Steam Downtime and Server Maintenance](https://help.steampowered.com/en/faqs/view/7016-8AFD-19F7-F397).

### 4.3 Sucesso, falha e ausência de medição

- **Sucesso observado:** resposta final com status HTTP de 200 a 399 e campo
  `erro` vazio, seguindo o contrato atual do coletor (`Response.ok`). Os códigos
  serão também exibidos separadamente para permitir uma análise de sensibilidade
  restrita a HTTP 2xx. Resposta semanticamente inválida marcada em `erro` será
  contada como falha mesmo com HTTP 2xx.
- **Falha observada:** tentativa registrada com HTTP 4xx/5xx, timeout, erro de
  conexão ou outro erro registrado pelo coletor. Será preservado o tipo de erro.
- **Faltante:** horário sem rodada, endpoint sem linha ou valor não disponível.
  Ausência de linha não será convertida em falha do serviço nem em sucesso.
- **Latência analisável:** valor finito e não negativo de uma resposta
  bem-sucedida. Duração até timeout não será misturada à latência de sucesso;
  será descrita junto às falhas, pois a resposta completa não foi recebida.

Para um endpoint e grupo, a disponibilidade será:

\[
\widehat{A}=100\times\frac{\text{tentativas bem-sucedidas observadas}}
{\text{tentativas observadas com classificação válida}}.
\]

Se o denominador for zero, o resultado será **não estimável**. A cobertura será
reportada separadamente: tentativas observadas divididas pelas tentativas
esperadas no calendário. A disponibilidade é uma proporção das requisições
amostradas, condicionada à origem e aos instantes de medição; não é uma
estimativa direta do uptime global da Steam ou do total de minutos de
interrupção. Uma coleta horária pode não observar uma interrupção breve.

## 5. Hipóteses e análise planejada

As três hipóteses são direcionais e foram formuladas antes de observar os
resultados confirmatórios. Será adotado **α = 0,05**. Na Sprint 2 serão
reportados valores-p brutos e ajustados por **Holm** para a família H1–H3 do
endpoint primário, de forma a controlar o erro familiar em 5%. Análises dos
demais endpoints serão explicitamente secundárias e terão seu conjunto de
comparações e ajuste registrado antes da interpretação. Intervalos descritivos
de confiança de 95% não serão confundidos com testes familiares ajustados.

### H1 — Latência em pico versus fora do pico

**Previsão substantiva:** a mediana da latência de sucesso será maior no
período candidato de pico.

- **H0₁:** não há deslocamento da distribuição de latência para valores maiores
  no pico; a formulação de igualdade das distribuições é a referência do teste.
- **H1₁:** a latência no pico tende a assumir valores maiores que fora do pico.
- **Teste inicial:** Mann–Whitney U unilateral, com o grupo pico como primeiro
  argumento e alternativa `greater`, desde que a independência seja defensável.
- **Magnitude:** mediana, IQR, p95, diferença e razão de medianas, e delta de
  Cliff com sinal positivo para latência maior no pico.

Mann–Whitney não é um teste geral de igualdade de medianas: sua interpretação
é distributiva, e a leitura como deslocamento de localização requer formas
comparáveis das distribuições. A interpretação de medianas será acompanhada
dos gráficos e dessa condição. O teste e seus pressupostos estão descritos na
[documentação oficial do SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html).

### H2 — Associação entre uso e latência

- **H0₂:** o coeficiente populacional de correlação de postos de Spearman entre
  `usuarios_online` e latência de sucesso é menor ou igual a zero (`ρₛ ≤ 0`).
- **H1₂:** a associação monotônica é positiva (`ρₛ > 0`).
- **Análise inicial:** coeficiente de Spearman e teste unilateral de associação
  positiva, para pares completos do mesmo endpoint e rodada, acompanhado de
  gráfico de dispersão e série temporal.
- **Magnitude:** `ρₛ` e intervalo de confiança obtido com reamostragem adequada
  à dependência temporal verificada no piloto.

Número de usuários e latência podem compartilhar um ciclo diário, e o runner
ou a rota também podem variar. Uma associação positiva não demonstra que o
número de usuários causou a latência. Também será examinada a associação por
período e dia como análise de sensibilidade, sem selecionar apenas a versão
mais significativa.

### H3 — Falhas na janela candidata de manutenção

- **H0₃:** a probabilidade de falha na janela candidata não é maior que fora
  dela (`p_falha,janela ≤ p_falha,fora`), ou razão de chances de falha `OR ≤ 1`.
- **H1₃:** a probabilidade de falha é maior na janela candidata
  (`p_falha,janela > p_falha,fora`), com `OR > 1`.
- **Análise inicial:** tabela 2×2 com linhas janela/fora e colunas falha/sucesso;
  teste exato de Fisher unilateral para a direção `OR > 1` quando houver
  poucas falhas. Um qui-quadrado só será utilizado para associação quando
  suas condições de frequência esperada e independência forem atendidas; sua
  significância, isoladamente, não indica a direção prevista.
- **Magnitude:** disponibilidade, diferença absoluta das taxas de falha e razão
  de chances com intervalo de confiança; zeros serão mostrados e não
  substituídos por falhas artificiais. Razões não estimáveis serão identificadas.

Se não houver falhas ou houver poucas janelas observadas, serão descritos os
dados e a limitação, sem concluir equivalência, disponibilidade de 100% em todos
os momentos ou ausência de efeito de manutenção.

### Dependência temporal e decisão de análise

As medições horárias do mesmo endpoint formam uma série temporal. Será
inspecionada a autocorrelação, além dos ciclos diários e semanais, antes da
inferência. Quando houver dependência relevante, os valores-p que pressupõem
observações independentes não serão apresentados como confirmatórios sem
adequação: serão considerados blocos de dias/rodadas ou reamostragem por blocos,
com tamanho de bloco e regra de análise registrados antes do teste final.
Se a amostra não sustentar uma inferência adequada, a conclusão ficará
descritiva. A justificativa vem da estrutura de série temporal do estudo, em
que a ordem e a dependência entre observações importam.
[Fonte: NIST — Introduction to Time Series Analysis](https://www.itl.nist.gov/div898/handbook/pmc/section4/pmc41.htm).

Não rejeitar H0 será interpretado como evidência insuficiente para a direção
proposta, e não como prova de igualdade. Todos os resultados previstos serão
reportados, inclusive os contrários à previsão.

## 6. Métricas, escalas e estatísticas permitidas

| Métrica/variável | Operacionalização e unidade | Escala | Estatísticas e operações apropriadas | Restrições |
|---|---|---|---|---|
| `timestamp` | Início da tentativa em UTC, ISO 8601; conversão explícita para fusos derivados. | Intervalar. | Ordenação, diferença entre instantes, duração e contagem por intervalo. | Razão entre datas não tem significado; hora do dia é circular, logo não se usa média aritmética de 23h e 1h. |
| `endpoint` | Nome do alvo configurado. | Nominal. | Frequências, proporções, moda e estratificação. | Sem média, mediana ou ordenação numérica entre nomes. |
| `latencia_ms` | Tempo em milissegundos até receber a resposta completa em uma conexão nova, incluindo rede. | Razão. | Mediana, IQR, quantis (inclusive p95), média e desvio padrão quando úteis, diferenças e razões; gráficos e comparação de distribuições. | Análise principal só de sucessos; timeout é falha, não uma resposta de 15 segundos. O p95 exige quantidade suficiente de sucessos. |
| `status` HTTP | Código final da resposta; vazio sem resposta. | Nominal. | Contagem e proporção por código/classe, moda e tabelas de contingência. | O número identifica uma categoria: média dos códigos HTTP não mede qualidade. |
| `erro` / sucesso-falha | Categoria do erro; indicador derivado conforme a seção 4.3. | Nominal, com indicador binário derivado. | Frequências, proporções, comparação de proporções e tabelas 2×2. | Status vazio por timeout é diferente de uma linha ausente. |
| Período pico/fora do pico | Derivado do timestamp UTC pela janela 14h–22h. | Nominal dicotômica. | Contagens, proporções e estratificação/comparação das latências. | Não codificar 0/1 como intensidade do período; não ajustar os limites após ver os valores-p. |
| Janela candidata/fora | Derivada de terça-feira 15h–18h em `America/Los_Angeles`. | Nominal dicotômica. | Contagens, proporções e tabela janela × falha. | A categoria não comprova que houve manutenção real. |
| `usuarios_online` | Contagem agregada oficial consultada na rodada. | Razão, discreta. | Mediana, quantis, média, variação, razões e correlação de postos com latência. | Valor faltante não vira zero; contagem repetida nos seis endpoints não cria seis observações independentes. |
| `jogadores_top` | Soma dos jogadores ativos dos três aplicativos configurados, quando todos responderem. | Razão, discreta. | Descrição e associação exploratória separada. | Não é o total de usuários Steam e não substitui silenciosamente `usuarios_online`. |
| Disponibilidade observada | Sucessos/tentativas classificadas × 100%, por endpoint e grupo. | Medida derivada: proporção, razão adimensional, limitada a 0–100%. | Proporção, IC binomial de Wilson como descrição inicial, diferença de proporções e razão de chances de falha. | Exibir numerador e denominador; denominador zero não estimável; não equivale a uptime global. A incerteza inferencial deve considerar dependência temporal. |
| Cobertura da coleta | Tentativas observadas/tentativas esperadas no calendário × 100%. | Medida derivada: proporção. | Contagens, proporção e descrição de lacunas. | Indica integridade da medição, não disponibilidade do serviço. |

Valores extremos de latência válidos serão mantidos. Correções, exclusões de
linhas malformadas e duplicatas exatas serão registradas no relatório do piloto,
preservando o CSV original. Falhas, valores faltantes e sucessos serão
contabilizados separadamente.

## 7. Primeira versão das sete categorias de pesquisa

| Categoria | Classificação inicial | Justificativa neste estudo |
|---|---|---|
| **1. Natureza/finalidade** | **Aplicada**. | Produz informação útil para entender a experiência de acesso e planejar medições e horários de uso dos serviços. |
| **2. Objetivos** | **Descritiva e correlacional**. | Descreve distribuições e falhas e investiga associações entre período, uso, janela candidata e resultados. |
| **3. Abordagem dos dados** | **Quantitativa**. | Usa tempos, contagens, proporções, coeficientes e incerteza estatística. |
| **4. Procedimento/ambiente** | **Observacional, com dados de campo**. | Mede serviços reais em operação por observação externa, sem manipular sua carga ou infraestrutura. |
| **5. Dimensão temporal** | **Longitudinal**. | Repete as medições durante vários dias, abrangendo ciclos diários e semanais. |
| **6. Controle das variáveis** | **Sem controle das variáveis de interesse**. | Não há randomização de tráfego, intervenções de manutenção ou controle do runner e da rota; apenas o protocolo de medição é padronizado. |
| **7. Nível da evidência** | **Correlacional**. | O desenho permite associações no conjunto observado, com confundimento possível e sem identificação causal. |

O laboratório é um estudo empírico em software real, mas não é um experimento
controlado com atribuição aleatória de tratamentos. Essa distinção orientará
as conclusões finais.

## 8. Piloto de 24–48 horas e planejamento da coleta

A **coleta piloto está em andamento**. O notebook
[`analise/piloto.ipynb`](../analise/piloto.ipynb) foi preparado para avaliar as
primeiras 24–48 horas realmente disponíveis; sua execução não deve apresentar
como concluída uma janela ainda incompleta. Um conjunto com uma ou poucas
rodadas permite conferir o esquema e o fluxo, mas não responde às hipóteses.

O piloto deverá verificar:

1. Integridade do esquema, timestamps UTC, duplicatas, seis endpoints esperados
   por rodada e exclusão da linha auxiliar `ValveStats`.
2. Cobertura real, atrasos do agendamento, horas faltantes, falhas HTTP,
   timeouts, valores ausentes e validade das contagens agregadas.
3. Número de sucessos por endpoint/período, mediana, IQR, p95 quando houver
   observações suficientes e distribuição das latências.
4. Presença dos dois períodos operacionais e indícios de dependência temporal;
   24–48 horas não validam um padrão semanal de manutenção.
5. Parâmetros e cenários de sensibilidade para a simulação de poder, sem
   transformar uma diferença casual do piloto no efeito mínimo de interesse.

### Duração inicial e poder

O ponto de partida para cobertura de calendário é **28 dias consecutivos de
coleta regular**, abrangendo **pelo menos quatro terças-feiras completas**.
O dimensionamento de H1 abaixo exige comparar esse prazo com durações maiores,
com revisão das premissas após o piloto. Os cálculos estão em
[`analise/poder.py`](../analise/poder.py). Com uma rodada por hora, o calendário
ideal corresponde a 672 rodadas por endpoint: 224 no período candidato de pico
e 448 fora dele. Esses números são limites nominais de planejamento; atrasos,
lacunas e falhas reduzem as observações de latência utilizáveis.

O planejamento reaproveita do Lab04 o procedimento de Monte Carlo, semente
reproduzível e intervalos de Wilson para a taxa de rejeição. O modelo deverá
ser parametrizado para **latências**, efeito de interesse e dependência
temporal deste laboratório: os dados de pull requests do Lab04 não são dados
da Steam e não serão usados como se fossem medições do novo estudo.

O código usa marginais lognormais, com aumento multiplicativo da mediana no
pico, e uma série AR(1) estacionária na escala logarítmica para a sensibilidade
temporal. A grade padrão considera 7, 14, 21, 28, 42 e 56 dias; aumentos de
0%, 10%, 20% e 30%; desvios na escala logarítmica de 0,5 e 1,0; correlações
horárias `ρ = 0` e `ρ = 0,5`; 10.000 repetições e semente 42. São cenários
sintéticos de planejamento, não estimativas já obtidas da Steam. A cobertura
ideal é 100%, e a cobertura efetiva deverá ser examinada após o piloto.

O Mann–Whitney unilateral é aplicado aos postos, sem correção de continuidade.
Para `ρ = 0`, sua taxa de rejeição sob efeito positivo representa o poder
modelado, após conferir a calibração sob efeito zero. Para `ρ > 0`, o teste
ingênuo viola a independência: sua taxa é um **diagnóstico de sensibilidade e
de possível inflação do erro tipo I**, e não poder validado. O código não
substitui a futura definição de uma inferência adequada por blocos.

A simulação foi executada para diferentes durações, dispersões e tamanhos de
efeito, incluindo cenário nulo para verificar erro tipo I, cenário de aumento
de latência e sensibilidade à autocorrelação. A meta inicial será **poder de
80%** para H1 sob o cenário declarado. Uma estimativa de poder é condicional ao
modelo e aos parâmetros; não constitui garantia de detecção no dataset real.
O arquivo de resultados deverá preservar configuração, semente, número de
repetições e intervalo de Monte Carlo. O poder de um teste isolado a α = 0,05
será diferenciado do poder após controle da família H1–H3.

O resumo inicial toma **aumento de 20% da mediana de latência** como efeito de
interesse de planejamento, com sensibilidades de 10% e 30%. Esse limiar é uma
escolha explícita da proposta, não um efeito observado nem um requisito oficial
da Steam. Para cada cenário independente, o resumo informa o primeiro prazo
**da grade testada** com poder pontual de pelo menos 80%, incluindo seu IC de
Wilson; não é um mínimo exato de dias nem uma garantia baseada no limite
inferior do IC. H2 e H3 não são dimensionadas por essa simulação de H1.

Os resultados são gravados em `resultados/planejamento/poder.csv`,
`poder_resumo.csv` e `poder_metadados.json`. O argumento `--alfa` permite
comparar o planejamento isolado (`0.05`) com o limiar conservador
`0.05/3 = 0.016666666666666666` da primeira etapa de Holm para três testes.
O planejamento conservador foi executado em `resultados/planejamento_familia/`
para preservar as duas configurações. Cada uma tem 96 configurações e 10.000
repetições por configuração, com semente 42.

**Resultado do planejamento executado em 19/11/2026:** sob independência,
cobertura de 100% e aumento de 20% no pico, os primeiros prazos avaliados que
superam 80% de poder foram:

| Limiar de H1 | Desvio de log(latência) | Primeiro prazo avaliado | Poder estimado | IC 95% de Wilson |
|---|---:|---:|---:|---:|
| α = 0,05, teste isolado | 0,5 | 14 dias | 92,67% | 92,14%–93,16% |
| α = 0,05, teste isolado | 1,0 | 42 dias | 85,05% | 84,34%–85,74% |
| α = 0,05/3, sensibilidade conservadora | 0,5 | 14 dias | 82,52% | 81,76%–83,25% |
| α = 0,05/3, sensibilidade conservadora | 1,0 | 56 dias | 83,49% | 82,75%–84,20% |

Assim, **56 dias são a referência prospectiva para H1 no cenário independente
mais disperso avaliado**, com efeito de interesse de 20% e limiar conservador.
Esse prazo equivale a oito semanas de coleta. O prazo inicial de 28 dias é
útil para cobertura de calendário, mas, nesse mesmo cenário disperso, apresentou
70,21% de poder a α = 0,05 e 52,09% a α = 0,05/3. Se o prazo acadêmico limitar a
coleta a quatro semanas, será preciso assumir essa capacidade de detecção
menor, sem apresentar 28 dias como dimensionamento suficiente para 20%.

Esse resultado não fixa uma data de corte nem altera a coleta em andamento.
Após o piloto, a duração deve ser fechada com a dupla considerando a dispersão,
as perdas, a dependência temporal e o prazo disponível. O modelo AR(1) com
ρ = 0,5 levou a cerca de 13%–14% de rejeições sob H₀ no teste isolado nominal de
5%; por isso suas taxas não recomendam um prazo. Aumentar a coleta, por si só,
não corrige um teste que ignora autocorrelação. H2 e H3 continuam exigindo
avaliação própria.

Em quatro terças com janela candidata de três horas, há somente **12 tentativas
horárias nominais de manutenção por endpoint**, contra 660 fora. Portanto,
uma duração suficiente para H1 não garante poder para detectar falhas raras em
H3. A análise de H3 poderá exigir mais semanas ou permanecer descritiva; os
endpoints secundários não serão somados para simular janelas adicionais
independentes.

Antes da coleta confirmatória, serão registrados início/fim, efeito mínimo de
interesse, duração escolhida, parâmetros da simulação e alterações feitas após
o piloto. A parada seguirá o prazo escolhido e não a primeira obtenção de um
valor-p significativo. Como a coleta já está em andamento, as primeiras 24–48
horas ficarão identificadas como piloto e sua inclusão ou separação da análise
final será documentada antes de testar as hipóteses.

## 9. Limitações e ameaças à validade previstas

- **Construção:** latência HTTP externa representa a experiência da requisição
  medida; a janela candidata de manutenção e a contagem de usuários são
  indicadores operacionais, com limites distintos dos eventos internos reais.
- **Validade interna:** carga real, campanhas, jogos lançados, região do runner,
  rede, cache, ordem fixa dos endpoints e ciclos de tempo podem confundir as
  associações. Não haverá atribuição de causalidade à manutenção ou ao uso.
- **Validade estatística:** autocorrelação, poucos eventos de falha, tamanhos
  desiguais dos grupos, comparações múltiplas e quantis instáveis serão
  considerados ao definir os testes e interpretar os intervalos.
- **Validade externa:** as conclusões se limitam aos endpoints, período,
  frequência e origem observados; não representam todos os jogadores, regiões,
  recursos da Steam ou janelas futuras.
- **Confiabilidade:** dados brutos serão preservados e as transformações
  reprodutíveis; a captura eventual de uma falha de rede do runner não deve ser
  descrita automaticamente como interrupção global da Steam.

## 10. Situação desta entrega

Esta Sprint 1 da Pessoa A contém a proposta, o protocolo de descrição do piloto
e o código de planejamento por simulação. A coleta piloto está em andamento.
Ainda não há, nesta proposta, testes confirmatórios ou conclusões sobre
latência, disponibilidade, correlação ou manutenção da Steam.

Depois de completar o piloto, será necessário executar o notebook com os dados
reais, rever os parâmetros da simulação e registrar a duração final da coleta.
Essa dependência é identificada para não confundir código pronto com coleta
concluída. A instrumentação e o protocolo de ética da Pessoa B são referenciados
para manter o método consistente com o coletor existente.

## Referências

Todas as fontes eletrônicas abaixo foram consultadas em **19/11/2026**.

1. Valve. [Steam Charts — painel oficial de uso simultâneo](https://store.steampowered.com/charts/).
2. Valve. [Estatísticas oficiais da Steam](https://www.valvesoftware.com/en/about/stats).
3. Valve / Steamworks. [ISteamWebAPIUtil — GetServerInfo](https://partner.steamgames.com/doc/webapi/ISteamWebAPIUtil).
4. Valve / Steamworks. [ISteamUserStats — GetNumberOfCurrentPlayers](https://partner.steamgames.com/doc/webapi/ISteamUserStats).
5. Valve / Steam Support. [Steam Downtime and Server Maintenance](https://help.steampowered.com/en/faqs/view/7016-8AFD-19F7-F397).
6. Valve. [Steam Web API Terms of Use](https://steamcommunity.com/dev/apiterms).
7. Basili, V. R.; Caldiera, G.; Rombach, H. D. [The Goal Question Metric Approach](https://www.cs.umd.edu/~basili/publications/technical/T89.pdf), 1994.
8. SciPy. [Documentação de `scipy.stats.mannwhitneyu`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html).
9. NIST/SEMATECH. [Introduction to Time Series Analysis](https://www.itl.nist.gov/div898/handbook/pmc/section4/pmc41.htm).
10. Repositório do estudo. [Configuração do coletor](../coleta/config.json) e [protocolo de ética](etica.md).
