#!/usr/bin/env python3
"""
Validate deploy/apps/<app>/ manifest bundle for slai-app-dev Platform deploy.

This is machine-checkable validation (CI / pre-PR), not manifest scaffolding.
Scaffolding is markdown + templates in the skill; this script only verifies a directory.

Usage:
  python3 main.py [--strict] <path-to-deploy/apps/<app_id>>

Exits 0 if deployment.yaml, service.yaml, secrets.enc.yaml exist and deployment.yaml
contains an image: line. Does not decrypt SOPS.

With --strict, also requires networkpolicy.yaml and OTEL-related env in deployment.yaml
(see skills/app-platform/references/platform-context.md § OpenTelemetry).
"""

import argparse
import re
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--strict",
        action="store_true",
        help="Require networkpolicy.yaml and OTEL env (OTEL_EXPORTER_OTLP_ENDPOINT or OTEL_SERVICE_NAME) in deployment.yaml",
    )
    p.add_argument(
        "manifest_dir",
        type=Path,
        help="Directory deploy/apps/<app_id>/",
    )
    args = p.parse_args()
    d = args.manifest_dir.resolve()

    errors: list[str] = []
    if not d.is_dir():
        print(f"error: not a directory: {d}", file=sys.stderr)
        return 2

    required = ("deployment.yaml", "service.yaml", "secrets.enc.yaml")
    for name in required:
        fp = d / name
        if not fp.is_file():
            errors.append(f"missing file: {fp}")

    dep = d / "deployment.yaml"
    if dep.is_file():
        text = dep.read_text(encoding="utf-8", errors="replace")
        if "image:" not in text:
            errors.append(f"{dep}: expected an 'image:' field")
        else:
            # Heuristic: discourage bare :latest as sole tag (still allows full refs)
            m = re.search(r"image:\s*(\S+)", text)
            if m:
                ref = m.group(1).strip("\"'")
                if ref.endswith(":latest"):
                    errors.append(
                        f"{dep}: avoid :latest for production-like deploys; use immutable tag (e.g. git SHA)"
                    )

    sec = d / "secrets.enc.yaml"
    if sec.is_file():
        head = sec.read_text(encoding="utf-8", errors="replace")[:800]
        if "ENC[" not in head and "sops:" not in head:
            errors.append(
                f"{sec}: does not look like SOPS ciphertext (expected ENC[ or sops: block) — verify file"
            )

    if args.strict:
        np = d / "networkpolicy.yaml"
        if not np.is_file():
            errors.append(
                f"missing file (required with --strict): {np} — see skills/app-platform/references/network-egress.md"
            )
        if dep.is_file():
            t = dep.read_text(encoding="utf-8", errors="replace")
            if not re.search(
                r"OTEL_EXPORTER_OTLP_ENDPOINT|OTEL_SERVICE_NAME",
                t,
            ):
                errors.append(
                    f"{dep}: with --strict, expected OTEL_EXPORTER_OTLP_ENDPOINT or OTEL_SERVICE_NAME in env (skills/app-platform/references/platform-context.md)"
                )

    if errors:
        print("validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"ok: {d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
