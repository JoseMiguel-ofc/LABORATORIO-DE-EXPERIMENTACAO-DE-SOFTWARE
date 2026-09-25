# RQ/H2 — Correção: conclusão dentro de 35 minutos

## Método

O desfecho de cada trial é binário: `1` somente quando a avaliação registra conclusão, os 26 casos são aprovados e o cronômetro termina antes de 2.100 segundos sem censura; `0` quando o trial não conclui no prazo. Aprovação obtida apenas após o limite continua como `0`. Campos faltantes ou contraditórios ficam como não avaliáveis, sem imputação. A estatística descritiva é a fração de trials concluídos em cada tratamento.

O teste exato de McNemar usa pares por integrante e família de kata: déficit (`ReposicaoEstoque`/`MetaProducao`) e excesso (`ExcessoBagagem`/`ConsumoEnergetico`). A alternativa unilateral, definida no [protocolo](../S01/PROTOCOLO.md), é maior proporção de conclusão com IA. Os 26 casos da suíte não são 26 observações independentes. Quando um integrante fornecer dois pares, o p-valor combinado será exploratório porque esses pares compartilham a mesma pessoa.

## Resultados atualizados em 25/09/2026

Com a [consolidação completa](../S02/resultados/consolidacoes) (12/12 trials com tempo e avaliação), a análise de H2 agora cobre os 3 integrantes:

| Tratamento | Trials avaliáveis | Concluídos no prazo | Proporção | Sem avaliação |
|---|---:|---:|---:|---:|
| `COM_IA` | 6 | 6 | 100% | 0 |
| `SEM_IA` | 6 | 6 | 100% | 0 |

Há **6 pares completos e 0 discordâncias** (todos os 6 pares concluíram nos dois tratamentos); o McNemar não tem p-valor calculável porque não existe nenhuma discordância para testar — não é evidência de ausência de efeito, é ausência de variação no desfecho binário observado. Com 100% de conclusão nos dois braços, H2 não pode ser testada de forma informativa nesta amostra: não há como diferenciar "IA não ajuda a concluir" de "a tarefa era fácil o suficiente para todos concluírem de qualquer forma" (efeito teto).

### Ressalvas que seguem valendo

- Sequência formal S1–S4 nunca foi sorteada pelo grupo; execução em ordem ad hoc.
- Nos trials `COM_IA` de `JoseMiguel` e `Pedro`, o assistente (Claude Code) teve acesso ao repositório completo, sem isolamento por "conversa nova só com o kata corrente" previsto no protocolo.
- Dois trials `SEM_IA` do `Eddie` foram registrados como soluções de prática assistida por IA (Codex), não representando observações genuinamente sem assistência.
- **Nova ressalva**: 4 dos 12 trials (`Eddie` COM_IA ×2, `Pedro` SEM_IA ×2) têm `tempo_segundos` divergente em várias centenas de segundos da diferença real entre `inicio` e `fim` em `tempos_trials.csv` — ver [análise de H1](../S03/resultados/h1_trials_suspeitos.csv). Isso não muda o desfecho binário de H2 (mesmo os tempos suspeitos ficam abaixo de 2.100s), mas é um problema de qualidade de dado que compromete a análise de tempo (H1) e deveria ser investigado antes do relatório final.

Nesta coleta, com 100% de conclusão nos dois tratamentos e múltiplos desvios de protocolo documentados, **não há base para confirmar, rejeitar ou atribuir efeito causal à IA em H2**.

## Reprodução e arquivos

O [script H2](scripts/analise_h2_correcao.py) lê um `trials_consolidados.csv` e gera [trials auditados](resultados/h2_trials.csv), [resumo por tratamento](resultados/h2_resumo_tratamentos.csv), [pares](resultados/h2_pares.csv), [tabela de McNemar](resultados/h2_mcnemar.csv) e [gráfico de barras](resultados/h2_proporcao_conclusao.svg). Os arquivos da S02 permanecem intactos; sem `--consolidado`, o script usa a consolidação mais recente em `S02/resultados/consolidacoes/` por data de modificação.

```bash
python3 "LABORATORIO 02/S03/scripts/analise_h2_correcao.py"
```

Quando a equipe gerar uma nova consolidação na S02, passe seu caminho com `--consolidado`. Sem essa opção, o script escolhe a consolidação mais recente da S02 por data de modificação. O [teste automatizado](testes/test_analise_h2.py) cobre a probabilidade exata, o pareamento e aprovação após o limite.
