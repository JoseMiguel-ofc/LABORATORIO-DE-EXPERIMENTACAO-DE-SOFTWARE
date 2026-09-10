# Manual de Utilização - Script de Cronometragem dos Katas

## Objetivo

O script `coletar_tempo.py` foi desenvolvido para registrar o tempo de execução dos katas do *Laboratório 02 - Assistentes de IA vs. Codificação Manual*.

Ele deve ser utilizado pelos integrantes do grupo durante a execução dos katas, tanto no tratamento `COM_IA` quanto no tratamento `SEM_IA`.

O script registra automaticamente:

- Integrante responsável pelo trial;
- Kata executado;
- Tratamento utilizado;
- Horário de início;
- Horário de término;
- Tempo total em segundos;
- Tempo total em minutos;
- Informação sobre censura por limite de tempo.

---

## Requisitos

É necessário possuir:

- Python 3 instalado;
- Acesso ao repositório do grupo;
- Terminal, PowerShell ou Prompt de Comando.

O script utiliza apenas bibliotecas padrão do Python, portanto não é necessário instalar dependências adicionais.

---

## Estrutura

O script está localizado em:

```text
LABORATORIO 02/
└── S01/
    └── scripts/
        └── coletar_tempo.py
