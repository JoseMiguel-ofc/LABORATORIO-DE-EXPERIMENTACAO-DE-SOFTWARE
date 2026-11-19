# Ética e regras da coleta

O estudo mede, de fora, serviços públicos da Steam. As regras abaixo valem para
toda a coleta e estão implementadas em `coleta/coletar.py` e `coleta/config.json`.

## 1. No máximo 1 requisição por segundo

- Cada rodada faz 7 requisições em sequência, com `sleep(1)` entre elas. O
  coletor força a pausa mínima de 1 s, mesmo se o `config.json` pedir menos.
- Há uma rodada por hora (cron `17 * * * *`): cerca de 170 requisições por dia
  no total, divididas entre `api.steampowered.com`, `store.steampowered.com` e
  `www.valvesoftware.com`. É uma carga desprezível perto do tráfego desses serviços.
- O workflow usa `concurrency`, então duas coletas nunca rodam ao mesmo tempo.
- Cada requisição tem timeout de 15 s e **não há novas tentativas**: uma falha é
  registrada como dado (indisponibilidade), sem insistir no servidor.

## 2. Respeito ao robots.txt e aos termos da Steam Web API

- `store.steampowered.com/robots.txt` (consultado em 19/11/2026) bloqueia
  `/share/`, `/news/externalpost/`, `/account/...`, `/login/...`, `/join/...`,
  `/email/` e `/widget/`. As URLs medidas (`/app/730/` e `/api/appdetails`) não
  estão nessa lista.
- `www.valvesoftware.com/robots.txt` (consultado em 19/11/2026) bloqueia apenas
  `/jobs`, `/en/jobs`, `/posting` e `/en/posting`. A página `/en/about/stats`,
  que devolve em JSON os mesmos números de "usuários online" da página oficial de
  estatísticas da Steam, é permitida e consultada uma vez por hora.
- `api.steampowered.com` é a Steam Web API pública. Os métodos usados
  (`GetServerInfo` e `GetNumberOfCurrentPlayers`) não exigem chave. O código aceita
  uma chave em `STEAM_API_KEY` (guardada em *Secrets* do GitHub) apenas para
  endpoints marcados com `usa_chave`; a chave nunca é gravada no CSV nem no log,
  porque erros registram só o tipo da exceção, não a mensagem com a URL.
- O uso é acadêmico e não comercial, e os dados brutos ficam públicos no
  repositório para reprodução, conforme os
  [Termos de Uso da Steam Web API](https://steamcommunity.com/dev/apiterms).

## 3. Nenhum dado de jogadores

- Nenhum endpoint recebe ou devolve dados pessoais: não há SteamID, perfil,
  inventário, lista de amigos nem login.
- `GetNumberOfCurrentPlayers` devolve só a contagem agregada de jogadores de um
  jogo (CS2, Dota 2 e PUBG), e a página de estatísticas da Valve devolve o total
  agregado de usuários online.
- O CSV guarda apenas: horário, endpoint, status HTTP, latência, contagens
  agregadas e o motivo de erro.

## 4. User-Agent que identifica o projeto acadêmico

Todas as requisições enviam:

```
LabExpSoftware-Steam/1.0 (projeto academico; medicao externa de latencia; +https://github.com/JoseMiguel-ofc/LABORATORIO-DE-EXPERIMENTACAO-DE-SOFTWARE)
```

Assim, quem administra os servidores consegue identificar a origem do tráfego e
chegar ao repositório. Se a Valve pedir para parar, desligamos o agendamento do
workflow na hora.

## 5. Fim da coleta

Na data de corte, o agendamento é desligado (o workflow é desativado em
*Actions*) e o dataset é congelado na tag `dados-v1.0`.
