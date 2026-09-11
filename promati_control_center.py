# promati_control_center.py
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"

API_BASE_URL = os.environ.get("PROMATI_API_BASE_URL", "http://localhost:8000")
FRONTEND_URL = os.environ.get("PROMATI_FRONTEND_URL", "http://localhost:5173")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:SterkWachtwoord123@localhost:15432/promati",
)

SCRIPTS = {
    "env_manager": ROOT / "promati_env_manager.py",
    "batch_menu": ROOT / "promati_batch_menu.py",
    "daily_batch": ROOT / "run_daily_inspection_batch.py",
}

BAT_FILES = {
    "compile_api": ROOT / "compile-api.bat",
    "compile_api_only": ROOT / "compile-api-only.bat",
    "postgres": ROOT / "postgres.bat",
    "ngrok": ROOT / "ngrok starteb.bat",
    "ingest_start": ROOT / "ingest_start.bat",
}


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause() -> None:
    input("\nDruk op ENTER om terug te gaan...")


def header(title: str = "PROMATI CONTROL CENTER") -> None:
    clear_screen()
    print("=" * 78)
    print(f" {title}")
    print("=" * 78)
    print(f"Projectmap : {ROOT}")
    print(f"API        : {API_BASE_URL}")
    print(f"Frontend   : {FRONTEND_URL}")
    print(f"Database   : {DATABASE_URL}")
    print("=" * 78)
    print()


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = DATABASE_URL
    env["DB_URL"] = DATABASE_URL
    return env


def run_command(
    cmd: list[str],
    cwd: Path | None = None,
    wait: bool = True,
    log_name: str | None = None,
    check: bool = False,
) -> int:
    LOG_DIR.mkdir(exist_ok=True)

    cwd = cwd or ROOT
    env = build_env()

    print()
    print("> " + " ".join(cmd))
    print()

    if log_name:
        log_file = LOG_DIR / f"{log_name}_{stamp()}.log"
        print(f"Logbestand: {log_file}")
        print()

        with log_file.open("w", encoding="utf-8", errors="replace") as f:
            result = subprocess.run(
                cmd,
                cwd=str(cwd),
                env=env,
                text=True,
                stdout=f,
                stderr=subprocess.STDOUT,
            )

        if result.returncode == 0:
            print("[OK] Klaar.")
        else:
            print(f"[FOUT] Exitcode {result.returncode}. Bekijk logbestand.")

        if check and result.returncode != 0:
            raise RuntimeError(f"Commando mislukt: {' '.join(cmd)}")

        return result.returncode

    if wait:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            text=True,
        )

        if result.returncode == 0:
            print("[OK] Klaar.")
        else:
            print(f"[FOUT] Exitcode {result.returncode}.")

        if check and result.returncode != 0:
            raise RuntimeError(f"Commando mislukt: {' '.join(cmd)}")

        return result.returncode

    subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
    )
    print("[OK] Gestart in nieuw venster.")
    return 0


def run_bat(path: Path, wait: bool = True) -> None:
    if not path.exists():
        print(f"[FOUT] Bestand niet gevonden: {path}")
        pause()
        return

    if os.name == "nt":
        run_command(["cmd", "/c", str(path)], wait=wait)
    else:
        print("[FOUT] .bat bestanden kunnen alleen direct op Windows worden gestart.")

    pause()


def http_get_json(url: str, timeout: int = 8) -> dict:
    request = Request(url, headers={"Accept": "application/json"})

    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return {
                "ok": True,
                "status_code": response.status,
                "data": json.loads(raw) if raw else None,
            }

    except HTTPError as exc:
        return {
            "ok": False,
            "status_code": exc.code,
            "error": str(exc),
        }

    except URLError as exc:
        return {
            "ok": False,
            "status_code": None,
            "error": str(exc.reason),
        }

    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def http_post_json(url: str, payload: dict, timeout: int = 30) -> dict:
    body = json.dumps(payload).encode("utf-8")

    request = Request(
        url,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return {
                "ok": True,
                "status_code": response.status,
                "data": json.loads(raw) if raw else None,
            }

    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status_code": exc.code,
            "error": raw or str(exc),
        }

    except URLError as exc:
        return {
            "ok": False,
            "status_code": None,
            "error": str(exc.reason),
        }

    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def print_json(data: object) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def option_system_status() -> None:
    header("SYSTEEMSTATUS")

    print("Docker compose status:")
    run_command(["docker", "compose", "ps"], wait=True)

    print("\nAPI health:")
    print_json(http_get_json(f"{API_BASE_URL}/diagnostics/health"))

    print("\nDatabase ping:")
    print_json(http_get_json(f"{API_BASE_URL}/diagnostics/database/ping"))

    print("\nFrontend check:")
    frontend = http_get_json(FRONTEND_URL)
    if frontend.get("ok"):
        print("[OK] Frontend reageert.")
    else:
        print("[WAARSCHUWING] Frontend check gaf geen JSON-response of is niet bereikbaar.")
        print_json(frontend)

    pause()


def option_api_management() -> None:
    while True:
        header("API BEHEER")
        print("1. API restart")
        print("2. API rebuild --no-cache")
        print("3. API logs tail 120")
        print("4. API syntaxcheck diagnostics_api.py")
        print("5. compile-api-only.bat")
        print("6. compile-api.bat")
        print("0. Terug")
        print()

        choice = input("Keuze: ").strip()

        if choice == "1":
            run_command(["docker", "compose", "up", "-d", "--force-recreate", "api"])
            pause()

        elif choice == "2":
            run_command(["docker", "compose", "build", "--no-cache", "api"], log_name="api_build")
            run_command(["docker", "compose", "up", "-d", "--force-recreate", "api"])
            pause()

        elif choice == "3":
            run_command(["docker", "compose", "logs", "--tail=120", "api"])
            pause()

        elif choice == "4":
            run_command([
                "docker",
                "compose",
                "run",
                "--rm",
                "api",
                "sh",
                "-lc",
                "PYTHONDONTWRITEBYTECODE=1 python -m py_compile /app/app/routers/diagnostics_api.py",
            ])
            pause()

        elif choice == "5":
            run_bat(BAT_FILES["compile_api_only"])

        elif choice == "6":
            run_bat(BAT_FILES["compile_api"])

        elif choice == "0":
            return

        else:
            input("Ongeldige keuze. Druk op ENTER...")


def option_diagnostics() -> None:
    while True:
        header("DATABASE / DIAGNOSTICS")
        print("1. Diagnostics health")
        print("2. Database ping")
        print("3. SQL deep dive test: E401 onderhoudstoplijst")
        print("4. Asset model health compact")
        print("5. Eigen sql_deep_dive vraag")
        print("6. Postgres.bat starten")
        print("0. Terug")
        print()

        choice = input("Keuze: ").strip()

        if choice == "1":
            print_json(http_get_json(f"{API_BASE_URL}/diagnostics/health"))
            pause()

        elif choice == "2":
            print_json(http_get_json(f"{API_BASE_URL}/diagnostics/database/ping"))
            pause()

        elif choice == "3":
            payload = {
                "domain": "database",
                "mode": "sql_deep_dive",
                "question": "Waar valt E401 weg in de keten van bandpositie naar onderhoudstoplijst?",
                "filters": {
                    "lijn_code": "MV2",
                    "band_code": "E401",
                    "response_profile": "gpt_compact",
                    "compare_mode": "chain",
                },
                "depth": "deep",
                "limit": 50,
            }
            result = http_post_json(f"{API_BASE_URL}/diagnostics/analyze", payload)
            print_json(result)
            pause()

        elif choice == "4":
            payload = {
                "domain": "database",
                "mode": "asset_model_health",
                "filters": {
                    "response_profile": "gpt_compact",
                },
                "depth": "deep",
                "limit": 20,
            }
            result = http_post_json(f"{API_BASE_URL}/diagnostics/analyze", payload)
            print_json(result)
            pause()

        elif choice == "5":
            vraag = input("Vraag: ").strip()
            lijn = input("lijn_code, leeg = geen filter: ").strip()
            band = input("band_code, leeg = geen filter: ").strip()

            filters = {
                "response_profile": "gpt_compact",
                "compare_mode": "chain",
            }
            if lijn:
                filters["lijn_code"] = lijn
            if band:
                filters["band_code"] = band

            payload = {
                "domain": "database",
                "mode": "sql_deep_dive",
                "question": vraag,
                "filters": filters,
                "depth": "deep",
                "limit": 50,
            }

            result = http_post_json(f"{API_BASE_URL}/diagnostics/analyze", payload)
            print_json(result)
            pause()

        elif choice == "6":
            run_bat(BAT_FILES["postgres"])

        elif choice == "0":
            return

        else:
            input("Ongeldige keuze. Druk op ENTER...")


def option_batch_imports() -> None:
    while True:
        header("INSPECTIE IMPORT / BATCH")
        print("1. Batchmenu openen")
        print("2. Test-run dry-run")
        print("3. Incremental Excel-only")
        print("4. Full rebuild Excel-only")
        print("5. Incremental Excel + Word")
        print("6. Ingest_start.bat")
        print("0. Terug")
        print()

        choice = input("Keuze: ").strip()

        batch = SCRIPTS["daily_batch"]

        if choice == "1":
            run_command([sys.executable, str(SCRIPTS["batch_menu"])])
            pause()

        elif choice == "2":
            run_command([sys.executable, str(batch), "--dry-run"])
            pause()

        elif choice == "3":
            run_command([sys.executable, str(batch), "--skip-word", "--mode", "incremental"], log_name="batch_excel_incremental")
            pause()

        elif choice == "4":
            confirm = input("Full rebuild kan lang duren. Doorgaan? typ JA: ").strip()
            if confirm == "JA":
                run_command([sys.executable, str(batch), "--skip-word", "--mode", "full-rebuild"], log_name="batch_excel_full_rebuild")
            pause()

        elif choice == "5":
            run_command([sys.executable, str(batch), "--mode", "incremental"], log_name="batch_excel_word_incremental")
            pause()

        elif choice == "6":
            run_bat(BAT_FILES["ingest_start"])

        elif choice == "0":
            return

        else:
            input("Ongeldige keuze. Druk op ENTER...")


def option_backup_restore() -> None:
    while True:
        header("BACKUP / RESTORE")
        print("1. Environment manager openen")
        print("2. Direct backup standaardlocatie")
        print("3. Docker/compose controle via env_manager")
        print("0. Terug")
        print()

        choice = input("Keuze: ").strip()

        env_manager = SCRIPTS["env_manager"]

        if choice == "1":
            run_command([sys.executable, str(env_manager)])
            pause()

        elif choice == "2":
            confirm = input("Backup naar standaardlocatie maken? typ JA: ").strip()
            if confirm == "JA":
                run_command([sys.executable, str(env_manager), "--backup"], log_name="environment_backup")
            pause()

        elif choice == "3":
            # Gewoon env_manager openen; daar zit optie 5 Docker/compose controle al in.
            run_command([sys.executable, str(env_manager)])
            pause()

        elif choice == "0":
            return

        else:
            input("Ongeldige keuze. Druk op ENTER...")


def option_external_access() -> None:
    while True:
        header("EXTERNE TOEGANG")
        print("1. ngrok starten")
        print("2. cloudflared logs")
        print("3. Toon lokale endpoints")
        print("0. Terug")
        print()

        choice = input("Keuze: ").strip()

        if choice == "1":
            run_bat(BAT_FILES["ngrok"], wait=False)

        elif choice == "2":
            run_command(["docker", "compose", "logs", "--tail=120", "cloudflared"])
            pause()

        elif choice == "3":
            print("Lokale endpoints:")
            print(f"- API       : {API_BASE_URL}")
            print(f"- Diagnostics health: {API_BASE_URL}/diagnostics/health")
            print(f"- Frontend  : {FRONTEND_URL}")
            print("- Postgres  : localhost:15432")
            print("- Qdrant    : intern via Docker (qdrant:6333)")
            print("- Minio     : localhost:9000 / 9001")
            pause()

        elif choice == "0":
            return

        else:
            input("Ongeldige keuze. Druk op ENTER...")


def option_logs() -> None:
    while True:
        header("LOGS")
        print("1. API logs")
        print("2. Frontend logs")
        print("3. Postgres logs")
        print("4. Laatste batchlogs tonen")
        print("0. Terug")
        print()

        choice = input("Keuze: ").strip()

        if choice == "1":
            run_command(["docker", "compose", "logs", "--tail=160", "api"])
            pause()

        elif choice == "2":
            run_command(["docker", "compose", "logs", "--tail=160", "frontend"])
            pause()

        elif choice == "3":
            run_command(["docker", "compose", "logs", "--tail=160", "postgres"])
            pause()

        elif choice == "4":
            LOG_DIR.mkdir(exist_ok=True)
            logs = sorted(LOG_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]
            if not logs:
                print("Geen logbestanden gevonden.")
            else:
                print("Laatste logbestanden:")
                for idx, log in enumerate(logs, start=1):
                    print(f"{idx}. {log.name}")

                raw = input("\nNummer openen, leeg = terug: ").strip()
                if raw.isdigit():
                    index = int(raw) - 1
                    if 0 <= index < len(logs):
                        print()
                        print("=" * 78)
                        print(logs[index])
                        print("=" * 78)
                        print(logs[index].read_text(encoding="utf-8", errors="replace")[-8000:])
            pause()

        elif choice == "0":
            return

        else:
            input("Ongeldige keuze. Druk op ENTER...")


def option_maintenance() -> None:
    while True:
        header("ONDERHOUD / CLEANUP")
        print("1. Docker builder prune")
        print("2. __pycache__ verwijderen in API container")
        print("3. diagnostics_api.py syntaxcheck")
        print("4. Docker system df")
        print("0. Terug")
        print()

        choice = input("Keuze: ").strip()

        if choice == "1":
            confirm = input("Docker build-cache opschonen? typ JA: ").strip()
            if confirm == "JA":
                run_command(["docker", "builder", "prune", "-a", "-f"])
            pause()

        elif choice == "2":
            run_command([
                "docker",
                "compose",
                "run",
                "--rm",
                "api",
                "sh",
                "-lc",
                "rm -rf /app/app/routers/__pycache__ /app/app/__pycache__",
            ])
            pause()

        elif choice == "3":
            run_command([
                "docker",
                "compose",
                "run",
                "--rm",
                "api",
                "sh",
                "-lc",
                "PYTHONDONTWRITEBYTECODE=1 python -m py_compile /app/app/routers/diagnostics_api.py",
            ])
            pause()

        elif choice == "4":
            run_command(["docker", "system", "df"])
            pause()

        elif choice == "0":
            return

        else:
            input("Ongeldige keuze. Druk op ENTER...")


def main_menu() -> str:
    header()
    print("Kies een optie:")
    print()
    print("1. Systeemstatus")
    print("2. API beheer")
    print("3. Database / diagnostics")
    print("4. Inspectie import / batch")
    print("5. Backup / restore")
    print("6. Externe toegang / ngrok")
    print("7. Logs bekijken")
    print("8. Onderhoud / cleanup")
    print("0. Afsluiten")
    print()
    return input("Keuze: ").strip()


def main() -> int:
    while True:
        choice = main_menu()

        if choice == "1":
            option_system_status()
        elif choice == "2":
            option_api_management()
        elif choice == "3":
            option_diagnostics()
        elif choice == "4":
            option_batch_imports()
        elif choice == "5":
            option_backup_restore()
        elif choice == "6":
            option_external_access()
        elif choice == "7":
            option_logs()
        elif choice == "8":
            option_maintenance()
        elif choice == "0":
            print("Afgesloten.")
            return 0
        else:
            input("Ongeldige keuze. Druk op ENTER...")


if __name__ == "__main__":
    raise SystemExit(main())