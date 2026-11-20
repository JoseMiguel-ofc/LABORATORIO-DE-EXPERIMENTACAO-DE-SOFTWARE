"""Planejamento prospectivo sintético de H1: latência no pico > fora do pico.

Adapta o motor em lotes, a semente comum e o IC de Wilson do Lab04. Nenhum
dado coletado é lido. O resultado depende de pressupostos de planejamento,
não estima a potência real e não dimensiona H2 nem H3.
"""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
from numbers import Integral, Real
from pathlib import Path
import platform

import numpy as np
import pandas as pd
from scipy import signal, stats

DIAS = (7, 14, 21, 28, 42, 56)
EFEITOS = (0.0, 0.1, 0.2, 0.3)
SIGMAS = (0.5, 1.0)
RHOS = (0.0, 0.5)
PICO_INICIO_UTC = 14
PICO_FIM_UTC = 22
VERSAO_METODO = 1
SAIDA = Path(__file__).resolve().parent.parent / "resultados" / "planejamento"
CHAVE = ["dias", "efeito", "sigma_log", "rho", "cobertura"]
COLUNAS = CHAVE + ["n_pico", "n_fora", "reps", "alfa", "rejeicoes", "taxa_rejeicao",
                   "ic_inf", "ic_sup", "hipotese_nula_verdadeira", "semente"]


def _inteiro(valor, nome, minimo=1):
    if isinstance(valor, (bool, np.bool_)) or not isinstance(valor, Integral) or valor < minimo:
        raise ValueError(f"{nome} deve ser inteiro maior ou igual a {minimo}.")
    return int(valor)


def _real(valor, nome, inferior, superior, *, inclui_inferior=False, inclui_superior=False):
    if isinstance(valor, (bool, np.bool_)) or not isinstance(valor, Real):
        raise ValueError(f"{nome} deve ser um número real válido.")
    valor = float(valor)
    if (not np.isfinite(valor) or (valor < inferior if inclui_inferior else valor <= inferior)
            or (valor > superior if inclui_superior else valor >= superior)):
        raise ValueError(f"{nome} fora do intervalo permitido.")
    return valor


def intervalo_wilson(sucessos, repeticoes, confianca=0.95):
    """Incerteza binomial de Monte Carlo; não é um IC de latência observada."""
    repeticoes = _inteiro(repeticoes, "repeticoes")
    sucessos = _inteiro(sucessos, "sucessos", 0)
    confianca = _real(confianca, "confianca", 0, 1)
    if sucessos > repeticoes:
        raise ValueError("sucessos não pode exceder repeticoes.")
    z = stats.norm.ppf((1 + confianca) / 2)
    p = sucessos / repeticoes
    denominador = 1 + z*z/repeticoes
    centro = (p + z*z/(2*repeticoes)) / denominador
    margem = z * np.sqrt(p*(1-p)/repeticoes + z*z/(4*repeticoes**2)) / denominador
    return float(max(0, centro-margem)), float(min(1, centro+margem))


def indices_horarios(dias, cobertura=1.0):
    """Uma tentativa por hora/endpoint: 8 horas de pico e 16 fora por dia.

    Pico 14h–22h UTC é uma definição operacional provisória, não um fato
    observado sobre a Steam. Cobertura reduz cada grupo por espaçamento
    determinístico de índices; não modela falhas dependentes da latência.
    """
    dias = _inteiro(dias, "dias")
    cobertura = _real(cobertura, "cobertura", 0, 1, inclui_superior=True)
    horas = np.arange(24*dias)
    pico = (horas % 24 >= PICO_INICIO_UTC) & (horas % 24 < PICO_FIM_UTC)
    grupos = []
    for mascara in (pico, ~pico):
        indices = horas[mascara]
        quantidade = int(np.floor(len(indices)*cobertura))
        if quantidade < 2:
            raise ValueError("cobertura deixa menos de duas observações em um grupo.")
        grupos.append(indices[np.linspace(0, len(indices)-1, quantidade, dtype=int)])
    return tuple(grupos)


def _gerar_ar1(rng, quantidade, horas, rho):
    """AR(1) estacionário de variância 1, sem reinicializar nas meias-noites."""
    inovacoes = rng.standard_normal((quantidade, horas))
    if rho == 0:
        return inovacoes
    escala = np.sqrt(1-rho*rho)
    # X0 ~ N(0,1); Xt = rho*X(t-1) + sqrt(1-rho²)*epsilon_t.
    inovacoes[:, 0] /= escala
    return signal.lfilter([escala], [1, -rho], inovacoes, axis=1)


def _p_valores(pico, fora):
    return stats.mannwhitneyu(pico, fora, axis=1, alternative="greater",
                              method="asymptotic", use_continuity=False).pvalue


def simular(dias=28, efeito=0.2, sigma_log=1.0, rho=0.0, cobertura=1.0,
            reps=10_000, semente=42, alfa=0.05, tamanho_lote=128):
    """Uma configuração de H1 com Mann–Whitney unilateral (pico > fora).

    log(L_t) = sigma_log*X_t + I(pico)*log(1+efeito), com X_t AR(1).
    O MW usa os logs: exp é estritamente crescente e preserva todos os postos.
    A escala absoluta é irrelevante para este teste. Mesmo rho>0 mantém as
    distribuições marginais iguais sob efeito=0, mas viola independência;
    por isso suas taxas são diagnóstico de rejeição, não poder validado.
    """
    dias = _inteiro(dias, "dias")
    reps = _inteiro(reps, "reps")
    semente = _inteiro(semente, "semente", 0)
    tamanho_lote = _inteiro(tamanho_lote, "tamanho_lote")
    efeito = _real(efeito, "efeito", 0, 100, inclui_inferior=True, inclui_superior=True)
    sigma_log = _real(sigma_log, "sigma_log", 0, 100, inclui_superior=True)
    rho = _real(rho, "rho", 0, 1, inclui_inferior=True)
    alfa = _real(alfa, "alfa", 0, 1)
    pico_idx, fora_idx = indices_horarios(dias, cobertura)
    cobertura = float(cobertura)
    horas = 24*dias
    # Limite por lote; reduzir o lote não altera o fluxo de sorteios por réplica.
    tamanho_lote = min(tamanho_lote, max(1, 500_000 // horas))
    rng = np.random.default_rng(semente)
    rejeicoes = 0
    for inicio in range(0, reps, tamanho_lote):
        quantidade = min(tamanho_lote, reps-inicio)
        serie = _gerar_ar1(rng, quantidade, horas, rho) * sigma_log
        p = _p_valores(serie[:, pico_idx] + np.log1p(efeito), serie[:, fora_idx])
        if not np.isfinite(p).all():
            raise ValueError("A simulação gerou p-valores indefinidos.")
        rejeicoes += int(np.count_nonzero(p < alfa))
    inferior, superior = intervalo_wilson(rejeicoes, reps)
    return {"dias": dias, "efeito": efeito, "sigma_log": sigma_log, "rho": rho,
            "cobertura": cobertura, "n_pico": len(pico_idx), "n_fora": len(fora_idx),
            "reps": reps, "alfa": alfa, "rejeicoes": rejeicoes,
            "taxa_rejeicao": rejeicoes/reps, "ic_inf": inferior, "ic_sup": superior,
            "hipotese_nula_verdadeira": efeito == 0, "semente": semente}


def _grade(valores, nome):
    valores = tuple(valores)
    if not valores or len(set(valores)) != len(valores):
        raise ValueError(f"{nome} deve conter valores únicos e não pode estar vazia.")
    return valores


def executar_simulacao(dias=DIAS, efeitos=EFEITOS, sigmas=SIGMAS, rhos=RHOS,
                      reps=10_000, semente=42, alfa=0.05, cobertura=1.0,
                      tamanho_lote=128, progresso=None):
    """Grade prospectiva; inclui efeito=0 para conferir calibração em cada célula.

    A mesma semente reinicia em cada configuração: números aleatórios comuns
    entre efeitos/rhos/sigmas, intervalos pontuais sem ajuste de multiplicidade.
    Dias diferentes usam o mesmo fluxo, mas não trajetórias longitudinais
    aninhadas, pois cada linha simulada tem 24*dias horas.
    """
    dias, efeitos = _grade(dias, "dias"), _grade(efeitos, "efeitos")
    sigmas, rhos = _grade(sigmas, "sigmas"), _grade(rhos, "rhos")
    if 0 not in efeitos:
        raise ValueError("efeitos deve incluir zero para diagnosticar a calibração sob H0.")
    linhas = []
    total = len(dias)*len(efeitos)*len(sigmas)*len(rhos)
    for dia in dias:
        for sigma in sigmas:
            for rho in rhos:
                for efeito in efeitos:
                    linhas.append(simular(dia, efeito, sigma, rho, cobertura, reps,
                                          semente, alfa, tamanho_lote))
                    if progresso is not None:
                        progresso(len(linhas), total, linhas[-1])
    df = pd.DataFrame(linhas, columns=COLUNAS)
    df.attrs["metadados"] = _metadados(df)
    return df


def validar_resultados(dados):
    """Confere contagens, ICs, n por grupo, configurações e presença de H0."""
    if not isinstance(dados, pd.DataFrame) or not set(COLUNAS).issubset(dados.columns):
        raise ValueError("Resultados sem as colunas exigidas.")
    df = dados[COLUNAS].copy()
    if df.empty or df.isna().any().any() or df.duplicated(CHAVE).any():
        raise ValueError("Resultados vazios, ausentes ou duplicados.")
    for nome in [c for c in COLUNAS if c != "hipotese_nula_verdadeira"]:
        if not pd.api.types.is_numeric_dtype(df[nome]) or not np.isfinite(df[nome]).all():
            raise ValueError(f"Coluna {nome} deve conter números finitos.")
    for nome, minimo in (("dias", 1), ("reps", 1), ("rejeicoes", 0), ("semente", 0),
                         ("n_pico", 2), ("n_fora", 2)):
        if ((df[nome] < minimo) | (df[nome] % 1 != 0)).any():
            raise ValueError(f"Coluna {nome} inválida.")
        df[nome] = df[nome].astype(int)
    for coluna in ("alfa", "reps", "semente", "cobertura"):
        if df[coluna].nunique() != 1:
            raise ValueError(f"A grade deve usar uma única configuração de {coluna}.")
    for linha in df.itertuples():
        _real(linha.alfa, "alfa", 0, 1)
        _real(linha.sigma_log, "sigma_log", 0, 100, inclui_superior=True)
        _real(linha.rho, "rho", 0, 1, inclui_inferior=True)
        _real(linha.efeito, "efeito", 0, 100, inclui_inferior=True, inclui_superior=True)
        indices = indices_horarios(linha.dias, linha.cobertura)
        if (linha.n_pico, linha.n_fora) != tuple(map(len, indices)):
            raise ValueError("Tamanhos dos grupos não correspondem ao desenho horário.")
        ic = intervalo_wilson(linha.rejeicoes, linha.reps)
        if not np.allclose([linha.ic_inf, linha.ic_sup], ic, atol=1e-12, rtol=1e-10):
            raise ValueError("IC incompatível com Wilson 95%.")
        if not np.isclose(linha.taxa_rejeicao, linha.rejeicoes/linha.reps, atol=1e-12):
            raise ValueError("Taxa não corresponde às contagens.")
        if not isinstance(linha.hipotese_nula_verdadeira, (bool, np.bool_)) or (
                linha.hipotese_nula_verdadeira != (linha.efeito == 0)):
            raise ValueError("Indicador de hipótese nula inconsistente.")
    for _, grupo in df.groupby(["dias", "sigma_log", "rho", "cobertura"]):
        if 0 not in grupo.efeito.values:
            raise ValueError("Falta a configuração nula para diagnosticar calibração.")
    df.attrs.update(dados.attrs)
    return df.sort_values(CHAVE, ignore_index=True)


def resumir_planejamento(dados, alvo=0.8, efeito_planejado=0.2):
    """Primeiro dia avaliado com taxa ≥ alvo, condicionado ao cenário IID.

    O IC de H0 conter alfa é apenas diagnóstico, não prova de validade.
    Nunca recomenda MW independente para rho>0, mesmo quando seu IC de H0
    contém alfa. O alvo usa a estimativa pontual; informa também se o limite
    inferior de Wilson supera o alvo, sem prometer um mínimo exato.
    """
    df = validar_resultados(dados)
    alvo = _real(alvo, "alvo", 0, 1)
    efeito_planejado = _real(efeito_planejado, "efeito_planejado", 0, 100,
                             inclui_superior=True)
    selecionados = df[np.isclose(df.efeito, efeito_planejado, rtol=0, atol=1e-12)]
    if selecionados.empty:
        raise ValueError("efeito_planejado ausente da grade.")
    linhas = []
    for (sigma, rho, cobertura), grupo in selecionados.groupby(["sigma_log", "rho", "cobertura"]):
        grupo = grupo.sort_values("dias")
        cruzam = grupo[grupo.taxa_rejeicao >= alvo]
        escolhido = cruzam.iloc[0] if not cruzam.empty else grupo.iloc[-1]
        nulo = df[(df.dias == escolhido.dias) & (df.sigma_log == sigma) &
                  (df.rho == rho) & (df.cobertura == cobertura) & (df.efeito == 0)].iloc[0]
        calibracao = bool(nulo.ic_inf <= nulo.alfa <= nulo.ic_sup)
        elegivel = rho == 0 and calibracao
        atingiu = not cruzam.empty
        if rho != 0:
            interpretacao = ("Diagnóstico de dependência: MW independente pode estar descalibrado; "
                             "taxa de rejeição não justifica duração nem poder válido.")
        elif not calibracao:
            interpretacao = ("O IC do nulo não contém alfa nesta configuração; revisar a calibração "
                             "antes de usar a taxa como poder de planejamento.")
        elif not atingiu:
            interpretacao = "Alvo não alcançado na grade IID; duração necessária não determinada."
        else:
            interpretacao = ("Primeiro dia avaliado com estimativa de poder ≥ alvo, condicional "
                             "ao modelo IID e aos parâmetros sintéticos; não é mínimo exato.")
        linhas.append({"efeito_planejado": efeito_planejado, "sigma_log": sigma, "rho": rho,
                       "cobertura": cobertura, "alvo": alvo,
                       "primeiro_dia_taxa_alvo": int(escolhido.dias) if atingiu else pd.NA,
                       "dias_planejamento_iid": int(escolhido.dias) if atingiu and elegivel else pd.NA,
                       "dia_reportado": int(escolhido.dias), "max_dias_avaliado": int(grupo.dias.max()),
                       "taxa_rejeicao": float(escolhido.taxa_rejeicao),
                       "ic_inf": float(escolhido.ic_inf), "ic_sup": float(escolhido.ic_sup),
                       "alvo_atingido": atingiu, "limite_inferior_atinge_alvo": bool(escolhido.ic_inf >= alvo),
                       "taxa_nulo": float(nulo.taxa_rejeicao), "ic_nulo_inf": float(nulo.ic_inf),
                       "ic_nulo_sup": float(nulo.ic_sup), "nulo_compativel_alfa": calibracao,
                       "elegivel_planejamento_iid": elegivel, "interpretacao": interpretacao})
    resumo = pd.DataFrame(linhas)
    for coluna in ("primeiro_dia_taxa_alvo", "dias_planejamento_iid"):
        resumo[coluna] = resumo[coluna].astype("Int64")
    return resumo


def _metadados(df):
    return {
        "versao_metodo": VERSAO_METODO,
        "dados_reais_utilizados": False,
        "data_used": False,
        "hipotese_dimensionada": "H1: latência pico > fora; H2/H3 não dimensionadas",
        "teste": "Mann–Whitney U", "alternativa": "greater",
        "metodo": "asymptotic", "correcao_continuidade": False,
        "intervalo": "Wilson 95%, pontual, incerteza de Monte Carlo",
        "modelo": "log(L_t)=sigma*X_t+I(pico)*log(1+efeito); X_t AR(1) estacionário, Var=1",
        "pico_utc": {"inicio_inclusivo": PICO_INICIO_UTC, "fim_exclusivo": PICO_FIM_UTC,
                     "status": "definição operacional provisória, não inferida de dados"},
        "unidade": "uma observação por hora para um único endpoint; endpoints não são réplicas independentes",
        "cobertura": "floor(8*dias*cobertura) pico, floor(16*dias*cobertura) fora; espaçamento determinístico",
        "pressupostos_sinteticos": True,
        "limites": ["Modelo não inclui falhas/timeouts, rajadas, tendências ou mudança de runner.",
                    "Dependência AR(1) é sensibilidade; MW independente não corrige autocorrelação.",
                    "Não mede associação com usuários (H2) nem manutenção semanal (H3).",
                    "Dias de uma grade não são o menor tamanho possível; ICs não são simultâneos."],
        "configuracao": {"dias": sorted(df.dias.unique().astype(int).tolist()),
                         "efeitos": sorted(df.efeito.unique().astype(float).tolist()),
                         "sigmas": sorted(df.sigma_log.unique().astype(float).tolist()),
                         "rhos": sorted(df.rho.unique().astype(float).tolist()),
                         "reps": int(df.reps.iloc[0]), "semente": int(df.semente.iloc[0]),
                         "alfa": float(df.alfa.iloc[0]), "cobertura": float(df.cobertura.iloc[0])},
        "versoes": {"python": platform.python_version(), **{
            pacote: version(pacote) for pacote in ("numpy", "pandas", "scipy")}},
        "codigo_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "reuso_lab04": "motor em lotes, sementes comuns e Wilson; adaptação autocontida ao desenho horário H1",
        "referencias": ["https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html",
                        "https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.lfilter.html"],
    }


def salvar_resultados(dados, diretorio=SAIDA, alvo=0.8, efeito_planejado=0.2):
    """Grava CSV, resumo condicional e metadados auditáveis, sem ler a coleta."""
    df = validar_resultados(dados)
    resumo = resumir_planejamento(df, alvo, efeito_planejado)
    diretorio = Path(diretorio)
    diretorio.mkdir(parents=True, exist_ok=True)
    caminhos = {"csv": diretorio / "poder.csv", "resumo": diretorio / "poder_resumo.csv",
                "metadados": diretorio / "poder_metadados.json"}
    df.to_csv(caminhos["csv"], index=False)
    resumo.to_csv(caminhos["resumo"], index=False)
    metadados = _metadados(df)
    metadados.update({"gerado_em_utc": datetime.now(timezone.utc).isoformat(),
                      "csv_sha256": sha256(caminhos["csv"].read_bytes()).hexdigest(),
                      "resumo_sha256": sha256(caminhos["resumo"].read_bytes()).hexdigest(),
                      "resumo_configuracao": {"alvo": alvo, "efeito_planejado": efeito_planejado}})
    caminhos["metadados"].write_text(json.dumps(metadados, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")
    return caminhos


def carregar_resultados(diretorio=SAIDA):
    """Recusa arquivos alterados ou produzidos por outra versão do método."""
    diretorio = Path(diretorio)
    csv, resumo = diretorio / "poder.csv", diretorio / "poder_resumo.csv"
    manifesto = json.loads((diretorio / "poder_metadados.json").read_text(encoding="utf-8"))
    if (manifesto.get("csv_sha256") != sha256(csv.read_bytes()).hexdigest()
            or manifesto.get("resumo_sha256") != sha256(resumo.read_bytes()).hexdigest()
            or manifesto.get("codigo_sha256") != sha256(Path(__file__).read_bytes()).hexdigest()
            or manifesto.get("versao_metodo") != VERSAO_METODO
            or manifesto.get("dados_reais_utilizados") is not False):
        raise ValueError("Artefatos divergentes dos metadados; execute novamente a simulação.")
    df = validar_resultados(pd.read_csv(csv))
    df.attrs["metadados"] = manifesto
    return df


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reps", type=int, default=10_000)
    parser.add_argument("--semente", type=int, default=42)
    parser.add_argument("--alfa", type=float, default=0.05)
    parser.add_argument("--cobertura", type=float, default=1.0)
    parser.add_argument("--dias", type=int, nargs="+", default=DIAS)
    parser.add_argument("--efeitos", type=float, nargs="+", default=EFEITOS)
    parser.add_argument("--sigmas", type=float, nargs="+", default=SIGMAS)
    parser.add_argument("--rhos", type=float, nargs="+", default=RHOS)
    parser.add_argument("--tamanho-lote", type=int, default=128)
    parser.add_argument("--efeito-planejado", type=float, default=0.2)
    parser.add_argument("--alvo", type=float, default=0.8)
    parser.add_argument("--saida", type=Path, default=SAIDA)
    args = parser.parse_args(argv)
    def progresso(atual, total, linha):
        print(f"[{atual}/{total}] dias={linha['dias']}; efeito={linha['efeito']:.0%}; "
              f"sigma={linha['sigma_log']:g}; rho={linha['rho']:g}; "
              f"rejeição={linha['taxa_rejeicao']:.2%}", flush=True)
    df = executar_simulacao(args.dias, args.efeitos, args.sigmas, args.rhos, args.reps,
                           args.semente, args.alfa, args.cobertura, args.tamanho_lote, progresso)
    for nome, caminho in salvar_resultados(df, args.saida, args.alvo, args.efeito_planejado).items():
        print(f"{nome}: {caminho}")
    print("Resultados sintéticos prospectivos de H1. Não são dados nem potência observada da Steam.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
