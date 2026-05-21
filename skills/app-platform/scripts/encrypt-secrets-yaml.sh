#!/usr/bin/env bash
# OPTIONAL convenience: SOPS-encrypt a plaintext Kubernetes Secret using slai-app-dev .sops.yaml.
# Canonical steps (any OS, full control) are in references/sops-slai-app-dev-clone.md -- prefer that
# when you need flexibility (macOS, ARM, airgap, custom paths).
#
# This script: shallow-clone SLAI_APP_DEV_DIR, chmod 700, optionally download sops (linux amd64 only),
# then sops encrypt with --filename-override for deploy/apps/<app_id>/secrets.enc.yaml.
#
# After encrypting, merge application-repo .gitignore entries from SKILL.md §0d / platform-context.md
# (*.enc.yaml, *.raw.yaml, .env) -- do not commit local *.enc.yaml in the app repo.
#
# Usage:
#   ./encrypt-secrets-yaml.sh --app-id <app_id> --raw /path/to/secrets.raw.yaml [--out /path/to/secrets.enc.yaml]
#
# Env (optional): SLAI_APP_DEV_DIR, SOPS_BIN (SOPS_VERSION set after --app-id validation)

set -euo pipefail

# Reject paths that enable traversal or odd option-like names (called before dirname/cd).
_require_safe_user_path() {
  local p="$1"
  local label="$2"
  if [[ -z "$p" || "$p" == -* ]]; then
    echo "Invalid ${label} (empty or option-like)" >&2
    return 1
  fi
  if [[ "$p" == *..* ]]; then
    echo "Invalid ${label} (must not contain ..)" >&2
    return 1
  fi
  if [[ "$p" =~ [[:cntrl:]] ]]; then
    echo "Invalid ${label} (control characters)" >&2
    return 1
  fi
  if [[ "$p" == *'$('* || "$p" == *'$['* ]]; then
    echo "Invalid ${label}" >&2
    return 1
  fi
  return 0
}

APP_ID=""
RAW=""
OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app-id)
      APP_ID="${2:?}"
      shift 2
      ;;
    --raw)
      RAW="${2:?}"
      shift 2
      ;;
    --out)
      OUT="${2:?}"
      shift 2
      ;;
    -h|--help)
      sed -n '1,25p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

: "${APP_ID:?--app-id is required}"
: "${RAW:?--raw is required}"

# Reject injection / path tricks in app id and pin sops release format
if [[ ! "$APP_ID" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]] || [[ ${#APP_ID} -gt 63 ]]; then
  echo "Invalid --app-id (use lowercase DNS-like labels, max 63 chars)" >&2
  exit 1
fi
SOPS_VERSION="${SOPS_VERSION:-3.9.4}"
if [[ ! "$SOPS_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid SOPS_VERSION (expected X.Y.Z)" >&2
  exit 1
fi
_require_safe_user_path "$RAW" "--raw" || exit 1

RAW="$(cd "$(dirname "$RAW")" && pwd)/$(basename "$RAW")"
if [[ ! -f "$RAW" ]]; then
  echo "Raw secret file not found: $RAW" >&2
  exit 1
fi

if [[ -z "$OUT" ]]; then
  base="${RAW%.yaml}"
  base="${base%.yml}"
  OUT="${base}.enc.yaml"
else
  _require_safe_user_path "$OUT" "--out" || exit 1
fi
OUT="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"
mkdir -p "$(dirname "$OUT")"
rm -f "$OUT"

SLAI_APP_DEV_DIR="${SLAI_APP_DEV_DIR:-/tmp/${USER:-user}/slai-app-dev}"
if [[ "$SLAI_APP_DEV_DIR" == *..* ]] || [[ "$SLAI_APP_DEV_DIR" =~ [[:cntrl:]] ]]; then
  echo "Invalid SLAI_APP_DEV_DIR" >&2
  exit 1
fi
if [[ -n "${SOPS_BIN:-}" ]]; then
  case "$SOPS_BIN" in
    /*) ;;
    *)
      echo "SOPS_BIN must be an absolute path" >&2
      exit 1
      ;;
  esac
  if [[ "$SOPS_BIN" == *..* ]]; then
    echo "SOPS_BIN must not contain .." >&2
    exit 1
  fi
fi
mkdir -p "$(dirname "$SLAI_APP_DEV_DIR")"
if [[ ! -d "$SLAI_APP_DEV_DIR/.git" ]]; then
  git clone --depth 1 https://github.com/AMD-SLAI/slai-app-dev.git "$SLAI_APP_DEV_DIR"
else
  git -C "$SLAI_APP_DEV_DIR" pull --ff-only
fi
chmod 700 "$SLAI_APP_DEV_DIR"

if [[ ! -f "$SLAI_APP_DEV_DIR/.sops.yaml" ]]; then
  echo "Missing .sops.yaml in $SLAI_APP_DEV_DIR" >&2
  exit 1
fi

ensure_sops() {
  if [[ -n "${SOPS_BIN:-}" && -x "$SOPS_BIN" ]]; then
    return 0
  fi
  if command -v sops >/dev/null 2>&1; then
    SOPS_BIN=$(command -v sops)
    return 0
  fi
  case "$(uname -s)/$(uname -m)" in
    Linux/x86_64|Linux/amd64)
      local cache="${HOME}/.cache/slai-app-platform-sops"
      mkdir -p "$cache"
      SOPS_BIN="${cache}/sops-${SOPS_VERSION}"
      if [[ ! -x "$SOPS_BIN" ]]; then
        echo "Downloading sops v${SOPS_VERSION}..." >&2
        _sops_bin_name="sops-v${SOPS_VERSION}.linux.amd64"
        _sops_url="https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/${_sops_bin_name}"
        _sums_url="https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.checksums.txt"
        _sums_file="${cache}/sops-v${SOPS_VERSION}.checksums.txt"
        curl -fsSL -o "$SOPS_BIN.part" -- "${_sops_url}"
        curl -fsSL -o "$_sums_file" -- "${_sums_url}"
        _want_sha256=""
        _want_sha256="$(awk -v "fn=${_sops_bin_name}" '$2 == fn { print $1; exit }' "$_sums_file")"
        if [[ -z "$_want_sha256" ]]; then
          echo "Checksum list missing entry for ${_sops_bin_name}" >&2
          rm -f "$SOPS_BIN.part" "$_sums_file"
          exit 1
        fi
        _got_sha256=""
        _got_sha256="$(sha256sum "$SOPS_BIN.part" | awk '{ print $1 }')"
        if [[ "$_got_sha256" != "$_want_sha256" ]]; then
          echo "SHA256 mismatch for downloaded sops (expected integrity check failed)" >&2
          rm -f "$SOPS_BIN.part" "$_sums_file"
          exit 1
        fi
        mv -f "$SOPS_BIN.part" "$SOPS_BIN"
        chmod +x "$SOPS_BIN"
      fi
      return 0
      ;;
    *)
      echo "Install sops (https://github.com/getsops/sops) and use references/sops-slai-app-dev-clone.md, or set SOPS_BIN." >&2
      exit 1
      ;;
  esac
}

ensure_sops

(
  cd "$SLAI_APP_DEV_DIR"
  "$SOPS_BIN" encrypt \
    --filename-override "deploy/apps/${APP_ID}/secrets.enc.yaml" \
    --input-type yaml \
    "$RAW" > "$OUT"
)

echo "Wrote $OUT"
