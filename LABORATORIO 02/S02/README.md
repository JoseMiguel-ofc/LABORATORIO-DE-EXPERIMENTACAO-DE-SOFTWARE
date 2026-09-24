# Lab02S02 — Executar katas e organizar resultados

As quatro soluções de validação foram implementadas e executadas, com **104/104 casos aprovados**. Consulte o [relatório de execução](RELATORIO_EXECUCAO.md) para os resultados, evidências e estado da coleta experimental.

## Artefatos entregues

| Artefato | Local |
|---|---|
| Quatro soluções geradas com IA | [validacao_tecnica/solucoes](validacao_tecnica/solucoes/) |
| Resultados dos testes e métricas por solução | [validacao_consolidada.csv](resultados/validacoes/execucao_tecnica_01/validacao_consolidada.csv) |
| Saída completa dos testes e dos coletores | [logs](resultados/validacoes/execucao_tecnica_01/logs/) |
| Versões, cópias dos arquivos e hashes SHA-256 | [manifesto.json](resultados/validacoes/execucao_tecnica_01/manifesto.json) |
| Consolidação dos dados experimentais existentes | [trials_consolidados.csv](resultados/consolidacoes/coleta_inicial/trials_consolidados.csv) |
| Pendências e exclusões da coleta | [diagnostico.json](resultados/consolidacoes/coleta_inicial/diagnostico.json) |

As soluções `Codex__...__COM_IA.py` são validações técnicas feitas nesta sessão. Não são trials de Eddie nem de outro integrante. A coleta prevista continua pendente: não há tempos de resolução ou avaliações experimentais registrados. O arquivo de Eddie em `solucoes/` permanece como modelo inicial.

## Repetir a validação técnica

Execute a partir da raiz do repositório. Ambiente usado nesta entrega: Python 3.9.6 e Radon 6.0.1. O ambiente virtual `.venv` já foi preparado localmente; em outra máquina, crie-o e instale a dependência:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r "LABORATORIO 02/S01/scripts/requirements.txt"
```

Para executar os quatro katas, salvar logs, coletar métricas estáticas e duplicação e reunir os resultados:

```bash
.venv/bin/python "LABORATORIO 02/S02/scripts/executar_validacao.py"
```

Cada execução cria uma pasta com data/hora UTC em `S02/resultados/validacoes/`. A opção `--saida CAMINHO` aceita uma pasta nova; o comando recusa sobrescrever uma pasta existente. Retorna zero quando todas as soluções são aprovadas e suas métricas estáticas são coletadas sem erro; retorna código diferente de zero para falhas. Para examinar outra pasta, use `--pasta-solucoes CAMINHO`.

O executor sempre registra `tipo_registro=VALIDACAO_TECNICA`: avaliar uma solução já pronta não comprova as condições de um trial. `duracao_testes_segundos` mede apenas a execução da suíte, incluindo inicialização do processo. Não corresponde ao tempo de implementação e não deve alimentar `tempo_segundos` do cronômetro.

Para um kata isolado:

```bash
.venv/bin/python "LABORATORIO 02/S01/scripts/executar_testes.py" --kata ReposicaoEstoque --arquivo "LABORATORIO 02/S02/validacao_tecnica/solucoes/Codex__ReposicaoEstoque__COM_IA.py"
```

## Registrar e consolidar os trials reais

Para testar o fluxo usando o rótulo `SEM_IA`, há uma [cópia experimental identificada como simulação](resultados/simulacoes/sem_ia_experimental_01/README.md). Os CSVs dessa cópia mantêm `tratamento_original=COM_IA` e `origem_codigo=GERADO_COM_IA`. Para gerar outra simulação em uma nova pasta:

```bash
.venv/bin/python "LABORATORIO 02/S02/scripts/simular_sem_ia.py"
```

### Coleta dos participantes

1. Registre a alocação antes de começar, conforme o [protocolo da S01](../S01/PROTOCOLO.md). Cada integrante faz quatro katas, dois `COM_IA` e dois `SEM_IA`. Forneça somente os materiais autorizados do kata corrente; as soluções técnicas e suas cópias em `fontes/` não fazem parte do pacote dos participantes.
2. Durante cada trial, use `S01/scripts/coletar_tempo.py`, implemente em `LABORATORIO 02/solucoes/` e rode `S01/scripts/executar_testes.py`. Preserve o arquivo e o log final. O cronômetro deve abranger leitura, implementação e depuração.
3. Preencha `S02/resultados/avaliacao_trials.csv` com o resultado final e metadados reais. Aprovação posterior ao limite não transforma o trial em concluído. Não renomeie uma solução gerada com IA como `SEM_IA`.
4. Colete as métricas dos arquivos dos participantes:

```bash
.venv/bin/python "LABORATORIO 02/S01/scripts/metricas_estaticas.py"
.venv/bin/python "LABORATORIO 02/S02/scripts/metricas_duplicacao.py"
```

Esses dois coletores existentes atualizam os CSVs de métricas em `S02/resultados/`; seus comandos também aceitam `--saida` para preservar versões anteriores.

5. Gere uma nova consolidação e confira o validador existente:

```bash
.venv/bin/python "LABORATORIO 02/S02/scripts/consolidar_trials.py"
.venv/bin/python "LABORATORIO 02/S02/scripts/validar_trials.py"
```

O consolidado relaciona tempos, avaliação, métricas estáticas e duplicação por `(integrante, kata, tratamento)`. Cada coluna recebe o prefixo da origem (`tempo_`, `avaliacao_`, `estatica_`, `duplicacao_`). Por exemplo, `tempo_tempo_segundos` é o tempo original do cronômetro; nenhum valor é estimado.

Linhas sem correspondência são mantidas com campos vazios e `fontes_pendentes`. Chaves duplicadas na mesma fonte e identificadores desconhecidos interrompem a consolidação, evitando perda silenciosa. Apenas o registro conhecido `Pedro/Teste/COM_IA` é excluído, com justificativa no diagnóstico; seu dado bruto é preservado.

O comando cria uma pasta nova em `S02/resultados/consolidacoes/` e não altera as fontes. `--resultados` seleciona outra pasta de CSVs; `--esperados` altera o total planejado (padrão: 12, conforme o validador do grupo). O consolidado pode ser gerado mesmo com a coleta incompleta: código zero significa geração bem-sucedida, não aprovação do dataset para análise. O diagnóstico verifica disponibilidade das fontes, e o validador existente verifica suas próprias regras de campos, tempos, duplicação de trials e balanceamento; ainda é necessária revisão do protocolo e dos registros.

## Testes da infraestrutura

```bash
.venv/bin/python -m unittest discover -s "LABORATORIO 02/S01/testes" -p "test_*.py" -v
.venv/bin/python -m unittest discover -s "LABORATORIO 02/S02/testes" -p "test_*.py" -v
```

São seis testes do avaliador e sete testes da leitura de resultados/consolidação. Os dados sintéticos desses testes ficam em diretórios temporários e não entram nos CSVs do experimento.
