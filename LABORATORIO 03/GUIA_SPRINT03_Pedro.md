# Lab 03 — Sprint 03 — Pessoa C (RQ07)

## Arquivos da entrega
- `analises/rq07_sensibilidade.py`: análise offline de C1, C2 e C3
- `tests/test_rq07_sensibilidade.py`: testes do cálculo e da ausência de dados

## Execução
Na pasta `LABORATORIO 03`:

```powershell
python -m pytest tests/test_rq07_sensibilidade.py
python -m analises.rq07_sensibilidade --config config.yaml
```

Os resultados são gravados em `dados/rq07_classificacoes.csv`, `dados/rq07_comparacoes.csv` e `dados/rq07_resumo.json`.

## Critérios metodológicos
- C1: frequência de releases (já consolidada), lead time (a), CFR (a).
- C2: frequência de releases publicados incluindo pré-releases, lead time (b), CFR (b).
- C3: frequência de tags com datas válidas na janela, lead time (b), CFR (a).
- Recuperação permanece igual nas três definições.
- Classificação usa os cortes de `metricas/dora.py` e exige as quatro métricas disponíveis; pares usam somente a interseção completa.
- Kappa ponderado com pesos lineares, calculado por fórmula equivalente a `cohen_kappa_score(weights='linear')`.
- Dados faltantes não são preenchidos artificialmente. C3 é indisponível sem coleta completa de tags.

## Pendência de C3
Confira em `config.yaml` a opção `tags.coletar`. No projeto anteriormente enviado ela estava `false`, e `tags.csv` continha só o cabeçalho. Para completar C3, é necessário coletar tags reais de toda a amostra; essa operação pode consumir muitas chamadas à API. **Não rerode o pipeline completo sem antes avaliar o tempo e custo**, pois as etapas de releases/commits podem repetir parte do trabalho; coordene a coleta seletiva com o grupo.

## Relatório
Descreva os tamanhos das interseções C1×C2, C1×C3, C2×C3, as proporções de mudança e os kappas. Não interprete comparações com `n=0` como zero mudança. Cite limitação das métricas faltantes (279/300 completamente disponíveis na consolidação informada) e a definição alternativa de deploy.
