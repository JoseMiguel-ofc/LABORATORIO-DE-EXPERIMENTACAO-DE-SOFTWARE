"""Cliente REST GitHub com autenticação, paginação, cache e limites de API."""
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import time
from urllib.parse import urljoin, urlsplit

import requests

from pipeline.cache import CacheJSON

log = logging.getLogger(__name__)
BASE_API = "https://api.github.com"


@dataclass(frozen=True)
class RespostaGitHub:
    status: int
    dados: object
    link: str = ""

    @property
    def ok(self):
        return self.status in (200, 204)


def proximo_link(link):
    """Lê a URL de rel=next sem depender da ordem dos links."""
    for trecho in (link or "").split(","):
        partes = [parte.strip() for parte in trecho.split(";")]
        if len(partes) > 1 and any(parte.strip('"') == "rel=next" or
                                   parte == 'rel="next"' for parte in partes[1:]):
            return partes[0].strip("<>")
    return None


class ClienteGitHub:
    def __init__(self, token, cache_dir, sessao=None, dormir=None, relogio=None,
                 max_tentativas=5):
        if not token:
            raise ValueError("Defina um token GitHub para autenticar o cliente")
        self.sessao = sessao or requests.Session()
        self.sessao.headers.update({"Authorization": f"Bearer {token}",
                                   "Accept": "application/vnd.github+json",
                                   "X-GitHub-Api-Version": "2022-11-28"})
        self.cache = CacheJSON(cache_dir)
        self.dormir = dormir or time.sleep
        self.relogio = relogio or time.time
        self.max_tentativas = max_tentativas
        self.chamadas_api = 0
        self.acertos_cache = 0

    def _url(self, caminho):
        url = caminho if caminho.startswith(("https://", "http://")) else urljoin(BASE_API, "/" + caminho.lstrip("/"))
        if urlsplit(url).netloc != "api.github.com" or urlsplit(url).scheme != "https":
            raise ValueError("O cliente só permite URLs HTTPS da API oficial do GitHub")
        return url

    def _espera_limite(self, resposta, tentativa):
        cabecalhos = resposta.headers
        restante = cabecalhos.get("X-RateLimit-Remaining")
        limite_secundario = resposta.status_code in (403, 429) and (
            "secondary rate limit" in str(getattr(resposta, "text", "")).lower() or
            "retry-after" in {k.lower() for k in cabecalhos})
        if resposta.status_code not in (403, 429) or (restante != "0" and not limite_secundario):
            return False
        retry = cabecalhos.get("Retry-After")
        if retry is not None:
            try:
                espera = max(1, float(retry))
            except ValueError:
                espera = 2 ** tentativa
        elif restante == "0" and cabecalhos.get("X-RateLimit-Reset"):
            espera = max(1, float(cabecalhos["X-RateLimit-Reset"]) - self.relogio() + 1)
        else:
            espera = min(60, 2 ** tentativa)
        log.warning("Limite da API atingido; aguardando %.1f segundos", espera)
        self.dormir(espera)
        return True

    def get(self, caminho, params=None):
        url = self._url(caminho)
        armazenado = self.cache.ler(url, params)
        if armazenado is not None:
            self.acertos_cache += 1
            return RespostaGitHub(**armazenado)

        for tentativa in range(self.max_tentativas):
            try:
                resposta = self.sessao.get(url, params=params, timeout=45)
                self.chamadas_api += 1
            except requests.RequestException:
                if tentativa + 1 == self.max_tentativas:
                    raise
                self.dormir(2 ** tentativa)
                continue
            if resposta.status_code >= 500:
                if tentativa + 1 < self.max_tentativas:
                    self.dormir(2 ** tentativa)
                    continue
            elif self._espera_limite(resposta, tentativa):
                if tentativa + 1 < self.max_tentativas:
                    continue
            try:
                dados = resposta.json() if resposta.content else None
            except ValueError:
                dados = None
            link = resposta.headers.get("Link", "")
            resultado = RespostaGitHub(resposta.status_code, dados, link)
            if resultado.ok:
                self.cache.gravar(url, params, resultado.status, dados, link)
            return resultado
        raise RuntimeError("Número máximo de tentativas excedido")

    def paginar(self, caminho, params=None, chave=None, max_paginas=None):
        url = self._url(caminho)
        parametros = dict(params or {})
        visitadas = set()
        pagina = 0
        while url:
            if max_paginas is not None and pagina >= max_paginas:
                return
            assinatura = (url, tuple(sorted((str(k), str(v)) for k, v in parametros.items())))
            if assinatura in visitadas:
                raise RuntimeError(f"Loop de paginação detectado: {url}")
            visitadas.add(assinatura)
            resposta = self.get(url, parametros)
            if not resposta.ok:
                raise RuntimeError(f"Erro HTTP {resposta.status} durante paginação de {url}")
            itens = resposta.dados.get(chave) if chave else resposta.dados
            if not isinstance(itens, list):
                raise ValueError(f"Resposta de paginação não contém lista: {url}")
            yield from itens
            pagina += 1
            url = proximo_link(resposta.link)
            parametros = {}  # A URL de Link já contém a query string completa.
