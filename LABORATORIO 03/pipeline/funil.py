"""Filtros de inclusão e tabela do funil de seleção (seções 3 e 7 do enunciado).

As contagens usadas aqui são baratas de propósito: servem só para decidir se o
repositório entra na amostra. A coleta completa de releases e runs (Pessoas B e
C) roda depois, apenas nos repositórios aprovados.
"""

from datetime import datetime, time, timezone


MIN_RELEASES = 5
MIN_RUNS = 50
CONCLUSOES_SUCESSO = {"success"}
CONCLUSOES_FALHA = {"failure", "timed_out", "startup_failure"}
CONCLUSOES_VALIDAS = CONCLUSOES_SUCESSO | CONCLUSOES_FALHA
# Releases vêm ordenadas por criação (mais nova primeiro), não por publicação.
# Depois desse número de releases seguidas anteriores à janela, paramos de paginar.
TOLERANCIA_FORA_DA_JANELA = 30

# Ordem em que os filtros são aplicados; o repositório sai na primeira etapa que falhar.
ETAPAS = [
    ("acessivel", "Repositórios acessíveis pela API", "erro ao consultar a API"),
    ("actions", "Com GitHub Actions", "sem workflows do GitHub Actions (total_count = 0)"),
    ("releases", f"Com >= {MIN_RELEASES} releases na janela",
     f"menos de {MIN_RELEASES} releases publicadas na janela"),
    ("runs", f"Com >= {MIN_RUNS} workflow runs válidos na janela",
     f"menos de {MIN_RUNS} workflow runs válidos (push, default branch) na janela"),
]
NAO_AVALIADO = "nao_avaliado"


def limites_da_janela(inicio, fim):
    """Converte as datas do config em instantes UTC; o dia final entra inteiro."""
    return (datetime.combine(inicio, time.min, timezone.utc),
            datetime.combine(fim, time.max, timezone.utc))


def ler_data(texto):
    return datetime.fromisoformat(texto.replace("Z", "+00:00")) if texto else None


def release_valida(release, inicio, fim):
    """Release publicada (``draft = false``), não pré-release, publicada na janela."""
    if release.get("draft") or release.get("prerelease"):
        return False
    publicada = ler_data(release.get("published_at"))
    return publicada is not None and inicio <= publicada <= fim


def contar_releases_na_janela(cliente, full_name, inicio, fim):
    total, seguidas_antes = 0, 0
    for release in cliente.paginar(f"/repos/{full_name}/releases", {"per_page": 100}):
        if release_valida(release, inicio, fim):
            total += 1
        publicada = ler_data(release.get("published_at"))
        if publicada is not None and publicada < inicio:
            seguidas_antes += 1
            if seguidas_antes >= TOLERANCIA_FORA_DA_JANELA:
                break
        else:
            seguidas_antes = 0
    return total


def contar_runs_validos(cliente, full_name, branch, inicio, fim):
    """Soma ``total_count`` por conclusão válida, sem baixar a lista de runs.

    O filtro ``status`` da API aceita também valores de ``conclusion``; assim
    runs cancelados, pulados ou em andamento ficam de fora, como manda a seção 3.
    """
    total = 0
    for conclusao in sorted(CONCLUSOES_VALIDAS):
        resposta = cliente.get(f"/repos/{full_name}/actions/runs", {
            "branch": branch, "event": "push", "status": conclusao,
            "created": f"{inicio.date()}..{fim.date()}", "per_page": 1,
        })
        if not resposta.ok:
            return None
        total += resposta.dados["total_count"]
    return total


def avaliar_contagens(n_releases, n_runs, min_releases=MIN_RELEASES, min_runs=MIN_RUNS):
    """Devolve a etapa em que o repositório foi descartado, ou ``None`` se aprovado.

    ``n_runs`` pode ser ``None`` quando nem foi consultado (releases já reprovou).
    """
    if n_releases < min_releases:
        return "releases"
    if n_runs is None or n_runs < min_runs:
        return "runs"
    return None


def montar_funil(total_candidatos, descartes):
    """Tabela do funil a partir do total inicial e da etapa de descarte de cada repositório.

    ``descartes`` mapeia ``full_name`` para a chave da etapa em que ele saiu
    (``None`` para os aprovados, ``NAO_AVALIADO`` para os que ficaram de fora
    porque a amostra já estava completa).
    """
    chaves = {chave for chave, _, _ in ETAPAS} | {None, NAO_AVALIADO}
    desconhecidas = set(descartes.values()) - chaves
    if desconhecidas:
        raise ValueError(f"Etapas desconhecidas: {sorted(map(str, desconhecidas))}")

    nao_avaliados = sum(1 for etapa in descartes.values() if etapa == NAO_AVALIADO)
    restantes = total_candidatos - nao_avaliados
    linhas = [
        {"etapa": "Candidatos da busca", "restantes": total_candidatos,
         "descartados": 0, "motivo": ""},
        {"etapa": "Candidatos avaliados", "restantes": restantes,
         "descartados": nao_avaliados,
         "motivo": "não avaliados: a amostra-alvo já tinha sido atingida" if nao_avaliados else ""},
    ]
    for chave, nome, motivo in ETAPAS:
        saiu = sum(1 for etapa in descartes.values() if etapa == chave)
        restantes -= saiu
        linhas.append({"etapa": nome, "restantes": restantes, "descartados": saiu,
                       "motivo": motivo if saiu else ""})
    linhas.append({"etapa": "Amostra final", "restantes": restantes,
                   "descartados": 0, "motivo": ""})
    return linhas
