# Lab05 — Ameaças à validade de conclusão e de construto

**Sprint 2 · Pessoa A — Método e Análise · 26/11/2026**

Este documento complementa a [proposta](proposta.md) e as
[ameaças internas e externas da Pessoa B](ameacas_interna_externa.md).
Os resultados desta etapa são exploratórios: a coleta continua, há lacunas
na série e a independência entre medições ainda não foi estabelecida.
As contagens e o período exatos devem ser lidos no relatório e nos metadados
da execução, para não confundir versões diferentes do CSV.

## Validade de conclusão

| Ameaça | Consequência para a conclusão | Mitigação nesta entrega e limite restante |
|---|---|---|
| **Assimetria, valores extremos e grupos pequenos.** A latência pode ter cauda longa; pico e fora do pico podem ter quantidades diferentes de sucessos. | A média pode representar mal o comportamento usual, e estimativas e testes ficam instáveis com poucos dados. | Mostrar n, mediana, quartis, IQR, p95, média e DP por endpoint e estrato. Manter valores extremos válidos, sem remover os que contrariam uma hipótese. H1 usa postos e H2 usa correlação de postos conforme o protocolo; suas suposições continuam necessárias. A robustez com e sem outliers é uma etapa posterior. |
| **Interpretação indevida do teste de normalidade.** Com poucas observações, Shapiro–Wilk tem pouca informação para detectar desvios; séries dependentes também limitam sua leitura. | Um p alto pode ser apresentado incorretamente como prova de normalidade, ou usado para escolher o teste que produz o menor p. | Normalidade é um diagnóstico separado, com tamanho do grupo e motivo quando não estimável. Não muda automaticamente os testes previstos. p ≥ 0,05 significa apenas que o diagnóstico não rejeitou a referência normal. Ver [documentação de Shapiro–Wilk](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.shapiro.html). |
| **Autocorrelação e ciclos diários/semanais.** Requisições próximas compartilham rede, carga e estado do serviço. | O número de linhas pode exagerar a informação independente; valores-p calculados como se todas as linhas fossem independentes podem ficar descalibrados. | Preservar timestamps e ordem temporal; analisar endpoints separadamente e manter os valores-p como exploratórios. Antes da inferência final, avaliar séries regulares e escolher método compatível, como blocos temporais, justificando tamanho e quantidade de blocos. Esse tratamento não é substituído pelo uso de testes não paramétricos. |
| **Lacunas e mudança do agendamento.** A primeira semana contém omissões e o mecanismo de disparo mudou em 26/11/2026. | Grupos de horários podem ficar desbalanceados, e observações consecutivas no arquivo podem estar separadas por muitas horas. | Informar o recorte utilizado e consultar a cobertura da Pessoa B. Usar o horário real da requisição para os grupos. Não preencher latências ou falhas para horas ausentes. Uma autocorrelação por posição no CSV não pode ser chamada de autocorrelação de uma hora quando há lacunas. A orientação do [NIST sobre autocorrelação](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35c.htm) pressupõe observações igualmente espaçadas. |
| **Pseudorreplicação.** A mesma contagem de usuários aparece em vários endpoints; uma hora também pode ter disparos extras. | Multiplicar o n por seis ou incluir repetidas tentativas de uma hora como réplicas independentes produz precisão artificial. | Uma observação por endpoint e hora UTC de calendário, conservando a primeira tentativa. Contabilizar as exclusões; não somar os endpoints como uma única amostra. Cada endpoint tem sua análise de H1–H3. |
| **Comparações múltiplas e seleção de resultados.** Há três hipóteses e seis endpoints. | Reportar apenas valores-p pequenos aumenta a chance de conclusões ocasionais. | Mostrar todas as hipóteses e valores-p brutos e ajustados por Holm nas famílias definidas no [método](metodo_analise_sprint2.md). Hipóteses sem dados continuam reservadas na família. Ajustar multiplicidade não corrige os valores-p individuais se sua suposição de independência temporal for inadequada. |
| **Poucas falhas ou nenhuma medição na janela candidata.** H3 depende de tentativas nos dois grupos, além de eventos informativos. | Ausência de registro pode ser confundida com ausência de efeito; uma razão de chances pode ficar indefinida. | Exibir a tabela 2×2 e os denominadores. Sem um grupo, H3 é não estimável. Sem falhas em ambos os grupos, o Fisher pode produzir p = 1, mas OR permanece indefinida e não se conclui igualdade. Não adicionar pseudofalhas nem uma correção arbitrária só para obter um número. |
| **Poder planejado diferente do poder com a coleta real.** A simulação inicial usa cenários e cobertura declarados; o CSV pode ter menos horas e dependência maior. | Um teste não significativo pode ser tomado como evidência de inexistência de associação. | Confrontar cobertura e n reais com as premissas, sem tratar linhas de endpoints diferentes como horas adicionais. Reportar magnitude e limitações. A não rejeição não prova equivalência. Não usar o efeito observado para declarar retrospectivamente que o estudo tinha poder suficiente. |

A introdução de métodos para séries temporais e a análise de sensibilidade
devem ser registradas antes da interpretação final. Com dados escassos, uma
conclusão descritiva pode ser o resultado adequado. A ordem e a estrutura
temporal fazem parte do desenho, conforme a
[introdução do NIST à análise de séries temporais](https://www.itl.nist.gov/div898/handbook/pmc/section4/pmc41.htm).

## Validade de construto

| Construto pretendido | O que o instrumento realmente mede | Mitigação e linguagem permitida |
|---|---|---|
| **Latência percebida por quem usa a Steam.** | Tempo de uma requisição HTTP externa até a resposta completa, incluindo conexão, rede e possível cache. Não mede a latência dentro do jogo, matchmaking, download ou todas as interações do cliente. | Usar “latência HTTP observada do endpoint”, unidade ms e origem de medição explícita. Limitar as conclusões aos serviços consultados. Uma resposta HTTP mais rápida não demonstra melhor experiência dentro do jogo. |
| **Uso da plataforma.** | `usuarios_online` é uma contagem agregada da fonte oficial; `jogadores_top` soma somente os aplicativos monitorados. São variáveis diferentes. | H2 usa `usuarios_online`. Manter `jogadores_top` como aproximação auxiliar identificada, sem substituir silenciosamente uma pela outra nem imputar zero quando a consulta falha. A [documentação Steamworks](https://partner.steamgames.com/doc/webapi/ISteamUserStats) define `GetNumberOfCurrentPlayers` como jogadores ativos de um aplicativo e não inclui quem joga desconectado. |
| **Pico de utilização.** | Categoria operacional de horário, 14:00–22:00 UTC, definida na proposta; ela não identifica diretamente o pico real em cada dia. | Descrever o grupo como “período candidato de pico”. Não redefinir os limites após procurar a maior latência ou o menor valor-p. A relação com o uso efetivamente observado é examinada separadamente em H2. |
| **Manutenção efetivamente ocorrida.** | Pertencimento à janela candidata de terça, 15:00–18:00 em `America/Los_Angeles`; o CSV não contém confirmação de intervenção da Valve. | Converter o timestamp com o fuso correto e chamar a variável de “janela candidata”. Uma falha dentro dela não identifica a causa; uma intervenção fora dela pode não ser capturada. Registros externos de incidentes são contexto, não rótulos automáticos de manutenção. |
| **Disponibilidade contínua da Steam.** | Sucesso entre tentativas observadas e classificáveis de um endpoint. Uma requisição por hora pode não capturar interrupções curtas. | Apresentar sucessos/tentativas válidas, n e cobertura separadamente. Hora sem coleta não vira falha nem sucesso. Não traduzir 100% das tentativas em 100% de uptime global. |
| **Resposta funcionalmente correta.** | Status HTTP de 200–399 e ausência de erro segundo o coletor; a validação semântica varia por endpoint. | Preservar status e motivo de erro. Diferenciar HTTP disponível de sucesso operacional e evitar afirmar que toda resposta 2xx comprova todas as funcionalidades. A consulta auxiliar `ValveStats` não entra como serviço adicional estudado. |
| **Aumento causado por usuários ou manutenção.** | Associação observacional entre variáveis sujeitas a ciclos e condições compartilhadas. | Empregar “associação” e “diferença observada”. Sem intervenção e controle dos fatores de confusão, nenhum dos testes estabelece causalidade. |

## Critério de interpretação desta sprint

O [método da Sprint 2](metodo_analise_sprint2.md) registra a escolha dos testes,
os grupos e o tratamento de casos não estimáveis. A entrega deve distinguir:

1. **Resultado calculável:** há dados suficientes para executar a fórmula.
2. **Evidência exploratória:** o número pode descrever este recorte, acompanhado
   das suposições e dos valores-p ajustados.
3. **Inferência confirmatória adequada:** exige recorte e protocolo fechados,
   cobertura avaliada e tratamento defensável da dependência temporal.

Os dois primeiros níveis não implicam o terceiro. Nesta etapa, os valores-p
convencionais e os diagnósticos de normalidade permanecem exploratórios.

As fontes eletrônicas citadas foram consultadas em **26/11/2026**.
