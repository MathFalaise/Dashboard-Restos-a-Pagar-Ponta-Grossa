#!/usr/bin/env bash
# Sanitization of the public Git history (corrective audit of 13/10/2026, phase P0). It NEVER pushes: it builds and
# checks a sanitized mirror in a private folder; the push is a separate, explicitly authorized step (see
# HIGIENIZACAO_HISTORICO.md, section 5).
#
# Usage:  bash docs/audits/privacidade/higienizar_historico.sh WORK_DIR LOCAL_REPO BRANCH [BRANCH...]
#   WORK_DIR    new private folder OUTSIDE OneDrive (e.g. ~/RestosAPagar_local/higienizacao_YYYYMMDD)
#   LOCAL_REPO  the working repository (to bring the local branches not yet on GitHub)
#   BRANCH      local branches to add to the mirror (e.g. auditoria-corretiva-20261013)
# Requires git-filter-repo (pip install git-filter-repo==2.47.0).
set -euo pipefail
WORK="$1"; LOCAL="$2"; shift 2
REMOTO="https://github.com/MathFalaise/Dashboard-Restos-a-Pagar-Ponta-Grossa.git"
[ -e "$WORK" ] && { echo "$WORK já existe: escolha uma pasta nova" >&2; exit 1; }
mkdir -p "$WORK"
git clone --mirror "$REMOTO" "$WORK/espelho.git"
for b in "$@"; do
    git -C "$WORK/espelho.git" fetch "$LOCAL" "refs/heads/$b:refs/heads/$b"
done
git -C "$WORK/espelho.git" for-each-ref --format='%(refname) %(objectname)' > "$WORK/refs_antes.txt"
git -C "$WORK/espelho.git" count-objects -vH > "$WORK/tamanho_antes.txt"
# The only text replaced: one real masked-CPF fragment that old report versions cited (the current versions already
# use a synthetic one). Raw folders, old and new names, leave the history entirely; the public SHA-256 lists stay.
printf '%s\n' '****NNN****==>****NNN****' > "$WORK/substituicoes.txt"
python -m git_filter_repo --source "$WORK/espelho.git" --target "$WORK/espelho.git" --force \
    --invert-paths \
    --path data/snapshots --path data/stage01-samples --path data/stage02-raw --path data/backups \
    --path snapshots --path etapa01/amostras_brutas --path etapa02/dados_brutos --path backups \
    --replace-text "$WORK/substituicoes.txt"
git -C "$WORK/espelho.git" for-each-ref --format='%(refname) %(objectname)' > "$WORK/refs_depois.txt"
git -C "$WORK/espelho.git" count-objects -vH > "$WORK/tamanho_depois.txt"
cp "$WORK/espelho.git/filter-repo/commit-map" "$WORK/mapa_de_commits.txt"
# No raw path may remain in any commit of any ref
if git -C "$WORK/espelho.git" log --all --name-only --format= | grep -E '^(data/(snapshots|stage01-samples|stage02-raw|backups)/|snapshots/|etapa01/amostras_brutas/|etapa02/dados_brutos/|backups/)' ; then
    echo "caminho bruto restante no histórico" >&2; exit 2
fi
echo "espelho higienizado em $WORK/espelho.git (nada foi enviado)"
