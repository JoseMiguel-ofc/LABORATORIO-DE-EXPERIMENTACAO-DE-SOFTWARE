# Lab03S01 — Entrega da Pessoa C

## Arquivos implementados

- `pipeline/api_client.py`: ClienteGitHub, paginação, autenticação, rate limit, backoff.
- `pipeline/cache.py`: cache JSON e retomada entre execuções.
- `pipeline/runs.py`: runs mensais, subdivisão do limite de 1000, CSVs.
- `metricas/cfr.py`: CFR(a) como fração.
- `metricas/recuperacao.py`: episódios por workflow, mediana em horas, censura.
- `tests/test_pessoa_c.py`: testes sem rede.
- `.github/workflows/testes.yml` **na raiz do repositório Git**, fora desta pasta.

## Arquivos existentes atualizados

- `tests/test_integracao_pessoa_b.py`: isola a etapa da Pessoa B da coleta de runs,
  para que o teste de integração da Pessoa B continue validando apenas suas saídas.
- `RELATORIO_LAB03.md`: hipótese H7 (RQ07) antes da coleta.
- `README.md`: documentação da entrega e saídas.
- `.gitignore`: ignora artefatos de Python e testes.

## Validação

Na pasta `LABORATORIO 03`:

```bash
python -m pip install -r requirements.txt
python -m pytest --cov=pipeline --cov=metricas --cov-report=term-missing --cov-fail-under=80
```

**Resultado local:** 162 testes aprovados; cobertura geral de 94,70%.

## Pendências antes da coleta real

1. Confirmar datas oficiais e editar `config.yaml`: `janela.inicio`, `janela.fim`
   e a data do filtro `busca.filtro_extra`.
2. Configurar o token de acesso do GitHub em `GITHUB_TOKEN`, nunca no Git.
3. Rodar `python -m pipeline --config config.yaml`.
4. Conferir `dados/metricas_ci.csv` e a coluna `coleta_completa`. Se houver
   `False`, revisar os erros no log antes de considerar a amostra completa.
5. Conferir se a CI foi criada na raiz do repositório e associar commits à Issue.

**Limite:** a coleta real dos 100 repositórios não foi executada neste ambiente;
os testes utilizaram respostas simuladas da API do GitHub.
