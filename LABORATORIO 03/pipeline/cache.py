"""Cache persistente de respostas JSON da API, indexado por URL e parâmetros.

A escrita atômica impede que uma interrupção deixe JSON parcial. Nenhum token
ou cabeçalho Authorization é armazenado. Respostas com erro não são cacheadas.
"""
import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class CacheJSON:
    def __init__(self, diretorio):
        self.diretorio = Path(diretorio)
        self.diretorio.mkdir(parents=True, exist_ok=True)

    def _caminho(self, url, params=None):
        partes = urlsplit(url)
        consulta = parse_qsl(partes.query, keep_blank_values=True)
        consulta += [(str(k), str(v)) for k, v in (params or {}).items() if v is not None]
        consulta.sort()
        chave = urlunsplit((partes.scheme, partes.netloc, partes.path,
                            urlencode(consulta), ""))
        digest = hashlib.sha256(chave.encode("utf-8")).hexdigest()
        # Agrupa por repositório e endpoint sem usar nomes externos como caminhos.
        segmentos = partes.path.strip("/").split("/")
        grupo = "__".join(segmentos[1:3]) if len(segmentos) >= 3 and segmentos[0] == "repos" else "geral"
        return self.diretorio / grupo / f"{digest}.json"

    def ler(self, url, params=None):
        caminho = self._caminho(url, params)
        if not caminho.exists():
            return None
        try:
            return json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Cache interrompido ou corrompido: refazer a requisição.
            return None

    def gravar(self, url, params, status, dados, link=""):
        if status not in (200, 204):
            return
        destino = self._caminho(url, params)
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporario = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=destino.parent,
                                    prefix=".tmp-", suffix=".json", delete=False) as arquivo:
                temporario = Path(arquivo.name)
                json.dump({"status": status, "dados": dados, "link": link}, arquivo,
                          ensure_ascii=False)
            os.replace(temporario, destino)
        finally:
            if temporario is not None:
                temporario.unlink(missing_ok=True)
