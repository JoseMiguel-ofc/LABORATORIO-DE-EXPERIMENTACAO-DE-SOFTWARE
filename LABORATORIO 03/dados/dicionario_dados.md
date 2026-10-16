# Dicionário de dados — Lab03, Sprint 02

**Unidade de análise:** repositório GitHub (`full_name` = `owner/repo`). Os dados referem-se à branch padrão e à janela de 12 meses indicada em `config.yaml`, com início e fim inclusivos, em UTC. As datas atualmente no config permanecem **provisórias**.

**Critérios de inclusão:** pelo menos 5 releases publicadas estáveis (`draft=false`, `prerelease=false`) e 50 GitHub Actions workflow runs válidos (`event=push`, branch padrão, conclusões `success`, `failure`, `timed_out`, `startup_failure`). Runs cancelados e sem conclusão válida ficam fora das métricas. Releases não são equivalentes garantidos a deploys de produção: tratam-se de *proxies*.

## Arquivos de origem

| Arquivo | Unidade | Descrição |
|---|---|---|
| `candidatos.csv` | repositório | Candidatos da GitHub Search API, antes dos filtros |
| `funil.csv` | etapa | Entradas, descartes e remanescentes em cada filtro |
| `descartes.csv` | repositório descartado | Motivo pelo qual o candidato não entrou na amostra |
| `repositorios.csv` | repositório aprovado | Chave `full_name`, metadados e contagens que validam o funil |
| `releases.csv` | release | Tag, publicação, flags, commits e status de extração |
| `commits.csv.gz` | commit por comparação de releases | SHA, datas e mensagens; comprimido por volume |
| `tags.csv` | tag | Variante opcional, quando habilitada a coleta de tags |
| `runs.csv` | workflow run | Execuções válidas da branch padrão na janela |
| `episodios_recuperacao.csv` | episódio de falha | Falha inicial, recuperação ou censura e duração em horas |
| `metricas_entrega.csv` | repositório | Frequência de releases, lead time variantes (a) e (b), indicadores de coleta |
| `metricas_ci.csv` | repositório | CFR(a) de CI e recuperação mediana, contagens e completude |
| `metricas_cfr_b.csv` | repositório | CFR(b) de entrega; heurística e censuras; produzido pela Pessoa B |
| `previsoes_cfr_b.csv` | release | Previsões de release corretiva e release que falhou |

## `metricas_consolidadas.csv` — criado pela Pessoa C

O comando `python -m pipeline.consolidar --config config.yaml` faz junção por `full_name`, preserva ausências, valida chaves duplicadas e integridade do funil, e **não** altera os arquivos de origem. A classificação geral toma como referência **frequência de releases, lead time (a), CFR(a) e recuperação** por meio de `metricas/dora.py`. `lead_time_b_horas` e `cfr_b` são exportadas para comparações posteriores, sem substituir a referência.

| Coluna | Tipo | Unidade/definição |
|---|---|---|
| `full_name` | texto, chave única | `owner/repo` |
| `default_branch` | texto | Branch principal do projeto |
| `estrelas` | inteiro | Estrelas da busca |
| `linguagem` | texto | Linguagem principal; pode ser ausente |
| `idade_anos` | decimal | Anos entre criação e fim da janela |
| `contribuidores` | inteiro opcional | Contribuidores observados pela API |
| `releases_janela` | inteiro | Número de releases que atenderam ao funil (≥5) |
| `runs_validos_janela` | inteiro | Contagem do funil (≥50); pode diferir de `runs_validos` detalhado conforme a extração |
| `releases_status` | texto | Estado da coleta de releases; apenas `ok` autoriza seus valores no consolidado |
| `coleta_ci_completa` | booleano | Se a coleta detalhada de runs está completa |
| `coleta_cfr_b_status` | texto | Estado do processamento do CFR(b); apenas `ok` autoriza taxa |
| `frequencia_releases_semana` | decimal opcional | Releases estáveis publicadas por semana na janela |
| `lead_time_a_horas` | decimal opcional | Mediana por release, em horas |
| `lead_time_b_horas` | decimal opcional | Mediana por commit, em horas |
| `cfr_a` | decimal opcional, 0 a 1 | `falhas de CI / (falhas + sucessos)` |
| `cfr_b` | decimal opcional, 0 a 1 | Releases com correção em até 7 dias sobre originais elegíveis (heurística da Pessoa B) |
| `recuperacao_mediana_horas` | decimal opcional | Mediana de horas de episódios resolvidos no mesmo workflow |
| `categoria_frequencia` | texto opcional | Elite / High / Medium / Low segundo cortes em `metricas/dora.py` |
| `categoria_lead_time` | texto opcional | Categoria do lead time (a) |
| `categoria_cfr` | texto opcional | Categoria do CFR(a) |
| `categoria_recuperacao` | texto opcional | Categoria da mediana de recuperação |
| `categoria_geral` | texto opcional | Mediana inferior dos pontos das categorias disponíveis, conforme `metricas/dora.py` |
| `metricas_disponiveis` | inteiro, 0–4 | Quantas das quatro métricas de referência não estão ausentes |
| `classificacao_completa` | booleano | `true` se as quatro métricas de referência existem |

**Valores ausentes:** campo CSV vazio significa métrica não observada/inaplicável ou extração incompleta — **nunca zero**. Em particular, um repositório sem episódio de falha resolvido não tem tempo de recuperação `0`. O arquivo `resumo_consolidacao.json` informa quantidade de repositórios, casos completos, categorias gerais e alertas de ausência. A meta de 300 é informada separadamente; o programa não fabrica registros para alcançá-la.

## Procedimento de reprodução

1. Verificar as datas oficiais em `config.yaml`, inclusive a data em `busca.filtro_extra`.
2. Alterar `amostra.tamanho` de 100 para **300** e executar `python -m pipeline --config config.yaml` com `GITHUB_TOKEN` no ambiente. Respeitar rate limit e cache; preservar CSVs existentes e fazer backup se necessário.
3. Calcular o CFR (b) atualizado com `python -m pipeline.cfr_entrega --config config.yaml`.
4. Consolidar com `python -m pipeline.consolidar --config config.yaml --exigir-300`.
5. Executar `python -m pytest --cov=pipeline --cov=metricas --cov=validacao --cov-fail-under=80`.
6. Realizar rotulagem independente de `validacao/planilha_rotulagem.xlsx`; os rótulos humanos e o consenso não são gerados pela consolidação.

**Atenção:** aumentar a configuração sozinho não realiza nova coleta; a amostra do ZIP recebido em 16/10/2026 contém 100 repositórios. Não declarar a meta atingida antes de conferir o relatório com pelo menos 300 registros reais.
