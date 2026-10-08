from dataclasses import dataclass
from urllib.parse import urlencode

import pytest



@dataclass
class Resposta:
    """Mesmo formato que o cliente da API devolve: status, JSON e cabeçalho Link."""
    status: int
    dados: object
    link: str = ""

    @property
    def ok(self):
        return self.status in (200, 204)


class ClienteFalso:
    """Substitui o ClienteGitHub: responde a partir de um dicionário, sem rede.

    ``rotas`` mapeia o caminho (sem query string) para uma ``Resposta`` ou para
    uma função ``params -> Resposta``. ``paginas`` mapeia o caminho para a lista
    de páginas devolvida por ``paginar`` (ou para uma função ``params -> páginas``).
    """

    def __init__(self, rotas, paginas=None):
        self.rotas = rotas
        self.paginas = paginas or {}
        self.chamadas = []

    def get(self, caminho, params=None):
        self.chamadas.append((caminho, dict(params or {})))
        rota = self.rotas.get(caminho)
        if rota is None:
            return Resposta(404, {"message": "Not Found"})
        return rota(params or {}) if callable(rota) else rota

    def paginar(self, caminho, params=None, chave=None, max_paginas=None):
        paginas = self.paginas[caminho]
        if callable(paginas):
            paginas = paginas(params or {})
        for numero, pagina in enumerate(paginas, 1):
            self.chamadas.append((caminho, {**(params or {}), "page": numero}))
            yield from (pagina[chave] if chave else pagina)
            if max_paginas is not None and numero >= max_paginas:
                return


def link(caminho, **rels):
    return ", ".join(f'<https://api.github.com{caminho}?{urlencode({"per_page": 1, "page": p})}>; '
                     f'rel="{rel}"' for rel, p in rels.items())


@pytest.fixture
def cliente_falso():
    return ClienteFalso
