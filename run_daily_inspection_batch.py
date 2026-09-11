# run_daily_inspection_batch.py
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent

# Zet hier eventueel je Word/docx hoofdmap.
# Laat None als je Word-import nu nog niet automatisch wilt draaien.
WORD_ROOT = r"C:\Users\John Koenders\Baucotech\Logbooks - Documenten\Onderhouds Logboeken - Rapport Entretiens\NL\TATA steel\Inspectie lijsten Tata Steel"

DEFAULT_DATABASE_URL = "postgresql://postgres:SterkWachtwoord123@localhost:15432/promati"


EXCEL_BATCH_SCRIPTS = [
    "ingest_excel_to_sb_staging_recursive_v3.py",
    "promote_to_inspections_v1.py",
    "promote_to_inspection_items_all_v4.py",
    "load_sb_excel_positions_v5.py",
]


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def resolve_database_url() -> str:
    return (
        os.environ.get("DATABASE_URL")
        or os.environ.get("DB_URL")
        or DEFAULT_DATABASE_URL
    )


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    db_url = resolve_database_url()

    # Sommige scripts gebruiken DATABASE_URL, andere DB_URL.
    # Daarom zetten we beide.
    env["DATABASE_URL"] = db_url
    env["DB_URL"] = db_url

    return env


def run_command(cmd: list[str], env: dict[str, str], dry_run: bool = False) -> None:
    print(f"\n[{timestamp()}] START: {' '.join(cmd)}")

    if dry_run:
        print(f"[{timestamp()}] DRY-RUN: niet uitgevoerd")
        return

    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Batch gestopt. Commando faalde met exitcode {result.returncode}: {' '.join(cmd)}"
        )

    print(f"[{timestamp()}] OK: {' '.join(cmd)}")


def script_exists(script_name: str) -> bool:
    return (ROOT / script_name).exists()




def parse_pg_args_from_url(database_url: str) -> dict[str, str]:
    parsed = urlparse(database_url)

    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 15432),
        "db": (parsed.path or "/promati").lstrip("/") or "promati",
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
    }


def run_word_import(env: dict[str, str], dry_run: bool = False) -> None:
    script_name = "import_inspectie_docx_doc.py"
    script_path = ROOT / script_name

    if not script_path.exists():
        print(f"[{timestamp()}] SKIP WORD: {script_name} niet gevonden")
        return

    if not WORD_ROOT or not Path(WORD_ROOT).exists():
        print(f"[{timestamp()}] SKIP WORD: WORD_ROOT bestaat niet of is leeg: {WORD_ROOT}")
        return

    pg = parse_pg_args_from_url(resolve_database_url())

    cmd = [
        sys.executable,
        str(script_path),
        "--root",
        WORD_ROOT,
        "--pg-host",
        pg["host"],
        "--pg-port",
        pg["port"],
        "--pg-db",
        pg["db"],
        "--pg-user",
        pg["user"],
        "--pg-password",
        pg["password"],
    ]

    run_command(cmd, env=env, dry_run=dry_run)


def run_python_script(
    script_name: str,
    env: dict[str, str],
    dry_run: bool = False,
    extra_args: list[str] | None = None,
) -> None:
    script_path = ROOT / script_name

    if not script_path.exists():
        raise FileNotFoundError(f"Script niet gevonden: {script_path}")

    cmd = [sys.executable, str(script_path)]
    if extra_args:
        cmd.extend(extra_args)

    run_command(cmd, env=env, dry_run=dry_run)


def run_excel_batch(env: dict[str, str], mode: str, dry_run: bool = False) -> None:
    for script in EXCEL_BATCH_SCRIPTS:
        extra_args = []

        if script in {
            "ingest_excel_to_sb_staging_recursive_v3.py",
            "promote_to_inspections_v1.py",
            "promote_to_inspection_items_all_v4.py",
            "load_sb_excel_positions_v5.py",
        }:
            extra_args = ["--mode", mode]

        run_python_script(script, env=env, dry_run=dry_run, extra_args=extra_args)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dagelijkse Promati inspectie batch-update"
    )
    parser.add_argument(
        "--skip-excel",
        action="store_true",
        help="Excel-import en Excel-promotie overslaan",
    )
    parser.add_argument(
        "--skip-word",
        action="store_true",
        help="Word/docx-import overslaan",
    )

    parser.add_argument(
        "--only-positions",
        action="store_true",
        help="Alleen load_sb_excel_positions_v5.py uitvoeren",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Toon wat uitgevoerd zou worden, zonder echt te draaien",
    )

    parser.add_argument(
        "--mode",
        choices=["incremental", "full-rebuild"],
        default="incremental",
        help="incremental = alleen gewijzigde sheets; full-rebuild = volledige herbouw",
    )

    args = parser.parse_args()

    if args.only_positions and args.skip_excel:
        parser.error("--only-positions en --skip-excel kunnen niet tegelijk gebruikt worden")

    env = build_env()

    print("=" * 80)
    print(f"[{timestamp()}] PROMATI DAILY INSPECTION BATCH")
    print(f"ROOT          : {ROOT}")
    print(f"DATABASE_URL  : {env.get('DATABASE_URL')}")
    print(f"WORD_ROOT     : {WORD_ROOT}")
    print("=" * 80)

    try:
        if args.only_positions:
            print(f"[{timestamp()}] ONLY POSITIONS")
            run_python_script(
                "load_sb_excel_positions_v5.py",
                env=env,
                dry_run=args.dry_run,
                extra_args=["--mode", args.mode],
            )
        elif not args.skip_excel:
            run_excel_batch(env=env, mode=args.mode, dry_run=args.dry_run)
        else:
            print(f"[{timestamp()}] SKIP EXCEL")

        if not args.skip_word:
            run_word_import(env=env, dry_run=args.dry_run)
        else:
            print(f"[{timestamp()}] SKIP WORD")

        print("\n" + "=" * 80)
        print(f"[{timestamp()}] BATCH KLAAR")
        print("=" * 80)
        return 0

    except Exception as exc:
        print("\n" + "=" * 80)
        print(f"[{timestamp()}] BATCH FOUT")
        print(str(exc))
        print("=" * 80)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
