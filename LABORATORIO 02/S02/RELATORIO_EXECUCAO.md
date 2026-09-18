# Relatório — Execução e validação dos katas

## Resultado técnico

As quatro soluções foram implementadas com auxílio de IA e executadas em Python 3.9.6. Cada solução aprovou os 26 casos de sua suíte, totalizando **104 casos aprovados, sem falhas ou erros**. As métricas estáticas foram coletadas com Radon 6.0.1. A execução começou em **18/09/2026 às 02:56:20 UTC**, equivalente a **17/09/2026 às 23:56:20 em São Paulo**.

| Kata | Testes aprovados | LOC | SLOC | Complexidade máxima | Duplicação literal |
|---|---:|---:|---:|---:|---:|
| ConsumoEnergetico | 26/26 | 17 | 14 | 7 | 33,33% |
| ExcessoBagagem | 26/26 | 17 | 14 | 7 | 33,33% |
| MetaProducao | 26/26 | 17 | 14 | 7 | 0,00% |
| ReposicaoEstoque | 26/26 | 17 | 14 | 7 | 0,00% |

Fonte: [validação consolidada da execução](resultados/validacoes/execucao_tecnica_01/validacao_consolidada.csv). Os valores de duplicação usam o coletor do grupo com blocos de quatro linhas. O trecho de retorno dos dois katas de excesso coincide literalmente; diferenças nos nomes das variáveis podem impedir a detecção nos katas de déficit. Percentual zero não significa ausência de semelhança estrutural.

As funções validam nomes e valores, normalizam identificadores, agregam registros, filtram pelo limite e ordenam a saída sem alterar a entrada. Os 26 casos de cada kata cobrem valores normais, fronteiras, repetição, ordenação, normalização e sete situações inválidas. A mesma função é chamada duas vezes por caso, conforme o avaliador existente.

Também passaram os **seis testes do avaliador** e os **sete testes novos da infraestrutura da S02**, incluindo relacionamento por chave, preservação de dados faltantes, rejeição de duplicatas e distinção entre aprovação, falha e timeout.

## Evidências

- [Soluções](validacao_tecnica/solucoes/), com autoria técnica identificada por `Codex` e tratamento `COM_IA`.
- [Resultados dos testes](resultados/validacoes/execucao_tecnica_01/resultados_testes.csv), com quantidade aprovada/executada, status, código de saída, duração dos testes e caminho do log.
- [Logs completos](resultados/validacoes/execucao_tecnica_01/logs/) das suítes e dos coletores.
- [Métricas estáticas](resultados/validacoes/execucao_tecnica_01/metricas_estaticas.csv) e [duplicação](resultados/validacoes/execucao_tecnica_01/metricas_duplicacao.csv).
- [Manifesto](resultados/validacoes/execucao_tecnica_01/manifesto.json), com ambiente, hashes SHA-256 e cópias dos arquivos usados em `fontes/`. As cópias são evidências do conteúdo original, não um novo pacote executável.

## Consolidação dos trials e pendências

Foram conferidos os dados presentes no repositório. `tempos_trials.csv` contém apenas `Pedro/Teste/COM_IA`, já documentado como teste de instrumentação. `avaliacao_trials.csv` contém apenas o cabeçalho. O único arquivo na pasta de soluções dos participantes, `Eddie__ReposicaoEstoque__COM_IA.py`, ainda contém `NotImplementedError` e não foi apresentado como solução concluída.

O [consolidado experimental](resultados/consolidacoes/coleta_inicial/trials_consolidados.csv) foi gerado somente com o cabeçalho: **0 dos 12 trials previstos têm dados de coleta disponíveis**. O [diagnóstico](resultados/consolidacoes/coleta_inicial/diagnostico.json) registra a ausência de métricas experimentais e a exclusão auditável do teste de instrumentação. O [validador existente](resultados/consolidacoes/coleta_inicial/validacao_dataset.txt) também informou que o dataset não está apto à análise da Sprint 3.

Continuam necessários os trials dos integrantes: alocação registrada, execução de quatro katas por pessoa (dois por tratamento), tempos reais, códigos finais, logs e avaliações. A consolidação está automatizada para relacionar esses registros quando forem coletados, mantendo dados faltantes em branco e recusando duplicatas na mesma fonte.

## Limites da conclusão

Esta execução comprova que as quatro implementações entregues atendem aos casos disponíveis. Ela não testa H1/H2/H3 e não compara desempenho humano com e sem IA: não houve sorteio, isolamento entre katas ou cronometragem de resolução. O assistente já tinha acesso aos enunciados, suítes e à relação entre os problemas.

Os segundos registrados em `duracao_testes_segundos` medem exclusivamente a execução automatizada dos testes. Não foram usados como tempo de resolução nem como evidência de conclusão de um trial em 35 minutos. Os resultados técnicos ficam separados das fontes experimentais, e os arquivos de solução e suas cópias não devem ser incluídos no material entregue aos participantes.
