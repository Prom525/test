# promati_env_manager.py
from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


DEFAULT_PROJECT_PATH = Path(r"C:\ai-platform")
DEFAULT_BACKUP_ROOT = Path(r"E:\PromatiUSB")
DEFAULT_WORK_ROOT = Path(r"C:\PromatiBackupWork")

DEFAULT_DB_NAME = "promati"
DEFAULT_DB_USER = "postgres"

DEFAULT_VOLUMES = [
    "ai-platform_pgdata",
    "ai-platform_qdrantdata",
    "ai-platform_minio",
]

DEFAULT_IMAGES = [
    "ai-platform-api:latest",
    "ai-platform-edocr2:latest",
    "ai-platform-techreview:latest",

    "postgres:16",
    "qdrant/qdrant:latest",
    "minio/minio:latest",

    "curlimages/curl:8.6.0",
    "alpine:3.20",

    # Alleen laten staan als deze services nog echt in docker-compose staan.
    "cloudflare/cloudflared:latest",
    "quay.io/keycloak/keycloak:25.0",
]

EXCLUDE_DIRS = {".git", "__pycache__", ".venv", "node_modules"}
EXCLUDE_EXTENSIONS = {".pyc"}


@dataclass
class Progress:
    total: int
    current: int = 0

    def step(self, text: str) -> None:
        self.current += 1
        print()
        print("=" * 78)
        print(f"[{self.current}/{self.total}] {text}")
        print("=" * 78)


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def run(
    cmd: list[str],
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    print(f"> {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )

    if capture and result.stdout:
        print(result.stdout)

    if check and result.returncode != 0:
        raise RuntimeError(
            f"Commando mislukt met exitcode {result.returncode}: {' '.join(cmd)}"
        )

    return result

def command_exists(command: str) -> bool:
    result = subprocess.run(
        ["where", command],
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0

def ollama_available() -> bool:
    return command_exists("ollama")


def write_ollama_info(work_root: Path) -> None:
    info_path = work_root / "ollama-models.txt"

    if not ollama_available():
        info_path.write_text(
            "Ollama niet gevonden op deze machine.\n"
            "Na restore installeren:\n"
            "  irm https://ollama.com/install.ps1 | iex\n"
            "Daarna model laden:\n"
            "  ollama pull phi3:mini\n",
            encoding="utf-8",
        )
        print("[WAARSCHUWING] Ollama niet gevonden. Alleen herstelinstructies opgeslagen.")
        return

    result = run(["ollama", "list"], capture=True, check=False)
    info_path.write_text(result.stdout or "", encoding="utf-8")

    if "phi3:mini" not in (result.stdout or ""):
        print("[WAARSCHUWING] phi3:mini staat niet in ollama list.")
    else:
        print("[OK] Ollama model phi3:mini gevonden.")

def check_command_version(name: str, cmd: list[str], required: bool = True) -> bool:
    print(f"Controle: {name}")

    try:
        result = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError:
        result = None

    if result is None or result.returncode != 0:
        if required:
            print(f"  [ONTBREEKT] {name}")
        else:
            print(f"  [WAARSCHUWING] {name} niet gevonden")
        return False

    first_line = (result.stdout or "").splitlines()[0] if result.stdout else "OK"
    print(f"  [OK] {first_line}")
    return True


def winget_available() -> bool:
    return command_exists("winget")


def install_with_winget(name: str, package_id: str) -> None:
    print()
    print(f"{name} ontbreekt of is niet goed bereikbaar.")
    print(f"Installatiepakket: {package_id}")

    if not ask_yes_no(f"{name} nu installeren via winget?", default_no=True):
        print(f"[SKIP] {name} niet geïnstalleerd.")
        return

    run(
        [
            "winget",
            "install",
            "--id",
            package_id,
            "-e",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ],
        check=True,
    )


def prepare_new_pc_software() -> None:
    progress = Progress(total=5)

    progress.step("Basissoftware controleren")
    python_ok = check_command_version("Python", ["python", "--version"], required=True)
    docker_ok = check_command_version("Docker", ["docker", "--version"], required=True)
    compose_ok = check_command_version("Docker Compose", ["docker", "compose", "version"], required=True)
    git_ok = check_command_version("Git", ["git", "--version"], required=False)
    ollama_ok = check_command_version("Ollama", ["ollama", "--version"], required=False)

    progress.step("winget controleren")
    if not winget_available():
        raise RuntimeError(
            "winget is niet beschikbaar. Installeer Python en Docker Desktop handmatig, "
            "of update Windows App Installer via Microsoft Store."
        )

    progress.step("Ontbrekende software installeren")
    if not python_ok:
        install_with_winget("Python 3.11", "Python.Python.3.11")

    if not docker_ok or not compose_ok:
        install_with_winget("Docker Desktop", "Docker.DockerDesktop")

    if not git_ok:
        if ask_yes_no("Git is niet verplicht, maar handig. Git installeren?", default_no=True):
            install_with_winget("Git", "Git.Git")

    if not ollama_ok:
        print()
        print("Ollama ontbreekt. Installeer Ollama handmatig of via:")
        print("  irm https://ollama.com/install.ps1 | iex")
        print("Na installatie:")
        print("  ollama pull phi3:mini")

    progress.step("Na-installatie controle")
    check_command_version("Python", ["python", "--version"], required=True)
    check_command_version("Docker", ["docker", "--version"], required=True)
    check_command_version("Docker Compose", ["docker", "compose", "version"], required=True)
    check_command_version("Git", ["git", "--version"], required=False)
    check_command_version("Ollama", ["ollama", "--version"], required=False)

    progress.step("Afronding")
    print("Nieuwe PC softwarematig voorbereid.")
    print()
    print("Belangrijk:")
    print("- Start Docker Desktop minimaal één keer handmatig.")
    print("- Accepteer eventuele Docker Desktop voorwaarden.")
    print("- Herstart de PC als Docker daarom vraagt.")
    print("- Draai daarna pas de restore.")

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def check_path_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} niet gevonden: {path}")


def ask_path(prompt: str, default_path: Path | None = None) -> Path:
    print()
    if default_path:
        print(f"{prompt}")
        print(f"Druk op ENTER voor standaardlocatie: {default_path}")
    else:
        print(prompt)

    raw = input("Locatie: ").strip().strip('"')
    if not raw and default_path:
        return default_path
    if not raw:
        raise RuntimeError("Geen locatie opgegeven.")
    return Path(raw)


def ask_yes_no(question: str, default_no: bool = True) -> bool:
    suffix = "[y/N]" if default_no else "[Y/n]"
    answer = input(f"{question} {suffix}: ").strip().lower()

    if not answer:
        return not default_no

    return answer in {"y", "yes", "j", "ja"}


def check_windows_filesystem(path: Path) -> None:
    drive = path.drive
    if not drive:
        print("[WAARSCHUWING] Kan drive-letter niet bepalen. Bestandssysteemcontrole overgeslagen.")
        return

    result = run(["fsutil", "fsinfo", "volumeinfo", drive], capture=True, check=False)
    output = result.stdout or ""

    if "FAT32" in output.upper():
        raise RuntimeError(
            f"Schijf {drive} is FAT32. FAT32 kan geen grote backupbestanden aan.\n"
            f"Zet de schijf eerst om naar NTFS, bijvoorbeeld:\n"
            f"convert {drive} /FS:NTFS"
        )


def copy_project(project_path: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)

    def ignore_func(src: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()

        for name in names:
            p = Path(src) / name
            if name in EXCLUDE_DIRS:
                ignored.add(name)
            elif p.suffix.lower() in EXCLUDE_EXTENSIONS:
                ignored.add(name)

        return ignored

    print(f"Kopiëren projectmap:")
    print(f"  Van : {project_path}")
    print(f"  Naar: {destination}")
    shutil.copytree(project_path, destination, ignore=ignore_func)


def detect_compose_db_service(project_path: Path) -> str:
    result = run(
        ["docker", "compose", "ps", "--services"],
        cwd=project_path,
        capture=True,
        check=True,
    )

    services = {line.strip() for line in (result.stdout or "").splitlines() if line.strip()}

    for candidate in ["postgres", "db", "database"]:
        if candidate in services:
            print(f"[INFO] Postgres compose service gevonden: {candidate}")
            return candidate

    raise RuntimeError("Kan geen Postgres service vinden. Verwachtte postgres, db of database.")


def dump_postgres_sql(project_path: Path, work_root: Path, service_name: str, db_user: str, db_name: str) -> Path:
    sql_path = work_root / "promati.sql"

    with sql_path.open("w", encoding="utf-8") as f:
        print(f"> docker compose exec -T {service_name} pg_dump -U {db_user} -d {db_name} > {sql_path}")
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", service_name, "pg_dump", "-U", db_user, "-d", db_name],
            cwd=str(project_path),
            text=True,
            stdout=f,
            stderr=subprocess.PIPE,
        )

    if result.returncode != 0:
        raise RuntimeError(f"Postgres pg_dump mislukt:\n{result.stderr or ''}")

    if not sql_path.exists() or sql_path.stat().st_size <= 0:
        raise RuntimeError(f"SQL dump is niet aangemaakt of leeg: {sql_path}")

    print(f"SQL dump klaar: {round(sql_path.stat().st_size / 1024 / 1024, 2)} MB")
    return sql_path


def restore_postgres_sql(project_path: Path, service_name: str, db_user: str, db_name: str, sql_file: Path) -> None:
    check_path_exists(sql_file, "SQL restorebestand")

    print("[LET OP] Database wordt opnieuw opgebouwd vanuit SQL dump.")

    reset_sql = f"""
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE datname = '{db_name}'
      AND pid <> pg_backend_pid();

    DROP DATABASE IF EXISTS {db_name};
    CREATE DATABASE {db_name};
    """

    run(
        ["docker", "compose", "exec", "-T", service_name, "psql", "-U", db_user, "-d", "postgres", "-c", reset_sql],
        cwd=project_path,
        check=True,
    )


    print(f"> SQL restore: {sql_file}")

    with sql_file.open("r", encoding="utf-8", errors="replace") as f:
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", service_name, "psql", "-U", db_user, "-d", db_name],
            cwd=str(project_path),
            text=True,
            stdin=f,
            stderr=subprocess.PIPE,
        )

    if result.returncode != 0:
        raise RuntimeError(f"SQL restore mislukt:\n{result.stderr or ''}")


def image_exists(image: str) -> bool:
    return run(["docker", "image", "inspect", image], check=False).returncode == 0


def export_docker_images(work_root: Path, images: list[str]) -> Path | None:
    existing = []
    missing = []

    for image in images:
        if image_exists(image):
            existing.append(image)
            print(f"  OK   {image}")
        else:
            missing.append(image)
            print(f"  SKIP {image}")

    if missing:
        print("[WAARSCHUWING] Sommige images bestaan lokaal niet en worden overgeslagen.")

    if not existing:
        print("[WAARSCHUWING] Geen Docker images gevonden om te exporteren.")
        return None

    target = work_root / "docker-images.tar"

    run(["docker", "save", "-o", str(target), *existing], check=True)

    if not target.exists() or target.stat().st_size <= 0:
        raise RuntimeError(f"Docker images export is leeg of ontbreekt: {target}")

    print(f"Docker images export klaar: {round(target.stat().st_size / 1024 / 1024, 2)} MB")
    return target


def load_docker_images(images_tar: Path) -> None:
    if not images_tar.exists():
        print("[WAARSCHUWING] docker-images.tar ontbreekt. Images laden overgeslagen.")
        return

    run(["docker", "load", "-i", str(images_tar)], check=True)


def docker_mount_test(work_root: Path) -> None:
    test_file = work_root / "docker-mount-test.txt"

    run(
        [
            "docker", "run", "--rm",
            "-v", f"{work_root}:/backup",
            "alpine:3.20",
            "sh", "-c",
            "echo test > /backup/docker-mount-test.txt && cat /backup/docker-mount-test.txt",
        ],
        check=True,
    )

    if not test_file.exists():
        raise RuntimeError("Docker mount testbestand is niet zichtbaar op Windows.")

    test_file.unlink(missing_ok=True)


def volume_exists(volume: str) -> bool:
    return run(["docker", "volume", "inspect", volume], check=False).returncode == 0


def export_volume(volume: str, work_root: Path) -> Path:
    if not volume_exists(volume):
        raise RuntimeError(f"Docker volume bestaat niet of is niet leesbaar: {volume}")

    target = work_root / f"{volume}.tar.gz"

    run(
        [
            "docker", "run", "--rm",
            "-v", f"{volume}:/volume:ro",
            "-v", f"{work_root}:/backup",
            "alpine:3.20",
            "sh", "-c",
            f"tar czf /backup/{volume}.tar.gz -C /volume .",
        ],
        check=True,
    )

    if not target.exists() or target.stat().st_size <= 0:
        raise RuntimeError(f"Volume backup is leeg of ontbreekt: {target}")

    print(f"Volume klaar: {target.name} ({round(target.stat().st_size / 1024 / 1024, 2)} MB)")
    return target


def restore_volume(volume: str, backup_file: Path) -> None:
    check_path_exists(backup_file, f"Volume backup {volume}")

    print(f"Volume herstellen: {volume}")

    if volume_exists(volume):
        run(["docker", "volume", "rm", volume], check=False)

    run(["docker", "volume", "create", volume], check=True)

    run(
        [
            "docker", "run", "--rm",
            "-v", f"{volume}:/volume",
            "-v", f"{backup_file.parent}:/backup:ro",
            "alpine:3.20",
            "sh", "-c",
            f"tar xzf /backup/{backup_file.name} -C /volume",
        ],
        check=True,
    )


def write_info_files(project_path: Path, work_root: Path) -> None:
    commands = [
        ("docker-volume-ls.txt", ["docker", "volume", "ls"]),
        ("docker-images.txt", ["docker", "images"]),
        ("docker-system-df.txt", ["docker", "system", "df"]),
    ]

    for filename, cmd in commands:
        result = run(cmd, capture=True, check=False)
        (work_root / filename).write_text(result.stdout or "", encoding="utf-8")

    result = run(["docker", "compose", "config"], cwd=project_path, capture=True, check=True)
    (work_root / "docker-compose.resolved.yml").write_text(result.stdout or "", encoding="utf-8")


def verify_required_files(paths: list[Path], label: str) -> None:
    print()
    print(f"{label} controleren...")

    for path in paths:
        if not path.exists():
            raise RuntimeError(f"Bestand ontbreekt: {path}")

        size = path.stat().st_size
        if size <= 0:
            raise RuntimeError(f"Bestand is leeg: {path}")

        print(f"  OK {path.name} ({round(size / 1024 / 1024, 2)} MB)")


def copy_workdir_to_backup(work_root: Path, backup_dir: Path) -> None:
    ensure_dir(backup_dir)

    items = list(work_root.iterdir())
    total = len(items)

    for idx, item in enumerate(items, start=1):
        target = backup_dir / item.name
        print(f"[{idx}/{total}] Kopiëren: {item.name}")

        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def validate_backup_folder(backup_root: Path, volumes: list[str]) -> tuple[Path, Path]:
    backup_dir = backup_root / "backup"
    project_dir = backup_root / "project"

    check_path_exists(backup_dir, "Backup submap")
    check_path_exists(project_dir, "Project backupmap")
    check_path_exists(backup_dir / "promati.sql", "Database dump")

    for volume in volumes:
        check_path_exists(backup_dir / f"{volume}.tar.gz", f"Volume backup {volume}")

    return backup_dir, project_dir


def backup_environment(
    project_path: Path,
    backup_root: Path,
    work_root: Path,
    db_user: str,
    db_name: str,
    volumes: list[str],
    images: list[str],
    prune_builder: bool,
    timestamped_folder: bool,
) -> None:
    progress = Progress(total=13)

    if timestamped_folder:
        backup_root = backup_root / f"backup_{now_stamp()}"

    backup_dir = backup_root / "backup"
    project_backup_dir = backup_root / "project"

    progress.step("Controle project en backup-locatie")
    check_path_exists(project_path, "Projectmap")
    ensure_dir(backup_root)
    ensure_dir(backup_dir)
    ensure_dir(project_backup_dir)

    print(f"Projectmap     : {project_path}")
    print(f"Backup-locatie : {backup_root}")
    print(f"Werkmap        : {work_root}")

    progress.step("Werkmap voorbereiden")
    if work_root.exists():
        shutil.rmtree(work_root)
    ensure_dir(work_root)

    progress.step("Backup-schijf bestandssysteem controleren")
    check_windows_filesystem(backup_root)

    progress.step("Docker status controleren")
    run(["docker", "version"], check=True)
    run(["docker", "info"], check=True)

    if prune_builder:
        progress.step("Docker build-cache opschonen")
        run(["docker", "builder", "prune", "-a", "-f"], check=True)
    else:
        progress.step("Docker build-cache overslaan")

    progress.step("Project kopiëren")
    copy_project(project_path, project_backup_dir)

    progress.step("Compose stack controleren")
    run(["docker", "compose", "ps"], cwd=project_path, check=True)
    db_service = detect_compose_db_service(project_path)

    progress.step("Postgres SQL dump maken")
    sql_path = dump_postgres_sql(project_path, work_root, db_service, db_user, db_name)

    progress.step("Docker images exporteren")
    images_tar = export_docker_images(work_root, images)

    progress.step("Docker volume mount test")
    docker_mount_test(work_root)

    progress.step("Volumes exporteren")
    volume_files = []
    for idx, volume in enumerate(volumes, start=1):
        print(f"Volume [{idx}/{len(volumes)}]: {volume}")
        volume_files.append(export_volume(volume, work_root))

    progress.step("Extra informatie opslaan")
    write_info_files(project_path, work_root)
    write_ollama_info(work_root)

    required_work_files = [
        sql_path,
        work_root / "docker-compose.resolved.yml",
        work_root / "ollama-models.txt",
        *volume_files,
    ]
    if images_tar:
        required_work_files.append(images_tar)

    verify_required_files(required_work_files, "Werkmap")

    progress.step("Backupbestanden kopiëren naar gekozen locatie")
    copy_workdir_to_backup(work_root, backup_dir)

    required_backup_files = [backup_dir / path.name for path in required_work_files]
    verify_required_files(required_backup_files, "Backup-locatie")

    print()
    print("=" * 78)
    print("BACKUP COMPLEET")
    print("=" * 78)
    print(f"Backup succesvol opgeslagen op: {backup_root}")


def restore_environment(
    project_path: Path,
    restore_root: Path,
    db_user: str,
    db_name: str,
    volumes: list[str],
    restore_project: bool,
    restore_images: bool,
    restore_volumes: bool,
    restore_database: bool,
) -> None:
    progress = Progress(total=9)

    progress.step("Restore-bron controleren")
    backup_dir, project_backup_dir = validate_backup_folder(restore_root, volumes)
    print(f"Restore-bron : {restore_root}")
    print(f"Project doel : {project_path}")

    progress.step("Docker status controleren")
    run(["docker", "version"], check=True)
    run(["docker", "info"], check=True)

    progress.step("Bevestiging")
    print("Deze restore kan bestaande projectbestanden, Docker volumes en database overschrijven.")
    print(f"Restore vanaf: {restore_root}")
    print(f"Project doel : {project_path}")
    if not ask_yes_no("Weet je zeker dat je wilt doorgaan?", default_no=True):
        print("Restore afgebroken.")
        return

    progress.step("Compose stack stoppen")
    if project_path.exists():
        run(["docker", "compose", "down"], cwd=project_path, check=False)

    if restore_project:
        progress.step("Projectmap herstellen")
        if project_path.exists():
            old_path = project_path.with_name(f"{project_path.name}_before_restore_{now_stamp()}")
            print(f"Bestaande projectmap wordt hernoemd naar: {old_path}")
            project_path.rename(old_path)

        shutil.copytree(project_backup_dir, project_path)
    else:
        progress.step("Projectmap overslaan")

    if restore_images:
        progress.step("Docker images laden")
        load_docker_images(backup_dir / "docker-images.tar")
    else:
        progress.step("Docker images overslaan")

    if restore_volumes:
        progress.step("Docker volumes herstellen")
        # Containers moeten uit staan voordat volumes betrouwbaar verwijderd worden.
        run(["docker", "compose", "down"], cwd=project_path, check=False)

        for idx, volume in enumerate(volumes, start=1):
            print(f"Volume [{idx}/{len(volumes)}]: {volume}")
            restore_volume(volume, backup_dir / f"{volume}.tar.gz")
    else:
        progress.step("Docker volumes overslaan")

    progress.step("Compose stack starten")
    run(["docker", "compose", "up", "-d"], cwd=project_path, check=True)

    if restore_database:
        progress.step("Database herstellen vanuit promati.sql")
        db_service = detect_compose_db_service(project_path)
        restore_postgres_sql(project_path, db_service, db_user, db_name, backup_dir / "promati.sql")
        print("Compose stack herstarten na database restore")
        run(["docker", "compose", "restart"], cwd=project_path, check=False)
    else:
        progress.step("Database restore overslaan")

    print()
    print("=" * 78)
    print()
    print("Ollama / Phi-3 controle:")
    print("- Als TechReview Phi-3 gebruikt, moet Ollama op de Windows-host draaien.")
    print("- Controleer met: ollama list")
    print("- Indien nodig: ollama pull phi3:mini")
    print("- TechReview gebruikt: http://host.docker.internal:11434/api/generate")
    print("RESTORE COMPLEET")
    print("=" * 78)
    print("Controleer nu de API en database.")


def docker_check(project_path: Path) -> None:
    print()
    print("=" * 78)
    print("DOCKER / COMPOSE CONTROLE")
    print("=" * 78)

    run(["docker", "version"], check=False)
    run(["docker", "compose", "ps"], cwd=project_path, check=False)
    run(["docker", "volume", "ls"], check=False)
    run(["docker", "images"], check=False)


def choose_restore_options() -> dict[str, bool]:
    print()
    print("Wat wil je herstellen?")
    print("Druk op ENTER voor standaard: alles herstellen.")
    print()

    all_restore = ask_yes_no("Alles herstellen? project + images + volumes + database", default_no=False)

    if all_restore:
        return {
            "restore_project": True,
            "restore_images": True,
            "restore_volumes": True,
            "restore_database": True,
        }

    return {
        "restore_project": ask_yes_no("Projectmap herstellen?", default_no=False),
        "restore_images": ask_yes_no("Docker images laden?", default_no=False),
        "restore_volumes": ask_yes_no("Docker volumes herstellen?", default_no=False),
        "restore_database": ask_yes_no("Database herstellen vanuit promati.sql?", default_no=False),
    }


def menu() -> None:
    while True:
        print()
        print("=" * 70)
        print(" PROMATI ENVIRONMENT MANAGER")
        print("=" * 70)
        print(f"Standaard projectmap : {DEFAULT_PROJECT_PATH}")
        print(f"Standaard backupmap  : {DEFAULT_BACKUP_ROOT}")
        print()
        print("1. Backup maken naar standaardlocatie")
        print("2. Backup maken naar zelfgekozen locatie")
        print("3. Nieuwe PC softwarematig voorbereiden")
        print("4. Restore vanaf zelfgekozen backup-locatie")
        print("5. Docker/compose controle")
        print("0. Afsluiten")
        print()

        choice = input("Keuze: ").strip()

        if choice == "1":
            backup_environment(
                project_path=DEFAULT_PROJECT_PATH,
                backup_root=DEFAULT_BACKUP_ROOT,
                work_root=DEFAULT_WORK_ROOT,
                db_user=DEFAULT_DB_USER,
                db_name=DEFAULT_DB_NAME,
                volumes=DEFAULT_VOLUMES,
                images=DEFAULT_IMAGES,
                prune_builder=True,
                timestamped_folder=True,
            )
            input("\nDruk op ENTER om terug te gaan...")

        elif choice == "2":
            backup_root = ask_path(
                "Kies backup-locatie.",
                DEFAULT_BACKUP_ROOT,
            )
            backup_environment(
                project_path=DEFAULT_PROJECT_PATH,
                backup_root=backup_root,
                work_root=DEFAULT_WORK_ROOT,
                db_user=DEFAULT_DB_USER,
                db_name=DEFAULT_DB_NAME,
                volumes=DEFAULT_VOLUMES,
                images=DEFAULT_IMAGES,
                prune_builder=True,
                timestamped_folder=True,
            )
            input("\nDruk op ENTER om terug te gaan...")

        elif choice == "3":
            prepare_new_pc_software()
            input("\nDruk op ENTER om terug te gaan...")

        elif choice == "4":
            restore_root = ask_path(
                "Kies restore-bronlocatie. Dit is de map met daarin 'backup' en 'project'.",
                None,
            )
            opts = choose_restore_options()
            restore_environment(
                project_path=DEFAULT_PROJECT_PATH,
                restore_root=restore_root,
                db_user=DEFAULT_DB_USER,
                db_name=DEFAULT_DB_NAME,
                volumes=DEFAULT_VOLUMES,
                **opts,
            )
            input("\nDruk op ENTER om terug te gaan...")

        elif choice == "5":
            docker_check(DEFAULT_PROJECT_PATH)
            input("\nDruk op ENTER om terug te gaan...")

        elif choice == "0":
            break

        else:
            input("Ongeldige keuze. Druk op ENTER...")


def main() -> int:
    parser = argparse.ArgumentParser(description="Promati environment backup/restore tool")
    parser.add_argument("--backup", action="store_true", help="Maak direct een backup zonder menu")
    parser.add_argument("--restore", action="store_true", help="Voer direct restore uit zonder menu")
    parser.add_argument("--project-path", default=str(DEFAULT_PROJECT_PATH))
    parser.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT))
    parser.add_argument("--restore-root", default="")
    parser.add_argument("--work-root", default=str(DEFAULT_WORK_ROOT))
    parser.add_argument("--db-user", default=DEFAULT_DB_USER)
    parser.add_argument("--db-name", default=DEFAULT_DB_NAME)
    parser.add_argument("--no-prune", action="store_true")
    parser.add_argument("--no-timestamp-folder", action="store_true")

    args = parser.parse_args()

    try:
        if args.backup:
            backup_environment(
                project_path=Path(args.project_path),
                backup_root=Path(args.backup_root),
                work_root=Path(args.work_root),
                db_user=args.db_user,
                db_name=args.db_name,
                volumes=DEFAULT_VOLUMES,
                images=DEFAULT_IMAGES,
                prune_builder=not args.no_prune,
                timestamped_folder=not args.no_timestamp_folder,
            )

        elif args.restore:
            if not args.restore_root:
                raise RuntimeError("--restore-root is verplicht bij --restore")

            restore_environment(
                project_path=Path(args.project_path),
                restore_root=Path(args.restore_root),
                db_user=args.db_user,
                db_name=args.db_name,
                volumes=DEFAULT_VOLUMES,
                restore_project=True,
                restore_images=True,
                restore_volumes=True,
                restore_database=True,
            )

        else:
            menu()

        return 0

    except Exception as exc:
        print()
        print("=" * 70)
        print("FOUT")
        print("=" * 70)
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())