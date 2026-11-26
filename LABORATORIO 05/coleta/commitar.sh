#!/usr/bin/env bash
# Commita e envia o CSV da coleta. Chamado pelo laço depois de cada rodada.
# Roda dentro de "LABORATORIO 05" no runner do GitHub Actions.
set -u
git add dados/brutos/
if git diff --cached --quiet; then
  echo "sem mudanças"
  exit 0
fi
git commit -q -m "coleta automática $(date -u +%FT%TZ)"
# Se alguém deu push durante a coleta, rebaseia e tenta de novo.
for tentativa in 1 2 3 4 5; do
  if git pull -q --rebase origin "${GITHUB_REF_NAME:-main}" && git push -q; then
    exit 0
  fi
  echo "push falhou (tentativa $tentativa); aguardando"
  sleep $((tentativa * 5))
done
echo "push não concluído; o commit fica local e segue na próxima rodada"
exit 1
