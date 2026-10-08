"""Classificação DORA (Elite/High/Medium/Low) com os cortes fixos da RQ 07.

Unidades de entrada:
- deployment frequency: deploys por semana;
- lead time e tempo de recuperação: horas;
- change failure rate: fração entre 0 e 1 (0,15 = 15%).

Métrica ausente (``None`` ou NaN), por exemplo um repositório sem nenhum
episódio de falha, não recebe categoria e fica fora da classificação geral.
"""

import math
import statistics


ELITE, HIGH, MEDIUM, LOW = "Elite", "High", "Medium", "Low"
PONTOS = {ELITE: 4, HIGH: 3, MEDIUM: 2, LOW: 1}
CATEGORIA_POR_PONTOS = {pontos: categoria for categoria, pontos in PONTOS.items()}

HORAS_POR_DIA = 24
HORAS_POR_SEMANA = 7 * HORAS_POR_DIA
SEMANAS_POR_ANO = 365 / 7
# "1 por mês" expresso em deploys por semana (12 meses / ~52,14 semanas ≈ 0,23).
UM_POR_MES_EM_SEMANAS = 12 / SEMANAS_POR_ANO


def _ausente(valor):
    return valor is None or (isinstance(valor, float) and math.isnan(valor))


def _nao_negativo(valor, nome):
    if valor < 0:
        raise ValueError(f"{nome} não pode ser negativo: {valor}")


def classificar_frequencia(deploys_por_semana):
    if _ausente(deploys_por_semana):
        return None
    _nao_negativo(deploys_por_semana, "Deployment frequency")
    if deploys_por_semana >= 7:
        return ELITE
    if deploys_por_semana >= 1:
        return HIGH
    if deploys_por_semana >= UM_POR_MES_EM_SEMANAS:
        return MEDIUM
    return LOW


def classificar_lead_time(horas):
    if _ausente(horas):
        return None
    _nao_negativo(horas, "Lead time")
    if horas < HORAS_POR_DIA:
        return ELITE
    if horas < HORAS_POR_SEMANA:
        return HIGH
    if horas < 30 * HORAS_POR_DIA:
        return MEDIUM
    return LOW


def classificar_cfr(taxa):
    if _ausente(taxa):
        return None
    if not 0 <= taxa <= 1:
        raise ValueError(f"CFR deve ser uma fração entre 0 e 1, não {taxa}")
    if taxa <= 0.15:
        return ELITE
    if taxa <= 0.30:
        return HIGH
    if taxa <= 0.45:
        return MEDIUM
    return LOW


def classificar_recuperacao(horas):
    if _ausente(horas):
        return None
    _nao_negativo(horas, "Tempo de recuperação")
    if horas < 1:
        return ELITE
    if horas < HORAS_POR_DIA:
        return HIGH
    if horas < HORAS_POR_SEMANA:
        return MEDIUM
    return LOW


def classificar_geral(categorias):
    """Mediana dos pontos (Elite=4 … Low=1), arredondada para baixo.

    Exemplo do enunciado: (Elite, High, High, Low) → (4, 3, 3, 1) → 3 → High.
    """
    pontos = [PONTOS[categoria] for categoria in categorias if categoria is not None]
    if not pontos:
        return None
    return CATEGORIA_POR_PONTOS[math.floor(statistics.median(pontos))]


def classificar_repositorio(deploys_por_semana, lead_time_horas, cfr, recuperacao_horas):
    por_metrica = {
        "frequencia": classificar_frequencia(deploys_por_semana),
        "lead_time": classificar_lead_time(lead_time_horas),
        "cfr": classificar_cfr(cfr),
        "recuperacao": classificar_recuperacao(recuperacao_horas),
    }
    return {**por_metrica, "geral": classificar_geral(por_metrica.values())}
