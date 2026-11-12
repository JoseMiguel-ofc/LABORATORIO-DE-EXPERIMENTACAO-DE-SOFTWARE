# Lab04: testes de hipótese por dentro

Comparação entre o **t de Welch** e o **Mann-Whitney** (par P1) por simulação,
com parâmetros tirados de dados reais: o tempo até o merge de PRs com e sem bot
de revisão.

**GitHub Project:** [quadro do grupo](https://github.com/users/JoseMiguel-ofc/projects/1)
(colunas `Backlog`, `In Progress`, `In Review`,
`Done`; limite de WIP de 2 cartões em `In Progress` por pessoa).

**Dashboard publicado:** a preencher.

## Como executar

Na pasta `LABORATORIO 04`, prepare um ambiente com Python 3.12 ou 3.13
(esta entrega foi validada com Python 3.12.14):

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Depois, o dashboard abre com um único comando:

```bash
.venv/bin/python -m streamlit run app.py
```

O dashboard abre em `http://localhost:8501`, lê o CSV versionado e não acessa a
API do GitHub. Para ver só o resumo dos dados: `.venv/bin/python -m src.dados`.
Se usar Python 3.13, troque somente o comando de criação do ambiente por
`python3.13 -m venv .venv`.

No Windows (PowerShell), o caminho do Python do ambiente muda:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

Nos demais comandos deste README, troque `.venv/bin/python` por
`.venv\Scripts\python`. O arquivo `.gitattributes` desta pasta mantém as quebras
de linha no padrão Unix (LF) também no Windows: os manifestos conferem o hash dos
bytes dos CSVs e do código, e a conversão para CRLF do Git no Windows faria o
dashboard pedir para refazer as simulações.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `app.py` | Dashboard com as 7 seções |
| `dados/prs.csv` | Amostra real coletada |
| `resultados/` | Taxas de rejeição, curvas de amostra e metadados das execuções |
| `src/coleta.py` | Coleta dos dados reais (já executada) |
| `src/dados.py` | Leitura do CSV e resumo estatístico |
| `src/cenario.py` | Pergunta, hipóteses, previsão e parâmetros estimados dos dados |
| `src/simulacao.py` | Gerador reproduzível de dados lognormais |
| `src/testes.py` | Welch e Mann-Whitney, com estatísticas, p-valores e interpretação |
| `src/graficos.py` | G1 a G4 e curva de tamanho da amostra do dashboard |
| `src/exemplo.py` | Execução do exemplo da Sprint 1 pelo terminal |
| `src/motor.py` | Repetições em lotes, taxas de rejeição, ICs e persistência |
| `src/rodar_q1_q2.py` | Q1/Q2 e opção de executar todas as situações da Q3 |
| `src/rodar_q3.py` | Q3 isolada, resumo por situação e textos das seções 4 e 5 |
| `src/aplicacao_real.py` | Testes nos dados reais: tabela e texto da seção 6 |
| `src/efeito.py` | g de Hedges e delta de Cliff |
| `src/amostra.py` | Poder com n real e busca de n para 80% de poder |
| `src/estilo.py` | Cores fixas e tema dos gráficos |
| `src/conclusoes.py` | Interpretações calculadas a partir dos resultados |
| `src/experimentos.py` | Cálculo e leitura das simulações para α de 1%, 5% e 10% |
| `src/intervalos_efeito.py` | ICs bootstrap BCa dos efeitos reais e sua persistência |
| `src/reproduzir.py` | Reprodução das Sprints 2 e 3 e dos extras em um comando |
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
efeito zero. As situações da Q3 estão descritas na seção da Sprint 2 abaixo.

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
os tempos lognormais assimétricos. A calibração do erro tipo I e o poder são
avaliados pelas repetições da Sprint 2. Não rejeitar H₀ não prova igualdade, e p não é a
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
interação com os controles do dashboard. As verificações das Sprints 2 e 3
também cobrem o motor, tamanhos de efeito, busca amostral e resultados persistidos.

Referências das implementações: [Welch no SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html)
e [Mann-Whitney no SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html).

## Sprints 2 e 3 — pessoa B

Estão implementados o motor, Q1/Q2, persistência de resultados, G4, tamanhos de
efeito, análise de tamanho da amostra, padronização visual e textos das seções
3, 4, 5 e 7. O dashboard lê os resultados salvos e não executa Monte Carlo ao
abrir ou alterar os controles do exemplo G2.

Os cenários da Q3, o G3 e a aplicação aos dados reais também estão integrados
localmente para permitir conferir as curvas e conclusões. Isso não substitui
a revisão e a entrega das tarefas atribuídas à Pessoa A no planejamento.

### Reproduzir os resultados

Partindo da raiz do repositório, entre primeiro na pasta do laboratório:

```bash
cd "LABORATORIO 04"
.venv/bin/python -m src.reproduzir
```

Esse comando usa **10.000 repetições por configuração e semente 42**, salva os
resultados de Q1/Q2/Q3 e calcula as curvas de tamanho da amostra para
**α = 1%, 5% e 10%**. Também calcula os ICs de 95% dos tamanhos de efeito com
10.000 reamostragens bootstrap. Arquivos válidos são reutilizados; só as etapas
ausentes, desatualizadas ou com outra configuração são recalculadas. O terminal
mostra o andamento; a busca de amostras grandes pode levar alguns minutos.
Depois, execute `.venv/bin/python -m streamlit run app.py` para abrir o dashboard.
O ambiente `.venv` fica nesta subpasta, não na raiz do repositório.

Também é possível executar as etapas separadamente:

```bash
.venv/bin/python -m src.rodar_q1_q2 --todas-situacoes
.venv/bin/python -m src.amostra
```

O primeiro comando substitui a grade completa de simulação e seu manifesto.
Sem `--todas-situacoes`, atualiza somente o cenário base e preserva Q3 quando
os dados e o método são os mesmos. Para experimentar outra configuração,
use `--saida` com outro destino. Execuções com menos de 10.000 repetições são
diagnósticos e não substituem os resultados da entrega.

Os CSVs são acompanhados por metadados com parâmetros, semente, versões das
bibliotecas e hashes dos dados e do código estatístico. Se os dados ou o método
mudarem, o dashboard pede nova execução em vez de exibir resultados antigos.
Os hashes verificam integridade e compatibilidade; não validam a escolha do modelo.

### Sprint 2: perguntas Q1, Q2 e Q3

`simular(situacao, efeito, n, reps, rng, ...)` aplica os dois testes ao mesmo
conjunto de amostras independentes em cada repetição. Retorna as contagens,
taxas de rejeição (`p < α`, com 0,05 na análise principal) e intervalos de Wilson
de 95%. O processamento
em lotes limita a memória sem alterar a sequência de sorteios. A opção
`testes=("welch",)` é usada na busca amostral quando só esse teste ainda
precisa de amostras maiores.

Q1 usa efeito zero; Q2 usa **0%, 10%, 20%, 30%, 40% e 50%** de aumento no
tempo com bot. Cada ponto reinicia a semente 42, compartilhando números
aleatórios para comparar efeitos. Por isso, os pontos das curvas são
correlacionados: os ICs são individuais, não bandas simultâneas nem testes
de diferença de poder.

| Situação | Distribuição e tamanho por grupo | Efeito zero |
|---|---|---|
| Base | Lognormal pooled da amostra real, n = 30 | H₀ verdadeira |
| Assimetria forte | σ base × 1,35 em ambos os grupos, n = 30 | H₀ verdadeira |
| Outliers | Contaminação independente de 5% por fator 20 em ambos os grupos, n = 30 | H₀ verdadeira |
| Amostra pequena | Distribuição base, n = 10 | H₀ verdadeira |
| Variâncias diferentes | Mediana inicial igual; σ × 1,35 somente com bot, n = 30 | Médias e distribuições já diferentes |

No último caso, médias e distribuições diferem mesmo com medianas iguais.
Suas taxas não são erro tipo I e não entram no G3. O painel correspondente
do G4 mostra taxas de rejeição, com essa ressalva, em vez de tratá-las como
uma comparação de poder para a mesma hipótese dos demais cenários.

O cenário base já é assimétrico: a situação de assimetria forte agrava essa
característica, não cria um contraste com normalidade perfeita. A interpretação
da calibração considera se o α selecionado está dentro do IC Monte Carlo; o IC não inclui
a incerteza dos parâmetros estimados dos 60 PRs reais.

### Sprint 3: efeito, amostra e conclusão

`hedges_g(com_bot, sem_bot)` calcula a diferença de médias pelo desvio combinado,
com a correção exata J obtida da função gamma. É uma medida adimensional e
descritiva; a correção usual deriva do modelo normal e não elimina a assimetria.
`cliffs_delta(com_bot, sem_bot)` calcula P(com > sem) − P(com < sem), entre −1 e 1,
com contribuição zero dos empates. Em ambas, o sinal positivo indica maior
tempo com bot. O tamanho do efeito não demonstra causalidade nem substitui o
p-valor; sua relevância prática exige considerar horas e contexto.

A análise amostral usa o modelo base comum com duas mudanças de escala:

- **Planejada:** +30%, uma hipótese de planejamento, sem presumir que esse seja
  o efeito verdadeiro ou o mínimo relevante para a equipe.
- **Inspirada na amostra:** razão das medianas com/sem bot menos 1. O modelo
  supõe forma lognormal comum; não preserva as dispersões reais diferentes.
  É uma análise de sensibilidade, não uma validação dos p-valores por “poder observado”.

O n real é sempre incluído. A grade inicial é 10, 20, 30, 50, 100, 200, 500,
1.000 e 2.000 por grupo. Se necessário, a busca dobra n apenas para os testes
que ainda não atingiram 80%, até o limite de 64.000 por grupo. O resultado
é o **primeiro n avaliado** com taxa estimada de pelo menos 80%, não o menor
n possível. Se a busca atingir o limite, informa que a meta não foi alcançada,
sem inventar um tamanho. O resumo também informa se o limite inferior do IC
atinge 80%; cruzar a meta apenas na estimativa pontual ainda envolve incerteza.

`resultados/amostra.csv` contém as curvas; `amostra_resumo.csv`, os pontos da
meta; e `amostra_metadados.json`, a configuração e sua proveniência. As curvas
podem terminar em n diferentes: após completar a grade inicial, somente os
testes abaixo da meta continuam na extensão. Não é necessário gerar novamente
esses arquivos para abrir o dashboard.

Resultados da execução principal salva (α = 5%, semente 42, 10.000 repetições;
versões nos metadados):

| Indicador no cenário base, n = 30 | Welch | Mann–Whitney |
|---|---:|---:|
| Erro tipo I (efeito zero) | 1,46% | 4,79% |
| Poder com efeito de +50% | 2,52% | 10,29% |
| Poder com efeito de +30% | 1,82% | 7,07% |
| Poder com efeito inspirado nas medianas (+81,87%) | 4,03% | 16,58% |

| Efeito para planejamento | Primeiro n avaliado ≥80%, Welch | Primeiro n avaliado ≥80%, Mann–Whitney |
|---|---:|---:|
| +30% | 32.000 por grupo (87,20%) | 2.000 por grupo (94,62%) |
| +81,87% inspirado nas medianas | 4.000 por grupo (84,85%) | 500 por grupo (98,04%) |

Os pontos anteriores da grade ficaram abaixo de 80%; os números acima são
resoluções da busca, não mínimos exatos nem garantias para uma coleta futura.
Nos dados reais, Welch apresentou p = 0,844723 e g de Hedges = 0,050139;
Mann–Whitney apresentou p = 0,071278 e delta de Cliff = 0,271111. Nenhum teste
rejeitou sua H₀ a 5%, o que não demonstra equivalência ou ausência de efeito.

As conclusões são derivadas das taxas salvas, comparadas à previsão registrada
na Sprint 1. A escolha do teste considera o parâmetro de interesse: Welch
compara médias; Mann–Whitney compara posições relativas e não testa medianas
sem condições adicionais. A análise mantém a limitação observacional da coleta.

Referências: [correção de Hedges no NIST](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/hedgeg.htm),
[intervalos binomiais no statsmodels](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html)
e [definição e opções de Mann–Whitney no SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html).

### Extras: significância e incerteza dos efeitos

O seletor global do dashboard permite comparar **α = 1%, 5% e 10%**. Ele altera
os limites críticos e a decisão do G2, a referência de erro tipo I no G3, as
curvas de rejeição do G4, a análise de tamanho da amostra e as decisões nos
dados reais. Os p-valores e os tamanhos de efeito de uma mesma amostra não
mudam ao trocar α: muda o limiar usado para decidir se `p < α`.

**A análise principal continua com α = 5%, definido na Sprint 1.** As opções
de 1% e 10% são análises de sensibilidade; não redefinem a hipótese ou a
conclusão principal depois de observar o resultado. Nos dados reais,
Mann–Whitney tem p = 0,071278, portanto rejeita sua H₀ a 10%, mas não a 1% ou
5%. Welch não rejeita sua H₀ em nenhuma das três opções. Essas diferenças de
decisão não demonstram causalidade nem equivalência entre os grupos.

As simulações de cada α usam as mesmas sementes nas mesmas configurações.
Com os mesmos p-valores simulados, aumentar α só pode manter ou aumentar a
contagem de rejeições; isso permite mostrar a troca entre falsos positivos
e detecção de diferenças. As curvas usam resultados próprios de cada nível,
com 10.000 repetições por ponto. Mudar o seletor apenas lê os resultados
salvos: não inicia uma simulação nem uma busca amostral durante a interação.

Na seção dos dados reais, **g de Hedges e δ de Cliff têm ICs bootstrap BCa
bilaterais de 95%**, calculados com 10.000 reamostragens e semente 42. A
reamostragem é feita com reposição e separadamente em cada grupo, preservando
seus tamanhos (`paired=False`). BCa corrige viés e aceleração usando também
jackknife; a implementação usa
[`scipy.stats.bootstrap`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html).

Esses ICs descrevem a incerteza dos efeitos estimados dos PRs reais. Diferem
dos ICs de Wilson das curvas, que descrevem o erro Monte Carlo das taxas.
**Ambos permanecem em 95% ao trocar α.** Os ICs BCa não são inversões dos testes
Welch e Mann–Whitney; não se deve exigir que incluir zero coincida com a
decisão do teste, especialmente com α de 1% ou 10%. São intervalos individuais,
sem ajuste para cobertura simultânea das duas medidas.

O bootstrap trata os PRs como observações independentes dentro de cada grupo.
Ele **não preserva os estratos mensais** do sorteio original nem modela
dependência entre PRs de um mesmo autor ou período. A cobertura é aproximada,
e a amostra pequena, a assimetria e os valores extremos limitam sua precisão.
Os intervalos não removem confundimento da coleta observacional. Grupos com
menos de três observações ou reamostragens degeneradas geram erro explicativo;
não são descartados sorteios nem substituído o método silenciosamente.

#### Reproduzir e conferir os extras

Na pasta `LABORATORIO 04`, o comando geral acima já inclui os extras. Para
explicitar as três opções:

```bash
.venv/bin/python -m src.reproduzir --alfas 0.01 0.05 0.10
```

Para calcular apenas simulações e curvas de amostra, ou apenas os ICs:

```bash
.venv/bin/python -m src.experimentos --alfas 0.01 0.05 0.10
.venv/bin/python -m src.intervalos_efeito --n-resamples 10000 --confianca 0.95 --semente 42
```

`--alfas` aceita uma ou mais opções; por exemplo, `--alfas 0.01` prepara somente
o nível de 1%. `src.reproduzir` ainda verifica os ICs compartilhados. O padrão
de `--reps` é 10.000 para Monte Carlo, e o de `--n-resamples` é 10.000 para
bootstrap: são contagens de processos distintos. Em `src.experimentos` e
`src.reproduzir`, `--forcar` refaz inclusive os arquivos válidos. A CLI isolada
`src.intervalos_efeito` sempre calcula novamente os ICs; para reutilização
automática, use `src.reproduzir`.

| Local | Resultados salvos |
|---|---|
| `resultados/` | Grade e análise amostral principal, α = 5% |
| `resultados/alfa_001/` | Grade e análise amostral com α = 1% |
| `resultados/alfa_010/` | Grade e análise amostral com α = 10% |
| `resultados/efeitos_ic.csv` | Estimativas e limites BCa comuns aos três níveis |
| `resultados/efeitos_ic_metadados.json` | Método, confiança, reamostragens, semente, versões e hashes do bootstrap |

Cada diretório de simulação inclui os CSVs e seus manifestos. Antes de
reutilizá-los, os carregadores conferem dados, código estatístico, configuração,
integridade e α esperado. Os ICs também têm os grupos reais e o CSV de origem
verificados. Alterar os dados ou o método exige recalcular os arquivos
correspondentes; mudar apenas α reaproveita os ICs de 95% existentes.

Para um diagnóstico rápido, salve em outro diretório, preservando os resultados
da entrega:

```bash
.venv/bin/python -m src.reproduzir --reps 100 --n-max 2000 --n-resamples 100 --saida resultados_diagnostico
```

Os testes automatizados incluem coerência entre níveis de α, decisões e regiões
críticas, textos derivados das taxas, integridade dos arquivos e intervalos
BCa comparados diretamente ao SciPy. Para executá-los, use o mesmo comando
`.venv/bin/python -m pytest -q` mostrado na Sprint 1.

### Entrega e apresentação

Cada integrante deve ter Issue com Assignee e código commitado com referência
ao número real da Issue. A outra pessoa revisa o PR; mantenham o Project
atualizado. Publicação, links públicos e ensaio oral dependem do grupo.

Para a fala da Pessoa B, use as seções 3 a 7: explique o parâmetro de cada teste,
a área do p-valor no G2, os erros tipo I/II, a comparação de poder no G4,
o que muda ao reduzir α, a previsão versus os resultados e a recomendação com
as limitações do estudo. Reduzir α torna a rejeição mais exigente e normalmente
reduz erro tipo I e poder; os números para α = 0,01 e 0,10 vêm das execuções
próprias de cada nível, descritas nos extras acima.

## Sprints 2 e 3 — pessoa A

### Q3: situações que violam os pressupostos

`src/rodar_q3.py` roda Q1 e Q2 nas quatro situações da Q3 (assimetria forte,
outliers, amostra pequena e variâncias diferentes) com o motor da Parte B. Cada
configuração reinicia a semente 42, então as taxas são idênticas às da grade
completa; um teste automatizado confere essa igualdade. A execução atualiza só as
linhas da Q3 e preserva o cenário base salvo:

```bash
.venv/bin/python -m src.rodar_q3                 # α = 5%
.venv/bin/python -m src.rodar_q3 --alfa 0.01     # outra grade da entrega
.venv/bin/python -m src.rodar_q3 --reps 200 --saida resultados_diagnostico/q3.csv
```

`resumo_q3()` reduz a grade a uma linha por situação: calibração no efeito zero
(pelo IC de Wilson) e taxas no maior efeito. Um teste só é apontado como o que
"rejeita mais" quando os intervalos dos dois não se sobrepõem. Variâncias
diferentes fica fora do veredito sobre poder, porque ali efeito zero já não é H₀.
Os textos das seções 4 e 5 saem desse resumo e mudam com o α selecionado.

Com α = 5%, Mann–Whitney ficou entre 4,79% e 5,23% de erro tipo I em todas as
situações sob H₀, enquanto Welch ficou conservador em todas (0,78% a 1,46%). No
efeito de +50%, Mann–Whitney rejeita mais em todas as situações, e Welch não
rejeitou mais em nenhum efeito positivo da grade: a vantagem não muda de lado.

### Seção 6: os testes nos dados reais

`src/aplicacao_real.py` aplica os dois testes ao CSV real e monta a tabela da
seção 6 com estatística, p-valor, decisão, tamanho do efeito, magnitude e uma
conclusão por teste. As magnitudes seguem as faixas de Cohen para o g de Hedges
(0,2; 0,5; 0,8) e de Romano et al. (2006) para o δ de Cliff (0,147; 0,33; 0,474).
Para ver no terminal: `.venv/bin/python -m src.aplicacao_real`.

Com α = 5%, nenhum teste rejeita H₀. O efeito é desprezível pelo g de Hedges
(0,050) e pequeno pelo δ de Cliff (0,271): o PR com bot demorou mais em 64% dos
pares. Em horas, a mediana com bot é 14,0 h maior e a média, 10,1 h maior, perto
de desvios padrão de 188 h e 211 h.

### Publicação no Streamlit Community Cloud

O dashboard só lê arquivos versionados (`dados/` e `resultados/`), então não roda
simulações na nuvem. Para publicar:

1. Entre em [share.streamlit.io](https://share.streamlit.io) com a conta do GitHub.
2. Em **Create app**, escolha o repositório
   `JoseMiguel-ofc/LABORATORIO-DE-EXPERIMENTACAO-DE-SOFTWARE`, a branch `main` e o
   arquivo `LABORATORIO 04/app.py`.
3. Em **Advanced settings**, escolha Python 3.12 e confirme.
4. Copie o link gerado para `DASHBOARD` em `app.py` e para o topo deste README.

O Streamlit Cloud instala o `requirements.txt` da mesma pasta do `app.py`.

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
