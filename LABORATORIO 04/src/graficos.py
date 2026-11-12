"""Gráficos do dashboard."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

from src.dados import GRUPOS
from src.testes import validar_alfa
from src.estilo import (
    CORES_GRUPO, CORES_TESTE, GRADE, NOMES_SITUACAO, NOMES_TESTE, TINTA,
    aplicar_estilo,
)


def _faixas(reais, n_faixas, log):
    """Faixas do histograma, iguais nos quatro painéis, definidas pelos dados reais."""
    todos = np.concatenate(list(reais.values()))
    if log:
        expoentes = np.linspace(np.floor(np.log10(todos.min())),
                                np.ceil(np.log10(todos.max())), n_faixas + 1)
        return 10.0 ** expoentes
    return np.linspace(0, todos.max(), n_faixas + 1)


def g1(reais, simulados, log=True, n_faixas=18):
    """G1: histograma de cada grupo, dados reais ao lado dos simulados.

    reais e simulados são dicionários {grupo: array de horas}. O eixo y é o
    percentual do grupo porque as duas colunas têm tamanhos de amostra diferentes.
    """
    colunas = [("Dados reais", reais), ("Dados simulados", simulados)]
    grupos = list(GRUPOS)
    fig = make_subplots(rows=2, cols=2, shared_xaxes=True, shared_yaxes=True,
                        horizontal_spacing=0.08, vertical_spacing=0.09,
                        subplot_titles=[f"{GRUPOS[g]} · {titulo}"
                                        for g in grupos for titulo, _ in colunas])
    aplicar_estilo(fig)
    faixas = _faixas(reais, n_faixas, log)
    posicoes = np.log10(faixas) if log else faixas
    centros = (posicoes[:-1] + posicoes[1:]) / 2
    for linha, grupo in enumerate(grupos, start=1):
        for coluna, (titulo, serie) in enumerate(colunas, start=1):
            contagem, _ = np.histogram(serie[grupo], bins=faixas)
            percentual = 100 * contagem / len(serie[grupo])
            fig.add_trace(go.Bar(
                x=centros, y=percentual, width=(posicoes[1] - posicoes[0]) * 0.92,
                name=GRUPOS[grupo], legendgroup=grupo, showlegend=coluna == 1,
                marker={"color": CORES_GRUPO[grupo], "line": {"width": 0},
                        "cornerradius": 3},
                customdata=np.column_stack([faixas[:-1], faixas[1:]]),
                hovertemplate=(f"{GRUPOS[grupo]} · {titulo}<br>"
                               "%{customdata[0]:,.1f} a %{customdata[1]:,.1f} h"
                               "<br>%{y:.1f}% dos PRs<extra></extra>"),
            ), row=linha, col=coluna)

    if log:
        expoentes = range(int(posicoes[0]), int(posicoes[-1]) + 1)
        eixo_x = {"tickvals": list(expoentes),
                  "ticktext": [f"{10.0 ** e:g} h" for e in expoentes]}
    else:
        eixo_x = {"ticksuffix": " h"}
    fig.update_xaxes(showgrid=False, linecolor=TINTA, **eixo_x)
    # Mesmo limite nos quatro painéis, para os grupos serem comparáveis.
    maximo = max(max(barras.y) for barras in fig.data)
    fig.update_yaxes(range=[0, maximo * 1.05], gridcolor=GRADE, ticksuffix="%",
                     zeroline=False)
    escala = "escala logarítmica" if log else "escala linear"
    for coluna in (1, 2):
        fig.update_xaxes(title_text=f"Tempo até o merge (horas, {escala})",
                         row=2, col=coluna)
    for linha in (1, 2):
        fig.update_yaxes(title_text="PRs do grupo (%)", row=linha, col=1)
    fig.update_layout(title="G1: tempo até o merge, dados reais × simulados",
                      height=620, bargap=0, plot_bgcolor="white",
                      font={"color": TINTA}, legend_title_text="Grupo",
                      legend={"y": -0.24},
                      margin={"t": 90, "r": 20, "l": 60, "b": 130})
    return fig


def _cor_alpha(hexadecimal, alpha):
    r, g, b = (int(hexadecimal[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {alpha})"


def g2(resultados, alfa=0.05):
    """G2: referências aproximadas sob H0, regiões críticas e p bicaudal.

    Recebe o retorno de ``aplicar_testes``. Welch usa t com os graus de liberdade
    observados; Mann–Whitney usa Z normal, corrigido para empates e sem correção
    de continuidade. As áreas p correspondem aos p-valores desses métodos, não
    a uma distribuição empírica obtida por Monte Carlo. As caudas continuam além
    da janela visível; seus valores são probabilidades analíticas até infinito.
    """
    alfa = validar_alfa(alfa)
    referencias = []
    for chave in ("welch", "mann_whitney"):
        resultado = resultados[chave]
        p = float(resultado["p_valor"])
        estatistica = float(resultado["estatistica"] if chave == "welch"
                            else resultado["z"])
        if not np.isfinite([p, estatistica]).all() or not 0 <= p <= 1:
            raise ValueError("G2 exige estatísticas finitas e p-valores entre 0 e 1.")
        if chave == "welch":
            gl = float(resultado["gl"])
            if not np.isfinite(gl) or gl <= 0:
                raise ValueError("G2 exige graus de liberdade positivos para Welch.")
            distribuicao = stats.t(df=gl)
            referencia = f"t com {gl:.2f} graus de liberdade"
        else:
            if resultado.get("correcao_continuidade", False):
                raise ValueError("G2 usa Mann–Whitney sem correção de continuidade.")
            distribuicao = stats.norm()
            referencia = "Normal N(0, 1) para U padronizado"
        p_area = float(2 * distribuicao.sf(abs(estatistica)))
        if not np.isclose(p, p_area, rtol=1e-8, atol=1e-14):
            raise ValueError("O p-valor informado não corresponde à referência do G2.")
        critico = float(distribuicao.isf(alfa / 2))
        limite = max(4.5, critico * 1.4, abs(estatistica) * 1.2)
        referencias.append((chave, resultado, distribuicao, estatistica, critico,
                            limite, referencia))

    titulos = []
    for chave, resultado, _, _, _, _, referencia in referencias:
        decisao = "rejeita H₀" if resultado["p_valor"] < alfa else "não rejeita H₀"
        titulos.append(f"{resultado['nome']}<br><sup>{referencia}<br>"
                       f"p = {resultado['p_valor']:.4g} · {decisao}</sup>")
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.13,
                        subplot_titles=titulos)
    aplicar_estilo(fig)
    metadados = {"alfa": alfa, "referencia": "aproximada sob H0", "testes": {}}
    for coluna, (chave, resultado, distribuicao, observado, critico,
                  limite, referencia) in enumerate(referencias, start=1):
        cor = CORES_TESTE[chave]
        nome = "Welch" if chave == "welch" else "Mann–Whitney"
        # Incluir exatamente as fronteiras evita deslocar visualmente as caudas.
        x = np.unique(np.r_[np.linspace(-limite, limite, 1201),
                            -critico, critico, -abs(observado), abs(observado)])
        for tipo, corte, probabilidade, preenchimento in (
            ("rejeicao", critico, alfa / 2, "rgba(185, 28, 28, 0.20)"),
            ("p_valor", abs(observado), resultado["p_valor"] / 2,
             _cor_alpha(cor, 0.35)),
        ):
            for lado in (-1, 1):
                inicio, fim = (-limite, -corte) if lado < 0 else (corte, limite)
                cauda_x = np.linspace(inicio, fim, 601)
                legenda = (f"{nome}: p/2 em cada cauda" if tipo == "p_valor"
                           else "Rejeição: α/2 em cada cauda")
                fig.add_trace(go.Scatter(
                    x=cauda_x, y=distribuicao.pdf(cauda_x), mode="lines",
                    line={"width": 0}, fill="tozeroy", fillcolor=preenchimento,
                    name=legenda, legendgroup=f"{tipo}_{chave}",
                    showlegend=lado < 0 and (tipo == "p_valor" or coluna == 1),
                    hovertemplate=(f"{legenda}<br>Área da cauda até ∞: "
                                   f"{probabilidade:.6g}<extra></extra>"),
                    meta={"teste": chave, "tipo": tipo, "lado": lado,
                          "corte": float(corte), "area": float(probabilidade),
                          "massa_fora_janela": float(distribuicao.sf(limite))},
                ), row=1, col=coluna)
        fig.add_trace(go.Scatter(
            x=x, y=distribuicao.pdf(x), mode="lines", name=f"{nome}: referência",
            line={"color": cor, "width": 2.5}, showlegend=False,
            hovertemplate="Estatística: %{x:.3f}<br>Densidade: %{y:.4f}<extra></extra>",
            meta={"teste": chave, "tipo": "densidade"},
        ), row=1, col=coluna)
        for sinal in (-1, 1):
            fig.add_vline(x=sinal * critico, line_color="#b91c1c",
                          line_dash="dot", line_width=1.4, row=1, col=coluna)
        fig.add_trace(go.Scatter(
            x=[observado, observado], y=[0, float(distribuicao.pdf(0)) * 1.04],
            mode="lines", name=f"{nome}: observado = {observado:.3f}",
            line={"color": cor, "dash": "dash", "width": 2},
            hovertemplate=f"Estatística observada: {observado:.6g}<extra></extra>",
            meta={"teste": chave, "tipo": "observado"},
        ), row=1, col=coluna)
        fig.add_annotation(
            x=0.5, y=0.96, xref=f"x{coluna if coluna > 1 else ''} domain",
            yref=f"y{coluna if coluna > 1 else ''} domain", showarrow=False,
            text=f"Limites críticos: ±{critico:.3f}",
            font={"size": 11, "color": "#991b1b"}, bgcolor="rgba(255,255,255,0.8)",
        )
        titulo_eixo = ("t = (média com bot − média sem bot) / erro padrão"
                       if chave == "welch" else "Z = (U com bot − E[U | H₀]) / DP[U | H₀]")
        fig.update_xaxes(title_text=titulo_eixo, range=[-limite, limite],
                         zeroline=False, gridcolor=GRADE, row=1, col=coluna)
        fig.update_yaxes(title_text="Densidade", rangemode="tozero",
                         gridcolor=GRADE, zeroline=False, row=1, col=coluna)
        metadados["testes"][chave] = {
            "estatistica_exibida": observado, "critico": critico,
            "p_valor": float(resultado["p_valor"]), "referencia": referencia,
        }
    fig.update_layout(
        title={"text": "G2: regiões críticas e p-valores"
               "<br><sup>Distribuições de referência aproximadas sob H₀ · "
               f"testes bicaudais · α = {alfa:g}</sup>"},
        height=590, plot_bgcolor="white", font={"color": TINTA},
        legend={"orientation": "h", "y": -0.20, "x": 0},
        margin={"t": 155, "r": 25, "l": 65, "b": 145}, meta=metadados,
    )
    return fig


def _validar_resultados_monte_carlo(dados):
    """Valida taxas e metadados antes de transformar proporções em percentuais."""
    obrigatorias = {
        "situacao", "efeito", "n", "reps", "teste", "alfa", "rejeicoes",
        "taxa_rejeicao", "ic_inf", "ic_sup", "hipotese_nula_verdadeira", "semente",
    }
    if not isinstance(dados, pd.DataFrame) or dados.empty:
        raise ValueError("Informe um DataFrame não vazio de resultados Monte Carlo.")
    faltantes = obrigatorias - set(dados.columns)
    if faltantes:
        raise ValueError(f"Resultados sem colunas obrigatórias: {', '.join(sorted(faltantes))}.")
    tabela = dados.copy()
    for coluna in ("efeito", "n", "reps", "alfa", "rejeicoes", "taxa_rejeicao",
                   "ic_inf", "ic_sup", "semente"):
        try:
            tabela[coluna] = pd.to_numeric(tabela[coluna], errors="raise")
        except (ValueError, TypeError) as erro:
            raise ValueError(f"A coluna {coluna} deve ser numérica.") from erro
        # Generator externo não implica uma semente conhecida. A ausência é
        # metadado válido e não deve impedir desenhar taxas já calculadas.
        valores = tabela[coluna].dropna() if coluna == "semente" else tabela[coluna]
        if not np.isfinite(valores.to_numpy(dtype=float)).all():
            raise ValueError(f"A coluna {coluna} exige valores finitos.")
    if not tabela["teste"].isin(CORES_TESTE).all():
        raise ValueError("Teste desconhecido; use welch ou mann_whitney.")
    if not tabela["situacao"].isin(NOMES_SITUACAO).all():
        raise ValueError("Situação desconhecida nos resultados Monte Carlo.")
    if not tabela["hipotese_nula_verdadeira"].map(
        lambda valor: isinstance(valor, (bool, np.bool_))
    ).all():
        raise ValueError("hipotese_nula_verdadeira deve conter booleanos.")
    if (tabela["n"] < 2).any() or (tabela["reps"] < 1).any():
        raise ValueError("n deve ser pelo menos 2 e reps deve ser positivo.")
    for coluna in ("n", "reps", "rejeicoes", "semente"):
        if (tabela[coluna].dropna() % 1 != 0).any():
            raise ValueError(f"A coluna {coluna} deve conter inteiros.")
    if (tabela["semente"].dropna() < 0).any():
        raise ValueError("A semente, quando conhecida, deve ser não negativa.")
    if (tabela["efeito"] <= -1).any():
        raise ValueError("O efeito deve ser maior que -1.")
    if not tabela["alfa"].between(0, 1, inclusive="neither").all():
        raise ValueError("alfa deve estar entre 0 e 1.")
    if tabela["alfa"].nunique() != 1:
        raise ValueError("Use um único alfa por gráfico para comparar os testes.")
    if ((tabela["rejeicoes"] < 0) | (tabela["rejeicoes"] > tabela["reps"])).any():
        raise ValueError("rejeicoes deve estar entre zero e reps.")
    if not np.allclose(tabela["taxa_rejeicao"], tabela["rejeicoes"] / tabela["reps"],
                       rtol=1e-8, atol=1e-10):
        raise ValueError("taxa_rejeicao não corresponde a rejeicoes / reps.")
    if not (tabela["ic_inf"].between(0, 1).all()
            and tabela["ic_sup"].between(0, 1).all()
            and (tabela["ic_inf"] <= tabela["taxa_rejeicao"] + 1e-12).all()
            and (tabela["ic_sup"] >= tabela["taxa_rejeicao"] - 1e-12).all()):
        raise ValueError("O intervalo de confiança deve conter a taxa e estar entre 0 e 1.")
    return tabela


def _sem_duplicatas(tabela, chaves):
    if tabela.duplicated(chaves).any():
        raise ValueError("Há pontos duplicados; selecione apenas uma execução por curva.")


def _barra_ic(linhas, cor):
    """Intervalos assimétricos de Wilson, convertidos para pontos percentuais."""
    return {
        "type": "data", "symmetric": False,
        "array": np.maximum(0, 100 * (linhas["ic_sup"] - linhas["taxa_rejeicao"])),
        "arrayminus": np.maximum(0, 100 * (linhas["taxa_rejeicao"] - linhas["ic_inf"])),
        "color": cor, "thickness": 1.2, "width": 3,
    }


def _dados_hover(linhas):
    sementes = linhas["semente"].map(lambda s: "não informada" if pd.isna(s) else int(s))
    return np.column_stack([
        100 * linhas["ic_inf"], 100 * linhas["ic_sup"], linhas["reps"], linhas["n"],
        linhas["rejeicoes"], sementes.to_numpy(dtype=object),
    ])


def _curva(linhas, teste, eixo, *, mostrar_legenda=True, metadados=None):
    linhas = linhas.sort_values(eixo)
    cor = CORES_TESTE[teste]
    efeito = eixo == "efeito"
    x = linhas[eixo].to_numpy() * (100 if efeito else 1)
    rotulo_x = "Efeito: %{x:g}%" if efeito else "n por grupo: %{x:g}"
    return go.Scatter(
        x=x, y=100 * linhas["taxa_rejeicao"].to_numpy(), mode="lines+markers",
        name=NOMES_TESTE[teste], legendgroup=teste, showlegend=mostrar_legenda,
        line={"color": cor, "width": 2.5}, marker={"color": cor, "size": 7},
        error_y=_barra_ic(linhas, cor), customdata=_dados_hover(linhas),
        hovertemplate=(f"{NOMES_TESTE[teste]}<br>{rotulo_x}<br>Rejeições: %{{y:.2f}}%"
                       "<br>IC 95% Wilson: [%{customdata[0]:.2f}%; %{customdata[1]:.2f}%]"
                       "<br>%{customdata[4]:g} / %{customdata[2]:g} réplicas"
                       "<br>n por grupo: %{customdata[3]:g} · semente: %{customdata[5]}"
                       "<extra></extra>"),
        meta={"tipo": "taxa_rejeicao", "teste": teste, **(metadados or {})},
    )


def g3(dados):
    """G3: erro tipo I apenas nos pontos cuja hipótese nula é verdadeira.

    Efeito zero não basta para definir erro tipo I: a situação de variâncias
    diferentes com medianas iguais tem médias e distribuições distintas e é
    excluída. ``layout.meta`` registra explicitamente as situações excluídas.
    """
    tabela = _validar_resultados_monte_carlo(dados)
    zero = tabela.loc[tabela["efeito"] == 0]
    excluidas = sorted(zero.loc[~zero["hipotese_nula_verdadeira"], "situacao"].unique())
    nula = zero.loc[zero["hipotese_nula_verdadeira"]].copy()
    if nula.empty:
        raise ValueError("G3 exige pontos com efeito zero e hipótese nula verdadeira.")
    _sem_duplicatas(nula, ["situacao", "teste"])
    if (nula.groupby("situacao")["n"].nunique() > 1).any():
        raise ValueError("Selecione um único n por situação no G3.")
    ordem = [situacao for situacao in NOMES_SITUACAO if situacao in set(nula["situacao"])]
    fig = aplicar_estilo(go.Figure())
    for teste in CORES_TESTE:
        linhas = nula.loc[nula["teste"] == teste].set_index("situacao").reindex(ordem).dropna()
        if linhas.empty:
            continue
        cor = CORES_TESTE[teste]
        fig.add_trace(go.Bar(
            x=[f"{NOMES_SITUACAO[s]}<br>n = {int(linhas.loc[s, 'n'])}" for s in linhas.index],
            y=100 * linhas["taxa_rejeicao"], name=NOMES_TESTE[teste],
            marker_color=cor, legendgroup=teste,
            error_y=_barra_ic(linhas, cor), customdata=_dados_hover(linhas),
            hovertemplate=(f"{NOMES_TESTE[teste]}<br>%{{x}}<br>Erro tipo I: %{{y:.2f}}%"
                           "<br>IC 95% Wilson: [%{customdata[0]:.2f}%; %{customdata[1]:.2f}%]"
                           "<br>%{customdata[4]:g} / %{customdata[2]:g} réplicas"
                           "<extra></extra>"),
            meta={"tipo": "erro_tipo_i", "teste": teste,
                  "situacoes": list(linhas.index)},
        ))
    alfa = float(nula["alfa"].iloc[0])
    fig.add_hline(y=100 * alfa, line_color="#b91c1c", line_dash="dash",
                  annotation_text=f"α = {100 * alfa:g}%", annotation_position="top right")
    fig.update_xaxes(title="Situação e tamanho de amostra por grupo", showgrid=False)
    fig.update_yaxes(title="Erro tipo I estimado (%)", ticksuffix="%", rangemode="tozero",
                     range=[0, min(105, max(100 * alfa, 100 * nula["ic_sup"].max()) * 1.25)])
    fig.update_layout(
        title=f"G3: calibração sob H₀<br><sup>α = {alfa:.0%} · IC 95% de Wilson</sup>",
        barmode="group", height=500,
        meta={"alfa": alfa, "situacoes_excluidas": excluidas,
              "criterio": "efeito = 0 e hipotese_nula_verdadeira"},
    )
    return fig


def g4(dados):
    """G4: curvas de rejeição por efeito, teste e situação com IC de Wilson.

    As taxas medem poder nos pontos sob H1. Efeito zero nas situações com
    distribuições idênticas mede erro tipo I. Variâncias diferentes são
    identificadas separadamente porque as hipóteses dos dois testes diferem.
    """
    tabela = _validar_resultados_monte_carlo(dados)
    _sem_duplicatas(tabela, ["situacao", "teste", "efeito"])
    if (tabela.groupby("situacao")["n"].nunique() > 1).any():
        raise ValueError("Selecione um único n por situação no G4.")
    ordem = [s for s in NOMES_SITUACAO if s in set(tabela["situacao"])]
    colunas = min(2, len(ordem))
    linhas = (len(ordem) + colunas - 1) // colunas
    titulos = []
    for situacao in ordem:
        n = int(tabela.loc[tabela["situacao"] == situacao, "n"].iloc[0])
        ressalva = " · hipóteses distintas" if situacao == "variancias_diferentes" else ""
        titulos.append(f"{NOMES_SITUACAO[situacao]} · n = {n}<br><sup>Taxa de rejeição{ressalva}</sup>")
    fig = aplicar_estilo(make_subplots(
        rows=linhas, cols=colunas, shared_yaxes=True,
        horizontal_spacing=0.12, vertical_spacing=0.16 if linhas > 1 else 0,
        subplot_titles=titulos,
    ))
    vistos = set()
    for indice, situacao in enumerate(ordem):
        linha, coluna = indice // colunas + 1, indice % colunas + 1
        for teste in CORES_TESTE:
            pontos = tabela.loc[(tabela["situacao"] == situacao) & (tabela["teste"] == teste)]
            if pontos.empty:
                continue
            fig.add_trace(_curva(pontos, teste, "efeito", mostrar_legenda=teste not in vistos,
                                 metadados={"situacao": situacao}), row=linha, col=coluna)
            vistos.add(teste)
        fig.update_xaxes(title="Efeito no grupo com bot (%)", ticksuffix="%", row=linha, col=coluna)
        fig.update_yaxes(title="Rejeições de H₀ (%)", ticksuffix="%", range=[0, 100],
                         row=linha, col=coluna)
    fig.update_layout(
        title={"text": f"G4: efeito e probabilidade de rejeição<br><sup>α = {float(tabela['alfa'].iloc[0]):.0%} · Poder sob H₁; calibração sob H₀ · IC 95% de Wilson</sup>",
               "y": 0.98, "yanchor": "top"},
        height=310 * linhas + 225, margin={"t": 165},
        legend={"y": -0.12 if linhas > 1 else -0.25},
        meta={"alfa": float(tabela["alfa"].iloc[0]), "situacoes": ordem,
              "variancias_diferentes": "taxa de rejeição; hipóteses distintas entre testes"},
    )
    return fig


def grafico_amostra(dados):
    """Curvas de poder por n e referência de efeito, sem extrapolar a grade."""
    tabela = _validar_resultados_monte_carlo(dados)
    if "referencia_efeito" not in tabela:
        raise ValueError("A análise de amostra exige referencia_efeito.")
    if tabela["hipotese_nula_verdadeira"].any() or (tabela["efeito"] == 0).any():
        raise ValueError("Curvas de poder por n exigem um efeito diferente de zero sob H₁.")
    _sem_duplicatas(tabela, ["referencia_efeito", "teste", "n"])
    if (tabela.groupby("referencia_efeito")["efeito"].nunique() > 1).any():
        raise ValueError("Cada curva de n deve manter o mesmo efeito.")
    if (tabela["situacao"] != "base").any():
        raise ValueError("A análise de n compara amostras do cenário base.")
    referencias = list(tabela["referencia_efeito"].unique())
    nomes = {"planejado_30pct": "Efeito planejado: +30%",
             "observado_mediana": "Efeito observado: razão de medianas"}
    titulos = []
    for referencia in referencias:
        pontos = tabela.loc[tabela["referencia_efeito"] == referencia]
        rotulo = pontos["rotulo_efeito"].iloc[0] if "rotulo_efeito" in pontos else nomes.get(referencia, referencia)
        titulos.append(f"{rotulo}<br><sup>Efeito simulado: {100 * pontos['efeito'].iloc[0]:.1f}%</sup>")
    colunas = min(2, len(referencias))
    linhas = (len(referencias) + colunas - 1) // colunas
    fig = aplicar_estilo(make_subplots(rows=linhas, cols=colunas, shared_yaxes=True,
                                       horizontal_spacing=0.12, subplot_titles=titulos))
    alvo = float(tabela["alvo_poder"].iloc[0]) if "alvo_poder" in tabela else 0.8
    if not 0 < alvo < 1 or ("alvo_poder" in tabela and tabela["alvo_poder"].nunique() != 1):
        raise ValueError("Use uma única meta de poder entre 0 e 1.")
    vistos = set()
    for indice, referencia in enumerate(referencias):
        linha, coluna = indice // colunas + 1, indice % colunas + 1
        pontos = tabela.loc[tabela["referencia_efeito"] == referencia]
        for teste in CORES_TESTE:
            curva = pontos.loc[pontos["teste"] == teste]
            if curva.empty:
                continue
            fig.add_trace(_curva(curva, teste, "n", mostrar_legenda=teste not in vistos,
                                 metadados={"referencia_efeito": referencia}), row=linha, col=coluna)
            vistos.add(teste)
        fig.add_hline(y=100 * alvo, line_dash="dash", line_color="#b91c1c",
                      annotation_text=f"Meta: {100 * alvo:g}%", annotation_position="top left",
                      row=linha, col=coluna)
        if "n_real_por_grupo" in pontos:
            if pontos["n_real_por_grupo"].nunique() != 1:
                raise ValueError("n_real_por_grupo deve ser constante em cada painel.")
            n_real = float(pontos["n_real_por_grupo"].iloc[0])
            if not np.isfinite(n_real) or n_real < 2:
                raise ValueError("n_real_por_grupo deve ser finito e pelo menos 2.")
            fig.add_vline(x=n_real, line_dash="dot", line_color=TINTA,
                          annotation_text=f"Amostra real: n = {n_real:g}",
                          # Anotações em eixo log recebem log10, ao contrário
                          # dos dados e da linha vertical, que recebem PRs.
                          annotation_x=float(np.log10(n_real)),
                          annotation_position="bottom right", row=linha, col=coluna)
        fig.update_xaxes(title="Amostra por grupo (PRs; escala logarítmica)", type="log",
                         row=linha, col=coluna)
        fig.update_yaxes(title="Poder estimado (%)", range=[0, 100], ticksuffix="%",
                         row=linha, col=coluna)
    fig.update_layout(
        title={"text": f"Tamanho de amostra e poder<br><sup>α = {float(tabela['alfa'].iloc[0]):.0%} · Cenário base · IC 95% de Wilson · sem extrapolação</sup>",
               "y": 0.98, "yanchor": "top"},
        height=430 * linhas + 215, margin={"t": 165},
        meta={"alfa": float(tabela["alfa"].iloc[0]), "alvo_poder": alvo,
              "referencias_efeito": referencias},
    )
    return fig
