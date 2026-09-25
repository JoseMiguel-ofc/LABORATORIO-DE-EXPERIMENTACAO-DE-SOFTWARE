# Relatório de Laboratório

*Laboratório de Experimentação de Software*

| Campo | Valor |
|---|---|
| Curso | Engenharia de Software |
| Disciplina | Laboratório de Experimentação de Software |
| Laboratório | Lab02 - Assistentes de IA vs. Codificação Manual |
| Grupo (trio) | Pedro Talma Toledo · Eddie Christian Pereira · José Miguel |
| Link do repositório / GitHub Projects | https://github.com/JoseMiguel-ofc/LABORATORIO-DE-EXPERIMENTACAO-DE-SOFTWARE |
| Data | 25/09/2026 |

---

## 1. Introdução

Este laboratório investiga o efeito do uso de um assistente de IA sobre o tempo e a correção na implementação de katas em Python, comparando os tratamentos `COM_IA` e `SEM_IA` num desenho pareado por integrante (*within-subject*). Cada um dos 3 integrantes do grupo resolveu 4 katas (2 por tratamento, sem repetir kata), sob limite de 35 minutos por trial. O desenho completo, as hipóteses e as ameaças previstas antes da coleta estão detalhados no [protocolo experimental](S01/PROTOCOLO.md).

As três hipóteses avaliadas:

- **H1 (primária, Tempo)**: com IA, o tempo até aprovação tende a ser menor.
- **H2 (secundária, Correção)**: com IA, a proporção de trials concluídos dentro do limite é maior.
- **H3 (exploratória, Estrutura do código)**: a complexidade ciclomática máxima (com LOC/SLOC e duplicação como descritores auxiliares) difere entre tratamentos, sem direção prevista.

## 2. Metodologia

### 2.1 Ambiente e katas

- Linguagem: Python 3 (José Miguel: 3.13.12; Eddie: 3.9.6; Pedro: não confirmado pelo integrante).
- Métricas estáticas: [Radon](S01/scripts/requirements.txt) 6.0.1 (LOC, complexidade ciclomática); duplicação de código com detector próprio do grupo (blocos de 4 linhas normalizadas) — métrica adicionada além do exigido pelo enunciado.
- 4 katas autorais do grupo, organizados em 2 pares estruturalmente espelhados para controlar dificuldade: [`ReposicaoEstoque`](S01/katas/ReposicaoEstoque.md)/[`MetaProducao`](S01/katas/MetaProducao.md) (padrão déficit) e [`ExcessoBagagem`](S01/katas/ExcessoBagagem.md)/[`ConsumoEnergetico`](S01/katas/ConsumoEnergetico.md) (padrão excesso), cada um com suíte de 26 casos de teste automatizados.
- Assistente de IA: **não uniforme entre integrantes**, ao contrário do exigido pelo enunciado. José Miguel e Pedro usaram Claude Code (`claude-sonnet-5`) nos trials `COM_IA`; Eddie usou Codex (`GPT-6`). Essa divergência é discutida como ameaça à validade (seção 4).
- Cronometragem: script próprio ([`coletar_tempo.py`](S01/scripts/coletar_tempo.py)), com corte automático em 35 minutos.
- Validação funcional: suíte de 26 testes automatizados por kata ([`executar_testes.py`](S01/scripts/executar_testes.py)).

### 2.2 Alocação

A alocação por sequência (S1–S4, contrabalanceando kata, tratamento e ordem) definida no protocolo **não chegou a ser sorteada formalmente pelo grupo**; a execução ocorreu em ordem decidida ad hoc por cada integrante. Isso reduz o controle sobre efeitos de ordem e aprendizagem entre katas.

### 2.3 Pipeline de coleta e análise

1. Cronometragem ([`coletar_tempo.py`](S01/scripts/coletar_tempo.py)) e validação funcional ([`executar_testes.py`](S01/scripts/executar_testes.py)) por trial.
2. Métricas estáticas ([`metricas_estaticas.py`](S01/scripts/metricas_estaticas.py)) e de duplicação ([`metricas_duplicacao.py`](S02/scripts/metricas_duplicacao.py)) sobre as soluções finais.
3. Consolidação por chave `(integrante, kata, tratamento)` ([`consolidar_trials.py`](S02/scripts/consolidar_trials.py)) e validação de desenho ([`validar_trials.py`](S02/scripts/validar_trials.py)).
4. Análise por hipótese: [`analise_h1_tempo.py`](S03/scripts/analise_h1_tempo.py), [`analise_h2_correcao.py`](S03/scripts/analise_h2_correcao.py), [`analise_h3_estrutura.py`](S03/scripts/analise_h3_estrutura.py) — teste de Wilcoxon pareado (H1/H3) ou McNemar exato (H2), sempre com o participante como unidade de comparação pareada.

Dados brutos: [`tempos_trials.csv`](S02/resultados/tempos_trials.csv), [`avaliacao_trials.csv`](S02/resultados/avaliacao_trials.csv), [`metricas_estaticas.csv`](S02/resultados/metricas_estaticas.csv), [`metricas_duplicacao.csv`](S02/resultados/metricas_duplicacao.csv). Commit que fixa os katas/testes usados nesta coleta: `9866b41` (`ReposicaoEstoque`/`ExcessoBagagem`) e `ae82ed3` (`ConsumoEnergetico`/`MetaProducao`).

## 3. Resultados por hipótese

### H1 — Tempo até aprovação

Dos 12 trials, **8 tiveram tempo considerado confiável** (o `tempo_segundos` registrado bate com a diferença entre `inicio` e `fim`, tolerância de 5s); os outros 4 foram excluídos da análise principal por divergência de várias centenas de segundos entre o valor registrado e o intervalo real (2 trials `COM_IA` do Eddie, 2 trials `SEM_IA` do Pedro — ver [`h1_trials_suspeitos.csv`](S03/resultados/h1_trials_suspeitos.csv)).

| Tratamento | n confiável | Mediana | Média | Desvio padrão |
|---|---:|---:|---:|---:|
| `COM_IA` | 4 | 26,05 s | 26,53 s | 4,93 s |
| `SEM_IA` | 4 | 934,50 s (~15,6 min) | 984,26 s (~16,4 min) | 243,53 s |

Com a exclusão dos trials não confiáveis, **restou apenas 1 participante (José Miguel) com par completo em ambos os tratamentos** — o teste de Wilcoxon pareado não é aplicável (mínimo de 3 pares). A diferença descritiva é grande e na direção esperada por H1, mas não pode ser atribuída ao tratamento com confiança: os tempos `COM_IA` confiáveis vêm de trials em que o assistente gerou a solução em segundos, sem o fluxo humano completo de leitura, prompt e revisão; e a amostra pareada útil é de apenas uma pessoa.

### H2 — Correção (conclusão dentro do limite)

| Tratamento | Concluídos | Proporção |
|---|---:|---:|
| `COM_IA` | 6/6 | 100% |
| `SEM_IA` | 6/6 | 100% |

Os 6 pares por integrante/família de kata concluíram em ambos os tratamentos — **0 discordâncias**, então o teste exato de McNemar não produz p-valor: não há variação no desfecho binário para testar. Isso não é evidência de que a IA não ajuda; é um efeito teto — com 35 minutos de limite, os katas foram concluíveis por todos os participantes independentemente do tratamento. Detalhes em [`RELATORIO_H2.md`](S03/RELATORIO_H2.md).

### H3 — Estrutura do código (exploratória)

Comparando as 6 soluções `COM_IA` concluídas contra as 6 `SEM_IA` concluídas:

| Métrica | `COM_IA` (mediana / média) | `SEM_IA` (mediana / média) | Wilcoxon pareado (n=3) |
|---|---|---|---|
| Complexidade ciclomática máxima | 7,0 / 7,33 | 7,0 / 7,0 | p = 1,0 |
| LOC | 20,0 / 22,33 | 21,0 / 21,0 | p = 1,0 |
| SLOC | 16,0 / 17,0 | 16,0 / 15,33 | p = 1,0 |
| Duplicação literal (%) | 0,0 / 5,56 | 0,0 / 5,56 | Empate perfeito (diferenças pareadas nulas) |

Nenhuma métrica estrutural mostrou diferença perceptível entre tratamentos nesta amostra. O teste pareado usa apenas 3 participantes (n=3), muito abaixo do necessário para qualquer inferência — os resultados são puramente descritivos.

## 4. Discussão

Os números desta primeira coleta apontam na direção esperada em H1 (mediana de 26,05s em `COM_IA` contra 934,50s em `SEM_IA`, nos 8 trials com tempo confiável), ficam empatados em H2 (100% de conclusão dentro do limite nos dois tratamentos, 12/12 trials) e não mostram diferença relevante em H3 (as 4 métricas estruturais comparadas ficam próximas entre tratamentos). Como é a primeira execução completa deste protocolo pelo grupo, alguns pontos do desenho original ainda podem ser ajustados numa próxima rodada:

- **Amostra**: 3 participantes e 4 katas cada resultam em no máximo 3 pares por hipótese (12 trials no total) — abaixo do ideal para testes não paramétricos com boa potência, então os números acima valem mais como retrato descritivo do que como confirmação estatística.
- **Assistente de IA**: José Miguel e Pedro usaram Claude Code (`claude-sonnet-5`); Eddie usou Codex (`GPT-6`). Padronizar um único assistente para todo o grupo na próxima coleta deixaria a comparação entre integrantes mais direta.
- **Escopo de contexto do assistente**: em parte dos trials `COM_IA`, o assistente teve acesso ao repositório inteiro, e não só ao kata corrente isolado como previa o protocolo — vale reforçar esse isolamento na próxima rodada.
- **Familiaridade prévia com os katas**: como José Miguel também preparou os katas `ConsumoEnergetico`/`MetaProducao`, optou-se por resolvê-los no tratamento `SEM_IA`; e 2 trials `SEM_IA` do Eddie partiram de uma versão já trabalhada com apoio do Codex. Ambos os casos estão sinalizados em `avaliacao_trials.csv` para quem for analisar os dados.
- **4 dos 12 registros de tempo** (33%) tiveram `tempo_segundos` divergente do intervalo `inicio`–`fim` do cronômetro — foram excluídos da análise de H1 para não distorcer as médias, restando 8/12 registros confiáveis. Vale investigar a causa antes da próxima coleta.
- **Ordem de execução**: o sorteio formal das sequências S1–S4 do protocolo não chegou a acontecer; cada integrante seguiu a própria ordem.
- **Time-box de 35 min**: não se mostrou restritivo nesta coleta (100% de conclusão nos dois tratamentos), o que limita o quanto H2 consegue diferenciar os tratamentos com este desenho.

## 5. Conclusão

O laboratório implementou a infraestrutura experimental completa: 4 katas autorais com suíte de 26 testes cada (104 casos no total), cronometragem, avaliação funcional, coleta de métricas estáticas (LOC, complexidade ciclomática) e de duplicação de código, consolidação de 12 trials por chave e scripts de análise estatística (Wilcoxon para H1/H3, McNemar exato para H2). Os números desta coleta, de forma descritiva: tempo mediano de 26,05s (`COM_IA`) contra 934,50s (`SEM_IA`) nos 8 trials com tempo confiável; 100% de conclusão dentro do limite nos dois tratamentos (12/12 trials); e métricas estruturais (complexidade, LOC, SLOC, duplicação) muito próximas entre os dois tratamentos nas 12 soluções avaliadas. Dado o tamanho da amostra (3 participantes) e os pontos discutidos na seção 4, esses resultados funcionam melhor como piloto para uma coleta futura maior e mais padronizada do que como confirmação estatística de H1, H2 ou H3.

## Link do repositório / GitHub Projects

https://github.com/JoseMiguel-ofc/LABORATORIO-DE-EXPERIMENTACAO-DE-SOFTWARE
