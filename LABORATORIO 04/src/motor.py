"""Monte Carlo de Welch e Mann–Whitney, com rastreabilidade dos resultados."""

from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
from numbers import Integral
import os
from pathlib import Path
import platform
import tempfile

import numpy as np
import pandas as pd
from scipy import stats

from src.cenario import ALFA, SEMENTE, ajustar_cenario
from src.dados import CSV
from src.simulacao import SITUACOES, _gerar_lote, _validar_geracao
from src.testes import validar_alfa

RAIZ = Path(__file__).resolve().parent.parent
RESULTADOS = RAIZ / "resultados" / "simulacao.csv"
EFEITOS_PADRAO = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5)
TESTES = ("welch", "mann_whitney")
CHAVE = ["situacao", "efeito", "n", "teste", "alfa"]
COLUNAS = ["situacao", "efeito", "n", "reps", "teste", "alfa", "rejeicoes",
           "taxa_rejeicao", "ic_inf", "ic_sup", "hipotese_nula_verdadeira", "semente"]
VERSAO_METODO = 1


def _inteiro(valor, nome, minimo):
    if isinstance(valor, (bool, np.bool_)) or not isinstance(valor, Integral) or valor < minimo:
        raise ValueError(f"{nome} deve ser um inteiro maior ou igual a {minimo}.")
    return int(valor)


def intervalo_wilson(sucessos, repeticoes, confianca=0.95):
    """IC binomial de Wilson: incerteza de Monte Carlo, não dos PRs reais."""
    repeticoes = _inteiro(repeticoes, "repeticoes", 1)
    sucessos = _inteiro(sucessos, "sucessos", 0)
    if sucessos > repeticoes or not np.isfinite(confianca) or not 0 < confianca < 1:
        raise ValueError("Contagem ou confiança inválida para o intervalo de Wilson.")
    z = stats.norm.ppf((1 + confianca) / 2)
    p = sucessos / repeticoes
    denominador = 1 + z*z/repeticoes
    centro = (p + z*z/(2*repeticoes)) / denominador
    margem = z * np.sqrt(p*(1-p)/repeticoes + z*z/(4*repeticoes**2)) / denominador
    return float(max(0, centro-margem)), float(min(1, centro+margem))


def _p_valores(com_bot, sem_bot, testes=TESTES):
    """Mesmas alternativas e métodos da função escalar aplicar_testes."""
    resultados = {}
    if "welch" in testes:
        resultados["welch"] = stats.ttest_ind(com_bot, sem_bot, axis=1, equal_var=False,
                                             alternative="two-sided").pvalue
    if "mann_whitney" in testes:
        resultados["mann_whitney"] = stats.mannwhitneyu(
            com_bot, sem_bot, axis=1, alternative="two-sided", method="asymptotic",
            use_continuity=False).pvalue
    valores = np.column_stack([resultados[teste] for teste in testes])
    if not np.isfinite(valores).all():
        raise ValueError("A simulação produziu testes indefinidos; verifique os parâmetros.")
    return valores


def simular(situacao="base", efeito=0.0, n=30, reps=10_000, rng=None, *,
            cenario=None, alfa=ALFA, tamanho_lote=500, semente=SEMENTE,
            testes=TESTES):
    """Estima a probabilidade de rejeição com IC95% de Wilson.

    ``n`` é por grupo. A contagem usa p < alfa e o mesmo conjunto de amostras
    para os dois testes. O tamanho do lote afeta memória, não os sorteios.
    ``rng`` fornecido avança normalmente e registra semente nula, pois seu
    estado não pode ser atribuído honestamente à semente padrão.
    ``testes`` permite calcular somente o teste ainda necessário na busca de
    tamanho amostral; o padrão continua comparando os dois. O lote efetivo é
    limitado a um milhão de valores (ou uma repetição, quando n é maior).

    Só chamamos a taxa de erro tipo I quando a H0 é verdadeira. No cenário
    de variâncias diferentes, efeito zero mantém medianas iguais, mas médias
    e distribuições são diferentes; ali a taxa é somente taxa de rejeição.
    """
    if situacao not in SITUACOES:
        raise ValueError(f"situacao deve estar em {SITUACOES}.")
    if not isinstance(testes, (tuple, list)) or not testes or any(
            teste not in TESTES for teste in testes) or len(set(testes)) != len(testes):
        raise ValueError("testes deve conter nomes conhecidos, únicos e pelo menos um teste.")
    reps = _inteiro(reps, "reps", 1)
    tamanho_lote = _inteiro(tamanho_lote, "tamanho_lote", 1)
    alfa = validar_alfa(alfa)
    parametros = _validar_geracao(n, efeito, situacao, cenario)
    n = int(n)
    tamanho_lote = min(tamanho_lote, max(1, 1_000_000 // (2*n)))
    semente = _inteiro(semente, "semente", 0)
    if rng is None:
        rng = np.random.default_rng(semente)
        semente_registrada = semente
    elif isinstance(rng, np.random.Generator):
        semente_registrada = None
    else:
        raise ValueError("rng deve ser um numpy.random.Generator ou None.")

    rejeicoes = np.zeros(len(testes), dtype=np.int64)
    for inicio in range(0, reps, tamanho_lote):
        quantidade = min(tamanho_lote, reps-inicio)
        amostras = _gerar_lote(n, efeito, situacao, rng, parametros, quantidade)
        rejeicoes += np.count_nonzero(_p_valores(amostras[:, 0], amostras[:, 1], testes) < alfa,
                                     axis=0)
    linhas = []
    for teste, contagem in zip(testes, rejeicoes):
        ic_inf, ic_sup = intervalo_wilson(int(contagem), reps)
        linhas.append({"situacao": situacao, "efeito": float(efeito), "n": n,
                       "reps": reps, "teste": teste, "alfa": alfa,
                       "rejeicoes": int(contagem), "taxa_rejeicao": float(contagem/reps),
                       "ic_inf": ic_inf, "ic_sup": ic_sup,
                       "hipotese_nula_verdadeira": bool(efeito == 0 and
                                                        situacao != "variancias_diferentes"),
                       "semente": semente_registrada})
    return pd.DataFrame(linhas, columns=COLUNAS)


def executar_grade(reps=10_000, todas_situacoes=False, n=30, alfa=ALFA,
                   semente=SEMENTE, tamanho_lote=500, cenario=None, progresso=None):
    """Q1/Q2 base; com todas_situacoes inclui Q3 para G4.

    Cada configuração reinicia a mesma semente: utiliza números aleatórios
    comuns para comparação de efeitos e testes. As taxas entre pontos são
    correlacionadas; os ICs são individuais, não bandas simultâneas.
    """
    cenario = ajustar_cenario() if cenario is None else cenario
    situacoes = SITUACOES if todas_situacoes else ("base",)
    linhas = []
    total = len(situacoes) * len(EFEITOS_PADRAO)
    for situacao in situacoes:
        for efeito in EFEITOS_PADRAO:
            if progresso is not None:
                progresso(len(linhas)+1, total, situacao, efeito)
            linhas.append(simular(situacao, efeito,
                                  n=10 if situacao == "n_pequeno" else n,
                                  reps=reps, cenario=cenario, alfa=alfa,
                                  tamanho_lote=tamanho_lote, semente=semente))
    return pd.concat(linhas, ignore_index=True)


def validar_resultados(dados):
    """Rejeita resultados incompletos, duplicados ou numericamente incoerentes."""
    if not isinstance(dados, pd.DataFrame) or not set(COLUNAS).issubset(dados.columns):
        raise ValueError("O CSV de simulação não contém todas as colunas exigidas.")
    df = dados[COLUNAS].copy()
    if df.empty or df[CHAVE].isna().any().any() or df.duplicated(CHAVE).any():
        raise ValueError("O CSV contém configurações vazias, ausentes ou duplicadas.")
    if not df.situacao.isin(SITUACOES).all() or not df.teste.isin(TESTES).all():
        raise ValueError("O CSV contém situação ou teste desconhecido.")
    numericas = ["efeito", "n", "reps", "alfa", "rejeicoes", "taxa_rejeicao", "ic_inf", "ic_sup"]
    try:
        df[numericas] = df[numericas].apply(pd.to_numeric, errors="raise")
        sementes = pd.to_numeric(df.semente, errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError("O CSV contém valores não numéricos.") from exc
    if not np.isfinite(df[numericas].to_numpy(dtype=float)).all():
        raise ValueError("O CSV contém valores não finitos.")
    for coluna, minimo in (("n", 2), ("reps", 1), ("rejeicoes", 0)):
        if ((df[coluna] < minimo) | (df[coluna] % 1 != 0)).any():
            raise ValueError(f"O CSV contém {coluna} inválido.")
        df[coluna] = df[coluna].astype(int)
    sementes_validas = sementes.dropna()
    if ((sementes_validas < 0) | (sementes_validas % 1 != 0)).any():
        raise ValueError("O CSV contém semente inválida.")
    df["semente"] = sementes.astype("Int64")
    if ((df.efeito <= -1) | (df.alfa <= 0) | (df.alfa >= 1)
            | (df.rejeicoes > df.reps)).any():
        raise ValueError("O CSV contém efeito, alfa ou contagem inválidos.")
    if not np.allclose(df.taxa_rejeicao, df.rejeicoes/df.reps, rtol=1e-12, atol=1e-12):
        raise ValueError("As taxas não correspondem às contagens do CSV.")
    verdade = df.hipotese_nula_verdadeira.map({True: True, False: False,
                                             "True": True, "False": False})
    esperado = df.efeito.eq(0) & df.situacao.ne("variancias_diferentes")
    if verdade.isna().any() or not verdade.astype(bool).equals(esperado):
        raise ValueError("A identificação de H0 verdadeira é inconsistente.")
    df["hipotese_nula_verdadeira"] = verdade.astype(bool)
    intervalos = np.array([intervalo_wilson(int(k), int(r))
                          for k, r in zip(df.rejeicoes, df.reps)])
    if not np.allclose(df[["ic_inf", "ic_sup"]], intervalos, rtol=1e-10, atol=1e-12):
        raise ValueError("Os intervalos não correspondem ao IC95% de Wilson.")
    for _, grupo in df.groupby(["situacao", "efeito", "n", "alfa"], dropna=False):
        if set(grupo.teste) != set(TESTES) or grupo.reps.nunique() != 1 or grupo.semente.nunique(dropna=False) != 1:
            raise ValueError("Cada configuração precisa dos dois testes da mesma execução.")
    return df.sort_values(CHAVE, ignore_index=True)


def caminho_manifesto(caminho=RESULTADOS):
    return Path(caminho).with_suffix(".manifest.json")


def _hash_arquivo(caminho):
    return sha256(Path(caminho).read_bytes()).hexdigest()


def _contexto(cenario):
    return {"versao_metodo": VERSAO_METODO, "dados_sha256": _hash_arquivo(CSV),
            "codigo_sha256": _hashes_codigo(),
            "parametros": cenario, "alternativa": "two-sided",
            "mann_whitney": {"metodo": "asymptotic", "continuidade": False},
            "intervalo": "Wilson 95%", "sigma_fator": 1.35,
            "contaminacao_probabilidade": 0.05, "contaminacao_fator": 20.0}


def _hashes_codigo():
    return {nome: _hash_arquivo(RAIZ / "src" / nome)
            for nome in ("cenario.py", "simulacao.py", "testes.py", "motor.py")}


def carregar_resultados(caminho=None, *, validar_manifesto=True):
    """Lê e valida o CSV; por padrão também confere hashes e método do manifesto."""
    caminho = RESULTADOS if caminho is None else Path(caminho)
    dados = validar_resultados(pd.read_csv(caminho))
    if validar_manifesto:
        try:
            manifesto = json.loads(caminho_manifesto(caminho).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError("O manifesto de simulação está ausente ou inválido; execute novamente a grade.") from exc
        if (manifesto.get("csv_sha256") != _hash_arquivo(caminho)
                or manifesto.get("contexto", {}).get("dados_sha256") != _hash_arquivo(CSV)
                or manifesto.get("contexto", {}).get("codigo_sha256") != _hashes_codigo()
                or manifesto.get("contexto", {}).get("versao_metodo") != VERSAO_METODO):
            raise ValueError("CSV, dados ou método divergem do manifesto; execute novamente a grade.")
    return dados


def _temporario(destino, conteudo):
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=destino.parent,
                                     prefix=f".{destino.name}.", suffix=".tmp", delete=False) as arquivo:
        arquivo.write(conteudo)
        arquivo.flush()
        os.fsync(arquivo.fileno())
        return Path(arquivo.name)


def salvar_resultados(dados, caminho=None, *, cenario=None, configuracao=None,
                      substituir=False):
    """Atualiza por situação/efeito/n/teste/alfa, preservando Q3 em execução base.

    Cada arquivo é substituído atomicamente. O manifesto guarda o hash do CSV,
    de modo que uma interrupção entre as duas substituições é detectada na
    leitura. Não mistura resultados calibrados por dados ou métodos diferentes.
    ``substituir=True`` troca o conjunto completo, permitindo recuperar um
    arquivo obsoleto; a CLI usa essa opção ao recalcular todas as situações.
    """
    caminho = RESULTADOS if caminho is None else Path(caminho)
    cenario = ajustar_cenario() if cenario is None else cenario
    contexto = _contexto(cenario)
    novos = validar_resultados(dados)
    historico = []
    if caminho.exists() and not substituir:
        anteriores = carregar_resultados(caminho)
        manifesto_anterior = json.loads(caminho_manifesto(caminho).read_text(encoding="utf-8"))
        if manifesto_anterior["contexto"] != contexto:
            raise ValueError("O arquivo existente usa outra calibração; escolha outro caminho para a nova grade.")
        historico = manifesto_anterior.get("execucoes", [])
        novos = validar_resultados(pd.concat([anteriores, novos], ignore_index=True)
                                   .drop_duplicates(CHAVE, keep="last"))
    caminho.parent.mkdir(parents=True, exist_ok=True)
    texto_csv = novos.to_csv(index=False, lineterminator="\n")
    historico.append({"gerado_em_utc": datetime.now(timezone.utc).isoformat(),
                      "configuracao": configuracao or {},
                      "configuracoes_atualizadas": len(dados)//2})
    manifesto = {"contexto": contexto, "csv_sha256": sha256(texto_csv.encode()).hexdigest(),
                 "versoes": {nome: version(nome) for nome in ("numpy", "pandas", "scipy")},
                 "python": platform.python_version(), "execucoes": historico}
    manifesto_path = caminho_manifesto(caminho)
    temporarios = []
    try:
        temp_csv = _temporario(caminho, texto_csv)
        temporarios.append(temp_csv)
        temp_manifesto = _temporario(manifesto_path, json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n")
        temporarios.append(temp_manifesto)
        os.replace(temp_csv, caminho)
        os.replace(temp_manifesto, manifesto_path)
    finally:
        for temporario in temporarios:
            temporario.unlink(missing_ok=True)
    return novos
