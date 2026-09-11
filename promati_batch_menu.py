# promati_batch_menu.py
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:SterkWachtwoord123@localhost:15432/promati",
)

BATCH_SCRIPT = ROOT / "run_daily_inspection_batch.py"


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def clear_screen() -> None:
    os.system("cls")


def print_header() -> None:
    clear_screen()
    print("=" * 70)
    print(" PROMATI BATCH MENU")
    print("=" * 70)
    print(f"Map      : {ROOT}")
    print(f"Database : {DATABASE_URL}")
    print("=" * 70)
    print()


def run_command(args: list[str], log_name: str | None = None) -> None:
    LOG_DIR.mkdir(exist_ok=True)

    env = os.environ.copy()
    env["DATABASE_URL"] = DATABASE_URL
    env["DB_URL"] = DATABASE_URL

    if not BATCH_SCRIPT.exists():
        print(f"[FOUT] Batch script niet gevonden: {BATCH_SCRIPT}")
        input("\nDruk op ENTER om terug te gaan...")
        return

    print()
    print("Commando:")
    print(" ".join(args))
    print()

    if log_name:
        log_file = LOG_DIR / f"{log_name}_{stamp()}.log"
        print(f"Logbestand: {log_file}")
        print()

        with open(log_file, "w", encoding="utf-8") as f:
            process = subprocess.run(
                args,
                cwd=str(ROOT),
                env=env,
                text=True,
                stdout=f,
                stderr=subprocess.STDOUT,
            )

        if process.returncode == 0:
            print("[OK] Klaar.")
        else:
            print(f"[FOUT] Script gestopt met exitcode {process.returncode}.")
            print("Bekijk het logbestand voor details.")

    else:
        process = subprocess.run(
            args,
            cwd=str(ROOT),
            env=env,
            text=True,
        )

        if process.returncode == 0:
            print("[OK] Klaar.")
        else:
            print(f"[FOUT] Script gestopt met exitcode {process.returncode}.")

    input("\nDruk op ENTER om terug te gaan naar het menu...")


def option_test_run() -> None:
    print_header()
    print("1. Test run zonder upload")
    print()
    print("Deze optie voert niets echt uit.")
    print("Hij laat alleen zien welke scripts zouden draaien.")
    print()

    run_command(
        [sys.executable, str(BATCH_SCRIPT), "--dry-run"],
        log_name=None,
    )


def option_excel_only() -> None:
    print_header()
    print("2. Alleen Excel")
    print()
    print("Deze optie draait:")
    print("- Excel staging")
    print("- inspections")
    print("- inspection items")
    print("- excel positions")
    print()
    print("Word/docx wordt overgeslagen.")
    print()

    run_command(
        [sys.executable, str(BATCH_SCRIPT), "--skip-word"],
        log_name=None,
    )


def option_excel_and_word() -> None:
    print_header()
    print("3. Excel en Word")
    print()
    print("Deze optie draait de volledige batch:")
    print("- Excel")
    print("- Word/docx")
    print()

    run_command(
        [sys.executable, str(BATCH_SCRIPT)],
        log_name=None,
    )


def option_with_log() -> None:
    print_header()
    print("4. Met log")
    print()
    print("Kies wat je met logbestand wilt draaien:")
    print()
    print("1. Test run zonder upload met log")
    print("2. Alleen Excel met log")
    print("3. Excel en Word met log")
    print("0. Terug")
    print()

    choice = input("Keuze: ").strip()

    if choice == "1":
        run_command(
            [sys.executable, str(BATCH_SCRIPT), "--dry-run"],
            log_name="test_run",
        )
    elif choice == "2":
        run_command(
            [sys.executable, str(BATCH_SCRIPT), "--skip-word"],
            log_name="excel_batch",
        )
    elif choice == "3":
        run_command(
            [sys.executable, str(BATCH_SCRIPT)],
            log_name="full_batch",
        )
    elif choice == "0":
        return
    else:
        input("Ongeldige keuze. Druk op ENTER...")


def show_menu() -> str:
    print_header()
    print("Kies een optie:")
    print()
    print("1. Test run zonder upload")
    print("2. Alleen Excel")
    print("3. Excel en Word")
    print("4. Met log")
    print("0. Afsluiten")
    print()
    return input("Keuze: ").strip()


def main() -> None:
    while True:
        choice = show_menu()

        if choice == "1":
            option_test_run()
        elif choice == "2":
            option_excel_only()
        elif choice == "3":
            option_excel_and_word()
        elif choice == "4":
            option_with_log()
        elif choice == "0":
            print("Afgesloten.")
            break
        else:
            input("Ongeldige keuze. Druk op ENTER...")


if __name__ == "__main__":
    main()