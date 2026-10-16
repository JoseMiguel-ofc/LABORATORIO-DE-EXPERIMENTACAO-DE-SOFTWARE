"""CFR de CI (a) e proxy por releases corretivas (b), como frações 0–1.

Em (b), a próxima release estável precisa incrementar somente o patch SemVer,
conter uma palavra corretiva nos commits da comparação e sair em até sete dias.
A falha pertence à release ANTERIOR; ``corretiva`` descreve a PRÓPRIA release.
``v1`` reconhece fix/hotfix/revert inteiros; ``v2`` também reconhece suas flexões
inglesas. São versões candidatas, sem alegação de validação humana.
"""

from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone
import re

from metricas.frequencia import data_da_janela, semanas_da_janela
from metricas.lead_time import instante
from pipeline.funil import CONCLUSOES_FALHA, CONCLUSOES_SUCESSO


VERSOES_HEURISTICA = ("v1", "v2")
DIAS_CORRETIVA = 7
_PALAVRAS = {
    "v1": re.compile(r"\b(?:fix|hotfix|revert)\b", re.IGNORECASE),
    "v2": re.compile(r"\b(?:fix(?:es|ed|ing)?|hotfix(?:es|ed|ing)?|revert(?:s|ed|ing)?)\b",
                     re.IGNORECASE),
}
_SEMVER = re.compile(
    r"^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
DEFINICOES_VERSOES = {
    versao: {
        "dias_corretiva": DIAS_CORRETIVA,
        "conjuncao": "AND",
        "sequencia": "proxima release estavel do mesmo repositorio",
        "patch": "major e minor iguais; patch estritamente maior; prefixo v opcional",
        "fonte_textual": "mensagens de commits entre tags consecutivas",
        "palavras": (["fix", "hotfix", "revert"] if versao == "v1" else
                     ["fix", "fixes", "fixed", "fixing", "hotfix", "hotfixes",
                      "hotfixed", "hotfixing", "revert", "reverts", "reverted", "reverting"]),
        "palavras_inteiras": True,
        "ignora_maiusculas": True,
        "censura": "originais sem sete dias completos ate o fim da janela",
        "validada": False,
    } for versao in VERSOES_HEURISTICA
}


def calcular_cfr(runs):
    """Falhas / (falhas + sucessos); None se não houver runs válidos."""
    conclusoes = [run.get("conclusion") for run in runs
                  if run.get("conclusion") in CONCLUSOES_FALHA | CONCLUSOES_SUCESSO]
    if not conclusoes:
        return None
    return sum(conclusao in CONCLUSOES_FALHA for conclusao in conclusoes) / len(conclusoes)


def palavras_corretivas(mensagem, versao="v1"):
    """Busca palavras inteiras, sem diferenciar maiúsculas e minúsculas."""
    if versao not in _PALAVRAS:
        raise ValueError(f"versao deve ser uma de {VERSOES_HEURISTICA}")
    return isinstance(mensagem, str) and bool(_PALAVRAS[versao].search(mensagem))


def _verdadeiro(valor):
    # Os CSVs da coleta escrevem True/False como texto.
    return valor is True or str(valor).strip().lower() in {"true", "1", "sim"}


def _semver(tag):
    encontrado = _SEMVER.fullmatch(str(tag or ""))
    return tuple(map(int, encontrado.groups())) if encontrado else None


def _quantidade(valor):
    if valor is None or valor == "":
        return None
    try:
        numero = int(valor)
    except (ValueError, TypeError):
        return None
    return numero if numero >= 0 and str(numero) == str(valor) else None


def _evidencia(release, versao):
    """Lista completa em memória ou resumo produzido pelo leitor do CSV.gz.

    O resumo tem ``v1``/``v2`` booleanos, ``total`` de SHAs únicos e
    ``incompletos`` (mensagens ausentes). Uma extração parcial nunca vira zero.
    """
    status = release.get("commits_status")
    if status and status not in {"ok", "sem_commits"}:
        return None, f"commits_{status}"
    esperado = _quantidade(release.get("commits_novos"))
    resumo = release.get("evidencia_commits")
    if resumo is not None:
        total = _quantidade(resumo.get("total"))
        incompletos = _quantidade(resumo.get("incompletos"))
        if (total is None or incompletos != 0 or
                (esperado is not None and total != esperado)):
            return None, "commits_incompletos"
        palavra = resumo.get(versao)
        if not isinstance(palavra, bool):
            return None, "mensagens_indisponiveis"
        return palavra, "ok"
    commits = release.get("commits")
    if commits is None:
        if status == "sem_commits" and esperado == 0:
            return False, "ok"
        return None, "commits_indisponiveis"
    vistos, mensagens = set(), []
    for commit in commits:
        sha = commit.get("sha")
        if sha and sha in vistos:
            continue
        if sha:
            vistos.add(sha)
        mensagem = commit.get("message", (commit.get("commit") or {}).get("message"))
        if not isinstance(mensagem, str) or not mensagem.strip():
            return None, "mensagens_indisponiveis"
        mensagens.append(mensagem)
    if esperado is not None and len(mensagens) != esperado:
        return None, "commits_incompletos"
    return any(palavras_corretivas(m, versao) for m in mensagens), "ok"


def classificar_corretiva(release, anterior=None, *, versao="v1"):
    """Classifica a própria release contra a imediatamente anterior estável.

    ``None`` representa evidência insuficiente, não um rótulo negativo. A função
    não aplica a censura de CFR: uma release nos últimos sete dias ainda pode
    ser identificada como corretiva. Para ordenar/detectar empates no histórico,
    use ``analisar_cfr_b`` e leia o campo ``corretiva`` de cada registro.
    """
    palavras_corretivas("", versao)  # valida também se não há commits
    resultado = {"corretiva": None, "motivo_corretiva": "", "versao": versao,
                 "tag_anterior": anterior.get("tag_name", "") if anterior else "",
                 "intervalo_dias": None, "patch_semver": None,
                 "palavra_corretiva": None}

    def concluir(valor, motivo):
        return {**resultado, "corretiva": valor, "motivo_corretiva": motivo}

    if _verdadeiro(release.get("draft")) or _verdadeiro(release.get("prerelease")):
        return concluir(None, "release_nao_estavel")
    publicada = instante(release.get("published_at"))
    if publicada is None:
        return concluir(None, "data_invalida")
    if anterior is None:
        return concluir(None, "primeira_release")
    if (release.get("full_name") and anterior.get("full_name") and
            release["full_name"] != anterior["full_name"]):
        return concluir(None, "repositorios_diferentes")
    if _verdadeiro(anterior.get("draft")) or _verdadeiro(anterior.get("prerelease")):
        return concluir(None, "predecessora_nao_estavel")
    data_anterior = instante(anterior.get("published_at"))
    if data_anterior is None:
        return concluir(None, "data_anterior_invalida")
    intervalo = publicada - data_anterior
    resultado["intervalo_dias"] = intervalo.total_seconds() / 86400
    if intervalo <= timedelta(0):
        return concluir(None, "ordem_temporal_ambigua")
    if intervalo > timedelta(days=DIAS_CORRETIVA):
        return concluir(False, "intervalo_maior_7_dias")
    base, atual = _semver(anterior.get("tag_name")), _semver(release.get("tag_name"))
    if base is None or atual is None:
        return concluir(None, "tag_nao_semver")
    patch = atual[:2] == base[:2] and atual[2] > base[2]
    resultado["patch_semver"] = patch
    if not patch:
        return concluir(False, "nao_incrementa_somente_patch")
    comparada = release.get("tag_anterior")
    if comparada and comparada != anterior.get("tag_name"):
        return concluir(None, "comparacao_predecessora_divergente")
    palavra, motivo = _evidencia(release, versao)
    resultado["palavra_corretiva"] = palavra
    if palavra is None:
        return concluir(None, motivo)
    return concluir(palavra, "patch_com_palavra_corretiva" if palavra else "sem_palavra_corretiva")


def analisar_cfr_b(releases, inicio, fim, *, versao="v1"):
    """Calcula falhas/observações completas com auditoria por release original.

    A janela inclui ambos os dias em UTC. Somente originais estáveis na janela,
    com sete dias inteiros observáveis até o fim e resultado determinável entram
    no denominador. Originais censuradas ou inconclusivas ficam separadas.
    A sequência é sempre por repositório; tags pré-janela servem como contexto.
    Espera histórico completo, conforme o coletor de releases. Ausência de
    sucessora nesse histórico significa ausência observada de correção.
    """
    palavras_corretivas("", versao)
    semanas_da_janela(inicio, fim)
    comeco = datetime.combine(data_da_janela(inicio), time.min, timezone.utc)
    termino = datetime.combine(data_da_janela(fim), time.max, timezone.utc)
    horizonte = timedelta(days=DIAS_CORRETIVA)
    registros, por_repo, datas_invalidas = [], defaultdict(list), set()
    for release in releases:
        publicada = instante(release.get("published_at"))
        estavel = not (_verdadeiro(release.get("draft")) or _verdadeiro(release.get("prerelease")))
        na_janela = publicada is not None and comeco <= publicada <= termino
        registro = {"full_name": release.get("full_name", ""),
                    "release_id": release.get("release_id", ""),
                    "tag_name": release.get("tag_name", ""),
                    "published_at": release.get("published_at"), "versao": versao,
                    "na_janela": na_janela, "estavel": estavel,
                    "corretiva": None, "motivo_corretiva": "",
                    "tag_anterior": "", "tag_corretiva": "", "tag_seguinte": "",
                    "intervalo_dias": None, "patch_semver": None,
                    "palavra_corretiva": None, "falhou": None, "motivo": "",
                    "elegivel": False, "censurada": False,
                    "fim_observacao": termino.isoformat(),
                    "fim_janela_correcao": (publicada + horizonte).isoformat() if publicada else None}
        registros.append(registro)
        if not estavel or publicada is None:
            motivo = "release_nao_estavel" if not estavel else "data_invalida"
            registro.update(motivo=motivo, motivo_corretiva=motivo)
            if estavel:
                datas_invalidas.add(registro["full_name"])
        elif publicada > termino:
            registro.update(motivo="fora_janela", motivo_corretiva="fora_observacao")
        else:
            por_repo[registro["full_name"]].append((publicada, release, registro))

    for nome, historico in por_repo.items():
        historico.sort(key=lambda item: (item[0], str(item[1].get("tag_name", ""))))
        frequencias = Counter(item[0] for item in historico)
        for i, (publicada, release, registro) in enumerate(historico):
            anterior = historico[i - 1] if i else None
            registro.update(classificar_corretiva(release, anterior[1] if anterior else None,
                                                 versao=versao))
            if nome in datas_invalidas:
                registro.update(corretiva=None, motivo_corretiva="historico_data_invalida")
            elif frequencias[publicada] > 1 or (anterior and frequencias[anterior[0]] > 1):
                registro.update(corretiva=None, motivo_corretiva="ordem_temporal_ambigua")
        for i, (publicada, release, registro) in enumerate(historico):
            seguinte = historico[i + 1] if i + 1 < len(historico) else None
            if seguinte:
                registro["tag_seguinte"] = seguinte[1].get("tag_name", "")
            if not registro["na_janela"]:
                registro["motivo"] = "fora_janela"
            elif publicada + horizonte > termino:
                registro.update(censurada=True, motivo="censurada_fim_janela")
            elif nome in datas_invalidas:
                registro["motivo"] = "historico_data_invalida"
            elif frequencias[publicada] > 1:
                registro["motivo"] = "ordem_temporal_ambigua"
            elif seguinte is None or seguinte[0] - publicada > horizonte:
                registro.update(falhou=False, elegivel=True, motivo="sem_corretiva_em_7_dias")
            else:
                corretiva = seguinte[2]["corretiva"]
                registro.update(falhou=corretiva, elegivel=corretiva is not None,
                                motivo=seguinte[2]["motivo_corretiva"])
                if corretiva:
                    registro["tag_corretiva"] = seguinte[1].get("tag_name", "")

    originais = [r for r in registros if r["na_janela"] and r["estavel"]]
    denominador = sum(r["elegivel"] for r in originais)
    falhas = sum(r["falhou"] is True for r in originais)
    censuradas = sum(r["censurada"] for r in originais)
    inconclusivas = sum(not r["elegivel"] and not r["censurada"] for r in originais)
    return {"versao": versao, "inicio": data_da_janela(inicio).isoformat(),
            "fim": data_da_janela(fim).isoformat(), "dias_corretiva": DIAS_CORRETIVA,
            "cfr_b": falhas / denominador if denominador else None,
            "falhas": falhas, "denominador": denominador, "censuradas": censuradas,
            "inconclusivas": inconclusivas, "releases_janela": len(originais),
            "releases": registros}


def calcular_cfr_b(releases, inicio, fim, *, versao="v1"):
    """Retorna a fração de CFR (b), ou None sem denominador elegível."""
    return analisar_cfr_b(releases, inicio, fim, versao=versao)["cfr_b"]
