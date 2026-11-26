from datetime import datetime, timedelta, timezone

from coleta.coletar import gravar
from coleta.laco import executar, horario, ultimo_timestamp

UTC = timezone.utc


class Relogio:
    """Relógio falso: dormir avança o tempo; cada rodada leva 10 s."""

    def __init__(self, inicio):
        self.t = inicio
        self.sonos = []

    def agora(self):
        return self.t

    def dormir(self, segundos):
        self.sonos.append(segundos)
        self.t += timedelta(seconds=segundos)


def linha(momento, endpoint="GetServerInfo"):
    return {"timestamp": momento.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "endpoint": endpoint, "status": 200, "latencia_ms": "10.0",
            "usuarios_online": 1, "erro": "", "jogadores_top": 2}


def coletor(relogio):
    def coletar():
        momento = relogio.t
        relogio.t += timedelta(seconds=10)
        return [linha(momento)]
    return coletar


def test_horario_vai_do_minuto_17_ao_16():
    assert horario(datetime(2026, 11, 26, 10, 17, tzinfo=UTC)) == datetime(2026, 11, 26, 10, 17, tzinfo=UTC)
    assert horario(datetime(2026, 11, 26, 10, 16, 59, tzinfo=UTC)) == datetime(2026, 11, 26, 9, 17, tzinfo=UTC)
    assert horario(datetime(2026, 11, 26, 0, 5, tzinfo=UTC)) == datetime(2026, 11, 25, 23, 17, tzinfo=UTC)


def test_ultimo_timestamp(tmp_path):
    caminho = tmp_path / "c.csv"
    assert ultimo_timestamp(caminho) is None
    gravar([linha(datetime(2026, 11, 26, 10, 17, 1, tzinfo=UTC))], caminho)
    gravar([linha(datetime(2026, 11, 26, 11, 17, 2, tzinfo=UTC))], caminho)
    assert ultimo_timestamp(caminho) == datetime(2026, 11, 26, 11, 17, 2, tzinfo=UTC)


def test_laco_coleta_uma_vez_por_hora_no_minuto_17(tmp_path, monkeypatch):
    import coleta.laco as laco
    commits = []
    monkeypatch.setattr(laco.subprocess, "run", lambda cmd, check: commits.append(cmd))
    relogio = Relogio(datetime(2026, 11, 26, 10, 40, tzinfo=UTC))
    caminho = tmp_path / "c.csv"
    total = executar({}, caminho, duracao_min=340, commit=["bash", "coleta/commitar.sh"],
                     agora=relogio.agora, dormir=relogio.dormir, coletar=coletor(relogio))

    # 10:40 (horário das 10:17 ainda sem rodada) + 11:17 ... 16:17 (fim às 16:20) = 7
    assert total == 7
    momentos = [l.split(",")[0] for l in caminho.read_text().splitlines()[1:]]
    assert momentos[0].startswith("2026-11-26T10:40")
    assert all(m[14:16] == "17" for m in momentos[1:])
    assert relogio.t < datetime(2026, 11, 26, 10, 40, tzinfo=UTC) + timedelta(minutes=340)
    assert commits == [["bash", "coleta/commitar.sh"]] * 7  # um commit por rodada


def test_laco_nao_repete_horario_ja_coletado(tmp_path):
    caminho = tmp_path / "c.csv"
    gravar([linha(datetime(2026, 11, 26, 10, 17, 5, tzinfo=UTC))], caminho)
    relogio = Relogio(datetime(2026, 11, 26, 10, 45, tzinfo=UTC))
    total = executar({}, caminho, duracao_min=60, agora=relogio.agora,
                     dormir=relogio.dormir, coletar=coletor(relogio))
    assert total == 1  # só a das 11:17
    assert ultimo_timestamp(caminho).hour == 11


def test_laco_curto_termina_sem_dormir_alem_do_fim(tmp_path):
    relogio = Relogio(datetime(2026, 11, 26, 10, 50, tzinfo=UTC))
    total = executar({}, tmp_path / "c.csv", duracao_min=10, agora=relogio.agora,
                     dormir=relogio.dormir, coletar=coletor(relogio))
    assert total == 1 and relogio.sonos == []
