#!/usr/bin/env bash
# Fill a checkout of a Hugging Face Space (Docker SDK) with the parser API.
#
#   git clone https://huggingface.co/spaces/<owner>/<space> ../syntaxlab-space
#   deploy/huggingface/prepare-space.sh ../syntaxlab-space
#   cd ../syntaxlab-space && git add -A && git commit -m "Deploy <sha>" && git push
#
# The Space gets the files of services/parser-api that git tracks (or would track: ignored
# files such as .venv and .models are never copied), with the Space README in place of the
# service README. Everything else in the checkout except .git is replaced.
set -euo pipefail

target="${1:?usage: prepare-space.sh <space-checkout-dir>}"
repo_root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
service="services/parser-api"

if [ ! -d "$target/.git" ]; then
  echo "error: $target is not a git checkout (clone the Space first)" >&2
  exit 1
fi
if [ "$(cd "$target" && pwd -P)" = "$(cd "$repo_root" && pwd -P)" ]; then
  echo "error: the target is this repository" >&2
  exit 1
fi

find "$target" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +

git -C "$repo_root" ls-files --cached --others --exclude-standard -z -- "$service" |
  while IFS= read -r -d '' file; do
    [ -f "$repo_root/$file" ] || continue # deleted but not yet staged
    relative="${file#"$service"/}"
    mkdir -p "$target/$(dirname "$relative")"
    cp "$repo_root/$file" "$target/$relative"
  done

cp "$repo_root/deploy/huggingface/README.md" "$target/README.md"
cp "$repo_root/LICENSE" "$target/LICENSE"

echo "Prepared $target from $(git -C "$repo_root" rev-parse --short HEAD)$(
  git -C "$repo_root" diff --quiet HEAD -- "$service" || echo ' (with uncommitted changes)'
)"
