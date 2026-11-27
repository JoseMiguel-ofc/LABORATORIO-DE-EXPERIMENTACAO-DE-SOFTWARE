"""Sprint 2 A: descrição, normalidade e testes exploratórios da coleta Steam.

Uso: python -m analise.analise [--inicio ISO_COM_FUSO] [--fim ISO_COM_FUSO]
O CSV bruto é somente lido. Os valores-p pressupõem independência e não são
conclusões confirmatórias de uma série temporal ainda em coleta.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform

import numpy as np
import pandas as pd

from analise.estatistica import (ajustar_holm, h1_latencia, h2_usuarios,
                                 h3_falhas, normalidade)
from analise.graficos_s2 import gerar_graficos
from analise.piloto import carregar_dados, CONFIG_PADRAO, CSV_PADRAO

RAIZ = Path(__file__).resolve().parents[1]
SAIDA_PADRAO = RAIZ / "resultados" / "analise_sprint2"
PRIMARIO = "GetServerInfo"
DIAS_SEMANA = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo")
ALFA = 0.05
METODO = "sprint2_exploratoria_v1"


def _config(config=None):
    if isinstance(config, dict):
        return config
    return json.loads(Path(config or CONFIG_PADRAO).read_text(encoding="utf-8"))


def _limite(valor, nome):
    if valor is None:
        return None
    try:
        instante = pd.Timestamp(valor)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{nome} deve ser um timestamp ISO 8601 com fuso.") from exc
    if pd.isna(instante) or instante.tzinfo is None:
        raise ValueError(f"{nome} deve ter fuso explícito, por exemplo 2026-11-26T15:17:00Z.")
    return instante.tz_convert("UTC")


def _iso(valor):
    return None if valor is None or pd.isna(valor) else valor.isoformat().replace("+00:00", "Z")


def preparar_dados(entrada=CSV_PADRAO, *, inicio=None, fim=None, config=None):
    """Normaliza, filtra [início,fim) e escolhe a primeira tentativa por hora.

    A escolha depende apenas do timestamp: não se prefere um sucesso a uma
    falha. Os descartes são contados e o bruto permanece intacto.
    """
    configuracao = _config(config)
    nomes = [item["nome"] for item in configuracao["endpoints"]]
    if not nomes or len(nomes) != len(set(nomes)) or PRIMARIO not in nomes:
        raise ValueError("A configuração deve conter endpoints únicos, incluindo GetServerInfo.")
    auxiliar = configuracao.get("usuarios_online", {}).get("nome", "ValveStats")
    inicio, fim = _limite(inicio, "inicio"), _limite(fim, "fim")
    if inicio is not None and fim is not None and inicio >= fim:
        raise ValueError("inicio deve ser anterior a fim (fim exclusivo).")
    entrada = Path(entrada)
    antes = entrada.read_bytes()
    todos = carregar_dados(entrada, config=configuracao)
    if antes != entrada.read_bytes():
        raise ValueError("O CSV mudou durante a leitura. Execute novamente para obter um retrato consistente.")
    diagnostico = dict(todos.attrs["diagnostico"])
    filtro = pd.Series(True, index=todos.index)
    if inicio is not None:
        filtro &= todos.timestamp.ge(inicio)
    if fim is not None:
        filtro &= todos.timestamp.lt(fim)
    janela = todos.loc[filtro].copy()
    servicos = janela.loc[janela.endpoint.isin(nomes)].copy()
    servicos["horario_utc"] = servicos.timestamp.dt.floor("h")
    repetidas = servicos.duplicated(["endpoint", "horario_utc"], keep="first")
    dados = servicos.loc[~repetidas].copy().reset_index(drop=True)
    dados["hora_utc"] = dados.timestamp.dt.hour
    dados["periodo"] = np.where(dados.hora_utc.ge(14) & dados.hora_utc.lt(22),
                                 "pico", "fora_do_pico")
    dados["dia_semana"] = dados.timestamp.dt.day_of_week
    dados["dia_semana_nome"] = dados.dia_semana.map(dict(enumerate(DIAS_SEMANA)))
    local = dados.timestamp.dt.tz_convert("America/Los_Angeles")
    dados["janela_manutencao"] = (local.dt.day_of_week.eq(1)
                                   & local.dt.hour.ge(15) & local.dt.hour.lt(18))
    dados["latencia_analisavel"] = (dados.sucesso_operacional
                                     & dados.latencia_ms.notna())
    dados.attrs["endpoints_esperados"] = nomes
    resumo = {
        "entrada": str(entrada.resolve()), "sha256_csv": sha256(antes).hexdigest(),
        "inicio_filtro_inclusivo_utc": _iso(inicio), "fim_filtro_exclusivo_utc": _iso(fim),
        "inicio_observado_utc": _iso(dados.timestamp.min()) if len(dados) else None,
        "fim_observado_utc": _iso(dados.timestamp.max()) if len(dados) else None,
        "diagnostico_entrada": diagnostico,
        "linhas_fora_filtro_temporal": len(todos) - len(janela),
        "consultas_auxiliares_excluidas": int(janela.endpoint.eq(auxiliar).sum()),
        "medicoes_desconhecidas_excluidas": int((~janela.endpoint.isin(nomes + [auxiliar])).sum()),
        "medicoes_servicos_antes_selecao_horaria": len(servicos),
        "repeticoes_endpoint_hora_excluidas": int(repetidas.sum()),
        "medicoes_analisadas": len(dados),
        "endpoints_planejados": nomes,
        "sha256_configuracao": sha256(json.dumps(configuracao, sort_keys=True,
                                                  ensure_ascii=False).encode()).hexdigest(),
        "selecao_horaria": "Primeira tentativa por endpoint e hora de calendário UTC, independente do resultado.",
    }
    return dados, resumo


def _resumo_grupo(grupo):
    lat = grupo.loc[grupo.latencia_analisavel, "latencia_ms"]
    n = len(grupo)
    classificaveis = int(grupo.tentativa_classificavel.sum())
    sucessos = int(grupo.sucesso_operacional.sum())
    return {
        "medicoes": n, "tentativas_classificaveis": classificaveis,
        "tentativas_nao_classificaveis": n - classificaveis,
        "sucessos": sucessos, "falhas": classificaveis - sucessos,
        "sucesso_observado_pct": 100 * sucessos / classificaveis if classificaveis else np.nan,
        "n_latencias": len(lat), "media_ms": lat.mean(), "dp_ms": lat.std(ddof=1),
        "min_ms": lat.min(), "p25_ms": lat.quantile(.25), "mediana_ms": lat.median(),
        "p75_ms": lat.quantile(.75), "iqr_ms": lat.quantile(.75)-lat.quantile(.25),
        "p95_ms": lat.quantile(.95), "max_ms": lat.max(),
        "usuarios_online_ausentes": int(grupo.usuarios_online.isna().sum()),
        "n_pares_usuarios_latencia": int((grupo.latencia_analisavel
                                          & grupo.usuarios_online.notna()).sum()),
        "medicoes_janela_manutencao": int(grupo.janela_manutencao.sum()),
    }


def tabelas_descritivas(dados, nomes):
    """Grades completas por endpoint, período e dia; grupos vazios têm n=0."""
    por_endpoint, por_periodo, por_dia, normais = [], [], [], []
    for nome in nomes:
        base = dados.loc[dados.endpoint.eq(nome)]
        por_endpoint.append({"endpoint": nome, **_resumo_grupo(base)})
        grupos = [("endpoint", "todos", base)]
        for periodo in ("pico", "fora_do_pico"):
            grupo = base.loc[base.periodo.eq(periodo)]
            por_periodo.append({"endpoint": nome, "periodo": periodo, **_resumo_grupo(grupo)})
            grupos.append(("periodo", periodo, grupo))
        for dia, rotulo in enumerate(DIAS_SEMANA):
            grupo = base.loc[base.dia_semana.eq(dia)]
            por_dia.append({"endpoint": nome, "dia_semana": dia,
                            "dia_semana_nome": rotulo, **_resumo_grupo(grupo)})
            grupos.append(("dia_semana", rotulo, grupo))
        for estrato, rotulo, grupo in grupos:
            teste = normalidade(grupo.loc[grupo.latencia_analisavel, "latencia_ms"].to_numpy())
            normais.append({"endpoint": nome, "estratificacao": estrato, "grupo": rotulo,
                            **teste, "carater": "diagnostico_exploratorio_iid"})
    return {"descritiva_endpoint": pd.DataFrame(por_endpoint),
            "descritiva_periodo": pd.DataFrame(por_periodo),
            "descritiva_dia_semana": pd.DataFrame(por_dia),
            "normalidade": pd.DataFrame(normais)}


def testar_hipoteses(dados, nomes):
    """Uma linha por hipótese/endpoint; Holm preserva a família pré-planejada."""
    linhas = []
    for nome in nomes:
        base = dados.loc[dados.endpoint.eq(nome)]
        lat = base.loc[base.latencia_analisavel]
        pares = lat.loc[lat.usuarios_online.notna()]
        classif = base.loc[base.tentativa_classificavel]
        janela = classif.loc[classif.janela_manutencao]
        fora = classif.loc[~classif.janela_manutencao]
        testes = {
            "H1": h1_latencia(lat.loc[lat.periodo.eq("pico"), "latencia_ms"].to_numpy(),
                              lat.loc[lat.periodo.eq("fora_do_pico"), "latencia_ms"].to_numpy()),
            "H2": h2_usuarios(pares.usuarios_online.to_numpy(), pares.latencia_ms.to_numpy()),
            "H3": h3_falhas(int((~janela.sucesso_operacional).sum()),
                            int(janela.sucesso_operacional.sum()),
                            int((~fora.sucesso_operacional).sum()),
                            int(fora.sucesso_operacional.sum())),
        }
        for hipotese, resultado in testes.items():
            linhas.append({"endpoint": nome, "hipotese": hipotese, **resultado,
                           "familia": "primaria_H1_H2_H3" if nome == PRIMARIO else "secundaria_todos_endpoints",
                           "carater": "exploratorio_independencia_nao_verificada", "alfa": ALFA})
    tabela = pd.DataFrame(linhas)
    tabela["p_holm"] = np.nan
    tabela["m_familia"] = 0
    for familia in tabela.familia.unique():
        indices = tabela.index[tabela.familia.eq(familia)]
        ajustados = ajustar_holm(tabela.loc[indices, "p_valor"].tolist())
        tabela.loc[indices, "p_holm"] = [np.nan if p is None else p for p in ajustados]
        tabela.loc[indices, "m_familia"] = len(indices)
    tabela["rejeita_h0_iid_holm"] = [None if pd.isna(p) else bool(p < ALFA) for p in tabela.p_holm]
    tabela["interpretacao"] = [
        ("Não estimável: " + str(r.motivo)) if pd.isna(r.p_holm) else (
            "Sinal exploratório na direção prevista após Holm, sob pressupostos IID; sem conclusão confirmatória."
            if r.p_holm < ALFA else
            "Evidência exploratória insuficiente após Holm; não demonstra igualdade nem ausência de efeito.")
        for r in tabela.itertuples()]
    return tabela


def diagnostico_temporal(dados, nomes):
    """Correlação descritiva só entre horas consecutivas de calendário UTC.

    Não se comprime uma lacuna de várias horas em um lag horário. Ausência
    de correlação detectável não valida a independência dos testes.
    """
    linhas = []
    for nome in nomes:
        base = dados.loc[dados.endpoint.eq(nome)].sort_values("horario_utc")
        x = base.set_index("horario_utc").latencia_ms.where(
            base.set_index("horario_utc").latencia_analisavel)
        pares = pd.DataFrame({"atual": x, "anterior": x.reindex(x.index-pd.Timedelta(hours=1)).to_numpy()}).dropna()
        rho = None
        if len(pares) >= 3 and pares.atual.nunique() > 1 and pares.anterior.nunique() > 1:
            rho = float(pares.atual.corr(pares.anterior))
        if len(base):
            calendario = pd.date_range(base.horario_utc.min(), base.horario_utc.max(), freq="h")
            esperadas = len(calendario)
        else:
            esperadas = 0
        linhas.append({"endpoint": nome, "horas_com_medicao": len(base),
                       "horas_calendario_entre_primeira_e_ultima": esperadas,
                       "cobertura_calendario_observado_pct": 100*len(base)/esperadas if esperadas else np.nan,
                       "pares_consecutivos_validos_1h": len(pares),
                       "correlacao_descritiva_lag1h": rho,
                       "status_inferencia": "exploratoria; independência não estabelecida"})
    return pd.DataFrame(linhas)


def analisar(entrada=CSV_PADRAO, *, inicio=None, fim=None, config=None):
    dados, metadados = preparar_dados(entrada, inicio=inicio, fim=fim, config=config)
    nomes = metadados["endpoints_planejados"]
    tabelas = tabelas_descritivas(dados, nomes)
    tabelas["hipoteses"] = testar_hipoteses(dados, nomes)
    tabelas["diagnostico_temporal"] = diagnostico_temporal(dados, nomes)
    return {"dados": dados, "tabelas": tabelas, "metadados": metadados}


def _numero(valor, precisao=4):
    if valor is None or pd.isna(valor):
        return "não estimável"
    if isinstance(valor, (int, np.integer)):
        return str(valor)
    return f"{float(valor):.{precisao}g}"


def _tabela_md(tabela):
    def celula(valor):
        if isinstance(valor, (float, np.floating)):
            return _numero(valor)
        if valor is None or pd.isna(valor):
            return "não estimável"
        return str(valor).replace("|", "/").replace("\n", " ")
    return "\n".join([
        "| " + " | ".join(tabela.columns) + " |",
        "| " + " | ".join("---" for _ in tabela.columns) + " |",
        *("| " + " | ".join(celula(v) for v in linha) + " |"
          for linha in tabela.itertuples(index=False, name=None))])


def _relatorio(resultado, saida):
    meta, tab = resultado["metadados"], resultado["tabelas"]
    principal = tab["hipoteses"].loc[tab["hipoteses"].endpoint.eq(PRIMARIO)]
    tabela = principal[["hipotese", "teste", "n1", "n2", "estatistica", "efeito_nome",
                        "efeito", "p_valor", "p_holm", "status"]]
    linhas = [
        "# Lab05 — Sprint 2 da Pessoa A: análise exploratória", "",
        "**A coleta está em andamento. Este relatório não declara o dataset congelado nem apresenta conclusões confirmatórias.**", "",
        f"- Período observado: {meta['inicio_observado_utc'] or 'sem dados'} até {meta['fim_observado_utc'] or 'sem dados'}.",
        f"- Medições de serviços antes da seleção horária: {meta['medicoes_servicos_antes_selecao_horaria']}.",
        f"- Medições analisadas: {meta['medicoes_analisadas']}; repetições de endpoint na mesma hora excluídas: {meta['repeticoes_endpoint_hora_excluidas']}.",
        f"- Consultas auxiliares excluídas: {meta['consultas_auxiliares_excluidas']}; desconhecidas excluídas: {meta['medicoes_desconhecidas_excluidas']}.",
        f"- SHA256 do CSV bruto: `{meta['sha256_csv']}`.", "",
        "## Método", "",
        "Uma observação por endpoint e hora de calendário UTC, conservando a primeira tentativa sem escolher pelo resultado. Pico: 14h ≤ hora UTC < 22h. Janela candidata: terça 15h ≤ hora < 18h em America/Los_Angeles, com horário de verão. ValveStats é apenas fonte auxiliar. Falhas, faltantes e tentativas não classificáveis são separados. Latências de sucesso válidas e outliers são mantidos; timeouts não entram na distribuição de sucesso.", "",
        "H1 usa Mann–Whitney unilateral e delta de Cliff; H2 usa Spearman unilateral; H3 usa Fisher unilateral, adequado a contagens pequenas. Todos os valores-p pressupõem observações independentes. Holm usa três hipóteses planejadas do endpoint primário e uma família separada para todos os testes secundários; hipóteses não estimáveis mantêm seu lugar na família.", "",
        "## Descrição por endpoint", "",
        _tabela_md(tab["descritiva_endpoint"][["endpoint", "medicoes", "tentativas_classificaveis",
                    "sucessos", "falhas", "n_latencias", "mediana_ms", "iqr_ms", "p95_ms"]]), "",
        "Proporções de sucesso são condicionais às tentativas classificáveis observadas. Não representam uptime global ou duração total de indisponibilidade. Tabelas completas: [endpoint](descritiva_endpoint.csv), [período](descritiva_periodo.csv) e [dia da semana](descritiva_dia_semana.csv). Grupos sem observações têm n=0 e estatísticas ausentes.", "",
        "## Normalidade", "",
        "Shapiro–Wilk é apenas diagnóstico por endpoint, período e dia da semana. Não rejeitar normalidade não prova distribuição normal nem independência. Amostra com menos de três valores ou sem variação não recebe uma conclusão artificial. A escolha dos testes de postos já foi definida na proposta e não muda para buscar significância.", "",
        "Resultados completos: [normalidade.csv](normalidade.csv).", "",
        "## H1–H3 do endpoint primário (GetServerInfo)", "",
        _tabela_md(tabela), "",
    ]
    for r in principal.itertuples():
        complemento = " " + str(r.motivo) if pd.notna(r.p_holm) and r.motivo else ""
        linhas += [f"**{r.hipotese}:** {r.interpretacao}{complemento}", ""]
    metodo = Path(os.path.relpath(RAIZ/"docs"/"metodo_analise_sprint2.md", saida)).as_posix()
    ameacas = Path(os.path.relpath(RAIZ/"docs"/"ameacas_conclusao_construto.md", saida)).as_posix()
    linhas += [
        "A diferença e a razão das medianas de H1 são descritivas; Mann–Whitney compara posições/distribuições, com condições adicionais para uma interpretação de medianas. O delta é positivo quando o pico tende a ser mais lento. Spearman mede associação monotônica e não causalidade; seu valor-p assintótico é especialmente limitado com amostras pequenas e dependência temporal. H3 requer observações dentro e fora da janela; ausência de falhas não demonstra equivalência nem disponibilidade perfeita. OR indefinida/infinita é indicada sem pseudocontagens.", "",
        "Todos os testes por endpoint estão em [hipoteses.csv](hipoteses.csv).", "",
        "## Cobertura e dependência temporal", "",
        _tabela_md(tab["diagnostico_temporal"]), "",
        "O denominador é o calendário horário entre a primeira e a última medição de cada endpoint. Ele não mede horas futuras nem substitui a validação do agendador da Pessoa B. O diagnóstico de lag 1h usa somente pares em horas consecutivas; lacunas não são comprimidas. Não se usa correlação pequena para declarar independência.", "",
        "A instrumentação mudou em 26/11/2026 para contornar omissões do agendador; a mistura de fases pode confundir horário, usuários e latência. Para analisar uma fase separada, informe --inicio e --fim com fusos explícitos. A seleção temporal deve ser registrada antes de interpretar os testes, sem escolher o período pelo menor p. Com baixa cobertura ou poucas janelas, os resultados permanecem exploratórios/descritivos; a adequação temporal e análises de robustez são etapas posteriores.", "",
        "## Gráficos", "",
        "![Latência por hora UTC](latencia_por_hora.png)", "",
        "![Pico e fora do pico](boxplot_pico_fora.png)", "",
        "![Latência e usuários](dispersao_usuarios_latencia.png)", "",
        "## Documentação e reprodução", "",
        f"[Método e justificativa dos testes]({metodo}) · [Ameaças de conclusão e construto]({ameacas}).", "",
        "Na pasta LABORATORIO 05: `.venv/bin/python -m analise.analise`. O manifesto registra dados, filtros, método, versões e hashes dos artefatos. A coleta não é disparada por esse comando.", "",
    ]
    return "\n".join(linhas)


def gerar_relatorio(entrada=CSV_PADRAO, saida=SAIDA_PADRAO, *, inicio=None, fim=None,
                    config=None):
    resultado = analisar(entrada, inicio=inicio, fim=fim, config=config)
    saida = Path(saida)
    # Evita que uma opção de saída sobrescreva a fonte ou a instrumentação.
    dados_raiz = (RAIZ / "dados").resolve()
    if (saida.resolve() in (Path(entrada).resolve().parent, dados_raiz)
            or dados_raiz in saida.resolve().parents):
        raise ValueError("Use uma pasta de resultados separada de dados/brutos e dados/.")
    saida.mkdir(parents=True, exist_ok=True)
    caminhos = {}
    for nome, tabela in resultado["tabelas"].items():
        caminhos[nome] = saida / f"{nome}.csv"
        tabela.to_csv(caminhos[nome], index=False)
    caminhos["dados_analisados"] = saida / "dados_analisados.csv"
    resultado["dados"].to_csv(caminhos["dados_analisados"], index=False)
    caminhos.update(gerar_graficos(resultado["dados"], saida))
    caminhos["relatorio"] = saida / "relatorio.md"
    caminhos["relatorio"].write_text(_relatorio(resultado, saida), encoding="utf-8")
    metadados = resultado["metadados"]
    metadados.update({
        "metodo": METODO, "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "status": "exploratorio_coleta_em_andamento", "dataset_congelado": False,
        "alfa": ALFA, "endpoint_primario": PRIMARIO,
        "pico_utc": [14, 22],
        "janela_candidata": {"dia": "terça-feira", "horas": [15, 18], "fuso": "America/Los_Angeles"},
        "correcao_multiplicidade": "Holm; família primária de 3, secundária com todas as H1-H3 dos demais endpoints configurados; ausentes preservadas",
        "outliers": "mantidos", "testes_independencia": "não estabelecida; valores-p exploratórios",
        "versoes": {"python": platform.python_version(), **{p: version(p) for p in ("numpy", "pandas", "scipy", "matplotlib")}},
        "sha256_codigo": {n: sha256((RAIZ/"analise"/n).read_bytes()).hexdigest()
                           for n in ("analise.py", "estatistica.py", "graficos_s2.py", "piloto.py")},
        "sha256_artefatos": {p.name: sha256(p.read_bytes()).hexdigest() for p in caminhos.values()},
    })
    caminhos["metadados"] = saida / "metadados.json"
    caminhos["metadados"].write_text(json.dumps(metadados, ensure_ascii=False, indent=2,
                                               allow_nan=False)+"\n", encoding="utf-8")
    return caminhos


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, default=CSV_PADRAO)
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    parser.add_argument("--inicio", help="Início inclusivo ISO 8601 com fuso.")
    parser.add_argument("--fim", help="Fim exclusivo ISO 8601 com fuso.")
    parser.add_argument("--config", type=Path, default=CONFIG_PADRAO)
    args = parser.parse_args(argv)
    try:
        caminhos = gerar_relatorio(args.entrada, args.saida, inicio=args.inicio,
                                   fim=args.fim, config=args.config)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"Erro na análise: {exc}\n")
    meta = json.loads(caminhos["metadados"].read_text(encoding="utf-8"))
    print(f"Análise exploratória: {meta['medicoes_analisadas']} medições; "
          f"{meta['repeticoes_endpoint_hora_excluidas']} repetições por hora excluídas.")
    hipoteses = pd.read_csv(caminhos["hipoteses"])
    for linha in hipoteses.loc[hipoteses.endpoint.eq(PRIMARIO)].itertuples():
        if pd.isna(linha.p_valor):
            print(f"{linha.hipotese} não estimável: {linha.motivo}")
    print(f"Relatório: {caminhos['relatorio'].resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
