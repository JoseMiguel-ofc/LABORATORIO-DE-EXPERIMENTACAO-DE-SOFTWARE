# Lab05 — Método de análise da Sprint 2

**Pessoa A — Método e Análise · 26/11/2026**

Esta etapa implementa a descrição por endpoint, período e dia da semana, o
diagnóstico de normalidade, H1–H3, os tamanhos de efeito e três gráficos.
As definições vêm da [proposta da Sprint 1](proposta.md). O recorte disponível
continua exploratório: há omissões de coleta e a dependência temporal ainda
precisa ser tratada antes da inferência final. Os limites estão nas
[ameaças de conclusão e de construto](ameacas_conclusao_construto.md).

## 1. Unidade de observação e preparação

- **Entrada:** CSV real com o esquema do coletor. O arquivo bruto é preservado.
  A normalização reaproveita `analise/piloto.py`: timestamps com fuso explícito
  convertidos para UTC, números inválidos como ausentes e classificação de
  sucesso/falha compatível com o instrumento.
- **Serviços:** somente os endpoints configurados. `ValveStats` fornece a
  covariável de uso e fica fora da estatística dos serviços; nomes desconhecidos
  são diagnosticados e excluídos.
- **Repetições:** identificadores `(timestamp, endpoint)` repetidos conservam
  a primeira linha e os conflitos são diagnosticados. Para evitar disparos
  extras como réplicas, conserva-se depois a primeira tentativa por endpoint e
  hora UTC de calendário. Não se escolhe a resposta mais rápida ou a primeira
  bem-sucedida.
- **Recorte:** início e fim opcionais devem conter fuso; o intervalo é
  semiaberto, com início inclusivo e fim exclusivo. Sem limites, usa-se o
  conteúdo disponível. Os limites usados ficam nos metadados.
- **Latência de sucesso:** valor finito, não negativo, em tentativa com HTTP
  final 200–399 e `erro` vazio. Tempos de timeout e de falha não entram na
  distribuição de latências de sucesso, mas as falhas continuam no denominador
  da disponibilidade observada quando são classificáveis.
- **Ausência:** não há preenchimento de latência, contagem ou resultado da
  tentativa para horários sem medição. Status inválido/ausente sem erro
  registrado torna a tentativa não classificável, separada do denominador.
- **Extremos:** valores extremos válidos são mantidos. A repetição sem outliers
  e a reamostragem de robustez pertencem à etapa posterior.

Não se juntam os seis endpoints numa única amostra. A contagem de usuários
repetida nas linhas da rodada não aumenta o número de observações independentes.
`jogadores_top` não substitui `usuarios_online` na análise principal.

## 2. Estratos e descrição

| Estrato | Regra fixa | Estatística reportada |
|---|---|---|
| Endpoint | Nome do serviço configurado. | Tentativas, classificáveis, não classificáveis, sucessos, falhas, valores ausentes, n de latências, média, DP, mediana, quartis, IQR e p95. |
| Pico / fora do pico | **14:00 ≤ hora UTC < 22:00** é pico; os demais horários são fora do pico. Classificação pelo instante real da medição. | Mesmas medidas, separadas por endpoint e período. |
| Dia da semana | Segunda = 0 até domingo = 6, derivados do timestamp em **UTC**. | Mesmas medidas, separadas por endpoint e dia, permitindo reconhecer grupos pequenos. |
| Janela candidata de manutenção | **Terça-feira, 15:00 ≤ hora < 18:00 em `America/Los_Angeles`**, com conversão de fuso e horário de verão. | Tabela de falhas e sucessos dentro/fora por endpoint para H3. A janela pode atravessar a meia-noite UTC. |

A latência é de **razão**, em ms; diferenças e razões têm interpretação
operacional. Endpoint, período, dia e status HTTP são categorias de
estratificação. Não se calcula média dos códigos HTTP nem média aritmética da
hora circular do dia. A disponibilidade é uma proporção derivada entre
tentativas classificáveis, sempre com numerador e denominador. DP com uma
observação e proporção com denominador zero são não estimáveis.

## 3. Diagnóstico de normalidade

Shapiro–Wilk é aplicado às latências de sucesso de cada endpoint e dos
estratos de período/dia quando há **ao menos três valores**, com tratamento
explícito de amostras constantes. Para n > 5.000, W é calculado, mas o
valor-p é omitido por sua precisão limitada, sem escolher uma subamostra.
O [SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.shapiro.html)
documenta o mínimo de observações e a limitação para amostras grandes.

O valor-p testa uma referência normal; p ≥ 0,05 não demonstra normalidade.
Esse diagnóstico não é uma regra automática para trocar os testes de H1–H3.
Ele também não verifica independência ou remove a estrutura temporal.

## 4. Justificativa dos testes e dos tamanhos de efeito

| Hipótese | Escalas e pergunta | Procedimento implementado | Magnitude e leitura |
|---|---|---|---|
| **H1:** latência maior no período candidato de pico. | Latência de razão, grupos nominais independentes sob a referência do teste; a pergunta é direcional e a distribuição pode ser assimétrica. | **Mann–Whitney U**, pico como primeiro grupo, alternativa `greater`, aproximação assintótica com correção de empates e sem correção de continuidade, conforme a simulação planejada. | **Delta de Cliff**, δ = 2U/(n_pico × n_fora) − 1. Sinal positivo indica tempos relativamente maiores no pico; empates contribuem zero. Medianas, sua diferença e sua razão acompanham o efeito. Razão com mediana de referência zero é não estimável. |
| **H2:** associação positiva entre usuários online e latência. | Contagem e latência são de razão; deseja-se associação monotônica, sem impor relação linear ou normalidade marginal. | **Spearman**, pares completos da mesma medição/endpoint, alternativa `greater`. O coeficiente e o valor-p convencional do SciPy são reportados com sua suposição de independência e a limitação da aproximação em amostras pequenas. | **ρ de Spearman**, entre −1 e 1, como medida de associação de postos. Covariável ou latência constante torna a correlação não estimável. Associação não implica causalidade. |
| **H3:** mais falhas na janela candidata de manutenção. | Duas categorias de janela e resultado binário; a tabela 2×2 pode ter poucos eventos e células zero. | **Fisher exato unilateral**, alternativa `greater`, com linhas janela/fora e colunas falha/sucesso. A escolha permanece fixa, evitando selecionar depois entre Fisher e qui-quadrado. | **Razão de chances de falha (OR)** e diferença das taxas. OR > 1 aponta maior chance de falha na janela. Células zero são mantidas; 0/0 fica indefinido. Uma OR infinita, quando matematicamente definida, deve ser lida junto das contagens e da instabilidade. |

Mann–Whitney compara distribuições/postos. Interpretá-lo como comparação de
medianas exige condições adicionais sobre as formas; a tabela de medianas,
isoladamente, não altera o objeto do teste. Ver
[documentação de Mann–Whitney](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html).

Para H2, a documentação de
[Spearman](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html)
ressalta a precisão limitada do valor-p convencional com poucos pares. Uma
permutação irrestrita das linhas também pressuporia permutabilidade; com
dependência temporal, ela não resolve o problema automaticamente. A adaptação
temporal e os intervalos por reamostragem são trabalho posterior.

Fisher evita a aproximação por frequências esperadas do qui-quadrado, mas
continua exigindo uma amostragem compatível com sua referência. O seu caráter
“exato” não corrige autocorrelação. Ver
[documentação de Fisher](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html).

### Casos sem informação suficiente

Cada resultado tem status e motivo. H1 exige pelo menos duas latências de
sucesso em cada grupo. Quando todas são iguais, δ = 0 é descritivo, mas o
valor-p assintótico sem continuidade fica ausente. H2 exige pelo menos três
pares completos e variação nas duas variáveis. H3 sem tentativas
classificáveis em um dos grupos não é estimável.
Se os dois grupos foram medidos, mas nenhuma falha foi observada, Fisher pode
devolver p = 1: isso não comprova igualdade nem disponibilidade contínua, e
uma razão 0/0 permanece ausente. Não são acrescentadas falhas artificiais.

## 5. Multiplicidade e interpretação

O nível de referência é **α = 0,05**. A família principal contém **H1, H2 e H3
de `GetServerInfo`** (três comparações). Os outros cinco endpoints formam uma
família secundária de **15 comparações** (cinco × três), identificada como
secundária. Caso a configuração de endpoints mude, a composição e o tamanho
das famílias devem ser registrados na execução.

O ajuste de **Holm** é aplicado dentro de cada família planejada. Hipóteses
não estimáveis reservam sua posição como p = 1 apenas no cálculo do ajuste;
seus valores-p exportados continuam ausentes, com motivo explícito. Isso
preserva o tamanho da família em vez de reduzi-la depois de observar quais
testes puderam ser executados. A
[documentação oficial de `p.adjust` do R](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/p.adjust.html)
descreve o tratamento conservador de comparações planejadas não observadas
para Holm.

São reportados valores-p brutos e ajustados, efeitos e tamanhos amostrais.
Os diagnósticos de normalidade são informativos e não entram nas famílias
H1–H3. O ajuste não torna válido um teste cuja referência de independência não
é defensável. Assim, mesmo um valor ajustado abaixo de 0,05 permanece uma
evidência **exploratória** nesta sprint; não é apresentado como confirmação
causal ou como conclusão definitiva sobre toda a Steam.

## 6. Gráficos e artefatos

Os gráficos mantêm painéis separados por endpoint e usam somente latências
de sucesso válidas:

1. **Latência por hora UTC:** mediana e dispersão por hora do dia, mostrando
   grupos sem dados como lacunas.
2. **Boxplot pico × fora do pico:** distribuições e quantidades dos dois grupos,
   sem criar valores zero para grupos vazios.
3. **Dispersão latência × usuários online:** pares completos, com usuários em
   milhões e latência em ms, sem juntar os endpoints como réplicas.

| Arquivo de saída | Conteúdo |
|---|---|
| `dados_analisados.csv` | Recorte normalizado e classificado, depois das exclusões documentadas. |
| `descritiva_endpoint.csv` | Estatísticas por endpoint. |
| `descritiva_periodo.csv` | Estatísticas por endpoint e pico/fora do pico. |
| `descritiva_dia_semana.csv` | Estatísticas por endpoint e dia da semana UTC. |
| `normalidade.csv` | Diagnósticos, n, estatística, valor-p quando calculável, status e motivo. |
| `hipoteses.csv` | H1–H3, efeitos, contagens, valores-p brutos/ajustados, famílias e status. |
| `metadados.json` | Fonte, período, configuração e rastreabilidade da execução. |
| `relatorio.md` | Leitura dos resultados e limitações do recorte. |
| Três figuras PNG | Latência por hora, boxplots e dispersões por endpoint. |

Na pasta `LABORATORIO 05`, a execução padrão é:

```bash
.venv/bin/python -m analise.analise
```

Os arquivos são gravados em `resultados/analise_sprint2/`. No Windows,
substituir `.venv/bin/python` por `.venv\Scripts\python`. As opções de recorte e
demais comandos de reprodução estão no [README](../README.md). Ao atualizar a
coleta ou escolher outro recorte, regenerar os artefatos; não interpretar um
relatório antigo como se tivesse usado o CSV mais recente. O congelamento do
dataset e a definição da data de corte seguem a tarefa da Pessoa B.

As fontes eletrônicas citadas foram consultadas em **26/11/2026**.
