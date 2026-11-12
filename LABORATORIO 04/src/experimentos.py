"""Pré-calcula e carrega os resultados para α = 1%, 5% e 10%.

O dashboard apenas lê estes arquivos. Cada alfa reinicia as mesmas sementes
nas mesmas células, preservando os sorteios e permitindo comparar limiares.
Os resultados originais de 5% continuam diretamente em ``resultados/``.
"""

import argparse
import sys
from hashlib import sha256
import json
from numbers import Integral
from pathlib import Path

import numpy as np

from src import amostra, dados as dados_reais, motor
from src.cenario import SEMENTE, ajustar_cenario
from src.simulacao import SITUACOES
from src.testes import validar_alfa

ALFAS = (0.01, 0.05, 0.10)


def _alfa_suportado(alfa):
    alfa = validar_alfa(alfa)
    if alfa not in ALFAS:
        raise ValueError("alfa deve ser 0.01, 0.05 ou 0.10.")
    return alfa


def diretorio_alfa(alfa, raiz=None):
    """Resolve o diretório sem criar arquivos; mantém o caminho histórico de 5%."""
    alfa = _alfa_suportado(alfa)
    raiz = motor.RAIZ / "resultados" if raiz is None else Path(raiz)
    return raiz if alfa == 0.05 else raiz / f"alfa_{round(alfa * 100):03d}"


def caminhos_alfa(alfa, raiz=None):
    diretorio = diretorio_alfa(alfa, raiz)
    return {"simulacao": diretorio / "simulacao.csv",
            "amostra": diretorio / "amostra.csv",
            "amostra_resumo": diretorio / "amostra_resumo.csv",
            "amostra_metadados": diretorio / "amostra_metadados.json"}


def _conferir_alfa(dados, alfa):
    if "alfa" not in dados or dados.empty or not dados["alfa"].eq(alfa).all():
        raise ValueError(f"O arquivo contém resultados de outro alfa; esperado α={alfa:g}.")


def carregar_simulacao_alfa(alfa, raiz=None):
    """Valida alfa e calibração real, além da integridade do manifesto."""
    alfa = _alfa_suportado(alfa)
    caminho = caminhos_alfa(alfa, raiz)["simulacao"]
    dados = motor.carregar_resultados(caminho)
    _conferir_alfa(dados, alfa)
    manifesto = json.loads(motor.caminho_manifesto(caminho).read_text(encoding="utf-8"))
    if manifesto.get("contexto", {}).get("parametros") != ajustar_cenario():
        raise ValueError("A simulação usa outro cenário; esperado o ajuste dos dados reais atuais.")
    return dados


def carregar_amostra_alfa(alfa, raiz=None):
    alfa = _alfa_suportado(alfa)
    dados = amostra.carregar_amostra(caminhos_alfa(alfa, raiz)["amostra"])
    _conferir_alfa(dados, alfa)
    if dados.attrs["metadados"].get("parametros", {}).get("alfa") != alfa:
        raise ValueError(f"Os metadados de amostra usam outro alfa; esperado α={alfa:g}.")
    _conferir_cenario_efeitos_amostra(dados)
    return dados


def _conferir_cenario_efeitos_amostra(dados):
    """Nomes de curvas não bastam: confere os efeitos realmente simulados."""
    fonte = dados_reais.carregar()
    cenario = ajustar_cenario(fonte)
    medianas = fonte.groupby("grupo")["horas"].median()
    efeitos = {"planejado_30pct": 0.3,
               "observado_mediana": float(medianas["com_bot"] / medianas["sem_bot"] - 1)}
    meta = dados.attrs["metadados"]
    if meta.get("cenario") != cenario:
        raise ValueError("As curvas de amostra usam outro cenário; esperado o ajuste dos dados reais atuais.")
    if meta.get("parametros", {}).get("efeitos") != efeitos:
        raise ValueError("As curvas de amostra usam outros efeitos; esperado +30% e a razão de medianas reais.")
    if (not {"referencia_efeito", "efeito"}.issubset(dados.columns)
            or set(dados["referencia_efeito"]) != set(efeitos)):
        raise ValueError("As curvas de amostra não contêm as referências de efeito esperadas.")
    for referencia, efeito in efeitos.items():
        valores = dados.loc[dados["referencia_efeito"].eq(referencia), "efeito"]
        try:
            coerentes = np.isclose(valores.to_numpy(dtype=float), efeito, rtol=1e-12, atol=1e-14)
        except (TypeError, ValueError) as exc:
            raise ValueError("Os efeitos das curvas de amostra não são numéricos.") from exc
        if not coerentes.all():
            raise ValueError("Os efeitos no CSV de amostra divergem dos efeitos reais esperados.")


def _inteiro(valor, nome, minimo):
    if isinstance(valor, (bool, np.bool_)) or not isinstance(valor, Integral) or valor < minimo:
        raise ValueError(f"{nome} deve ser inteiro maior ou igual a {minimo}.")
    return int(valor)


def _grade_reutilizavel(dados, reps, semente):
    esperadas = {(situacao, efeito, 10 if situacao == "n_pequeno" else 30, teste)
                 for situacao in SITUACOES for efeito in motor.EFEITOS_PADRAO
                 for teste in motor.TESTES}
    presentes = set(dados[["situacao", "efeito", "n", "teste"]]
                    .itertuples(index=False, name=None))
    return (presentes == esperadas and len(dados) == len(esperadas)
            and dados["reps"].eq(reps).all()
            and dados["semente"].notna().all()
            and dados["semente"].eq(semente).all())


def _amostra_reutilizavel(dados, caminhos, reps, semente, n_max, cenario):
    meta = dados.attrs["metadados"]
    params = meta.get("parametros", {})
    grade = sorted(set(amostra.GRADE_N) | {cenario["n_por_grupo"]["com_bot"]})
    esperados = {"reps": reps, "semente": semente, "n_max": n_max,
                 "buscar_alvo": True, "grade_n": grade, "alvo_poder": 0.8}
    resumo = caminhos["amostra_resumo"]
    return (all(params.get(chave) == valor for chave, valor in esperados.items())
            and dados["reps"].eq(reps).all() and dados["semente"].eq(semente).all()
            and set(dados["referencia_efeito"]) == set(amostra.ROTULOS)
            and resumo.is_file()
            and sha256(resumo.read_bytes()).hexdigest()
            == meta.get("arquivos_sha256", {}).get(resumo.name))


def precomputar(reps=10_000, semente=SEMENTE, n_max=64_000, *, raiz=None,
                alfas=ALFAS, forcar=False, progresso=print):
    """Gera Q1/Q2/Q3 e busca de n por alfa, reutilizando caches válidos.

    ``forcar`` recalcula tudo. Sem ele, cada fase é validada separadamente:
    uma curva ausente não exige refazer a grade. Progresso recebe uma mensagem
    por fase/célula; a busca adaptativa não tem total conhecido a priori.
    """
    reps = _inteiro(reps, "reps", 1)
    semente = _inteiro(semente, "semente", 0)
    n_max = _inteiro(n_max, "n_max", max(amostra.GRADE_N))
    if not isinstance(forcar, (bool, np.bool_)):
        raise ValueError("forcar deve ser booleano.")
    if progresso is not None and not callable(progresso):
        raise ValueError("progresso deve ser uma função ou None.")
    try:
        alfas = tuple(dict.fromkeys(_alfa_suportado(alfa) for alfa in alfas))
    except TypeError as exc:
        raise ValueError("alfas deve ser uma sequência de valores suportados.") from exc
    if not alfas:
        raise ValueError("alfas não pode ser vazio.")
    cenario = ajustar_cenario()
    if n_max < cenario["n_por_grupo"]["com_bot"]:
        raise ValueError("n_max deve incluir o tamanho da amostra real.")
    resultado = {}

    def informar(mensagem):
        if progresso is not None:
            progresso(mensagem)

    for alfa in alfas:
        prefixo = f"α={alfa:.0%}"
        caminhos = caminhos_alfa(alfa, raiz)
        grade = curvas = None
        if not forcar:
            try:
                candidato = carregar_simulacao_alfa(alfa, raiz)
                if _grade_reutilizavel(candidato, reps, semente):
                    grade = candidato
            except (OSError, ValueError):
                pass
            try:
                candidato = carregar_amostra_alfa(alfa, raiz)
                if _amostra_reutilizavel(candidato, caminhos, reps, semente, n_max, cenario):
                    curvas = candidato
            except (OSError, ValueError):
                pass
        if grade is None:
            grade = motor.executar_grade(
                reps=reps, todas_situacoes=True, n=30, alfa=alfa, semente=semente,
                cenario=cenario, progresso=lambda i, total, situacao, efeito: informar(
                    f"{prefixo} | Simulação [{i}/{total}] {situacao}, efeito={efeito:+.0%}"),
            )
            motor.salvar_resultados(
                grade, caminhos["simulacao"], cenario=cenario, substituir=True,
                configuracao={"reps": reps, "semente": semente, "alfa": alfa,
                              "n": 30, "todas_situacoes": True},
            )
        else:
            informar(f"{prefixo} | Simulação: cache válido reutilizado.")
        if curvas is None:
            curvas = amostra.analisar_amostra(
                reps=reps, semente=semente, alfa=alfa, cenario=cenario, n_max=n_max,
                progresso=lambda referencia, n, efeito: informar(
                    f"{prefixo} | Amostra: {referencia}, n={n} por grupo, efeito={efeito:+.1%}"),
            )
            amostra.salvar_amostra(curvas, diretorio_alfa(alfa, raiz))
        else:
            informar(f"{prefixo} | Amostra: cache válido reutilizado.")
        resultado[alfa] = {"simulacao": grade, "amostra": curvas, "caminhos": caminhos}
    return resultado


def argumentos(parser):
    """Argumentos comuns às CLIs experimentos e reproduzir."""
    parser.add_argument("--reps", type=int, default=10_000)
    parser.add_argument("--semente", type=int, default=SEMENTE)
    parser.add_argument("--n-max", type=int, default=64_000,
                        help="Limite por grupo da busca de 80%% de poder (mínimo: 2000).")
    parser.add_argument("--saida", type=Path, default=motor.RAIZ / "resultados",
                        help="Diretório raiz dos resultados.")
    parser.add_argument("--alfas", type=float, nargs="+", choices=ALFAS, default=ALFAS)
    parser.add_argument("--forcar", action="store_true",
                        help="Recalcula também os arquivos válidos existentes.")
    return parser


def main(argv=None):
    parser = argumentos(argparse.ArgumentParser(description=__doc__))
    args = parser.parse_args(argv)
    saida = args.saida if args.saida.is_absolute() else motor.RAIZ / args.saida
    try:
        precomputar(args.reps, args.semente, args.n_max, raiz=saida, alfas=args.alfas,
                    forcar=args.forcar, progresso=lambda texto: print(texto, flush=True))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(f"Resultados salvos em: {saida}")
    if args.reps < 10_000:
        print("Execução reduzida apenas para diagnóstico; a entrega usa 10.000 repetições.")
    return 0


# Saída redirecionada no Windows usa cp1252, que não tem α.
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
