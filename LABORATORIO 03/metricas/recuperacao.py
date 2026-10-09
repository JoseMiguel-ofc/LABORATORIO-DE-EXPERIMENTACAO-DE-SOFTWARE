"""RQ04: episódios de falha por workflow e mediana do tempo de recuperação."""
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median

from pipeline.funil import CONCLUSOES_FALHA, CONCLUSOES_SUCESSO


def _data(valor):
    if not valor:
        return None
    data = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    return data if data.tzinfo else data.replace(tzinfo=timezone.utc)


def calcular_episodios(runs):
    """Retorna episódios resolvidos e censurados, separados por workflow.

    Considera início na primeira falha após um sucesso; se a primeira observação
    do workflow já for falha, também a registra como início observado na janela.
    Runs inválidos não alteram o estado. O último episódio sem sucesso é censurado.
    """
    por_workflow = defaultdict(list)
    for run in runs:
        conclusao = run.get("conclusion")
        if conclusao not in CONCLUSOES_FALHA | CONCLUSOES_SUCESSO:
            continue
        identificador = run.get("workflow_id") or run.get("path") or run.get("name")
        if identificador is None:
            continue
        inicio = _data(run.get("run_started_at"))
        if inicio is None:
            continue
        por_workflow[identificador].append((inicio, run))

    episodios = []
    for workflow, lista in por_workflow.items():
        pendente = None
        for inicio, run in sorted(lista, key=lambda item: (item[0], item[1].get("id", 0))):
            if run["conclusion"] in CONCLUSOES_FALHA:
                if pendente is None:
                    pendente = inicio
            elif pendente is not None:
                fim = _data(run.get("updated_at"))
                if fim is not None and fim >= pendente:
                    episodios.append({"workflow_id": workflow,
                                      "inicio": pendente.isoformat(),
                                      "fim": fim.isoformat(),
                                      "horas": (fim - pendente).total_seconds() / 3600,
                                      "censurado": False})
                    pendente = None
        if pendente is not None:
            episodios.append({"workflow_id": workflow, "inicio": pendente.isoformat(),
                              "fim": None, "horas": None, "censurado": True})
    return episodios


def calcular_recuperacao(runs):
    """Mediana em horas dos episódios resolvidos; None quando não existem."""
    duracoes = [e["horas"] for e in calcular_episodios(runs) if not e["censurado"]]
    return median(duracoes) if duracoes else None
