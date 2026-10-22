import csv
from pathlib import Path

from pipeline.coletar_tags_rq07 import coletar_apenas_tags, _repositorios


class ClienteFalso:
    def __init__(self):
        self.chamadas = 0

    def get(self, caminho, params=None):
        self.chamadas += 1
        class Resposta:
            ok = True
            status = 200
            dados = []
        return Resposta()

    def paginar(self, caminho, params=None):
        return iter([])


def test_checkpoint_e_saida(tmp_path):
    cliente = ClienteFalso()
    repos = ['org/repositorio', 'outra/projeto']
    for _ in range(2):
        estados = coletar_apenas_tags(cliente, repos, '2025-10-01', '2026-09-30',
                                      tmp_path / 'checkpoints', tmp_path)
    assert len(estados) == 2
    assert all(r['tags_status'] == 'ok' for r in estados)
    assert cliente.chamadas == 2
    with (tmp_path / 'status_tags_rq07.csv').open() as f:
        assert len(list(csv.DictReader(f))) == 2
    assert (tmp_path / 'tags.csv').exists()
