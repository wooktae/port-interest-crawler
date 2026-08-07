"""Build deterministic Git SHA-based Crawler Windows deployment bundle.

The builder reads only explicitly listed committed Git files.
It does not import or execute Crawler modules and does not access
database, network, Selenium, KRX, SSM, CodeDeploy, or AWS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[3]
INCLUDE_FILE = ROOT / ".devops" / "bundle" / "windows-include.txt"
ARTIFACT_DIR = ROOT / ".devops" / "artifacts"

FORBIDDEN_NAMES = {
    ".env",
    ".env.local",
    "ALL_SCHEMA_TABLE_DUMP.txt",
    "load-crawler-db-env.ps1",
    "load-krx-env.ps1",
}

FORBIDDEN_PARTS = {
    ".git",
    ".github",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "_patches",
}

FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def load_include_paths() -> list[Path]:
    if not INCLUDE_FILE.is_file():
        raise RuntimeError(
            f"Include manifest missing: {INCLUDE_FILE}"
        )

    relative_paths: list[Path] = []

    for raw_line in INCLUDE_FILE.read_text(
        encoding="utf-8-sig"
    ).splitlines():
        value = raw_line.strip()

        if not value or value.startswith("#"):
            continue

        relative_path = Path(value)

        if relative_path.is_absolute():
            raise RuntimeError(
                f"Absolute path is not allowed: {value}"
            )

        if ".." in relative_path.parts:
            raise RuntimeError(
                f"Parent traversal is not allowed: {value}"
            )

        if relative_path.name.lower() in {
            name.lower()
            for name in FORBIDDEN_NAMES
        }:
            raise RuntimeError(
                f"Forbidden file in bundle: {value}"
            )

        normalized_parts = {
            part.lower()
            for part in relative_path.parts
        }

        if any(
            forbidden.lower() in normalized_parts
            for forbidden in FORBIDDEN_PARTS
        ):
            raise RuntimeError(
                f"Forbidden path in bundle: {value}"
            )

        source_path = ROOT / relative_path

        if not source_path.is_file():
            raise RuntimeError(
                f"Bundle source file missing: {value}"
            )

        relative_paths.append(relative_path)

    if not relative_paths:
        raise RuntimeError(
            "Bundle include manifest is empty."
        )

    posix_paths = [
        path.as_posix()
        for path in relative_paths
    ]

    if len(posix_paths) != len(set(posix_paths)):
        raise RuntimeError(
            "Duplicate entries exist in bundle include manifest."
        )

    return sorted(
        relative_paths,
        key=lambda path: path.as_posix(),
    )


def read_git_blob(relative_path: Path) -> bytes:
    result = subprocess.run(
        [
            "git",
            "show",
            f"HEAD:{relative_path.as_posix()}",
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )

    return result.stdout


def add_bytes(
    archive: zipfile.ZipFile,
    archive_name: str,
    content: bytes,
    mode: int,
) -> None:
    info = zipfile.ZipInfo(
        filename=archive_name,
        date_time=FIXED_ZIP_TIME,
    )
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = mode << 16

    archive.writestr(
        info,
        content,
    )


def build_bundle(expected_sha: str | None) -> Path:
    branch = run_git("branch", "--show-current")
    source_sha = run_git("rev-parse", "HEAD")
    short_sha = source_sha[:12]
    worktree = run_git("status", "--porcelain")

    if branch and branch != "main":
        raise RuntimeError(
            f"Expected branch main or detached HEAD, actual={branch}"
        )

    if not branch and not expected_sha:
        raise RuntimeError(
            "Detached HEAD requires --expected-sha"
        )

    if expected_sha and source_sha != expected_sha:
        raise RuntimeError(
            "Expected SHA does not match current HEAD: "
            f"expected={expected_sha}, actual={source_sha}"
        )

    if worktree:
        raise RuntimeError(
            "Worktree must be clean before bundle build."
        )

    include_paths = load_include_paths()
    file_records: list[dict[str, object]] = []

    for relative_path in include_paths:
        content = read_git_blob(relative_path)

        file_records.append(
            {
                "path": relative_path.as_posix(),
                "sha256": sha256_bytes(content),
                "size": len(content),
            }
        )

    manifest = {
        "artifact_type": "crawler-windows-versioned-zip",
        "service": "port-interest-crawler",
        "runtime": "windows-krx-worker",
        "source_branch": "main",
        "source_sha": source_sha,
        "source_short_sha": short_sha,
        "file_count": len(file_records),
        "files": file_records,
    }

    manifest_bytes = (
        json.dumps(
            manifest,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")

    ARTIFACT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    bundle_path = (
        ARTIFACT_DIR
        / f"port-interest-crawler-windows-{short_sha}.zip"
    )

    if bundle_path.exists():
        bundle_path.unlink()

    with zipfile.ZipFile(
        bundle_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for relative_path in include_paths:
            content = read_git_blob(relative_path)

            archive_name = PurePosixPath(
                relative_path.as_posix()
            ).as_posix()

            mode = (
                0o100755
                if relative_path.suffix.lower() in {".sh", ".ps1"}
                else 0o100644
            )

            add_bytes(
                archive,
                archive_name,
                content,
                mode,
            )

        add_bytes(
            archive,
            "deployment-manifest.json",
            manifest_bytes,
            0o100644,
        )

    bundle_hash = sha256_bytes(
        bundle_path.read_bytes()
    )

    print("SOURCE_BRANCH=main")
    print(
        "CHECKOUT_MODE="
        f"{'branch' if branch else 'detached-head'}"
    )
    print(f"SOURCE_SHA={source_sha}")
    print(f"SOURCE_SHORT_SHA={short_sha}")
    print(f"BUNDLE_PATH={bundle_path}")
    print(
        f"BUNDLE_FILE_COUNT={len(file_records) + 1}"
    )
    print(f"BUNDLE_SHA256={bundle_hash}")
    print(
        "CRAWLER_WINDOWS_BUNDLE_BUILD=SUCCESS"
    )

    return bundle_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha")
    args = parser.parse_args()

    try:
        build_bundle(args.expected_sha)
    except (
        OSError,
        RuntimeError,
        subprocess.CalledProcessError,
        zipfile.BadZipFile,
    ) as exc:
        print(
            f"BUNDLE_BUILD_FAILED={exc}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())