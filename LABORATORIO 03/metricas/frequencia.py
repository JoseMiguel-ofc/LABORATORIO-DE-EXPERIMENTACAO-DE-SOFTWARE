"""Frequência de entrega, expressa em eventos por semana da janela inclusiva."""

from datetime import date, datetime
import math


def data_da_janela(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(valor)


def semanas_da_janela(inicio, fim):
    dias = (data_da_janela(fim) - data_da_janela(inicio)).days + 1
    if dias <= 0:
        raise ValueError("O fim da janela deve ser igual ou posterior ao início")
    return dias / 7


def frequencia_por_semana(quantidade, inicio, fim):
    """Conta inclusive o primeiro e o último dia; zero observado continua zero."""
    semanas = semanas_da_janela(inicio, fim)
    if quantidade is None:
        return None
    if not isinstance(quantidade, (int, float)) or not math.isfinite(quantidade):
        raise ValueError("A quantidade deve ser um número finito")
    if quantidade < 0 or int(quantidade) != quantidade:
        raise ValueError("A quantidade deve ser um inteiro não negativo")
    return quantidade / semanas
