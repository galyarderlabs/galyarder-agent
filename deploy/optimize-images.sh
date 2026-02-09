#!/usr/bin/env bash
set -euo pipefail

MIN_BYTES="${G_AGENT_IMG_MIN_BYTES:-500000}"
MAX_WIDTH="${G_AGENT_IMG_MAX_WIDTH:-1800}"
PNG_COLORS="${G_AGENT_IMG_PNG_COLORS:-384}"
JPEG_QUALITY="${G_AGENT_IMG_JPEG_QUALITY:-84}"
WEBP_QUALITY="${G_AGENT_IMG_WEBP_QUALITY:-82}"

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

if ! command -v magick >/dev/null 2>&1; then
  echo "optimize-images: missing 'magick' (ImageMagick)"
  exit 1
fi

if ! repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "optimize-images: run this inside the galyarder-agent git repo"
  exit 1
fi
cd "$repo_root"

human_bytes() {
  local value="$1"
  if command -v numfmt >/dev/null 2>&1; then
    numfmt --to=iec --suffix=B "$value"
  else
    echo "${value}B"
  fi
}

file_size() {
  wc -c < "$1" | tr -d '[:space:]'
}

mapfile -t tracked_images < <(git ls-files -- '*.png' '*.jpg' '*.jpeg' '*.webp')

if [[ ${#tracked_images[@]} -eq 0 ]]; then
  echo "optimize-images: no tracked image files found"
  exit 0
fi

checked=0
optimized=0
total_before=0
total_after=0

for file in "${tracked_images[@]}"; do
  [[ -f "$file" ]] || continue

  before_size="$(file_size "$file")"
  if (( before_size < MIN_BYTES )); then
    continue
  fi

  checked=$((checked + 1))
  total_before=$((total_before + before_size))
  ext="${file##*.}"
  ext_lower="$(printf '%s' "$ext" | tr '[:upper:]' '[:lower:]')"
  tmp_file="$(mktemp "${TMPDIR:-/tmp}/gagent-img.XXXXXX.${ext_lower}")"

  case "$ext_lower" in
    png)
      magick "$file" -resize "${MAX_WIDTH}x>" -strip -colors "$PNG_COLORS" "$tmp_file"
      ;;
    jpg|jpeg)
      magick "$file" -resize "${MAX_WIDTH}x>" -strip -interlace Plane -quality "$JPEG_QUALITY" "$tmp_file"
      ;;
    webp)
      magick "$file" -resize "${MAX_WIDTH}x>" -strip -quality "$WEBP_QUALITY" "$tmp_file"
      ;;
    *)
      rm -f "$tmp_file"
      continue
      ;;
  esac

  after_size="$(file_size "$tmp_file")"
  if (( after_size < before_size )); then
    optimized=$((optimized + 1))
    total_after=$((total_after + after_size))
    saved=$((before_size - after_size))
    percent=$((saved * 100 / before_size))
    echo "optimized: $file ($(human_bytes "$before_size") -> $(human_bytes "$after_size"), -${percent}%)"
    if [[ "$DRY_RUN" == false ]]; then
      mv "$tmp_file" "$file"
    else
      rm -f "$tmp_file"
    fi
  else
    total_after=$((total_after + before_size))
    rm -f "$tmp_file"
    echo "skipped:   $file (no reduction)"
  fi
done

if (( checked == 0 )); then
  echo "optimize-images: no files above threshold $(human_bytes "$MIN_BYTES")"
  exit 0
fi

total_saved=$((total_before - total_after))
echo
echo "checked:   $checked"
echo "optimized: $optimized"
echo "saved:     $(human_bytes "$total_saved")"
echo "before:    $(human_bytes "$total_before")"
echo "after:     $(human_bytes "$total_after")"

if [[ "$DRY_RUN" == true ]]; then
  echo
  echo "dry-run only, no files changed"
fi
