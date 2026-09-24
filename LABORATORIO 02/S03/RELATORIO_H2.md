# RQ/H2 — Correção: conclusão dentro de 35 minutos

## Método

O desfecho de cada trial é binário: `1` somente quando a avaliação registra conclusão, os 26 casos são aprovados e o cronômetro termina antes de 2.100 segundos sem censura; `0` quando o trial não conclui no prazo. Aprovação obtida apenas após o limite continua como `0`. Campos faltantes ou contraditórios ficam como não avaliáveis, sem imputação. A estatística descritiva é a fração de trials concluídos em cada tratamento.

O teste exato de McNemar usa pares por integrante e família de kata: déficit (`ReposicaoEstoque`/`MetaProducao`) e excesso (`ExcessoBagagem`/`ConsumoEnergetico`). A alternativa unilateral, definida no [protocolo](../S01/PROTOCOLO.md), é maior proporção de conclusão com IA. Os 26 casos da suíte não são 26 observações independentes. Quando um integrante fornecer dois pares, o p-valor combinado será exploratório porque esses pares compartilham a mesma pessoa.

## Resultados disponíveis em 24/09/2026

A [consolidação desta análise](resultados/consolidacao_h2_20260924/trials_consolidados.csv), gerada das fontes existentes sem alterar a S02, contém quatro registros `COM_IA` e nenhum `SEM_IA`. Dois registros de `JoseMiguel` têm avaliação 26/26 e conclusão dentro do limite. Os dois registros de `Pedro` têm tempo, mas ainda não têm avaliação; por isso seu desfecho permanece desconhecido. O [diagnóstico](resultados/consolidacao_h2_20260924/diagnostico.json) registra quatro tempos e duas avaliações dos 12 trials previstos.

| Tratamento | Trials avaliáveis | Concluídos no prazo | Proporção | Sem avaliação |
|---|---:|---:|---:|---:|
| `COM_IA` | 2 | 2 | 100% | 2 |
| `SEM_IA` | 0 | 0 | Indefinida | 0 |

Há **0 pares completos e 0 discordâncias**; o McNemar não tem p-valor calculável. A proporção de 100% descreve somente os dois trials avaliados, não uma comparação entre tratamentos. As observações da avaliação desses trials registram sequência sem sorteio formal, acesso do assistente ao repositório inteiro e tempos que não representam o fluxo humano completo de leitura, prompt e revisão. Nesta coleta não há base para confirmar ou rejeitar H2 ou atribuir efeito causal à IA.

## Reprodução e arquivos

O [script H2](scripts/analise_h2_correcao.py) lê um `trials_consolidados.csv` e gera [trials auditados](resultados/h2_trials.csv), [resumo por tratamento](resultados/h2_resumo_tratamentos.csv), [pares](resultados/h2_pares.csv), [tabela de McNemar](resultados/h2_mcnemar.csv) e [gráfico de barras](resultados/h2_proporcao_conclusao.svg). A consolidação dentro de `S03/resultados/` é uma cópia derivada para esta análise; os arquivos da S02 permanecem intactos.

```bash
python3 "LABORATORIO 02/S03/scripts/analise_h2_correcao.py" \
  --consolidado "LABORATORIO 02/S03/resultados/consolidacao_h2_20260924/trials_consolidados.csv"
```

Quando a equipe gerar uma nova consolidação na S02, passe seu caminho com `--consolidado`. Sem essa opção, o script escolhe a consolidação mais recente da S02 por data de modificação. O [teste automatizado](testes/test_analise_h2.py) cobre a probabilidade exata, o pareamento e aprovação após o limite.
