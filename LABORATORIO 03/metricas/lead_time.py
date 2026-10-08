"""Lead time em horas: (a) commit mais antigo por release; (b) cada commit.

A referência usa ``commit.committer.date``. A data de autoria é preservada para
análises de sensibilidade. Datas ausentes ou posteriores à publicação não viram
zeros: os commits são contados como inválidos e omitidos das duas variantes.
"""

from datetime import datetime, timezone
from statistics import median


def instante(valor):
    if valor is None or valor == "":
        return None
    try:
        resultado = valor if isinstance(valor, datetime) else datetime.fromisoformat(
            str(valor).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if resultado.tzinfo is None:
        return None
    return resultado.astimezone(timezone.utc)


def data_commit(commit, campo_data="committer_date"):
    if campo_data not in {"committer_date", "author_date"}:
        raise ValueError("campo_data deve ser committer_date ou author_date")
    pessoa = "committer" if campo_data == "committer_date" else "author"
    valor = commit.get(campo_data)
    if valor is None:
        valor = (commit.get("commit", {}).get(pessoa) or {}).get("date")
    return instante(valor)


def horas_ate_publicacao(publicada, commit, campo_data="committer_date"):
    publicada, criada = instante(publicada), data_commit(commit, campo_data)
    if publicada is None or criada is None or criada > publicada:
        return None
    return (publicada - criada).total_seconds() / 3600


def calcular_lead_times(publicada, commits, campo_data="committer_date"):
    """Retorna a observação (a), todas as observações (b) e sua qualidade.

    ``commits=None`` significa comparação indisponível; ``[]`` significa uma
    comparação concluída, sem mudanças. Nenhum dos dois gera lead time zero.
    """
    if commits is None:
        return {"lead_time_a_horas": None, "lead_times_b_horas": [],
                "commits_validos": 0, "commits_invalidos": 0}
    valores, invalidos, vistos = [], 0, set()
    for commit in commits:
        sha = commit.get("sha")
        if sha and sha in vistos:
            continue
        if sha:
            vistos.add(sha)
        horas = horas_ate_publicacao(publicada, commit, campo_data)
        if horas is None:
            invalidos += 1
        else:
            valores.append(horas)
    return {"lead_time_a_horas": max(valores) if valores else None,
            "lead_times_b_horas": valores, "commits_validos": len(valores),
            "commits_invalidos": invalidos}


def resumir_lead_times(releases, campo_data="committer_date"):
    """Mediana de (a) por release e mediana de (b) sobre todos os commits.

    A variante (b) não é a mediana das medianas de cada release.
    """
    por_release, por_commit, invalidos = [], [], 0
    for release in releases:
        resultado = calcular_lead_times(release.get("published_at"),
                                       release.get("commits"), campo_data)
        if resultado["lead_time_a_horas"] is not None:
            por_release.append(resultado["lead_time_a_horas"])
        por_commit.extend(resultado["lead_times_b_horas"])
        invalidos += resultado["commits_invalidos"]
    return {"lead_time_a_horas": median(por_release) if por_release else None,
            "lead_time_b_horas": median(por_commit) if por_commit else None,
            "releases_com_lead_time": len(por_release),
            "commits_com_lead_time": len(por_commit),
            "commits_datas_invalidas": invalidos}
