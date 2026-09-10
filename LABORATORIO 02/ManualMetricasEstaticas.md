# Manual de Utilização - Métricas Estáticas (Radon)

## Objetivo

O script `metricas_estaticas.py` calcula, para cada solução de kata, as métricas estáticas usadas no *Laboratório 02 - Assistentes de IA vs. Codificação Manual*:

- LOC, LLOC, SLOC, comentários e linhas em branco (via `radon.raw`);
- Complexidade ciclomática por função/método (via `radon.complexity`), consolidada em total, média e máxima por arquivo.

---

## Requisitos

- Python 3 instalado;
- Dependências do arquivo `requirements.txt`.

Instale as dependências (rodar dentro de `LABORATORIO 02/S01/scripts/`):

```bash
pip install -r requirements.txt
```

Recomenda-se usar um ambiente virtual:

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

---

## Estrutura

```text
LABORATORIO 02/
├── S01/
│   └── scripts/
│       ├── coletar_tempo.py
│       ├── metricas_estaticas.py
│       └── requirements.txt
├── S02/
│   └── resultados/
│       ├── tempos_trials.csv
│       └── metricas_estaticas.csv
└── solucoes/
    └── {integrante}__{kata}__{tratamento}.py
```

## Convenção de nomes das soluções

Cada solução final de um trial deve ser salva em `LABORATORIO 02/solucoes/` com o nome:

```text
integrante__kata__tratamento.py
```

Exemplo: `Pedro__FizzBuzz__COM_IA.py`. Os campos `integrante` e `kata` devem ser os mesmos usados no `coletar_tempo.py`, e `tratamento` deve ser `COM_IA` ou `SEM_IA`. Isso garante que as métricas estáticas possam ser cruzadas com os tempos de cada trial pela combinação (integrante, kata, tratamento).

---

## Uso

### Analisar todas as soluções da pasta `solucoes/`

```bash
python metricas_estaticas.py
```

Isso lê todos os `.py` de `LABORATORIO 02/solucoes/`, calcula as métricas e salva o resultado em `LABORATORIO 02/S02/resultados/metricas_estaticas.csv`.

### Analisar um arquivo específico (fora do padrão de nomes)

```bash
python metricas_estaticas.py --arquivo caminho\para\arquivo.py --integrante Pedro --kata FizzBuzz --tratamento COM_IA
```

### Outras opções

```bash
python metricas_estaticas.py --pasta OUTRA_PASTA --saida OUTRO_ARQUIVO.csv
```

---

## Saída (`metricas_estaticas.csv`)

| Coluna | Descrição |
|---|---|
| integrante | Quem resolveu o kata |
| kata | Nome do kata |
| tratamento | `COM_IA` ou `SEM_IA` |
| arquivo | Nome do arquivo analisado |
| loc | Total de linhas |
| lloc | Linhas lógicas de código |
| sloc | Linhas de código-fonte (sem brancos/comentários) |
| comentarios | Linhas de comentário |
| linhas_em_branco | Linhas em branco |
| num_blocos | Quantidade de funções/métodos analisados |
| complexidade_total | Soma da complexidade ciclomática dos blocos |
| complexidade_media | Média da complexidade ciclomática dos blocos |
| complexidade_maxima | Maior complexidade ciclomática entre os blocos |
| erro | Preenchido se o arquivo não seguiu o padrão de nome ou teve erro de sintaxe |

Arquivos que não seguirem o padrão de nomes, ou que tiverem erro de sintaxe, aparecem no CSV com a coluna `erro` preenchida em vez de serem descartados silenciosamente.
