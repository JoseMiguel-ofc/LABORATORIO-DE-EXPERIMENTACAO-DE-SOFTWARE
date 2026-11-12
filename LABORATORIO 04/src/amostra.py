"""Planejamento de tamanho amostral por simulação no cenário lognormal base.

Execute ``python -m src.amostra`` para salvar curvas, resumo e metadados.
As curvas com o efeito observado são análises de sensibilidade condicionais ao
modelo, não evidência adicional nem validação por poder observado dos p-valores.
"""

import argparse
import sys
import hashlib
import importlib.metadata
import json
from numbers import Integral, Real
from pathlib import Path
import platform

import numpy as np
import pandas as pd

from src.cenario import ALFA, SEMENTE, ajustar_cenario
from src.dados import CSV, carregar
from src.testes import validar_alfa

RAIZ = Path(__file__).resolve().parent.parent
GRADE_N = (10, 20, 30, 50, 100, 200, 500, 1000, 2000)
ROTULOS = {
    "planejado_30pct": "Efeito planejado: +30%",
    "observado_mediana": "Efeito observado: razão de medianas",
}
ARQUIVOS_METODO = ("cenario.py", "simulacao.py", "motor.py", "testes.py", "amostra.py")


def _sha256(conteudo):
    return hashlib.sha256(conteudo).hexdigest()


def _json_estavel(valor):
    return json.dumps(valor, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()


def _hash_dataframe(df):
    return _sha256(df.to_csv(index=False, float_format="%.17g").encode())


def _hashes_metodo():
    return {nome: _sha256((RAIZ / "src" / nome).read_bytes())
            for nome in ARQUIVOS_METODO}


def _inteiro(valor, nome, minimo):
    if isinstance(valor, (bool, np.bool_)) or not isinstance(valor, Integral) or valor < minimo:
        raise ValueError(f"{nome} deve ser inteiro maior ou igual a {minimo}.")
    return int(valor)


def _grade(valores):
    try:
        grade = sorted({_inteiro(n, "n", 2) for n in valores})
    except TypeError as exc:
        raise ValueError("grade_n deve ser uma sequência de inteiros.") from exc
    if not grade:
        raise ValueError("grade_n não pode ser vazia.")
    return grade


def _efeitos(efeitos):
    if not isinstance(efeitos, dict) or not efeitos:
        raise ValueError("efeitos deve mapear nomes para valores numéricos.")
    resultado = {}
    for nome, efeito in efeitos.items():
        if not isinstance(nome, str) or not nome.strip():
            raise ValueError("Cada referência de efeito precisa de um nome não vazio.")
        if (isinstance(efeito, (bool, np.bool_)) or not isinstance(efeito, Real)
                or not np.isfinite(efeito) or efeito <= -1 or efeito == 0):
            raise ValueError("Para planejar poder, o efeito deve ser finito, maior que -1 e não zero.")
        resultado[nome] = float(efeito)
    return resultado


def analisar_amostra(grade_n=GRADE_N, efeitos=None, reps=10_000, semente=SEMENTE,
                    alfa=ALFA, *, df=None, cenario=None, tamanho_lote=500, progresso=None,
                    buscar_alvo=True, n_max=64_000):
    """Estima poder bilateral por n em dois efeitos, no cenário base comum.

    Cada n indica observações POR GRUPO. A grade é ordenada, deduplicada e inclui
    automaticamente o tamanho real (os grupos reais devem ser equilibrados).
    Por padrão usa +30% e mediana(com_bot)/mediana(sem_bot)−1. Ambos representam
    escala aplicada à mesma lognormal pooled; os sigmas reais diferentes não
    são preservados. A incerteza dos parâmetros e da razão observada não entra
    no IC Wilson, que quantifica somente o erro de Monte Carlo.

    O tamanho real é simulado primeiro e reutilizado na grade. Cada combinação
    (n, efeito) é calculada uma única vez. A mesma semente inicia cada célula;
    curvas compartilham números aleatórios, não são estimativas independentes.
    Com buscar_alvo=True, dobra n após o maior ponto da grade inicial, até cada
    teste atingir poder estimado 0,8 ou chegar a n_max. Somente testes ainda
    abaixo do alvo são computados nos pontos adicionais. Isso é busca em grade,
    não uma otimização que identifique o mínimo exato. ICs são pontuais, sem
    ajuste pela seleção adaptativa do ponto; não garantem poder de 80%.
    Retorna DataFrame do motor mais referencia_efeito, rotulo_efeito,
    n_real_por_grupo e alvo_poder. attrs['metadados'] registra reprodutibilidade.
    """
    from src.motor import simular

    reps = _inteiro(reps, "reps", 1)
    semente = _inteiro(semente, "semente", 0)
    tamanho_lote = _inteiro(tamanho_lote, "tamanho_lote", 1)
    n_max = _inteiro(n_max, "n_max", 2)
    if not isinstance(buscar_alvo, (bool, np.bool_)):
        raise ValueError("buscar_alvo deve ser booleano.")
    alfa = validar_alfa(alfa)
    grade = _grade(grade_n)
    fonte_padrao = df is None
    dados = carregar() if fonte_padrao else df
    ajuste_real = ajustar_cenario(dados)
    dados = dados.copy(deep=True)
    if progresso is not None and not callable(progresso):
        raise ValueError("progresso deve ser uma função ou None.")
    if cenario is None:
        cenario = ajuste_real
    tamanhos = ajuste_real["n_por_grupo"]
    if len(set(tamanhos.values())) != 1:
        raise ValueError("O planejamento atual exige grupos reais com o mesmo tamanho.")
    n_real = int(tamanhos["com_bot"])
    medianas = dados.groupby("grupo")["horas"].median()
    efeito_observado = float(medianas["com_bot"] / medianas["sem_bot"] - 1)
    if efeitos is None:
        efeitos = {"planejado_30pct": 0.30, "observado_mediana": efeito_observado}
    efeitos = _efeitos(efeitos)
    grade = sorted(set(grade) | {n_real})
    if buscar_alvo and n_max < max(grade):
        raise ValueError("n_max deve ser pelo menos o maior n da grade inicial e da amostra real.")
    ordem_execucao = [n_real] + [n for n in grade if n != n_real]
    cache = {}
    partes = []

    def calcular(referencia, efeito, n, testes):
        faltantes = tuple(teste for teste in testes if (n, efeito, teste) not in cache)
        if faltantes:
            if progresso is not None:
                progresso(referencia, n, efeito)
            simulados = simular(
                situacao="base", efeito=efeito, n=n, reps=reps,
                cenario=cenario, alfa=alfa, tamanho_lote=tamanho_lote,
                semente=semente, testes=faltantes,
            )
            for teste, linha in simulados.groupby("teste", sort=False):
                cache[(n, efeito, teste)] = linha.copy()
        parte = pd.concat([cache[(n, efeito, teste)] for teste in testes], ignore_index=True)
        parte["referencia_efeito"] = referencia
        parte["rotulo_efeito"] = ROTULOS.get(referencia, referencia)
        parte["n_real_por_grupo"] = n_real
        parte["alvo_poder"] = 0.8
        return parte

    for referencia, efeito in efeitos.items():
        pontos_referencia = []
        for n in ordem_execucao:
            pontos_referencia.append(calcular(referencia, efeito, n, ("welch", "mann_whitney")))
        n_atual = max(grade)
        curva_atual = pd.concat(pontos_referencia, ignore_index=True)
        faltantes = tuple(teste for teste, curva in curva_atual.groupby("teste")
                          if not curva["taxa_rejeicao"].ge(0.8).any())
        while buscar_alvo and faltantes and n_atual < n_max:
            n_atual = min(2 * n_atual, n_max)
            novo_ponto = calcular(referencia, efeito, n_atual, faltantes)
            pontos_referencia.append(novo_ponto)
            faltantes = tuple(novo_ponto.loc[novo_ponto["taxa_rejeicao"] < 0.8, "teste"])
        partes.extend(pontos_referencia)
    resultado = pd.concat(partes, ignore_index=True).sort_values(
        ["referencia_efeito", "teste", "n"], ignore_index=True,
    )
    resultado.attrs["metadados"] = {
        "versao_esquema": 1,
        "fonte": "dados/prs.csv" if fonte_padrao else "dataframe_fornecido",
        "tipo_hash_dados": "arquivo" if fonte_padrao else "dataframe",
        "dados_sha256": _sha256(CSV.read_bytes()) if fonte_padrao else _hash_dataframe(dados),
        "cenario": cenario,
        "cenario_sha256": _sha256(_json_estavel(cenario)),
        "metodo_sha256": _hashes_metodo(),
        "parametros": {"situacao": "base", "grade_n": grade, "efeitos": efeitos,
                       "n_real_por_grupo": n_real, "reps": reps, "semente": semente,
                       "alfa": alfa, "tamanho_lote": tamanho_lote, "alvo_poder": 0.8,
                       "buscar_alvo": bool(buscar_alvo), "n_max": n_max,
                       "grade_n_por_curva": {
                           referencia: {teste: sorted(curva["n"].astype(int).tolist())
                                        for teste, curva in grupo.groupby("teste")}
                           for referencia, grupo in resultado.groupby("referencia_efeito")}},
        "efeito_observado_mediana": efeito_observado,
        "versoes": {"python": platform.python_version(), **{
            pacote: importlib.metadata.version(pacote)
            for pacote in ("numpy", "pandas", "scipy")}},
        "interpretacao": (
            "Planejamento condicional à lognormal base de forma comum. O efeito observado "
            "é razão de medianas empíricas menos um; sua curva é sensibilidade, não "
            "evidência adicional para os testes reais. IC Wilson de 95% cobre apenas "
            "erro Monte Carlo; não inclui incerteza no efeito ou nos parâmetros. "
            "n80 é o primeiro ponto avaliado com poder estimado >= 0,8, não mínimo exato."
            " A extensão adaptativa dobra n somente para testes ainda abaixo do alvo; "
            "os ICs são pontuais e não corrigem a seleção do ponto da grade."
        ),
    }
    return resultado


def _validar_curvas(df):
    campos = {"referencia_efeito", "teste", "n", "reps", "taxa_rejeicao", "ic_inf", "ic_sup"}
    if not isinstance(df, pd.DataFrame) or df.empty or not campos.issubset(df.columns):
        raise ValueError("As curvas de amostra estão vazias ou não têm as colunas exigidas.")
    if df[list(campos)].isna().any().any():
        raise ValueError("As curvas de amostra contêm valores ausentes.")
    if not set(df["teste"]).issubset({"welch", "mann_whitney"}):
        raise ValueError("As curvas contêm um teste desconhecido.")
    for campo, minimo in (("n", 2), ("reps", 1)):
        valores = pd.to_numeric(df[campo], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(valores).all() or np.any(valores < minimo) or np.any(valores != np.floor(valores)):
            raise ValueError(f"As curvas têm {campo} inválido.")
    taxas = df[["taxa_rejeicao", "ic_inf", "ic_sup"]].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(taxas.to_numpy()).all() or ((taxas < 0) | (taxas > 1)).any().any():
        raise ValueError("As probabilidades e os limites de IC devem estar entre 0 e 1.")
    if ((taxas.ic_inf > taxas.taxa_rejeicao + 1e-12)
            | (taxas.ic_sup < taxas.taxa_rejeicao - 1e-12)).any():
        raise ValueError("O intervalo deve conter a estimativa de poder.")
    if df.duplicated(["referencia_efeito", "teste", "n"]).any():
        raise ValueError("Há pontos duplicados para a mesma curva e tamanho amostral.")


def resumir_amostra(df, alvo=0.8):
    """Resume o primeiro n da grade cuja estimativa pontual atinge o alvo.

    Se não atinge: n_grade_80 é NaN, atingiu_alvo é False e limite_censurado
    mostra '> n_max'. Não interpola nem extrapola um mínimo. O campo
    limite_inferior_atinge_alvo informa se o IC Wilson também supera o alvo;
    uma estimativa pontual >= alvo com IC inferior menor permanece incerta.
    """
    _validar_curvas(df)
    alvo = validar_alfa(alvo)
    linhas = []
    for (referencia, teste), curva in df.groupby(["referencia_efeito", "teste"], sort=True):
        curva = curva.sort_values("n")
        candidatos = curva.loc[curva["taxa_rejeicao"] >= alvo]
        atingiu = not candidatos.empty
        ponto = candidatos.iloc[0] if atingiu else curva.iloc[-1]
        n_max = int(curva["n"].max())
        linha = {"referencia_efeito": referencia, "teste": teste, "alvo_poder": alvo,
                 "n_grade_80": int(ponto["n"]) if atingiu else np.nan,
                 "atingiu_alvo": bool(atingiu), "n_max": n_max,
                 "limite_censurado": "" if atingiu else f"> {n_max}",
                 "n_ponto_reportado": int(ponto["n"]),
                 "poder_ponto_reportado": float(ponto["taxa_rejeicao"]),
                 "ic_inf": float(ponto["ic_inf"]), "ic_sup": float(ponto["ic_sup"]),
                 "limite_inferior_atinge_alvo": bool(ponto["ic_inf"] >= alvo),
                 "interpretacao": ("Primeiro ponto da grade que atinge o alvo estimado."
                                    if atingiu else "Alvo não atingido na grade avaliada.")}
        for campo in ("rotulo_efeito", "efeito", "n_real_por_grupo"):
            if campo in ponto:
                linha[campo] = ponto[campo]
        linhas.append(linha)
    return pd.DataFrame(linhas)


def salvar_amostra(df, diretorio=None):
    """Salva curvas, resumo e proveniência com hashes verificáveis."""
    _validar_curvas(df)
    metadados = dict(df.attrs.get("metadados", {}))
    if not metadados:
        raise ValueError("As curvas não têm metadados de analisar_amostra.")
    diretorio = Path(diretorio) if diretorio is not None else RAIZ / "resultados"
    diretorio.mkdir(parents=True, exist_ok=True)
    caminhos = {"curvas": diretorio / "amostra.csv", "resumo": diretorio / "amostra_resumo.csv",
                "metadados": diretorio / "amostra_metadados.json"}
    df.to_csv(caminhos["curvas"], index=False, float_format="%.17g", lineterminator="\n")
    resumir_amostra(df).to_csv(caminhos["resumo"], index=False, float_format="%.17g",
                                lineterminator="\n")
    metadados["arquivos_sha256"] = {
        caminhos[chave].name: _sha256(caminhos[chave].read_bytes())
        for chave in ("curvas", "resumo")}
    caminhos["metadados"].write_text(
        json.dumps(metadados, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return caminhos


def carregar_amostra(caminho=None, validar_metadados=True):
    """Lê curvas persistidas e rejeita resultados modificados ou desatualizados.

    Por padrão confere hash do CSV de curvas, fonte atual, cenário e código do
    método. A validação pode ser desativada explicitamente para inspeção de
    arquivos históricos, mas as colunas e probabilidades continuam validadas.
    """
    caminho = Path(caminho) if caminho is not None else RAIZ / "resultados" / "amostra.csv"
    metadados = {}
    if validar_metadados:
        arquivo_meta = caminho.with_name("amostra_metadados.json")
        try:
            metadados = json.loads(arquivo_meta.read_text(encoding="utf-8"))
            if metadados["versao_esquema"] != 1:
                raise ValueError("Versão de metadados de amostra incompatível.")
            if _sha256(caminho.read_bytes()) != metadados["arquivos_sha256"][caminho.name]:
                raise ValueError("O CSV de amostra foi modificado após a simulação.")
            hash_dados = (_sha256(CSV.read_bytes()) if metadados["tipo_hash_dados"] == "arquivo"
                          else _hash_dataframe(carregar()))
            if hash_dados != metadados["dados_sha256"]:
                raise ValueError("Os dados reais mudaram; gere novamente as curvas de amostra.")
            if _sha256(_json_estavel(ajustar_cenario())) != metadados["cenario_sha256"]:
                raise ValueError("Os parâmetros do cenário mudaram; gere novamente as curvas.")
            if _hashes_metodo() != metadados["metodo_sha256"]:
                raise ValueError("O método de simulação mudou; gere novamente as curvas de amostra.")
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Metadados de amostra ausentes, incompletos ou inválidos.") from exc
    df = pd.read_csv(caminho)
    _validar_curvas(df)
    df.attrs["metadados"] = metadados
    return df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grade-n", type=int, nargs="+", default=list(GRADE_N),
                        help="Tamanhos por grupo; o n real também será incluído.")
    parser.add_argument("--reps", type=int, default=10_000)
    parser.add_argument("--semente", type=int, default=SEMENTE)
    parser.add_argument("--tamanho-lote", type=int, default=500)
    parser.add_argument("--sem-busca-alvo", action="store_true",
                        help="Executa somente a grade solicitada, sem dobrar n até 80%.")
    parser.add_argument("--n-max", type=int, default=64_000,
                        help="Maior tamanho por grupo permitido na extensão adaptativa.")
    parser.add_argument("--saida", type=Path, default=RAIZ / "resultados")
    argumentos = parser.parse_args()
    try:
        curvas = analisar_amostra(argumentos.grade_n, reps=argumentos.reps,
                                 semente=argumentos.semente, tamanho_lote=argumentos.tamanho_lote,
                                 buscar_alvo=not argumentos.sem_busca_alvo, n_max=argumentos.n_max,
                                 progresso=lambda referencia, n, efeito: print(
                                     f"Simulando {referencia}: n={n} por grupo; efeito={efeito:.4g}",
                                     flush=True))
        caminhos = salvar_amostra(curvas, argumentos.saida)
    except ValueError as exc:
        parser.error(str(exc))
    print(resumir_amostra(curvas).to_string(index=False))
    for tipo, caminho in caminhos.items():
        print(f"{tipo}: {caminho}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
