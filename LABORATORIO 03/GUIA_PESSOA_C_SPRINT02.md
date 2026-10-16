# Sprint 02 — Pessoa C

## Entregue neste pacote

- `pipeline/consolidar.py`: lê quatro CSVs existentes, faz junção por `full_name`, valida chaves, dados e funil, calcula categorias de referência sem inventar valores ausentes e gera `dados/metricas_consolidadas.csv` e `dados/resumo_consolidacao.json`.
- `dados/dicionario_dados.md`: origens, campos, unidades, definições, ausências e procedimentos reprodutíveis.
- `tests/test_consolidar.py`: 18 testes novos de integração local e casos de erro.
- Os CSVs atuais (100 repositórios) **foram preservados**; o resultado de consolidação local dos 100 foi gerado como demonstração, mas **não representa a coleta final**.

## Validado

`python -m pytest -q --cov=pipeline --cov=metricas --cov=validacao --cov-fail-under=80`: **349 passed, cobertura total 95,09%** neste pacote (ambiente de teste). A cobertura de `pipeline/consolidar.py` foi 83%.

## Falta concluir com dados reais

A amostra atual é de 100 repositórios. Para completar a Sprint 02, use a janela oficial do professor no `config.yaml`, aumente `amostra.tamanho` para 300, faça a coleta real com `GITHUB_TOKEN`, execute o CFR de entrega da Pessoa B e consolide. Não commite o token, cache bruto, `.coverage`, `__pycache__` ou `.pytest_cache`.

### Comandos (PowerShell, na pasta `LABORATORIO 03`)

```powershell
python -m pip install -r requirements.txt
python -m pytest --cov=pipeline --cov=metricas --cov=validacao --cov-fail-under=80
# Quando as datas oficiais estiverem confirmadas, ajuste config.yaml:
# amostra.tamanho: 300; janela.inicio/fim; busca.filtro_extra
$env:GITHUB_TOKEN = "SEU_TOKEN"
python -m pipeline --config config.yaml
python -m pipeline.cfr_entrega --config config.yaml
python -m pipeline.consolidar --config config.yaml --exigir-300
```

**Atenção:** a execução do pipeline regrava CSVs; faça backup dos arquivos da coleta atual antes. A flag `--exigir-300` faz a consolidação devolver erro se a amostra ficar abaixo da meta, embora os CSVs gerados continuem disponíveis para diagnóstico.

### Atenção ao GitHub

Crie/associe uma Issue da Sprint 02 à Pessoa C; o commit precisa mencionar seu número. Antes de comitar, confira no GitHub Desktop a lista de alterações e inclua apenas os arquivos correspondentes à sua responsabilidade. A rotulagem independente da amostra-ouro precisa ser feita por cada integrante, sem copiar rótulos uns dos outros.
