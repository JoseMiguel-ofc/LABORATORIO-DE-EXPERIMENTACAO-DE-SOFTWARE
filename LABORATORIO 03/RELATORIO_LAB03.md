# Mineração de métricas DORA em repositórios open-source

## 1. Introdução

### 1.1 Contexto

Medir o desempenho de entrega de software é difícil porque "entregar bem" tem
duas faces que costumam ser vistas como opostas: entregar **rápido** e entregar
com **estabilidade**. O programa de pesquisa DORA (*DevOps Research and
Assessment*), popularizado pelo livro *Accelerate* (Forsgren, Humble & Kim, 2018)
e atualizado anualmente pelo relatório *Accelerate State of DevOps*, propôs quatro
métricas que se tornaram o padrão de mercado para capturar essas duas faces. Na
dimensão de velocidade estão a **frequência de deploy** e o **lead time for
changes** (tempo entre o commit e a chegada da mudança em produção). Na dimensão
de estabilidade estão a **taxa de falha das mudanças** (*change failure rate*,
CFR) e o **tempo de recuperação** após um deploy com falha, chamado de *mean time
to restore* até 2023 e de *failed deployment recovery time* desde então. Um dos
achados centrais do DORA é que velocidade e estabilidade não formam um
*trade-off*: as equipes de melhor desempenho vão bem nas duas dimensões ao mesmo
tempo.

Essas métricas foram construídas a partir de questionários respondidos por
profissionais, que relatam a própria percepção sobre a equipe. Este trabalho
investiga se elas podem ser **mineradas** automaticamente a partir dos dados
públicos de repositórios open-source no GitHub que usam integração e entrega
contínuas (CI/CD) com GitHub Actions. A dificuldade é que o GitHub não registra
"deploys em produção" nem "falhas em produção". Por isso, cada métrica é
calculada a partir de um **proxy**: uma release publicada é tratada como um
deploy; uma execução de workflow com falha, ou uma release seguida de outra
corretiva em poucos dias, é tratada como uma falha. Proxies podem distorcer o
fenômeno medido. Uma biblioteca que publica uma release por mês não está
colocando nada em produção, quem faz isso são os usuários dela.

Por esse motivo, o estudo tem dois objetivos. O primeiro é **descrever** o
desempenho DORA de repositórios populares que usam CI/CD e verificar quais
características dos projetos estão associadas a um desempenho melhor. O segundo
é **avaliar a confiabilidade das medidas**: comparamos os critérios automáticos
com o julgamento humano em uma amostra-ouro rotulada manualmente e medimos o
quanto a classificação de cada repositório muda quando a definição operacional
de deploy, lead time ou falha muda. A pergunta deixa de ser só "qual é o valor
da métrica?" e passa a ser também "o quanto podemos confiar nesse valor?".

A amostra é composta por repositórios com mais de 1.000 estrelas que usam GitHub
Actions e que, numa janela de 12 meses, publicaram ao menos 5 releases e tiveram
ao menos 50 execuções de workflow válidas no branch principal. Para cada
repositório calculamos as quatro métricas em mais de uma variante e classificamos
o desempenho em Elite, High, Medium ou Low segundo cortes adaptados dos relatórios
DORA. As questões de pesquisa (RQs) são:

- **RQ 01.** Qual a frequência de deploys dos repositórios populares que usam CI/CD?
- **RQ 02.** Qual o tempo entre um commit e seu respectivo deploy?
- **RQ 03.** Qual a taxa de falha das mudanças entregues por esses repositórios?
- **RQ 04.** Qual o tempo de recuperação após uma execução de CI/CD com falha?
- **RQ 05.** Repositórios com maior frequência de deploy apresentam maior ou menor taxa de falha?
- **RQ 06.** Quais características dos repositórios estão associadas a um melhor desempenho DORA?
- **RQ 07.** O quanto a classificação DORA de um repositório depende da definição operacional escolhida?

### 1.2 Hipóteses informais

As hipóteses abaixo foram escritas **antes** da coleta dos dados e registram o
que o grupo espera encontrar e por quê.

**H1 (RQ 01, frequência de deploy).** Esperamos uma mediana entre 0,25 e 0,75
release por semana, ou seja, de uma release por mês a uma a cada duas semanas,
o que coloca o repositório típico na categoria **Medium**, perto da fronteira
com High. Projetos open-source costumam agrupar mudanças em versões e publicá-las
num ritmo planejado, e não a cada mudança. Esperamos uma distribuição muito
assimétrica à direita: uma minoria de repositórios que publica releases
automaticamente (versões *nightly*, bots de release ou monorepos que lançam vários
pacotes) deve atingir Elite e puxar a média para cima, o que justifica reportar
mediana e IQR. O próprio critério de inclusão (≥ 5 releases em 12 meses)
garante um piso de cerca de 0,1 release por semana, então a categoria Low deve
aparecer menos do que apareceria na população geral de repositórios.

**H2 (RQ 02, lead time).** Esperamos lead times longos em comparação com as
faixas DORA. Na variante por release (a), a mediana deve ficar entre duas e
quatro semanas (**Medium**, com boa parte dos repositórios em Low). Na variante
por commit (b), deve ficar em torno de uma semana (fronteira entre **High** e
Medium). O motivo é que cada release acumula todos os commits desde a anterior,
e o commit mais antigo espera o ciclo de release inteiro. A variante (a) olha
apenas para esse commit mais antigo, enquanto a (b) olha para todos, e a maioria
dos commits fica mais perto da data de publicação. Esperamos ainda que o uso de
`commit.author.date` aumente as duas variantes: em fluxos com pull requests, o
commit é escrito dias antes de ser revisado e integrado, e rebases preservam a
data original.

**H3 (RQ 03, taxa de falha).** Na variante de CI (a), esperamos uma mediana
entre 10% e 25% de execuções com falha (entre **Elite** e **High**). Falhas no
branch principal são menos comuns que em pull requests, porque o código já passou
pela CI do PR antes do merge, mas *testes instáveis* (*flaky tests*), workflows
de documentação e falhas de infraestrutura mantêm a taxa acima de zero. Na
variante de entrega (b), esperamos uma mediana entre 10% e 20%, com grande
variação entre projetos. Projetos que seguem SemVer e publicam *patches* com
frequência devem ter CFR (b) bem mais alto que os demais, mesmo que nem todo
*patch* corrija uma falha recente. Esperamos correlação fraca entre as duas
variantes, porque elas medem fenômenos diferentes: uma falha de pipeline
raramente chega ao usuário, e um defeito que chega ao usuário quase nunca foi
detectado pela CI.

**H4 (RQ 04, tempo de recuperação).** Esperamos uma mediana de algumas horas,
entre 1 e 12 horas (categoria **High**). Uma falha no branch principal costuma
bloquear o trabalho de todos os mantenedores, então tende a ser corrigida no
mesmo dia, muitas vezes pelo próprio push seguinte. Esperamos, porém, uma cauda
longa: workflows secundários (documentação, *benchmarks*, *deploy* de sites) podem
permanecer quebrados por semanas sem que ninguém priorize a correção. Por isso
esperamos uma parcela não desprezível de **episódios censurados**, que ainda não
tinham sido resolvidos no fim da janela. Também esperamos que a recuperação seja
mais lenta em repositórios com menos contribuidores, porque há menos pessoas
disponíveis para corrigir a falha.

**H5 (RQ 05, velocidade e estabilidade).** Esperamos uma associação fraca entre
frequência de releases e CFR de CI (a). Releases frequentes podem refletir lotes
menores, mas também mais oportunidades de executar workflows com falhas. Para
CFR de entrega (b), esperamos uma associação positiva mais acentuada: projetos
que publicam muitos patches têm maior chance de satisfazer a heurística de
correção em sete dias. Essa associação pode decorrer da definição do proxy e,
isoladamente, não demonstra que entregar mais rápido reduza a estabilidade.

**H6 (RQ 06, características dos projetos).** Esperamos que projetos com mais
contribuidores tenham maior frequência de releases e menor lead time, por
disporem de mais capacidade de revisão e manutenção. Para idade e estrelas,
esperamos associações menos claras: maturidade pode melhorar a automação, mas
também acompanhar maior complexidade e ciclos de entrega mais longos. Não
assumimos uma relação causal entre popularidade e qualidade. As comparações
serão feitas entre quartis de estrelas, idade e contribuidores.

<!-- Hipótese da RQ 07: Pessoa C. -->
