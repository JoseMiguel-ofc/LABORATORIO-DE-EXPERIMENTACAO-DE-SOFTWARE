# Lab02S01 — Preparar katas e testes automatizados

Material para comparar resolução de tarefas em Python nos tratamentos `COM_IA` e `SEM_IA`, com limite de **35 minutos por trial**. As hipóteses, justificativas, avaliação da dificuldade e ameaças estão no [protocolo experimental](PROTOCOLO.md).

| Kata | Enunciado | Modelo | Suíte |
|---|---|---|---|
| `ReposicaoEstoque` | [Reposição de estoque](katas/ReposicaoEstoque.md) | [Arquivo inicial](katas/modelos/ReposicaoEstoque.py) | [26 casos](testes/ReposicaoEstoque.json) |
| `ExcessoBagagem` | [Excesso de bagagem](katas/ExcessoBagagem.md) | [Arquivo inicial](katas/modelos/ExcessoBagagem.py) | [26 casos](testes/ExcessoBagagem.json) |
| `ConsumoEnergetico` | [Consumo energético excedente](katas/ConsumoEnergetico.md) | [Arquivo inicial](katas/modelos/ConsumoEnergetico.py) | [26 casos](testes/ConsumoEnergetico.json) |
| `MetaProducao` | [Meta de produção](katas/MetaProducao.md) | [Arquivo inicial](katas/modelos/MetaProducao.py) | [26 casos](testes/MetaProducao.json) |

`ConsumoEnergetico` espelha exatamente a suíte de `ExcessoBagagem` (mesma lógica de excedente) e `MetaProducao` espelha exatamente a suíte de `ReposicaoEstoque` (mesma lógica de déficit), só variando domínio e nomes — garante dificuldade formalmente equivalente dentro de cada par. Os 4 katas juntos atendem ao mínimo de 4 katas exigido pelo enunciado do laboratório (número par, para dividir metade `COM_IA` e metade `SEM_IA`).

## Executar um trial

Os comandos abaixo partem da raiz do repositório. Requisito: **Python 3.9 ou superior**. Os testes usam `unittest` e não exigem instalação de pacotes. Em ambientes onde o executável se chama `python`, substitua `python3` por `python`.

1. Registre a alocação e a familiaridade conforme o protocolo. Prepare o terminal, uma cópia do modelo na pasta `LABORATORIO 02/solucoes/` e o ambiente do tratamento sorteado.
2. Use o nome `INTEGRANTE__KATA__TRATAMENTO.py`. Por exemplo, `Ana__ReposicaoEstoque__COM_IA.py`.
3. Inicie a cronometragem e então libere a leitura do enunciado. Leitura, prompts, espera pela IA, implementação e depuração fazem parte do tempo.

```bash
python3 "LABORATORIO 02/S01/scripts/coletar_tempo.py"
```

4. Implemente a função do modelo e execute a suíte do kata em outro terminal, quantas vezes necessário:

```bash
python3 "LABORATORIO 02/S01/scripts/executar_testes.py" --kata ReposicaoEstoque --arquivo "LABORATORIO 02/solucoes/Ana__ReposicaoEstoque__COM_IA.py"
```

Repita para os outros katas da sua alocação, ajustando também a identificação do trial no cronômetro:

```bash
python3 "LABORATORIO 02/S01/scripts/executar_testes.py" --kata ExcessoBagagem --arquivo "LABORATORIO 02/solucoes/Ana__ExcessoBagagem__SEM_IA.py"
python3 "LABORATORIO 02/S01/scripts/executar_testes.py" --kata ConsumoEnergetico --arquivo "LABORATORIO 02/solucoes/Ana__ConsumoEnergetico__COM_IA.py"
python3 "LABORATORIO 02/S01/scripts/executar_testes.py" --kata MetaProducao --arquivo "LABORATORIO 02/solucoes/Ana__MetaProducao__SEM_IA.py"
```

5. Pressione ENTER no cronômetro **somente após 26/26 casos aprovados**. Se atingir 35 minutos, interrompa a edição e preserve a solução parcial. Execute a suíte final sobre esse arquivo sem corrigi-lo.
6. Salve a saída dos testes e preencha [avaliacao_trials.csv](../S02/resultados/avaliacao_trials.csv), usando os mesmos identificadores de `tempos_trials.csv`. Para guardar a saída, acrescente `> "caminho/do/log.txt" 2>&1` ao comando de testes. Não sobrescreva o log de outro trial.
7. Colete as métricas estáticas conforme o [manual existente](../ManualMetricasEstaticas.md). O coletor já reconhece a convenção de nomes adotada.

## Interpretar os testes

- Código de saída **0**: todos os casos aprovados; **1**: falha, erro ao carregar a solução ou tempo dos testes excedido; **2**: uso/configuração inválida do executor.
- Cada suíte contém 26 casos determinísticos. Cada caso chama a função duas vezes; essas repetições não são observações experimentais independentes.
- São conferidos os valores, a ordem, o tipo de retorno, a exceção `ValueError` quando exigida e a preservação da entrada. Os testes também exercitam chamadas sucessivas no mesmo módulo.
- O processo da suíte tem limite de **10 segundos**, incluindo importação, para encerrar implementações que entram em loop. Esse limite é diferente dos 35 minutos do trial. Pode ser alterado com `--tempo-limite`, mas deve ser congelado e igual nos dois tratamentos.
- Se houver erro de importação ou timeout, registre `status_testes` correspondente e deixe `casos_aprovados` vazio: a avaliação não terminou. Não interprete esse campo como zero casos executados.
- Os modelos contêm `NotImplementedError`: **é esperado que falhem** até serem implementados. As [soluções técnicas da S02](../S02/README.md) e suas cópias de evidência devem ficar fora dos materiais dos participantes.

Os arquivos JSON guardam entradas e saídas esperadas explícitas. Em todos eles, `limite` representa o segundo argumento da função (`minimo`, `franquia` ou `meta`, conforme o kata). Arrays de registros e resultados são convertidos em tuplas pelo executor. A suíte é pública e idêntica entre tratamentos; não é uma avaliação secreta nem uma prova de correção para todas as entradas possíveis.

## Verificar a preparação

Os testes de regressão do próprio avaliador podem ser executados sem resolver os katas:

```bash
python3 -m unittest discover -s "LABORATORIO 02/S01/testes" -p "test_*.py" -v
```

Na preparação dos katas A/B (`ReposicaoEstoque`/`ExcessoBagagem`), em Python 3.9.6, os seis testes do avaliador passaram. Também foram realizadas 33 execuções de verificação com arquivos temporários: duas implementações de referência aprovaram os 52 casos; 22 variantes com defeitos deliberados e os dois modelos incompletos foram rejeitados; sete cenários de erro/timeout do executor produziram os códigos esperados. As referências temporárias não integram os materiais entregues. Essa verificação técnica não substitui revisão humana nem o piloto de dificuldade.

Na inclusão dos katas C/D (`ConsumoEnergetico`/`MetaProducao`), em Python 3.13.12, os seis testes do avaliador seguiram passando. Uma implementação de referência temporária por kata aprovou os 26/26 casos de sua suíte; rodar a suíte contra o modelo inicial (`NotImplementedError`) produziu os 26 erros esperados em ambos. As referências temporárias também não integram os materiais entregues.

## Registro complementar

O arquivo `avaliacao_trials.csv` começa apenas com o cabeçalho, sem dados experimentais inventados. Preencha uma linha por trial:

| Campo | Preenchimento |
|---|---|
| `integrante`, `kata`, `tratamento` | Mesma chave usada nos tempos e no nome da solução |
| `sequencia`, `periodo` | Sequência S1–S4 e período 1 a 4 do protocolo |
| `concluido` | `True` somente se a suíte inteira passou dentro de 35 minutos; caso contrário, `False` |
| `casos_aprovados`, `total_casos` | Contagem da avaliação final e total previsto (26) |
| `status_testes` | `APROVADO`, `REPROVADO`, `ERRO_CARGA`, `TIMEOUT` ou `ERRO_EXECUTOR` |
| `python`, `ide`, `assistente`, `modelo` | Versões/identificação observadas; `NA` para IA no tratamento `SEM_IA`; `nao_informado` se a versão do modelo não estiver disponível |
| `familiaridade_python`, `exposicao_previa` | Informações levantadas antes de mostrar os katas |
| `commit_suite` | Commit que fixa enunciados, modelos e testes usados |
| `observacoes` | Interrupções, desvios, caminho do log e identificação do histórico de prompts, quando aplicável |

Mantenha registros do piloto separados da coleta principal. O registro `Pedro,Teste,COM_IA` já presente em `tempos_trials.csv` é um teste de instrumentação e não pertence à amostra destes katas.
