from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

INCLUDE_FILE = (
    ROOT
    / ".devops"
    / "bundle"
    / "windows-include.txt"
)

ARTIFACT_DIR = (
    ROOT
    / ".devops"
    / "artifacts"
)

REQUIRED_FILES = {
    "db_config.py",
    "interest_get_holidays.py",
    "interest_krx_chrome.py",
    "interest_krx_login_new.py",
    "interest_krx_raw_validate_daily.py",
    "interest_log_format.py",
    "interest_program.py",
    "interest_shortsell.py",
    "requirements.txt",
    "ops/run_krx_worker_daily.ps1",
    "deployment-manifest.json",
}

FORBIDDEN_NAMES = {
    ".env",
    ".env.local",
    "ALL_SCHEMA_TABLE_DUMP.txt",
    "load-crawler-db-env.ps1",
    "load-krx-env.ps1",
}

FORBIDDEN_SUFFIXES = {
    ".bak",
    ".log",
    ".pyc",
}

FORBIDDEN_PARTS = {
    ".git",
    ".github",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "_patches",
    "artifacts",
}


def load_include_manifest() -> set[str]:
    if not INCLUDE_FILE.is_file():
        raise RuntimeError(
            f"Include manifest missing: {INCLUDE_FILE}"
        )

    entries = {
        line.strip().replace("\\", "/")
        for line in INCLUDE_FILE.read_text(
            encoding="utf-8-sig"
        ).splitlines()
        if line.strip()
        and not line.strip().startswith("#")
    }

    if not entries:
        raise RuntimeError(
            "Include manifest is empty."
        )

    return entries


def find_single_bundle() -> Path:
    bundles = sorted(
        ARTIFACT_DIR.glob(
            "port-interest-crawler-windows-*.zip"
        )
    )

    if len(bundles) != 1:
        raise RuntimeError(
            "Expected exactly one Windows bundle, "
            f"actual={len(bundles)}"
        )

    return bundles[0]


def validate_forbidden_path(name: str) -> None:
    normalized = (
        name.replace("\\", "/").strip("/")
    )

    path = Path(normalized)

    if path.name.lower() in {
        value.lower()
        for value in FORBIDDEN_NAMES
    }:
        raise RuntimeError(
            f"Forbidden file included: {name}"
        )

    if path.suffix.lower() in {
        value.lower()
        for value in FORBIDDEN_SUFFIXES
    }:
        raise RuntimeError(
            f"Forbidden suffix included: {name}"
        )

    lowered_parts = {
        part.lower()
        for part in path.parts
    }

    if any(
        forbidden.lower() in lowered_parts
        for forbidden in FORBIDDEN_PARTS
    ):
        raise RuntimeError(
            f"Forbidden path included: {name}"
        )


def main() -> int:
    try:
        include_entries = (
            load_include_manifest()
        )

        bundle_path = (
            find_single_bundle()
        )

        with zipfile.ZipFile(
            bundle_path,
            mode="r",
        ) as archive:
            names = {
                name.replace("\\", "/")
                for name in archive.namelist()
                if not name.endswith("/")
            }

            for name in sorted(names):
                validate_forbidden_path(name)

            missing_required = (
                REQUIRED_FILES - names
            )

            if missing_required:
                raise RuntimeError(
                    "Required bundle files missing: "
                    + ", ".join(
                        sorted(missing_required)
                    )
                )

            expected_names = (
                include_entries
                | {"deployment-manifest.json"}
            )

            if names != expected_names:
                unexpected = (
                    names - expected_names
                )
                missing = (
                    expected_names - names
                )

                raise RuntimeError(
                    "Bundle content mismatch: "
                    f"unexpected={sorted(unexpected)}, "
                    f"missing={sorted(missing)}"
                )

            manifest_raw = archive.read(
                "deployment-manifest.json"
            )

            manifest = json.loads(
                manifest_raw.decode("utf-8")
            )

        if (
            manifest.get("artifact_type")
            != "crawler-windows-versioned-zip"
        ):
            raise RuntimeError(
                "Unexpected artifact_type."
            )

        if (
            manifest.get("service")
            != "port-interest-crawler"
        ):
            raise RuntimeError(
                "Unexpected service."
            )

        if (
            manifest.get("runtime")
            != "windows-krx-worker"
        ):
            raise RuntimeError(
                "Unexpected runtime."
            )

        source_sha = (
            manifest.get("source_sha")
        )

        source_short_sha = (
            manifest.get("source_short_sha")
        )

        if (
            not isinstance(source_sha, str)
            or len(source_sha) != 40
        ):
            raise RuntimeError(
                "Invalid source_sha."
            )

        if (
            source_short_sha
            != source_sha[:12]
        ):
            raise RuntimeError(
                "source_short_sha mismatch."
            )

        records = (
            manifest.get("files")
        )

        if not isinstance(records, list):
            raise RuntimeError(
                "Manifest files must be a list."
            )

        manifest_paths = {
            str(record.get("path"))
            for record in records
        }

        if manifest_paths != include_entries:
            raise RuntimeError(
                "Manifest file paths do not match "
                "include manifest."
            )

        if (
            manifest.get("file_count")
            != len(include_entries)
        ):
            raise RuntimeError(
                "Manifest file_count mismatch."
            )

        print(
            f"BUNDLE={bundle_path.name}"
        )
        print(
            f"BUNDLE_FILE_COUNT={len(names)}"
        )
        print(
            f"MANIFEST_SOURCE_SHA={source_sha}"
        )
        print(
            "FORBIDDEN_FILE_COUNT=0"
        )
        print(
            "WINDOWS_WRAPPER_INCLUDED=YES"
        )
        print(
            "RUNTIME_ENV_LOADER_INCLUDED=NO"
        )
        print(
            "CRAWLER_WINDOWS_BUNDLE_CONTRACT=SUCCESS"
        )

        return 0

    except (
        OSError,
        RuntimeError,
        zipfile.BadZipFile,
        json.JSONDecodeError,
    ) as exc:
        print(
            f"WINDOWS_BUNDLE_VERIFY_FAILED={exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())