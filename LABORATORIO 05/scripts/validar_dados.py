"""Validação do dataset da coleta: faltantes, duplicatas, execuções puladas,
outliers e cobertura.

Uso (na pasta LABORATORIO 05):

    python scripts/validar_dados.py                       # relatório no terminal
    python scripts/validar_dados.py --saida resultados/validacao
    python scripts/validar_dados.py --ate 2026-12-20      # até a data de corte (inclusiva)

Com ``--saida``, grava ``relatorio_validacao.md`` e ``cobertura_por_horario.csv``.

Definições (as mesmas da proposta, docs/proposta.md, seções 4.1 a 4.3):
- Horário de coleta: do minuto 17 de uma hora UTC ao minuto 16 da seguinte. Uma
  execução pulada é um horário sem nenhuma rodada.
- Sucesso: status HTTP de 200 a 399 e campo ``erro`` vazio.
- Pico: 14:00 <= hora < 22:00 UTC. Janela candidata de manutenção: terça,
  15:00 <= hora < 18:00 em America/Los_Angeles (com horário de verão).

Sai com código 1 só quando o arquivo está quebrado (colunas erradas, timestamps
ilegíveis, duplicatas, linhas sem status e sem motivo de erro). Execuções puladas,
atrasos e outliers são características dos dados: entram no relatório sem
reprovar o push.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

LAB05 = Path(__file__).resolve().parent.parent
CSV_PADRAO = LAB05 / "dados" / "brutos" / "coleta.csv"
CONFIG_PADRAO = LAB05 / "coleta" / "config.json"
COLUNAS = ["timestamp", "endpoint", "status", "latencia_ms", "usuarios_online",
           "erro", "jogadores_top"]
MINUTO = 17
NOVA_RODADA = pd.Timedelta(minutes=5)   # medições separadas por mais que isso são rodadas distintas
ATRASO_TOLERADO_MIN = 30
PICO_UTC = (14, 22)
JANELA_LA = {"dia_semana": 1, "inicio": 15, "fim": 18}   # terça, 15h-18h em Los Angeles


@dataclass
class Relatorio:
    erros: list[str] = field(default_factory=list)
    secoes: list[tuple[str, str]] = field(default_factory=list)
    cobertura: pd.DataFrame | None = None

    def secao(self, titulo: str, texto: str) -> None:
        self.secoes.append((titulo, texto))

    def markdown(self) -> str:
        partes = ["# Relatório de validação da coleta", ""]
        if self.erros:
            partes += ["**Problemas que reprovam a validação:**", ""]
            partes += [f"- {erro}" for erro in self.erros] + [""]
        else:
            partes += ["Nenhum problema estrutural encontrado.", ""]
        for titulo, texto in self.secoes:
            partes += [f"## {titulo}", "", texto.rstrip(), ""]
        return "\n".join(partes)


def tabela_md(df: pd.DataFrame) -> str:
    """Tabela em Markdown sem depender do pacote tabulate."""
    linhas = ["| " + " | ".join(str(c) for c in df.columns) + " |",
              "|" + "---|" * len(df.columns)]
    for valores in df.itertuples(index=False):
        linhas.append("| " + " | ".join(str(v) for v in valores) + " |")
    return "\n".join(linhas)


def pct(parte: float, total: float) -> str:
    return f"{100 * parte / total:.1f}%" if total else "n/d"


def horario(momentos: pd.Series) -> pd.Series:
    """Início do horário de coleta (minuto 17) que contém cada momento."""
    return (momentos - pd.Timedelta(minutes=MINUTO)).dt.floor("h") + pd.Timedelta(minutes=MINUTO)


def na_janela(momentos: pd.Series) -> pd.Series:
    local = momentos.dt.tz_convert("America/Los_Angeles")
    return (local.dt.day_of_week.eq(JANELA_LA["dia_semana"])
            & local.dt.hour.ge(JANELA_LA["inicio"]) & local.dt.hour.lt(JANELA_LA["fim"]))


def no_pico(momentos: pd.Series) -> pd.Series:
    return momentos.dt.hour.ge(PICO_UTC[0]) & momentos.dt.hour.lt(PICO_UTC[1])


# ---------------------------------------------------------------- checagens

def checar_estrutura(bruto: pd.DataFrame, rel: Relatorio) -> bool:
    faltando = [c for c in COLUNAS if c not in bruto.columns]
    sobrando = [c for c in bruto.columns if c not in COLUNAS]
    if faltando:
        rel.erros.append(f"colunas ausentes: {', '.join(faltando)}")
    if sobrando:
        rel.erros.append(f"colunas fora do esquema: {', '.join(sobrando)}")
    return not faltando


def preparar(bruto: pd.DataFrame, rel: Relatorio) -> pd.DataFrame:
    df = bruto[COLUNAS].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="ISO8601",
                                     errors="coerce")
    invalidos = int(df["timestamp"].isna().sum())
    if invalidos:
        rel.erros.append(f"{invalidos} timestamps vazios ou ilegíveis")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp", kind="stable")
    for coluna in ("status", "latencia_ms", "usuarios_online", "jogadores_top"):
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
    df["endpoint"] = df["endpoint"].fillna("").str.strip()
    df["erro"] = df["erro"].fillna("").str.strip()
    df["sucesso"] = df["status"].between(200, 399) & df["erro"].eq("")
    nova = df["timestamp"].diff().gt(NOVA_RODADA) | df["timestamp"].diff().isna()
    df["rodada"] = nova.cumsum()
    return df.reset_index(drop=True)


def checar_faltantes(df: pd.DataFrame, rel: Relatorio) -> None:
    sem_status = df["status"].isna()
    incoerentes = int((sem_status & df["erro"].eq("")).sum())
    latencia_invalida = int((df["latencia_ms"].isna() | (df["latencia_ms"] < 0)).sum())
    contagens = pd.DataFrame({
        "verificação": ["endpoint vazio", "latência ausente ou negativa",
                        "status vazio com erro registrado (falha sem resposta)",
                        "status vazio **sem** erro registrado",
                        "usuarios_online ausente", "jogadores_top ausente"],
        "linhas": [int(df["endpoint"].eq("").sum()), latencia_invalida,
                   int((sem_status & df["erro"].ne("")).sum()), incoerentes,
                   int(df["usuarios_online"].isna().sum()),
                   int(df["jogadores_top"].isna().sum())]})
    contagens["%"] = [pct(n, len(df)) for n in contagens["linhas"]]
    if incoerentes:
        rel.erros.append(f"{incoerentes} linhas sem status HTTP e sem motivo de erro")
    if int(df["endpoint"].eq("").sum()):
        rel.erros.append("há medições sem nome de endpoint")
    rel.secao("Valores faltantes",
              tabela_md(contagens) + "\n\nStatus vazio com erro preenchido é uma falha "
              "registrada (timeout, conexão recusada) e conta como indisponibilidade. "
              "`usuarios_online` e `jogadores_top` ficam vazios quando a fonte falhou "
              "naquela rodada.")


def checar_duplicatas(bruto: pd.DataFrame, df: pd.DataFrame, rel: Relatorio) -> None:
    exatas = int(bruto.duplicated().sum())
    chave = int(df.duplicated(subset=["timestamp", "endpoint"]).sum())
    if chave:
        rel.erros.append(f"{chave} linhas repetem timestamp e endpoint")
    repetidos = df.groupby("rodada")["endpoint"].apply(lambda s: s.duplicated().any())
    rel.secao("Duplicatas",
              f"- Linhas idênticas: {exatas}\n- Mesmo timestamp e endpoint: {chave}\n"
              f"- Rodadas com um endpoint medido duas vezes: {int(repetidos.sum())}")


def checar_execucoes(df: pd.DataFrame, rel: Relatorio, endpoints: list[str],
                     inicio: pd.Timestamp | None, fim: pd.Timestamp | None) -> pd.DataFrame:
    rodadas = df.groupby("rodada").agg(inicio=("timestamp", "min"),
                                       medicoes=("endpoint", "nunique"),
                                       sucessos=("sucesso", "sum"))
    rodadas["horario"] = horario(rodadas["inicio"])
    rodadas["atraso_min"] = ((rodadas["inicio"] - rodadas["horario"])
                             .dt.total_seconds() / 60).round(1)

    primeiro = inicio if inicio is not None else rodadas["horario"].min()
    ultimo = fim if fim is not None else rodadas["horario"].max()
    esperados = pd.date_range(horario(pd.Series([primeiro])).iloc[0],
                              horario(pd.Series([ultimo])).iloc[0], freq="h")
    por_horario = rodadas.groupby("horario").agg(rodadas=("inicio", "size"),
                                                 atraso_min=("atraso_min", "min"))
    cobertura = pd.DataFrame({"horario_utc": esperados})
    cobertura = cobertura.merge(por_horario, left_on="horario_utc", right_index=True,
                                how="left")
    cobertura["rodadas"] = cobertura["rodadas"].fillna(0).astype(int)
    cobertura["coletado"] = cobertura["rodadas"] > 0
    cobertura["pico"] = no_pico(cobertura["horario_utc"])
    cobertura["janela_manutencao"] = na_janela(cobertura["horario_utc"])

    puladas = cobertura.loc[~cobertura["coletado"], "horario_utc"]
    extras = int((cobertura["rodadas"] - 1).clip(lower=0).sum())
    incompletas = int((rodadas["medicoes"] < len(endpoints)).sum())
    falha_geral = int((rodadas["sucessos"] == 0).sum())
    atraso = rodadas["atraso_min"]
    atrasadas = int((atraso > ATRASO_TOLERADO_MIN).sum())

    # Maior sequência de horários sem coleta.
    grupos = (cobertura["coletado"] != cobertura["coletado"].shift()).cumsum()
    lacunas = cobertura.loc[~cobertura["coletado"]].groupby(grupos[~cobertura["coletado"]]).size()
    maior_lacuna = int(lacunas.max()) if len(lacunas) else 0

    texto = [
        f"- Período avaliado: {esperados[0]:%Y-%m-%d %H:%M} a {esperados[-1]:%Y-%m-%d %H:%M} UTC "
        f"({len(esperados)} horários de coleta)",
        f"- Rodadas observadas: {len(rodadas)}; horários com pelo menos uma rodada: "
        f"{int(cobertura['coletado'].sum())}; **execuções puladas: {len(puladas)}**",
        f"- Maior sequência de horários seguidos sem coleta: {maior_lacuna} h",
        f"- Rodadas extras no mesmo horário (ex.: disparo manual): {extras}",
        f"- Rodadas incompletas (menos de {len(endpoints)} medições): {incompletas}",
        f"- Rodadas em que tudo falhou (provável problema do runner, não da Steam): "
        f"{falha_geral}",
        f"- Atraso do início da rodada em relação ao minuto {MINUTO}: mediana "
        f"{atraso.median():.1f} min, p90 {atraso.quantile(0.9):.1f} min, máximo "
        f"{atraso.max():.1f} min; acima de {ATRASO_TOLERADO_MIN} min: {atrasadas}",
        "",
        "O atraso é medido contra o minuto 17 do próprio horário, porque o GitHub não "
        "informa qual disparo do `cron` originou cada execução: uma execução que "
        "começou com horas de atraso aparece como rodada daquele horário posterior, e "
        "os horários anteriores contam como pulados."]
    rel.secao("Execuções do agendador", "\n".join(texto))
    return cobertura


def checar_outliers(df: pd.DataFrame, rel: Relatorio) -> None:
    linhas = []
    for endpoint, grupo in df[df["sucesso"]].groupby("endpoint"):
        lat = grupo["latencia_ms"].dropna()
        if len(lat) < 4:
            continue
        q1, q3 = lat.quantile([0.25, 0.75])
        iqr = q3 - q1
        linhas.append({"endpoint": endpoint, "n": len(lat),
                       "mediana_ms": round(lat.median(), 1),
                       "Q3 + 1,5 IQR (ms)": round(q3 + 1.5 * iqr, 1),
                       "outliers 1,5 IQR": int(((lat > q3 + 1.5 * iqr)
                                                | (lat < q1 - 1.5 * iqr)).sum()),
                       "extremos 3 IQR": int((lat > q3 + 3 * iqr).sum()),
                       "máximo (ms)": round(lat.max(), 1)})
    if linhas:
        rel.secao("Outliers de latência (só requisições com sucesso)",
                  tabela_md(pd.DataFrame(linhas)) + "\n\nCritério de Tukey por endpoint. "
                  "Nada é removido aqui; a análise de robustez repete os testes com e sem "
                  "esses valores.")


def checar_cobertura(df: pd.DataFrame, cobertura: pd.DataFrame, rel: Relatorio) -> None:
    total = len(cobertura)
    coletados = int(cobertura["coletado"].sum())
    grupos = []
    for nome, filtro in [("pico (14h-22h UTC)", cobertura["pico"]),
                         ("fora do pico", ~cobertura["pico"]),
                         ("janela candidata de manutenção", cobertura["janela_manutencao"]),
                         ("fora da janela", ~cobertura["janela_manutencao"])]:
        parte = cobertura[filtro]
        grupos.append({"grupo": nome, "horários": len(parte),
                       "com coleta": int(parte["coletado"].sum()),
                       "cobertura": pct(parte["coletado"].sum(), len(parte))})
    servicos = df[df["endpoint"] != "ValveStats"]
    por_endpoint = (servicos.groupby("endpoint")
                    .agg(medicoes=("sucesso", "size"), sucessos=("sucesso", "sum"))
                    .reset_index())
    por_endpoint["sucesso entre medições"] = [
        pct(s, m) for s, m in zip(por_endpoint["sucessos"], por_endpoint["medicoes"])]
    por_endpoint["horários cobertos"] = [pct(m, total) for m in por_endpoint["medicoes"]]
    rel.secao("Cobertura",
              f"**{coletados} de {total} horários com dados ({pct(coletados, total)}).**\n\n"
              + tabela_md(pd.DataFrame(grupos)) + "\n\n" + tabela_md(por_endpoint)
              + "\n\nHorário sem coleta não é falha da Steam: a taxa de sucesso usa como "
              "denominador só as medições feitas. `ValveStats` (fonte de usuários online) "
              "fica fora desta tabela.")


# ---------------------------------------------------------------- principal

def validar(caminho: Path = CSV_PADRAO, ate: str | None = None,
            config: Path = CONFIG_PADRAO) -> Relatorio:
    rel = Relatorio()
    if not caminho.exists():
        rel.erros.append(f"arquivo não encontrado: {caminho}")
        return rel
    bruto = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    if not checar_estrutura(bruto, rel):
        return rel
    df = preparar(bruto, rel)
    fim = None
    if ate:
        fim = pd.Timestamp(ate, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(minutes=1)
        df = df[df["timestamp"] <= fim]
    if df.empty:
        rel.erros.append("nenhuma linha com timestamp válido")
        return rel

    with open(config, encoding="utf-8") as arquivo:
        coleta = json.load(arquivo)
    endpoints = [coleta["usuarios_online"]["nome"]] + [e["nome"] for e in coleta["endpoints"]]
    desconhecidos = sorted(set(df["endpoint"]) - set(endpoints) - {""})
    rel.secao("Resumo",
              f"- Arquivo: `{caminho.name}`\n- Linhas: {len(df)}\n"
              f"- Primeira medição: {df['timestamp'].min():%Y-%m-%d %H:%M} UTC; "
              f"última: {df['timestamp'].max():%Y-%m-%d %H:%M} UTC\n"
              f"- Endpoints fora do config.json: {', '.join(desconhecidos) or 'nenhum'}")
    checar_faltantes(df, rel)
    checar_duplicatas(bruto, df, rel)
    rel.cobertura = checar_execucoes(df, rel, endpoints, None, fim)
    checar_outliers(df, rel)
    checar_cobertura(df, rel.cobertura, rel)
    return rel


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida o CSV da coleta da Steam.")
    parser.add_argument("--csv", type=Path, default=CSV_PADRAO)
    parser.add_argument("--saida", type=Path, default=None,
                        help="pasta onde gravar relatorio_validacao.md e cobertura_por_horario.csv")
    parser.add_argument("--ate", default=None, help="data de corte AAAA-MM-DD (inclusiva)")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # console do Windows usa cp1252
        sys.stdout.reconfigure(encoding="utf-8")

    rel = validar(args.csv, args.ate)
    texto = rel.markdown()
    if args.saida:
        args.saida.mkdir(parents=True, exist_ok=True)
        (args.saida / "relatorio_validacao.md").write_text(texto, encoding="utf-8")
        if rel.cobertura is not None:
            saida = rel.cobertura.assign(
                horario_utc=rel.cobertura["horario_utc"].dt.strftime("%Y-%m-%dT%H:%MZ"))
            saida.to_csv(args.saida / "cobertura_por_horario.csv", index=False,
                         lineterminator="\n")
    print(texto)
    return 1 if rel.erros else 0


if __name__ == "__main__":
    sys.exit(main())
