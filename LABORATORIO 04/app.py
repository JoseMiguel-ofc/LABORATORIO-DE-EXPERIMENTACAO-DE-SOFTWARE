"""Dashboard do Lab04: t de Welch × Mann-Whitney no tempo de merge de PRs."""
import numpy as np
import pandas as pd
import streamlit as st

from src.cenario import ALFA, H0, H1, PERGUNTA, PREVISAO, SEMENTE, ajustar_cenario
from src.amostra import resumir_amostra
from src.aplicacao_real import aplicar_dados_reais, tabela_secao6, texto_secao6
from src.coleta import BOT, FIM, INICIO, REPO
from src.conclusoes import (classificacao_calibracao, textos_simulacao,
                            validar_configuracao_dashboard)
from src.dados import GRUPOS, carregar, resumo
from src.estilo import NOMES_SITUACAO, NOMES_TESTE
from src.experimentos import ALFAS, carregar_amostra_alfa, carregar_simulacao_alfa
from src.graficos import g1, g2, g3, g4, grafico_amostra
from src.intervalos_efeito import carregar_intervalos
from src.rodar_q3 import resumo_q3, texto_erro_tipo_i, texto_poder
from src.simulacao import gerar
from src.testes import aplicar_testes

REPOSITORIO = ("https://github.com/JoseMiguel-ofc/LABORATORIO-DE-EXPERIMENTACAO-DE-SOFTWARE"
               "/tree/main/LABORATORIO%2004")
PROJECT = "https://github.com/users/JoseMiguel-ofc/projects/1"
DASHBOARD = ""  # Preencher com o link público


def link(rotulo, url):
    return f"[{rotulo}]({url})" if url else f"{rotulo}: *a preencher*"


st.set_page_config(page_title="Lab04: Welch × Mann-Whitney", layout="wide")
st.title("Testes de hipótese por dentro")
st.markdown("Bot de revisão e tempo até o merge: **t de Welch × Mann-Whitney**")
st.markdown(" · ".join([link("Dashboard publicado", DASHBOARD),
                        link("Repositório", REPOSITORIO),
                        link("GitHub Project", PROJECT)]))
alfa = st.selectbox("Nível de significância (α)", ALFAS,
                    index=ALFAS.index(ALFA), format_func=lambda valor: f"{valor:.0%}",
                    key="alfa")
coluna_decisao = f"Decisão (α = {alfa:.0%})"
comando_experimentos = f".venv/bin/python -m src.experimentos --alfas {alfa:g}"
st.caption("A análise principal usa α = 5%; 1% e 10% permitem explorar a sensibilidade "
           "das decisões. A seleção atualiza regiões críticas, taxas de rejeição "
           "e tamanho da amostra. Os p-valores e os IC de 95% dos efeitos não mudam.")

df = carregar()
reais = {grupo: df.loc[df["grupo"] == grupo, "horas"].to_numpy() for grupo in GRUPOS}
tabela = resumo(df)
cenario = ajustar_cenario(df)
simulados = gerar(10_000, situacao="ajuste_real", rng=np.random.default_rng(SEMENTE),
                  cenario=cenario)

st.header("1. Cenário")
st.markdown(f"""
**Pergunta.** {PERGUNTA}

- **H₀ da simulação:** {H0}
- **H₁ da simulação:** {H1}

Os testes são **bicaudais**, pois investigamos diferenças em qualquer direção,
com nível de significância **α = {alfa:.0%}**.

**Dados reais.** {len(df)} PRs mergeados de
[{REPO}](https://github.com/{REPO}), {len(reais["com_bot"])} revisados pelo bot
`{BOT}` e {len(reais["sem_bot"])} sem ele, entre {INICIO:%d/%m/%Y} e {FIM:%d/%m/%Y}.
Cada PR foi sorteado da população completa do período, com 5 PRs por mês em cada
grupo. Autores bot e backports ficaram de fora. O tempo até o merge vai da abertura
do PR até o merge, em horas.
""")
st.markdown(f"**Previsão antes de medir erro tipo I e poder.** {PREVISAO}")

st.header("2. Os dados")
log = st.radio("Escala do eixo x", ["Logarítmica", "Linear"], horizontal=True) == "Logarítmica"
st.plotly_chart(g1(reais, simulados, log=log), theme=None)
st.dataframe(tabela.style.format({coluna: "{:.2f}" for coluna in tabela.columns
                                  if coluna not in ("n", "Outliers (Tukey)")}
                                 | {"n": "{:.0f}", "Outliers (Tukey)": "{:.0f}"}),
             width="stretch")
razao_media = tabela["Média (h)"] / tabela["Mediana (h)"]
st.markdown(f"Os tempos reais têm forte assimetria à direita nos dois grupos: a média é "
            f"de {razao_media.min():.1f} a {razao_media.max():.1f} vezes a mediana, a "
            f"assimetria fica entre {tabela['Assimetria'].min():.2f} e "
            f"{tabela['Assimetria'].max():.2f}, e há "
            f"{int(tabela['Outliers (Tukey)'].sum())} outliers pela regra de Tukey. "
            "Na escala logarítmica os tempos ficam próximos de um sino, por isso a "
            "simulação usa uma lognormal, com μ e σ estimados dos logaritmos dos "
            "tempos reais. O G1 ajusta cada grupo separadamente só para comparar "
            "formas; a cauda do modelo é mais longa que a observada, e esse ajuste "
            "descritivo não é a geração sob H₀, que usa os 60 PRs reunidos.")
st.caption("G1: 10.000 observações simuladas por grupo, semente 42. As faixas são "
           "definidas pelos dados reais; valores simulados fora delas não aparecem "
           "nas barras, em ambas as escalas. Os percentuais usam a amostra inteira.")
with st.expander("Parâmetros da simulação e diferença entre G1 e o cenário base"):
    parametros = pd.DataFrame.from_dict(cenario["parametros_descritivos"], orient="index")
    parametros.index = parametros.index.map(GRUPOS)
    st.dataframe(parametros.rename(columns={
        "mu": "μ de log(horas)", "sigma": "σ de log(horas)", "n": "n real",
        "media_modelo": "Média do modelo (h)",
        "mediana_modelo": "Mediana do modelo (h)",
    }).style.format(precision=3), width="stretch")
    base = cenario["parametros_base"]
    st.markdown(f"No cenário base, os logaritmos dos **{len(df)} PRs** são reunidos: "
                f"**μ = {base['mu']:.3f}** e **σ = {base['sigma']:.3f}**. "
                "Os dois grupos usam esses mesmos parâmetros quando o efeito é zero, "
                "com sorteios independentes. Um efeito de 30% multiplica os tempos "
                "do grupo com bot por 1,30, alterando sua média e sua mediana "
                "populacionais nessa proporção; isso é uma intervenção na simulação.")

st.header("3. Como os testes funcionam")
st.markdown("**Welch compara médias** de duas amostras independentes, sem exigir "
            "variâncias iguais. **Mann-Whitney compara os postos** das observações "
            "e testa a igualdade das distribuições; interpretá-lo como um teste "
            "de medianas exige condições adicionais sobre suas formas.")
col_n, col_efeito = st.columns(2)
with col_n:
    n_exemplo = st.number_input("PRs por grupo no exemplo", min_value=10, max_value=200,
                                value=30, step=10)
with col_efeito:
    efeito_percentual = st.slider("Mudança simulada no tempo do grupo com bot (%)",
                                  min_value=-80, max_value=200, value=30, step=10,
                                  help="0%: H₀ verdadeira; positivo: mais tempo; "
                                       "negativo: menos tempo. Não é um efeito causal estimado.")
exemplo = gerar(int(n_exemplo), efeito_percentual / 100, "base",
                np.random.default_rng(SEMENTE), cenario=cenario)
resultados = aplicar_testes(exemplo["com_bot"], exemplo["sem_bot"], alfa=alfa)
st.caption(f"Um único conjunto simulado, com {n_exemplo} PRs por grupo, "
           f"semente {SEMENTE} e efeito configurado de {efeito_percentual}%. "
           "Uma realização não mede poder nem erro tipo I.")
st.dataframe(pd.DataFrame([
    {"Teste": r["nome"], "Estatística": r["estatistica"], "p-valor": r["p_valor"],
     coluna_decisao: "Rejeitar H₀" if r["rejeita_h0"] else "Não rejeitar H₀"}
    for r in resultados.values()
]).style.format({"Estatística": "{:.4f}", "p-valor": "{:.6f}"}),
    hide_index=True, width="stretch")
st.plotly_chart(g2(resultados, alfa=alfa), theme=None)
st.markdown("O G2 mostra as **distribuições de referência aproximadas sob H₀**: "
            "t com os graus de liberdade de Welch e normal padrão para U padronizado "
            "em Z. As duas caudas além dos limites críticos formam a região de "
            "rejeição, enquanto as caudas tão extremas quanto a estatística observada "
            "formam a área do p-valor. O p-valor não é a probabilidade de H₀ ser verdadeira. "
            "Com dados lognormais assimétricos, a calibração dessas aproximações "
            "é investigada pelas repetições mostradas nas próximas seções.")
st.caption("Na tabela, a estatística de Mann-Whitney é U do grupo com bot; no G2 ela "
           "é padronizada em Z. Usamos aproximação normal com correção de empates, "
           "sem correção de continuidade, para que a área exibida corresponda ao p-valor. "
           "As áreas informadas incluem as caudas até infinito; o desenho usa uma janela finita.")
for resultado in resultados.values():
    st.markdown(f"**{resultado['nome']}:** {resultado['interpretacao']}")

st.header("4. Erro tipo I")
resultados_mc = None
textos = None
try:
    resultados_mc = carregar_simulacao_alfa(alfa)
    validar_configuracao_dashboard(resultados_mc, alfa=alfa)
    textos = textos_simulacao(resultados_mc)
except (FileNotFoundError, ValueError) as exc:
    st.warning(f"Os resultados da simulação precisam ser gerados ou atualizados: {exc}")
    st.code(comando_experimentos, language="bash")
if resultados_mc is not None and textos is not None:
    resumo_situacoes = resumo_q3(resultados_mc)
    st.plotly_chart(g3(resultados_mc), theme=None)
    st.markdown(textos["erro_tipo_i"])
    st.markdown(f"**Por situação (Q3).** {texto_erro_tipo_i(resumo_situacoes, alfa)}")
    nulos = resultados_mc[np.isclose(resultados_mc["efeito"], 0)].copy()
    nulos["Avaliação"] = nulos.apply(classificacao_calibracao, axis=1)
    nulos["Situação"] = nulos["situacao"].map(NOMES_SITUACAO)
    nulos["Teste"] = nulos["teste"].map(NOMES_TESTE)
    with st.expander("Taxas de rejeição com efeito configurado zero"):
        st.dataframe(nulos[["Situação", "Teste", "n", "reps", "taxa_rejeicao",
                            "ic_inf", "ic_sup", "Avaliação"]].rename(columns={
            "n": "PRs por grupo", "reps": "Repetições", "taxa_rejeicao": "Rejeições",
            "ic_inf": "IC 95% inferior", "ic_sup": "IC 95% superior",
        }).style.format({
            "Rejeições": "{:.2%}", "IC 95% inferior": "{:.2%}", "IC 95% superior": "{:.2%}",
        }), hide_index=True, width="stretch")
    st.caption("Intervalos de Wilson de 95%. Uma classificação conservadora/liberal "
               f"compara o intervalo Monte Carlo ao nível de {alfa:.0%}; não é uma afirmação "
               "de igualdade exata ou uma comparação formal entre os testes.")
    st.markdown("**Atenção ao cenário com variâncias diferentes:** manter a mediana "
                "da lognormal e alterar σ também altera sua média e sua distribuição. "
                "Por isso, mesmo com efeito configurado zero, essas rejeições "
                "não são classificadas como erro tipo I no G3.")

st.header("5. Poder")
if resultados_mc is not None and textos is not None:
    st.plotly_chart(g4(resultados_mc), theme=None)
    st.markdown(textos["poder"])
    st.markdown(f"**Por situação (Q3).** {texto_poder(resumo_situacoes)}")
    maior_efeito = resumo_situacoes["efeito_maior"].iloc[0]
    st.dataframe(pd.DataFrame({
        "Situação": resumo_situacoes["situacao"].map(NOMES_SITUACAO),
        "PRs por grupo": resumo_situacoes["n"],
        "Welch, efeito 0": resumo_situacoes["zero_welch"],
        "Mann–Whitney, efeito 0": resumo_situacoes["zero_mann_whitney"],
        f"Welch, +{maior_efeito:.0%}": resumo_situacoes["maior_welch"],
        f"Mann–Whitney, +{maior_efeito:.0%}": resumo_situacoes["maior_mann_whitney"],
        "Rejeita mais": resumo_situacoes["mais_rejeicoes"].map(NOMES_TESTE)
                        .fillna("ICs se sobrepõem"),
    }).style.format({coluna: "{:.2%}" for coluna in (
        "Welch, efeito 0", "Mann–Whitney, efeito 0",
        f"Welch, +{maior_efeito:.0%}", f"Mann–Whitney, +{maior_efeito:.0%}")}),
        hide_index=True, width="stretch")
    st.caption("“Rejeita mais” só aponta um teste quando os intervalos de Wilson de 95% "
               "não se sobrepõem. Em variâncias diferentes, efeito 0 não é H₀ verdadeira.")
    st.caption("Cada ponto é calculado a partir dos resultados salvos; os controles "
               "do exemplo G2 não alteram esta grade. O painel de variâncias diferentes "
               "mostra taxas de rejeição sob distribuições diferentes, sem uma comparação "
               "de poder para a mesma hipótese científica dos demais painéis.")
    with st.expander("Como foram definidas as situações"):
        st.markdown("""
- **Base:** lognormal estimada dos logaritmos reunidos da amostra real, n = 30.
- **Assimetria forte:** σ multiplicado por 1,35 em ambos os grupos, n = 30.
- **Outliers:** cada observação tem 5% de chance de ser multiplicada por 20,
  independentemente e de forma idêntica nos dois grupos, n = 30.
- **Amostra pequena:** mesma distribuição base, n = 10 por grupo.
- **Variâncias diferentes:** mesma mediana inicial, com σ multiplicado por 1,35
  apenas no grupo com bot; as médias e distribuições já diferem no efeito zero.

Nos quatro primeiros casos, efeito zero gera grupos independentes com a mesma
distribuição. O efeito positivo multiplica os tempos com bot por `1 + efeito`.
""")
    st.download_button("Baixar resultados das simulações", resultados_mc.to_csv(index=False),
                       file_name=f"simulacao_alfa_{alfa:.0%}.csv", mime="text/csv")

st.header("6. Dados reais")
resultado_real = aplicar_dados_reais(reais["com_bot"], reais["sem_bot"], alfa=alfa)
st.dataframe(tabela_secao6(resultado_real).style.format(
    {"Estatística": "{:.4f}", "p-valor": "{:.6f}", "Tamanho do efeito": "{:.4f}"}),
    hide_index=True, width="stretch")
st.markdown(texto_secao6(resultado_real))
st.caption("g de Hedges: diferença de médias dividida pelo desvio combinado, com correção "
           "para amostras pequenas. δ de Cliff: P(com bot demora mais) − P(com bot demora "
           "menos), entre −1 e 1. Valores positivos indicam mais tempo com bot. Magnitudes "
           "pelas faixas de Cohen (g) e de Romano et al. (δ).")
st.caption("Hedges padroniza a diferença, mas não elimina a assimetria nem torna "
           "as variâncias iguais; sua correção usual deriva do modelo normal. "
           "A amostra observacional continua sujeita a diferenças de complexidade dos PRs.")
st.subheader("Incerteza dos tamanhos de efeito")
try:
    intervalos = carregar_intervalos()
    if (not np.allclose(intervalos["confianca"], 0.95)
            or not intervalos["n_resamples"].eq(10_000).all()
            or not intervalos["semente"].eq(SEMENTE).all()):
        raise ValueError("Os intervalos usam confiança de 95%, 10.000 reamostragens e semente 42.")
except (FileNotFoundError, ValueError) as exc:
    st.warning(f"Os intervalos dos efeitos precisam ser gerados ou atualizados: {exc}")
    st.code(".venv/bin/python -m src.intervalos_efeito", language="bash")
else:
    st.dataframe(intervalos[["medida", "estimativa", "ic_inf", "ic_sup"]].rename(columns={
        "medida": "Medida do efeito", "estimativa": "Estimativa",
        "ic_inf": "IC 95% inferior", "ic_sup": "IC 95% superior",
    }).style.format({"Estimativa": "{:.4f}", "IC 95% inferior": "{:.4f}",
                     "IC 95% superior": "{:.4f}"}), hide_index=True, width="stretch")
    st.caption("Bootstrap BCa: 10.000 reamostragens independentes dentro de cada grupo, "
               "semente 42. Os IC permanecem em 95% para qualquer α selecionado. "
               "Eles descrevem a incerteza de g e δ; não são a inversão dos testes "
               "de Welch e Mann-Whitney. O procedimento assume PRs independentes "
               "e não preserva os estratos mensais da coleta.")
    st.download_button("Baixar intervalos dos efeitos", intervalos.to_csv(index=False),
                       file_name="efeitos_ic.csv", mime="text/csv")

st.header("7. Conclusão")
if textos is not None:
    st.markdown(textos["previsao"])
    st.markdown(textos["recomendacao"])
st.subheader("Quanto aumentar a amostra?")
try:
    amostra = carregar_amostra_alfa(alfa)
    if (not np.allclose(amostra["alfa"], alfa)
            or not amostra["reps"].eq(10_000).all()
            or not amostra["semente"].eq(SEMENTE).all()):
        raise ValueError(f"A análise usa α = {alfa:.0%}, semente 42 e 10.000 repetições.")
except (FileNotFoundError, ValueError) as exc:
    st.warning(f"A análise de tamanho da amostra precisa ser gerada ou atualizada: {exc}")
    st.code(comando_experimentos, language="bash")
else:
    st.plotly_chart(grafico_amostra(amostra), theme=None)
    st.markdown("A análise mantém o modelo base e varia o número de PRs por grupo. "
                "Compara uma mudança de 30% definida para planejamento com a mudança "
                "inspirada na razão das medianas observadas. O segundo cenário assume "
                "a mesma forma lognormal nos grupos: não estima um efeito causal "
                "nem comprova o poder do estudo realizado.")
    n_real = int(amostra["n_real_por_grupo"].iloc[0])
    no_n_real = amostra[amostra["n"] == n_real].copy()
    no_n_real["Teste"] = no_n_real["teste"].map(NOMES_TESTE)
    st.markdown(f"**Poder simulado com o tamanho real: {n_real} PRs por grupo.**")
    st.dataframe(no_n_real[["rotulo_efeito", "efeito", "Teste", "taxa_rejeicao",
                           "ic_inf", "ic_sup"]].rename(columns={
        "rotulo_efeito": "Referência", "efeito": "Mudança de escala", "taxa_rejeicao": "Poder",
        "ic_inf": "IC 95% inferior", "ic_sup": "IC 95% superior",
    }).style.format({
        "Mudança de escala": "{:+.1%}", "Poder": "{:.2%}",
        "IC 95% inferior": "{:.2%}", "IC 95% superior": "{:.2%}",
    }), hide_index=True, width="stretch")
    st.markdown("**Meta de 80% de poder na grade simulada.**")
    resumo_amostra = resumir_amostra(amostra)
    resumo_legivel = pd.DataFrame([
        {"Referência": r.rotulo_efeito, "Teste": NOMES_TESTE[r.teste],
         "Primeiro n testado com ≥80% (por grupo)":
             str(int(r.n_grade_80)) if r.atingiu_alvo else r.limite_censurado,
         "Poder no ponto reportado": r.poder_ponto_reportado,
         "IC 95%": f"{r.ic_inf:.2%} a {r.ic_sup:.2%}",
         "Limite inferior também ≥80%": "Sim" if r.limite_inferior_atinge_alvo else "Não"}
        for r in resumo_amostra.itertuples()
    ])
    st.dataframe(resumo_legivel.style.format({"Poder no ponto reportado": "{:.2%}"}),
                 hide_index=True, width="stretch")
    st.caption("O primeiro ponto da grade com taxa estimada de pelo menos 80% "
               "não é o tamanho mínimo exato. Se a meta não foi atingida, o resultado "
               "é um limite da busca; não extrapolamos um número. Os intervalos "
               "são pontuais: não corrigem a seleção adaptativa do n e medem somente "
               "o erro Monte Carlo, não a incerteza do efeito e do modelo.")
    st.download_button("Baixar análise de tamanho da amostra", amostra.to_csv(index=False),
                       file_name=f"amostra_alfa_{alfa:.0%}.csv", mime="text/csv")
