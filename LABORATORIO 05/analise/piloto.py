"""Estatísticas descritivas das primeiras 24 ou 48 horas da coleta Steam.

O CSV bruto é somente lido. Ausências no agendamento não são convertidas em
falhas, e tempos de requisições com erro não são misturados às latências de
sucessos. Não são executados testes de hipótese nesta etapa.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

LAB05 = Path(__file__).resolve().parents[1]
CSV_PADRAO = LAB05 / "dados" / "brutos" / "coleta.csv"
CONFIG_PADRAO = LAB05 / "coleta" / "config.json"
SAIDA_PADRAO = LAB05 / "resultados" / "piloto"
COLUNAS = ("timestamp", "endpoint", "status", "latencia_ms", "usuarios_online",
           "erro", "jogadores_top")


def _configuracao(config: dict | str | Path | None) -> dict:
    if isinstance(config, dict):
        return config
    with open(config or CONFIG_PADRAO, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _timestamp_utc(valor: str) -> pd.Timestamp:
    try:
        momento = datetime.fromisoformat(str(valor).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"timestamp inválido: {valor!r}; use ISO 8601 com fuso.") from exc
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise ValueError(f"timestamp sem fuso: {valor!r}; use UTC/Z ou um offset explícito.")
    return pd.Timestamp(momento).tz_convert("UTC")


def _numero_valido(serie: pd.Series, *, inteiro: bool = False) -> pd.Series:
    valores = pd.to_numeric(serie, errors="coerce").astype(float)
    validos = np.isfinite(valores) & (valores >= 0)
    if inteiro:
        validos &= valores.eq(np.floor(valores))
    return valores.where(validos)


def carregar_dados(caminho: str | Path = CSV_PADRAO, *,
                   config: dict | str | Path | None = None) -> pd.DataFrame:
    """Carrega e normaliza o CSV; registra exclusões em ``df.attrs``.

    Linhas com o mesmo par (timestamp, endpoint) conservam a primeira ocorrência.
    Endpoints desconhecidos e a consulta auxiliar ValveStats permanecem no frame
    auditável e são excluídos posteriormente das estatísticas dos serviços.
    """
    caminho = Path(caminho)
    configuracao = _configuracao(config)
    try:
        bruto = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError as exc:
        raise ValueError("CSV vazio: o cabeçalho do coletor é necessário.") from exc
    faltantes = set(COLUNAS) - set(bruto.columns)
    if faltantes:
        raise ValueError("Colunas obrigatórias ausentes: " + ", ".join(sorted(faltantes)))
    df = bruto.loc[:, COLUNAS].copy()
    df["timestamp"] = pd.Series([_timestamp_utc(x) for x in df["timestamp"]],
                                dtype="datetime64[ns, UTC]")
    df["endpoint"] = df["endpoint"].str.strip()
    if df["endpoint"].eq("").any():
        raise ValueError("Há uma medição sem nome de endpoint.")
    df["erro"] = df["erro"].str.strip()
    duplicadas = df.duplicated(["timestamp", "endpoint"], keep="first")
    repetidas = df.loc[df.duplicated(["timestamp", "endpoint"], keep=False)]
    conflitos = int((repetidas.drop_duplicates().groupby(
        ["timestamp", "endpoint"]).size() > 1).sum())
    df = df.loc[~duplicadas].copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
    for coluna in ("latencia_ms", "usuarios_online", "jogadores_top"):
        df[coluna] = _numero_valido(df[coluna], inteiro=coluna != "latencia_ms")
    status = _numero_valido(df["status"], inteiro=True)
    df["status"] = status.where(status.between(100, 599)).astype("Int64")
    df["disponivel_http"] = df["status"].between(200, 399).fillna(False).astype(bool)
    # Um HTTP 1xx isolado não é uma resposta final. Ausência/invalidade do
    # código sem motivo registrado não permite decidir sucesso ou falha.
    df["tentativa_classificavel"] = (
        df["status"].between(200, 599).fillna(False) | df["erro"].ne("")).astype(bool)
    df["sucesso_operacional"] = df["disponivel_http"] & df["erro"].eq("")
    nomes = [x["nome"] for x in configuracao["endpoints"]]
    auxiliar = configuracao.get("usuarios_online", {}).get("nome", "ValveStats")
    desconhecidos = sorted(set(df["endpoint"]) - set(nomes) - {auxiliar})
    df.attrs["diagnostico"] = {
        "linhas_brutas": len(bruto), "duplicatas_excluidas": int(duplicadas.sum()),
        "pares_duplicados_com_valores_divergentes": conflitos,
        "linhas_apos_deduplicacao": len(df),
        "endpoints_desconhecidos": desconhecidos,
        "medicoes_endpoints_desconhecidos": int(df["endpoint"].isin(desconhecidos).sum()),
        "latencias_ausentes_ou_invalidas": int(df["latencia_ms"].isna().sum()),
        "status_ausentes_ou_invalidos": int(df["status"].isna().sum()),
    }
    df.attrs["entrada"] = str(caminho.resolve())
    df.attrs["sha256_csv"] = hashlib.sha256(caminho.read_bytes()).hexdigest()
    return df


def _iso(momento: pd.Timestamp | None) -> str | None:
    return None if momento is None else momento.isoformat().replace("+00:00", "Z")


def analisar_piloto(dados: pd.DataFrame, *, horas: int = 48,
                    config: dict | str | Path | None = None) -> dict:
    """Descreve a janela semiaberta ``[primeiro timestamp, início + horas)``.

    O denominador da cobertura são os 24/48 intervalos planejados, ancorados no
    início da janela. As horas de calendário UTC são relatadas separadamente.
    Uma proporção de sucessos entre tentativas observadas não estima uptime.
    """
    if horas not in (24, 48):
        raise ValueError("horas deve ser 24 ou 48.")
    configuracao = _configuracao(config)
    nomes = [x["nome"] for x in configuracao["endpoints"]]
    auxiliar = configuracao.get("usuarios_online", {}).get("nome", "ValveStats")
    inicio = None if dados.empty else dados["timestamp"].min()
    fim = None if inicio is None else inicio + pd.Timedelta(hours=horas)
    janela = dados.copy() if inicio is None else dados.loc[
        dados["timestamp"].ge(inicio) & dados["timestamp"].lt(fim)].copy()
    if inicio is None:
        janela["intervalo_horario"] = pd.Series(dtype="int64")
    else:
        janela["intervalo_horario"] = (
            (janela["timestamp"] - inicio) / pd.Timedelta(hours=1)).astype(int)
    janela["hora_utc"] = janela["timestamp"].dt.floor("h")
    servicos = janela.loc[janela["endpoint"].isin(nomes)].copy()
    linhas = []
    for nome in nomes:
        grupo = servicos.loc[servicos["endpoint"].eq(nome)]
        sucessos = grupo.loc[grupo["sucesso_operacional"]]
        latencias = sucessos["latencia_ms"].dropna()
        n, n_http, n_sucessos = len(grupo), int(grupo["disponivel_http"].sum()), len(sucessos)
        n_validos = int(grupo["tentativa_classificavel"].sum())
        intervalos = int(grupo["intervalo_horario"].nunique())
        linhas.append({
            "endpoint": nome, "medicoes": n, "tentativas_classificaveis": n_validos,
            "tentativas_nao_classificaveis": n - n_validos,
            "sucessos_operacionais": n_sucessos,
            "falhas_operacionais": n_validos - n_sucessos, "respostas_http_disponiveis": n_http,
            "disponibilidade_http_observada_pct": 100 * n_http / n_validos if n_validos else np.nan,
            "sucesso_operacional_observado_pct": 100 * n_sucessos / n_validos if n_validos else np.nan,
            "latencias_sucesso_validas": len(latencias),
            "latencias_ausentes_ou_invalidas": int(grupo["latencia_ms"].isna().sum()),
            "latencia_media_ms": latencias.mean(), "latencia_dp_ms": latencias.std(ddof=1),
            "latencia_p25_ms": latencias.quantile(.25),
            "latencia_p50_ms": latencias.quantile(.50),
            "latencia_p75_ms": latencias.quantile(.75),
            "latencia_iqr_ms": latencias.quantile(.75) - latencias.quantile(.25),
            "latencia_p95_ms": latencias.quantile(.95),
            "usuarios_online_ausentes": int(grupo["usuarios_online"].isna().sum()),
            "intervalos_horarios_com_dados": intervalos,
            "horas_calendario_utc_com_dados": int(grupo["hora_utc"].nunique()),
            "cobertura_horaria_pct": 100 * intervalos / horas,
        })
    resumo = pd.DataFrame(linhas)
    # Uma contagem por hora, preferindo a consulta auxiliar original. Valores
    # replicados nos endpoints da mesma rodada não viram novas observações.
    usuarios = []
    for hora, grupo in janela.groupby("hora_utc", sort=True):
        conhecidos = grupo.loc[grupo["endpoint"].isin(nomes + [auxiliar])]
        if conhecidos.empty:
            continue
        contagens = conhecidos.loc[conhecidos["usuarios_online"].notna()]
        prioritarias = contagens.loc[contagens["endpoint"].eq(auxiliar)]
        escolhida = (prioritarias if not prioritarias.empty else contagens).head(1)
        jogadores = conhecidos.loc[conhecidos["jogadores_top"].notna(), "jogadores_top"]
        usuarios.append({"hora_utc": hora,
                         "timestamp_fonte": escolhida["timestamp"].iloc[0] if len(escolhida) else pd.NaT,
                         "usuarios_online": escolhida["usuarios_online"].iloc[0] if len(escolhida) else np.nan,
                         "jogadores_top": jogadores.iloc[0] if len(jogadores) else np.nan,
                         "valores_usuarios_distintos_na_hora": int(contagens["usuarios_online"].nunique())})
    populacao = pd.DataFrame(usuarios, columns=["hora_utc", "timestamp_fonte", "usuarios_online",
                                               "jogadores_top", "valores_usuarios_distintos_na_hora"])
    duracao = 0.0 if dados.empty else float((dados["timestamp"].max() - inicio).total_seconds() / 3600)
    amplit_janela = 0.0 if janela.empty else float(
        (janela["timestamp"].max() - inicio).total_seconds() / 3600)
    minimos = bool(duracao >= 24 and resumo["latencias_sucesso_validas"].ge(2).all())
    avisos = [
        "Percentuais de HTTP disponível e sucesso operacional usam somente tentativas classificáveis observadas; não são uptime.",
        "Status ausente, inválido ou apenas HTTP 1xx sem erro registrado é não classificável; não conta como falha nem entra no denominador de sucesso.",
        "Intervalos sem medição representam ausência de dados, não falha do serviço.",
        "Latências de falhas e timeouts foram excluídas das estatísticas de latência de sucesso.",
        "Percentis com poucas observações são apenas descritivos; DP com n=1 permanece ausente.",
        "A série de usuários usa uma observação por hora UTC; réplicas entre endpoints não aumentam n.",
    ]
    if not minimos:
        avisos.insert(0, "Piloto parcial: aguardar ao menos 24 horas e medições repetidas dos endpoints antes de concluir a análise.")
    diagnostico = dict(dados.attrs.get("diagnostico", {}))
    if diagnostico.get("endpoints_desconhecidos"):
        avisos.append("Endpoints desconhecidos foram excluídos da análise dos serviços e da série de população.")
    if diagnostico.get("pares_duplicados_com_valores_divergentes"):
        avisos.append("Há identificadores (timestamp, endpoint) repetidos com valores divergentes; foi conservada a primeira ocorrência, mantendo o bruto para auditoria.")
    metadados = {
        "status": "disponivel_para_inspecao" if minimos else "parcial",
        "horas_planejadas": horas, "janela_inicio_inclusivo_utc": _iso(inicio),
        "janela_fim_exclusivo_utc": _iso(fim), "duracao_coleta_observada_h": duracao,
        "amplitude_observada_na_janela_h": amplit_janela,
        "intervalos_horarios_com_dados": int(servicos["intervalo_horario"].nunique()),
        "horas_calendario_utc_com_dados": int(servicos["hora_utc"].nunique()),
        "cobertura_horaria_pct": 100 * servicos["intervalo_horario"].nunique() / horas,
        "linhas_na_janela": len(janela), "medicoes_servicos_na_janela": len(servicos),
        "tentativas_classificaveis_na_janela": int(servicos["tentativa_classificavel"].sum()),
        "tentativas_nao_classificaveis_na_janela": int((~servicos["tentativa_classificavel"]).sum()),
        "medicoes_auxiliares_na_janela": int(janela["endpoint"].eq(auxiliar).sum()),
        "linhas_fora_da_janela": len(dados) - len(janela),
        "endpoints_esperados": nomes, "diagnostico_entrada": diagnostico,
        "usuarios_horas_observadas": int(populacao["usuarios_online"].notna().sum()),
        "horas_com_contagens_usuarios_conflitantes": int(
            populacao["valores_usuarios_distintos_na_hora"].gt(1).sum()),
        "entrada": dados.attrs.get("entrada"), "sha256_csv": dados.attrs.get("sha256_csv"),
        "avisos": avisos,
    }
    return {"dados": servicos, "resumo_endpoints": resumo,
            "usuarios_por_hora": populacao, "metadados": metadados}


def _grafico(analise: dict, caminho: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    resumo, populacao = analise["resumo_endpoints"], analise["usuarios_por_hora"]
    fig, eixos = plt.subplots(2, 2, figsize=(15, 10), constrained_layout=True)
    ax = eixos[0, 0]
    validos = resumo.loc[resumo["latencias_sucesso_validas"].gt(0)]
    if validos.empty:
        ax.text(.5, .5, "Sem latências de sucesso válidas", ha="center", va="center", transform=ax.transAxes)
    else:
        pos = np.arange(len(validos))
        ax.barh(pos, validos["latencia_p50_ms"], color="#2563eb", label="p50")
        ax.scatter(validos["latencia_p95_ms"], pos, color="#d97706", marker="D", label="p95", zorder=3)
        ax.set_yticks(pos, validos["endpoint"])
        ax.invert_yaxis()
        ax.legend()
    ax.set(xlabel="Latência de sucesso (ms)", title="Latências observadas por serviço")
    ax = eixos[0, 1]
    medidos = resumo.loc[resumo["tentativas_classificaveis"].gt(0)]
    if medidos.empty:
        ax.text(.5, .5, "Sem tentativas classificáveis", ha="center", va="center", transform=ax.transAxes)
    else:
        pos = np.arange(len(medidos))
        ax.barh(pos - .17, medidos["disponibilidade_http_observada_pct"], height=.32,
                color="#2563eb", label="HTTP 200–399")
        ax.barh(pos + .17, medidos["sucesso_operacional_observado_pct"], height=.32,
                color="#059669", label="Sucesso operacional")
        ax.set_yticks(pos, [f"{r.endpoint} (n válido={r.tentativas_classificaveis}/{r.medicoes})"
                           for r in medidos.itertuples()])
        ax.invert_yaxis()
        ax.legend(loc="upper center", bbox_to_anchor=(.5, -.15), ncol=2)
    ax.set(xlim=(0, 105), xlabel="% das tentativas classificáveis", title="Respostas observadas — não representa uptime")
    ax = eixos[1, 0]
    dados = analise["dados"]
    houve = False
    for nome, grupo in dados.loc[dados["sucesso_operacional"] & dados["latencia_ms"].notna()].groupby("endpoint"):
        ax.plot(grupo["timestamp"], grupo["latencia_ms"], marker="o", markersize=3,
                linewidth=1, label=nome)
        houve = True
    if houve:
        ax.legend(fontsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m\n%H:%M", tz=timezone.utc))
        tempos = dados.loc[dados["sucesso_operacional"] & dados["latencia_ms"].notna(), "timestamp"]
        if tempos.max() - tempos.min() < pd.Timedelta(hours=1):
            momento = tempos.min() + (tempos.max() - tempos.min()) / 2
            ax.set_xlim(momento - pd.Timedelta(minutes=30), momento + pd.Timedelta(minutes=30))
    else:
        ax.text(.5, .5, "Sem latências de sucesso válidas", ha="center", va="center", transform=ax.transAxes)
    ax.set(xlabel="Início da requisição (UTC)", ylabel="Latência de sucesso (ms)", title="Série temporal dos serviços")
    ax = eixos[1, 1]
    validos = populacao.loc[populacao["usuarios_online"].notna()]
    if validos.empty:
        ax.text(.5, .5, "Sem contagens de usuários válidas", ha="center", va="center", transform=ax.transAxes)
    else:
        ax.plot(validos["hora_utc"], validos["usuarios_online"] / 1e6,
                marker="o", color="#7c3aed")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m\n%H:%M", tz=timezone.utc))
        if validos["hora_utc"].max() - validos["hora_utc"].min() < pd.Timedelta(hours=1):
            momento = validos["hora_utc"].min() + (
                validos["hora_utc"].max() - validos["hora_utc"].min()) / 2
            ax.set_xlim(momento - pd.Timedelta(minutes=30), momento + pd.Timedelta(minutes=30))
    ax.set(xlabel="Hora (UTC)", ylabel="Usuários online (milhões)", title="População — uma observação por hora")
    for ax in eixos.flat:
        ax.grid(axis="x", alpha=.2)
    estado = "piloto parcial" if analise["metadados"]["status"] == "parcial" else "inspeção descritiva do piloto"
    fig.suptitle(f"Steam · primeiras {analise['metadados']['horas_planejadas']} horas · {estado}", fontsize=16)
    fig.savefig(caminho, dpi=150)
    plt.close(fig)


def gerar_relatorio(entrada: str | Path = CSV_PADRAO, saida: str | Path = SAIDA_PADRAO,
                    *, horas: int = 48, config: dict | str | Path | None = None) -> dict:
    """Salva tabelas, PNG e metadados reproduzíveis sem modificar a coleta."""
    analise = analisar_piloto(carregar_dados(entrada, config=config), horas=horas, config=config)
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    caminhos = {"resumo_endpoints": saida / "resumo_endpoints.csv",
                "usuarios_por_hora": saida / "usuarios_por_hora.csv",
                "grafico": saida / "piloto.png", "metadados": saida / "metadados.json"}
    for nome in ("resumo_endpoints", "usuarios_por_hora"):
        analise[nome].to_csv(caminhos[nome], index=False, float_format="%.8g")
    _grafico(analise, caminhos["grafico"])
    import matplotlib
    metadados = analise["metadados"]
    metadados["gerado_em_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    metadados["versoes"] = {"python": platform.python_version(), "numpy": np.__version__,
                            "pandas": pd.__version__, "matplotlib": matplotlib.__version__}
    metadados["sha256_codigo_piloto"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    configuracao_serializada = json.dumps(_configuracao(config), sort_keys=True, ensure_ascii=False,
                                         separators=(",", ":")).encode("utf-8")
    metadados["sha256_configuracao"] = hashlib.sha256(configuracao_serializada).hexdigest()
    metadados["sha256_artefatos"] = {
        nome: hashlib.sha256(caminho.read_bytes()).hexdigest()
        for nome, caminho in caminhos.items() if nome != "metadados"}
    caminhos["metadados"].write_text(json.dumps(metadados, ensure_ascii=False, indent=2,
                                              allow_nan=False) + "\n", encoding="utf-8")
    return caminhos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--entrada", type=Path, default=CSV_PADRAO)
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    parser.add_argument("--config", type=Path, default=CONFIG_PADRAO)
    parser.add_argument("--horas", type=int, choices=(24, 48), default=48)
    args = parser.parse_args(argv)
    try:
        caminhos = gerar_relatorio(args.entrada, args.saida, horas=args.horas, config=args.config)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"Erro ao gerar piloto: {exc}\n")
    metadados = json.loads(caminhos["metadados"].read_text(encoding="utf-8"))
    print(f"Piloto: {metadados['status']}; {metadados['medicoes_servicos_na_janela']} medições de serviços; "
          f"{metadados['intervalos_horarios_com_dados']}/{args.horas} intervalos horários observados.")
    for aviso in metadados["avisos"]:
        print(f"- {aviso}")
    print(f"Artefatos: {args.saida.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
