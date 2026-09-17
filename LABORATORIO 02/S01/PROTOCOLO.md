# Protocolo — Assistentes de IA versus codificação manual

## Objetivo e estado da preparação

Investigar o efeito de usar um assistente de IA sobre o tempo e a correção na implementação de quatro katas em Python. Este documento define o desenho proposto **antes da coleta**; não apresenta resultados nem afirma equivalência empírica de dificuldade. A realização do piloto e a alocação dos participantes permanecem pendentes.

O fator experimental é o tratamento (`COM_IA` ou `SEM_IA`). Cada integrante executa **quatro trials, um por kata**, sendo dois com o tratamento `COM_IA` e dois com `SEM_IA` — metade dos katas em cada tratamento, conforme exige o enunciado do laboratório —, sem repetir o mesmo problema. O participante é a unidade de comparação pareada; os casos da suíte não são participantes nem repetições independentes do experimento.

## Hipóteses

| Questão | Hipótese nula | Hipótese alternativa | Medida |
|---|---|---|---|
| H1 — Tempo (primária) | A distribuição do tempo até aprovação é igual entre tratamentos | Com IA, o tempo até aprovação tende a ser menor | Segundos desde a liberação do enunciado até aprovação completa, com censura à direita em 2.100 s |
| H2 — Correção (secundária) | A probabilidade de concluir dentro do limite é igual entre tratamentos | Com IA, a probabilidade de concluir dentro do limite é maior | Fração de trials com 26/26 testes dentro de 35 minutos |
| H3 — Estrutura do código (exploratória) | A complexidade ciclomática máxima tem a mesma distribuição entre tratamentos | A distribuição difere entre tratamentos, sem direção prevista | `complexidade_maxima` do coletor Radon; LOC/SLOC como descritores auxiliares |

As direções de H1/H2 são expectativas a confrontar com dados, não benefícios presumidos. A proporção de casos aprovados ao final é uma medida descritiva auxiliar; uma suíte incompleta por timeout/erro de carga precisa ser identificada separadamente.

Apresente tempos individuais, conclusão, censuras e diferenças por integrante, kata e período. Não trate o limite de 35 minutos como tempo de conclusão, não descarte censurados silenciosamente e não compare apenas médias de quem terminou como se representassem toda a amostra. Diferenças pareadas entre trials concluídos podem ser descritas, identificando o subconjunto e o viés de seleção. Se houver censura, a análise inferencial de tempo deverá considerá-la e respeitar o pareamento; com poucos integrantes, priorize descrição e explicite a incerteza, sem declarar efeito causal ou significância com base apenas em médias.

Compare métricas estáticas de soluções sintaticamente válidas e apresente separadamente completas e parciais. Menor LOC ou complexidade não demonstra, por si só, maior qualidade. H3 é exploratória e pode sofrer seleção por conclusão. Qualquer teste estatístico formal, tratamento de multiplicidade e critério de exclusão adicional deve ser definido antes de consultar resultados por tratamento.

## Escolha dos katas

- **ReposicaoEstoque:** agrupar lotes por produto normalizado e informar déficits em relação a um mínimo.
- **ExcessoBagagem:** agrupar volumes por passageiro normalizado e informar excessos em relação a uma franquia.
- **ConsumoEnergetico:** agrupar leituras por apartamento normalizado e informar excessos em relação a uma franquia mensal.
- **MetaProducao:** agrupar produção por item normalizado e informar déficits em relação a uma meta mínima.

O enunciado do laboratório exige um número par de katas (4 ou 6), para dividir exatamente a metade dos trials entre os tratamentos `COM_IA` e `SEM_IA`; por isso o conjunto tem quatro katas, o mínimo permitido.

Os quatro enunciados foram preparados para este laboratório com regras explícitas, funções puras e saídas verificáveis. Dispensam rede, frameworks, banco de dados, conhecimentos de domínio e dependências externas. Os nomes do domínio são distintos, mas as operações centrais são deliberadamente semelhantes para controlar a carga algorítmica. `ConsumoEnergetico` reutiliza a mesma suíte de 26 casos de `ExcessoBagagem` (lógica de excesso) e `MetaProducao` reutiliza a mesma suíte de `ReposicaoEstoque` (lógica de déficit) — dentro de cada par a dificuldade formal é idêntica por construção; a comparação de esforço entre os dois pares ainda depende do piloto, como para o par original.

Preferiu-se esses pares a exercícios canônicos muito curtos, como FizzBuzz, porque permitem observar normalização, agregação, validação e limites em uma tarefa pequena. Isso não demonstra ineditismo: agrupar e filtrar são padrões comuns, que podem ser reconhecidos por participantes e modelos.

## Dificuldade comparável

| Dimensão controlada | ReposicaoEstoque | ExcessoBagagem | ConsumoEnergetico | MetaProducao |
|---|---|---|---|---|
| Interface | Lista de pares + inteiro → lista de pares | Lista de pares + inteiro → lista de pares | Lista de pares + inteiro → lista de pares | Lista de pares + inteiro → lista de pares |
| Normalização | `strip().lower()` | `strip().lower()` | `strip().lower()` | `strip().lower()` |
| Agregação | Soma por produto normalizado | Soma por passageiro normalizado | Soma por apartamento normalizado | Soma por item normalizado |
| Regra final | Total < mínimo; mínimo − total | Total > franquia; total − franquia | Total > franquia; total − franquia | Total < meta; meta − total |
| Ordenação | Nome normalizado crescente | Nome normalizado crescente | Nome normalizado crescente | Nome normalizado crescente |
| Validação | Limite negativo, valor negativo, nome vazio | Limite negativo, valor negativo, nome vazio | Limite negativo, valor negativo, nome vazio | Limite negativo, valor negativo, nome vazio |
| Casos especiais | Vazio, zero, igualdade, repetição, entrada preservada | Vazio, zero, igualdade, repetição, entrada preservada | Vazio, zero, igualdade, repetição, entrada preservada | Vazio, zero, igualdade, repetição, entrada preservada |
| Suíte | 26 casos, 7 de erro | 26 casos, 7 de erro | 26 casos, 7 de erro (idêntica a ExcessoBagagem) | 26 casos, 7 de erro (idêntica a ReposicaoEstoque) |
| Solução esperada em termos de custo | O(n + k log k), memória O(k) | O(n + k log k), memória O(k) | O(n + k log k), memória O(k) | O(n + k log k), memória O(k) |

`n` é o número de registros e `k` o número de nomes distintos. O custo descreve uma abordagem possível, não uma exigência de implementação ou medição de desempenho pela suíte. O mesmo número de testes e regras **não comprova** dificuldade igual; diferenças no domínio, na direção da comparação e na familiaridade podem alterar o esforço. Entre `ConsumoEnergetico`/`ExcessoBagagem` e entre `MetaProducao`/`ReposicaoEstoque` a suíte é a mesma por construção, o que reduz (mas não elimina) essa incerteza para esses pares; entre os dois pares (déficit vs. excesso) a situação é a mesma do par original.

Antes da coleta principal, faça um piloto com, idealmente, pelo menos quatro pessoas de familiaridade semelhante à amostra, fora dela, em condição `SEM_IA`, equilibrando a ordem entre os quatro katas. Registre tempos, conclusão, dúvidas de interpretação e dificuldade percebida de 1 (muito fácil) a 5 (muito difícil). Critérios operacionais propostos para revisar os katas:

- Diferença entre medianas dos tempos concluídos superior a 20% da menor mediana, comparando em especial o padrão déficit (`ReposicaoEstoque`/`MetaProducao`) com o padrão excesso (`ExcessoBagagem`/`ConsumoEnergetico`);
- Diferença superior a 1 ponto entre medianas de dificuldade percebida;
- Qualquer enunciado ambíguo ou não conclusão dentro de 35 minutos.

Esses limiares são decisões de planejamento, não evidência estatística de equivalência. Se não houver conclusões suficientes para comparar, o piloto é inconclusivo. Ajuste regras e testes em conjunto, repita o piloto quando necessário e congele a versão antes da coleta principal. Participantes do piloto também podem aprender nos primeiros katas; mantenha essa limitação explícita ao interpretar os tempos.

## Alocação e controle da execução

Cada integrante resolve os quatro katas (`A = ReposicaoEstoque`, `B = ExcessoBagagem`, `C = ConsumoEnergetico`, `D = MetaProducao`), dois em `COM_IA` e dois em `SEM_IA`. Distribua os participantes aleatoriamente entre as quatro sequências abaixo, registrando o sorteio antes dos trials. Equilibre a experiência em Python entre sequências quando possível. Se o grupo não for múltiplo de quatro, minimize e reporte o desequilíbrio — com 3 integrantes, sorteie 3 das 4 sequências, sem repetir nenhuma.

| Sequência | Período 1 | Período 2 | Período 3 | Período 4 |
|---|---|---|---|---|
| S1 | A — COM_IA | C — SEM_IA | B — COM_IA | D — SEM_IA |
| S2 | B — SEM_IA | D — COM_IA | A — SEM_IA | C — COM_IA |
| S3 | C — COM_IA | A — SEM_IA | D — COM_IA | B — SEM_IA |
| S4 | D — SEM_IA | B — COM_IA | C — SEM_IA | A — COM_IA |

Esse arranjo é um quadrado latino: cada kata ocupa uma posição (período) diferente em cada sequência, e cada kata recebe `COM_IA` em exatamente 2 das 4 sequências e `SEM_IA` nas outras 2 — controla ordem, posição e tratamento simultaneamente, mas não elimina transferência de conhecimento entre katas estruturalmente parecidos. Não atribua sempre os mesmos katas à IA. Use intervalo padronizado de 5 minutos entre trials; ele reduz fadiga, mas não desfaz aprendizagem.

Antes dos trials, faça apenas um aquecimento de ambiente com tarefa diferente, sem revelar estes katas. Registre experiência em Python (meses e frequência de uso), experiência com IA e contato prévio com tarefas de agregação ou com estes materiais. Pessoas que prepararam ou revisaram os testes devem ser identificadas como expostas; prefira não incluí-las na coleta principal. Se todos os integrantes já conhecerem o material, declare a limitação e trate a execução como exploratória.

Mantenha o mesmo Python, máquina, IDE, enunciado e suíte em ambos os tratamentos. No `SEM_IA`, desabilite assistentes generativos e permita apenas edição, autocomplete convencional e consulta à mesma documentação de Python disponibilizada ao outro tratamento. Não permita busca de soluções prontas ou ajuda de terceiros em nenhum tratamento.

No `COM_IA`, fixe o assistente/modelo disponível, permita geração, explicação e depuração, e registre identificação do modelo, prompts e respostas. A cada trial, inicie uma conversa nova com acesso apenas ao enunciado, modelo inicial, suíte pública e arquivo corrente; evite fornecer o repositório inteiro ou a solução do outro trial. Não forneça este protocolo, que revela a relação entre os problemas, antes da execução. Em ambos os tratamentos, disponibilize somente o kata corrente e não permita copiar a solução anterior.

Inicie o cronômetro antes da leitura e encerre após aprovação integral. O cronômetro existente depende de ENTER manual e não verifica os testes: retenha o log e confira esse marco. Ao atingir 35 minutos, pare de editar. Uma aprovação obtida apenas na avaliação posterior não comprova conclusão dentro do limite. Registre interrupções e desvios; não exclua tentativas ruins depois de conhecer o tratamento.

Use a chave `(integrante, kata, tratamento)` nos três arquivos: tempos, avaliação funcional e métricas estáticas. Este desenho prevê apenas um trial por chave. Repetições técnicas devem ficar em coleta separada e ser documentadas, pois os coletores atuais não possuem identificador de repetição.

## Ameaças à validade

| Tipo | Ameaça | Mitigação e limitação residual |
|---|---|---|
| Interna | Experiência em Python/IA, diferenças entre os katas | Comparação pareada, registro de familiaridade, alocação equilibrada e piloto; amostras pequenas podem continuar desequilibradas |
| Interna | Aprendizagem, fadiga e transferência da solução | Alternar ordem/tratamento, intervalo e impedir cópia; o segundo kata ainda pode se beneficiar do primeiro |
| Interna | Modelo, latência, prompts e ambiente variáveis | Fixar ferramentas e registrar versões/histórico; variação do serviço permanece possível e sua espera integra o tempo |
| Interna | Contaminação do SEM_IA e contato prévio com material | Desativar assistência, registrar exposição e fornecer pacotes separados por trial; autorrelato pode ser incompleto |
| Construção | Passar nos testes ser confundido com correção geral | Casos normais, fronteiras, validação e imutabilidade; a suíte finita não cobre todo o domínio |
| Construção | Cronometragem manual e métricas usadas como qualidade | Incluir leitura/depuração, verificar logs, separar estrutura de correção; há atraso de reação ao ENTER |
| Externa | Dois problemas curtos, Python e amostra de conveniência | Restringir conclusões a este contexto; não generalizar diretamente para projetos, linguagens ou modelos diferentes |
| Conclusão | Poucos participantes, censura e casos tratados como amostras | Relatar dados individuais e incerteza, respeitar pareamento e censura; não usar os 26 testes como tamanho amostral |
| Conclusão | Seleção de soluções concluídas e exploração de várias métricas | H1 primária; H2 secundária; H3 exploratória; explicitar subconjuntos e desvios antes de interpretar efeitos |

## Risco de memorização pela IA

O assistente pode reconhecer um problema ou padrão visto no treinamento e recuperar uma solução. Também pode receber respostas por histórico de conversa, memória do produto, busca ou indexação do repositório. São mecanismos distintos e nenhum é descartado apenas por alterar nomes e exemplos.

Os quatro katas utilizam contextos e regras definidos para o laboratório, porém mantêm padrões comuns entre si (dois pares com a mesma lógica central). Não há acesso aos dados de treinamento para confirmar ausência de contaminação, nem teste confiável neste protocolo que distinga recordação de raciocínio. Resposta rápida, código parecido ou declaração do próprio modelo não provam memorização.

Para reduzir e registrar o risco:

1. Não disponibilize soluções de referência, respostas de outros participantes ou histórico de trials ao assistente. Forneça apenas os materiais autorizados do kata corrente e registre quais foram enviados.
2. Use conversa nova, registre configurações de memória e indexação disponíveis e limite o contexto acessível. Conversa nova sozinha não garante ausência de memória externa.
3. Congele regras, exemplos e testes após o piloto; não mude a dificuldade por tratamento para tentar surpreender a IA. Se variantes forem necessárias, pilote e equilibre previamente sua alocação.
4. Preserve prompts, respostas e versões para auditoria do procedimento. Não interprete a auditoria como prova sobre o treinamento do modelo.
5. Declare a autoria assistida dos materiais: enunciados e testes desta preparação foram elaborados com auxílio de IA. Isso requer revisão humana das expectativas antes da coleta e pode favorecer padrões familiares ao assistente.

Há também risco de memorização e transferência **humana**, especialmente porque os katas são estruturalmente semelhantes. A alternância reduz confusão sistemática, mas os resultados continuam sendo sobre desempenho com os materiais e ferramentas usados; não isolam a capacidade de resolver problemas inéditos.
