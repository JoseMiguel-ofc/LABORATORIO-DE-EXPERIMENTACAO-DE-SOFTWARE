## Estatística descritiva (RQ 01 a 04)

| RQ | Métrica | n | Mediana | Q1 | Q3 | IQR |
|---|---|---:|---:|---:|---:|---:|
| RQ 01 | Frequência de deploy | 300 | 0,32/semana | 0,15/semana | 0,82/semana | 0,67/semana |
| RQ 02 | Lead time (a) por release | 300 | 12,8 dias | 3,0 dias | 39,9 dias | 36,9 dias |
| RQ 02 | Lead time (b) por commit | 300 | 8,5 dias | 2,1 dias | 36,5 dias | 34,4 dias |
| RQ 03 | CFR (a) proxy de CI | 300 | 5,6% | 1,9% | 14,5% | 12,6% |
| RQ 03 | CFR (b) proxy de entrega | 299 | 11,1% | 0,0% | 27,5% | 27,5% |
| RQ 04 | Tempo de recuperação | 279 | 3,7 h | 0,9 h | 20,1 h | 19,2 h |

## Categorias DORA na combinação de referência (C1)

| Métrica | Elite | High | Medium | Low | Sem dado |
|---|---:|---:|---:|---:|---:|
| Frequência de deploy | 7 (2%) | 51 (17%) | 131 (44%) | 111 (37%) | 0 (0%) |
| Lead time (a) | 51 (17%) | 62 (21%) | 91 (30%) | 96 (32%) | 0 (0%) |
| CFR (a) | 228 (76%) | 35 (12%) | 19 (6%) | 18 (6%) | 0 (0%) |
| Tempo de recuperação | 72 (24%) | 150 (50%) | 37 (12%) | 20 (7%) | 21 (7%) |
| Classificação geral | 20 (7%) | 111 (37%) | 130 (43%) | 39 (13%) | 0 (0%) |

## Casos censurados

| Item | Valor |
|---|---:|
| Episódios de falha resolvidos (RQ 04) | 12051 |
| Episódios de falha censurados (RQ 04) | 200 |
| Repositórios com ao menos 1 episódio censurado | 108 |
| Mediana da proporção de episódios censurados por repositório | 0 |
| Repositórios sem episódio resolvido (sem tempo de recuperação) | 21 |
| Releases censuradas no CFR (b) (últimos 7 dias da janela) | 295 |
