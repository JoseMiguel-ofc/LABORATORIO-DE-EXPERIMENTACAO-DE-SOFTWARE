# Soluções dos Katas

Coloque aqui o código final de cada trial (kata resolvido), com nome de arquivo no padrão:

```text
integrante__kata__tratamento.py
```

- **integrante**: mesmo nome usado no script de cronometragem (`coletar_tempo.py`);
- **kata**: mesmo nome do kata usado no trial;
- **tratamento**: `COM_IA` ou `SEM_IA`.

Exemplo:

```text
Pedro__ReposicaoEstoque__COM_IA.py
Pedro__ExcessoBagagem__SEM_IA.py
```

Esse padrão permite que o script `metricas_estaticas.py` (em `S01/scripts/`) identifique automaticamente integrante/kata/tratamento de cada arquivo e depois cruze essas métricas com os tempos coletados em `S02/resultados/tempos_trials.csv`.

Consulte os [enunciados, modelos e comandos de testes da S01](../S01/README.md). Cada integrante resolve um kata por tratamento, conforme a alocação do protocolo.
