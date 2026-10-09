"""RQ03(a): taxa de falhas nas execuções válidas de CI (fração 0–1)."""
from pipeline.funil import CONCLUSOES_FALHA, CONCLUSOES_SUCESSO


def calcular_cfr(runs):
    """Falhas / (falhas + sucessos); None se não houver runs válidos."""
    conclusoes = [run.get("conclusion") for run in runs
                  if run.get("conclusion") in CONCLUSOES_FALHA | CONCLUSOES_SUCESSO]
    if not conclusoes:
        return None
    return sum(conclusao in CONCLUSOES_FALHA for conclusao in conclusoes) / len(conclusoes)
