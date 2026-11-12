"""ICs bootstrap BCa para os tamanhos de efeito nos dois grupos independentes.

Os intervalos são bilaterais, descritivos e orientados com bot menos sem bot.
O nível de confiança (95% por padrão) é independente do alfa dos testes Welch
e Mann–Whitney: estes ICs não são a inversão daqueles testes e não sustentam
conclusões causais. Execute ``python -m src.intervalos_efeito`` para salvar.
"""

import argparse
import sys
import hashlib
import importlib.metadata
import json
from numbers import Integral, Real
from pathlib import Path
import platform
import warnings

import numpy as np
import pandas as pd
from scipy.stats import bootstrap, DegenerateDataWarning

from src.dados import CSV, carregar
from src.efeito import _amostra, cliffs_delta, hedges_g


RAIZ = Path(__file__).resolve().parent.parent
METODO = "BCa"
ARQUIVOS_METODO = ("efeito.py", "intervalos_efeito.py")
MEDIDAS = {"welch": "g de Hedges", "mann_whitney": "δ de Cliff"}
COLUNAS = ("teste", "medida", "estimativa", "ic_inf", "ic_sup", "confianca",
           "n_resamples", "semente", "metodo")


def _sha256(conteudo):
    return hashlib.sha256(conteudo).hexdigest()


def _hash_amostras(com, sem):
    conteudo = {"com_bot": np.asarray(com, dtype=float).tolist(),
                "sem_bot": np.asarray(sem, dtype=float).tolist()}
    return _sha256(json.dumps(conteudo, sort_keys=True, allow_nan=False).encode())


def _hashes_metodo():
    return {nome: _sha256((RAIZ / "src" / nome).read_bytes())
            for nome in ARQUIVOS_METODO}


def _inteiro(valor, nome, minimo):
    if (isinstance(valor, (bool, np.bool_)) or not isinstance(valor, Integral)
            or valor < minimo):
        raise ValueError(f"{nome} deve ser inteiro maior ou igual a {minimo}.")
    return int(valor)


def _confianca(valor):
    if (isinstance(valor, (bool, np.bool_)) or not isinstance(valor, Real)
            or not np.isfinite(valor) or not 0 < valor < 1):
        raise ValueError("confianca deve ser um número finito entre zero e um.")
    return float(valor)


def _grupos_reais():
    dados = carregar()
    return (dados.loc[dados.grupo == "com_bot", "horas"].to_numpy(),
            dados.loc[dados.grupo == "sem_bot", "horas"].to_numpy())


def calcular_intervalos(com_bot, sem_bot, n_resamples=10_000, confianca=.95, semente=42):
    """Retorna g de Hedges e delta de Cliff com ICs BCa bilaterais.

    SciPy reamostra separadamente os dois grupos (paired=False), preservando
    cada tamanho original. As mesmas sequências de índices são utilizadas
    para as duas medidas: cada chamada inicia um Generator com a mesma semente
    e batch=500. Nenhuma observação é pareada entre grupos. O jackknife BCa
    remove uma observação por vez, por isso são necessárias pelo menos três
    observações por grupo para as funções de efeito deste projeto.

    Distribuições degeneradas, reamostras com g indefinido ou ICs não finitos
    geram ValueError; não se descartam reamostras nem se troca o método sem
    informar. Os ICs BCa não precisam conter a estimativa pontual. O resultado
    inclui attrs['metadados'] para salvar e verificar sua procedência.
    """
    n_resamples = _inteiro(n_resamples, "n_resamples", 2)
    semente = _inteiro(semente, "semente", 0)
    confianca = _confianca(confianca)
    com = _amostra(com_bot, "com_bot")
    sem = _amostra(sem_bot, "sem_bot")
    if min(len(com), len(sem)) < 3:
        raise ValueError("O jackknife BCa exige ao menos três observações por grupo.")
    linhas = []
    for teste, funcao in (("welch", hedges_g), ("mann_whitney", cliffs_delta)):
        medida = MEDIDAS[teste]
        try:
            estimativa = funcao(com, sem)
            with warnings.catch_warnings(record=True) as avisos:
                warnings.simplefilter("always", DegenerateDataWarning)
                warnings.simplefilter("always", RuntimeWarning)
                resultado = bootstrap(
                    (com, sem), funcao, n_resamples=n_resamples, batch=500,
                    vectorized=False, paired=False, confidence_level=confianca,
                    alternative="two-sided", method=METODO,
                    random_state=np.random.default_rng(semente),
                )
            limites = np.asarray(resultado.confidence_interval, dtype=float)
            distribuicao = np.asarray(resultado.bootstrap_distribution, dtype=float)
            degenerado = any(issubclass(aviso.category, DegenerateDataWarning)
                             for aviso in avisos)
            if (degenerado or not np.isfinite(distribuicao).all()
                    or not np.isfinite(limites).all()
                    or np.ptp(distribuicao) == 0 or limites[0] > limites[1]):
                raise ValueError("distribuição bootstrap ou jackknife degenerado; IC BCa indefinido")
        except (ValueError, FloatingPointError) as exc:
            raise ValueError(f"Não foi possível calcular o IC BCa de {medida}: {exc}. "
                             "Nenhuma reamostra foi descartada; revise a variabilidade "
                             "e o tamanho dos grupos.") from exc
        linhas.append({"teste": teste, "medida": medida, "estimativa": estimativa,
                       "ic_inf": float(limites[0]), "ic_sup": float(limites[1]),
                       "confianca": confianca, "n_resamples": n_resamples,
                       "semente": semente, "metodo": METODO})
    df = pd.DataFrame(linhas, columns=COLUNAS)
    df.attrs["metadados"] = {
        "versao_esquema": 1, "fonte": "amostras_fornecidas",
        "dados_sha256": _hash_amostras(com, sem), "metodo_sha256": _hashes_metodo(),
        "parametros": {"n_resamples": n_resamples, "confianca": confianca,
                       "semente": semente, "metodo": METODO, "paired": False,
                       "alternative": "two-sided", "batch": 500,
                       "n_com_bot": len(com), "n_sem_bot": len(sem)},
        "versoes": {"python": platform.python_version(), **{
            pacote: importlib.metadata.version(pacote)
            for pacote in ("numpy", "pandas", "scipy")}},
        "reamostragem": "Grupos independentes; mesma semente reiniciada por medida, "
                        "compartilhando índices de reamostragem entre as duas medidas.",
        "interpretacao": "Efeitos descritivos, com bot menos sem bot, sem interpretação "
                         "causal. ICs BCa não são inversões dos testes Welch e Mann–Whitney. "
                         "Confiança independente do alfa do dashboard; sem ajuste "
                         "simultâneo entre as duas medidas.",
    }
    return df


def gerar_intervalos_reais(n_resamples=10_000, confianca=.95, semente=42):
    """Calcula ICs dos dados reais e registra também o hash do CSV de origem."""
    com, sem = _grupos_reais()
    resultado = calcular_intervalos(com, sem, n_resamples, confianca, semente)
    resultado.attrs["metadados"]["fonte"] = "dados/prs.csv"
    resultado.attrs["metadados"]["arquivo_dados_sha256"] = _sha256(CSV.read_bytes())
    return resultado


def _validar_intervalos(df):
    if not isinstance(df, pd.DataFrame) or not set(COLUNAS).issubset(df.columns):
        raise ValueError("Intervalos de efeito devem conter todas as colunas esperadas.")
    if len(df) != 2 or set(df.teste) != set(MEDIDAS):
        raise ValueError("É necessária uma linha de intervalo para cada medida de efeito.")
    for linha in df.itertuples(index=False):
        if linha.medida != MEDIDAS[linha.teste] or linha.metodo != METODO:
            raise ValueError("Medida ou método de intervalo incompatível.")
        _confianca(linha.confianca)
        _inteiro(linha.n_resamples, "n_resamples", 2)
        _inteiro(linha.semente, "semente", 0)
        valores = [linha.estimativa, linha.ic_inf, linha.ic_sup]
        if any(isinstance(v, (bool, np.bool_)) or not isinstance(v, Real)
               or not np.isfinite(v) for v in valores):
            raise ValueError("Estimativas e limites devem ser números finitos.")
        if linha.ic_inf > linha.ic_sup:
            raise ValueError("O limite inferior não pode superar o superior.")
        if linha.teste == "mann_whitney" and any(abs(v) > 1 for v in valores):
            raise ValueError("Delta de Cliff e seus limites devem estar entre -1 e 1.")
    if any(df[campo].nunique() != 1 for campo in ("confianca", "n_resamples", "semente")):
        raise ValueError("As duas medidas devem compartilhar a configuração do bootstrap.")


def _validar_configuracao(df, metadados):
    try:
        if metadados["versao_esquema"] != 1:
            raise ValueError("Versão de metadados de intervalos incompatível.")
        parametros = metadados["parametros"]
        for campo in ("confianca", "n_resamples", "semente", "metodo"):
            if not df[campo].eq(parametros[campo]).all():
                raise ValueError("A configuração do bootstrap não corresponde aos resultados.")
        if (parametros["paired"] is not False or parametros["alternative"] != "two-sided"
                or parametros["batch"] != 500):
            raise ValueError("Método bootstrap diferente do método independente bilateral esperado.")
        for campo in ("n_com_bot", "n_sem_bot"):
            _inteiro(parametros[campo], campo, 3)
        for campo in ("dados_sha256", "metodo_sha256", "versoes"):
            if not metadados[campo]:
                raise ValueError("Metadados de intervalos incompletos.")
    except (KeyError, TypeError) as exc:
        raise ValueError("Metadados de intervalos ausentes, incompletos ou inválidos.") from exc


def salvar_intervalos(df, caminho=None):
    """Salva CSV e manifesto ao lado dele, preservando configuração e hashes."""
    _validar_intervalos(df)
    metadados = dict(df.attrs.get("metadados", {}))
    _validar_configuracao(df, metadados)
    caminho = Path(caminho) if caminho is not None else RAIZ / "resultados" / "efeitos_ic.csv"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    manifesto = caminho.with_name(caminho.stem + "_metadados.json")
    df.to_csv(caminho, index=False, float_format="%.17g", lineterminator="\n")
    metadados["arquivos_sha256"] = {caminho.name: _sha256(caminho.read_bytes())}
    manifesto.write_text(json.dumps(metadados, ensure_ascii=False, indent=2, allow_nan=False)
                         + "\n", encoding="utf-8")
    return {"csv": caminho, "metadados": manifesto}


def carregar_intervalos(caminho=None):
    """Carrega ICs somente se CSV, dados reais, método e configuração são coerentes.

    O caminho padrão é relativo à raiz do projeto, independente do diretório
    corrente. Resultados de amostras sintéticas podem ser salvos para inspeção,
    mas este carregador aceita somente os grupos do dataset real atual.
    """
    caminho = Path(caminho) if caminho is not None else RAIZ / "resultados" / "efeitos_ic.csv"
    manifesto = caminho.with_name(caminho.stem + "_metadados.json")
    try:
        metadados = json.loads(manifesto.read_text(encoding="utf-8"))
        if _sha256(caminho.read_bytes()) != metadados["arquivos_sha256"][caminho.name]:
            raise ValueError("O CSV de intervalos foi modificado após o cálculo.")
        df = pd.read_csv(caminho)
        _validar_intervalos(df)
        _validar_configuracao(df, metadados)
        com, sem = _grupos_reais()
        if _hash_amostras(com, sem) != metadados["dados_sha256"]:
            raise ValueError("Os dados reais mudaram; gere novamente os intervalos de efeito.")
        if ("arquivo_dados_sha256" in metadados
                and _sha256(CSV.read_bytes()) != metadados["arquivo_dados_sha256"]):
            raise ValueError("O CSV de origem mudou; gere novamente os intervalos de efeito.")
        if _hashes_metodo() != metadados["metodo_sha256"]:
            raise ValueError("O método mudou; gere novamente os intervalos de efeito.")
        if (metadados["parametros"]["n_com_bot"] != len(com)
                or metadados["parametros"]["n_sem_bot"] != len(sem)):
            raise ValueError("Tamanhos dos grupos não correspondem aos metadados.")
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Metadados de intervalos ausentes, incompletos ou inválidos.") from exc
    df.attrs["metadados"] = metadados
    return df


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-resamples", "--reps", type=int, default=10_000)
    parser.add_argument("--confianca", type=float, default=.95)
    parser.add_argument("--semente", type=int, default=42)
    parser.add_argument("--saida", type=Path, default=RAIZ / "resultados" / "efeitos_ic.csv")
    args = parser.parse_args(argv)
    try:
        resultado = gerar_intervalos_reais(args.n_resamples, args.confianca, args.semente)
        caminhos = salvar_intervalos(resultado, args.saida)
    except ValueError as exc:
        parser.error(str(exc))
    print(resultado.to_string(index=False))
    for tipo, caminho in caminhos.items():
        print(f"{tipo}: {caminho}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
