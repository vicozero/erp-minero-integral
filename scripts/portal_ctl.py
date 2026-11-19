from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"
RUN_DIR = ROOT / "var" / "run"
LOG_DIR = ROOT / "var" / "log"
DEFAULT_ENV_FILE = ROOT / ".env"


def load_env_file(path: Path) -> dict[str, str]:
    """Lee variables del perfil activo sin imprimir valores sensibles."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def child_environment(env_file: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key, value in load_env_file(env_file).items():
        env.setdefault(key, value)
    env["ERP_ENV_FILE"] = str(env_file)
    return env


def env_int(env: dict[str, str], name: str, default: int) -> int:
    try:
        return int(env.get(name, str(default)))
    except ValueError:
        return default


def pid_alive(pid: int) -> bool:
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def listener_pid(port: int) -> int | None:
    """Devuelve el PID que realmente escucha en un puerto TCP local."""
    if os.name != "nt":
        return None
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-NetTCPConnection -State Listen -LocalPort {port} "
                "-ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return int(result.stdout.strip())
    except (ValueError, OSError):
        return None


def read_pid(name: str) -> int | None:
    path = RUN_DIR / f"{name}.pid"
    if not path.is_file():
        return None
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None
    return pid if pid_alive(pid) else None


def write_pid(name: str, pid: int) -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    (RUN_DIR / f"{name}.pid").write_text(str(pid), encoding="utf-8")


def clear_pid(name: str) -> None:
    (RUN_DIR / f"{name}.pid").unlink(missing_ok=True)


def http_ok(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def wait_for(url: str, timeout_seconds: int, label: str) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if http_ok(url):
            return True
        time.sleep(0.4)
    print(f"ERROR: {label} no respondió en {timeout_seconds} s.")
    return False


def build_frontend(env: dict[str, str]) -> bool:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if npm is None:
        print("ERROR: no se encontró npm; no se pudo compilar el frontend.")
        return False
    print("Compilando React (npm run build)…")
    result = subprocess.run([npm, "run", "build"], cwd=FRONTEND_DIR, env=env, check=False)
    if result.returncode != 0:
        print("ERROR: la compilación de React falló.")
        return False
    return True


def spawn(name: str, command: list[str], cwd: Path, env: dict[str, str]) -> int | None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{name}.log"
    creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    with log_path.open("ab") as log_file:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
        )
    write_pid(name, process.pid)
    return process.pid


def stop_process(pid: int) -> None:
    """Termina el proceso y sus hijos. En Windows el intérprete puede crear
    procesos intermedios, por lo que se mata el árbol completo."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
        return
    try:
        os.kill(pid, 15)  # SIGTERM
    except OSError:
        return
    for _ in range(20):
        if not pid_alive(pid):
            return
        time.sleep(0.25)
    try:
        os.kill(pid, 9)  # SIGKILL
    except OSError:
        pass


def stop_pid(name: str, port: int) -> bool:
    candidates = {pid for pid in (read_pid(name), listener_pid(port)) if pid is not None}
    for pid in candidates:
        stop_process(pid)

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and listener_pid(port) is not None:
        time.sleep(0.25)
    clear_pid(name)
    return listener_pid(port) is None


def do_start(env_file: Path, build: bool) -> int:
    backend_pid = read_pid("backend")
    portal_pid = read_pid("portal")
    if backend_pid or portal_pid:
        print("El portal ya está iniciado. Use restart o stop antes de volver a iniciar.")
        return 1
    env = child_environment(env_file)
    if build and not build_frontend(env):
        return 1
    if not (DIST_DIR / "index.html").is_file():
        print(f"ERROR: no existe {DIST_DIR / 'index.html'}. Ejecute con --build.")
        return 1

    backend_port = env_int(env, "BACKEND_PORT", 8000)
    portal_port = env_int(env, "PORTAL_PORT", 8080)
    backend_url = f"http://127.0.0.1:{backend_port}"

    occupied = [port for port in (backend_port, portal_port) if listener_pid(port) is not None]
    if occupied:
        print(
            f"ERROR: los puertos {occupied} ya tienen un proceso escuchando. "
            "Ejecute stop antes de iniciar; no se reutilizará un servicio huérfano."
        )
        return 1

    spawn(
        "backend",
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(backend_port)],
        BACKEND_DIR,
        env,
    )
    if not wait_for(f"{backend_url}/health", 60, "FastAPI"):
        do_stop(env_file)
        return 1

    spawn("portal", [sys.executable, str(ROOT / "scripts" / "portal_proxy.py")], ROOT, env)
    if not wait_for(f"http://127.0.0.1:{portal_port}/health", 30, "Proxy inverso"):
        do_stop(env_file)
        return 1

    print(f"Portal listo en http://127.0.0.1:{portal_port}")
    print(f"API detrás del proxy en {backend_url}")
    print(f"Logs en {LOG_DIR}")
    return 0


def do_stop(env_file: Path) -> int:
    env = child_environment(env_file)
    ok_portal = stop_pid("portal", env_int(env, "PORTAL_PORT", 8080))
    ok_backend = stop_pid("backend", env_int(env, "BACKEND_PORT", 8000))
    if ok_portal and ok_backend:
        print("Portal y API detenidos.")
        return 0
    print("Se detuvieron los procesos, pero quedó algún PID pendiente de revisión.")
    return 1


def do_status(env_file: Path) -> int:
    env = child_environment(env_file)
    backend_port = env_int(env, "BACKEND_PORT", 8000)
    portal_port = env_int(env, "PORTAL_PORT", 8080)
    state = {
        "perfil": str(env_file),
        "backend_pid": read_pid("backend") or listener_pid(backend_port),
        "portal_pid": read_pid("portal") or listener_pid(portal_port),
        "backend_health": http_ok(f"http://127.0.0.1:{backend_port}/health"),
        "portal_health": http_ok(f"http://127.0.0.1:{portal_port}/health"),
    }
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0 if state["backend_health"] and state["portal_health"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Control local del portal ERP MINERO.")
    parser.add_argument("command", choices=["start", "stop", "restart", "status"])
    parser.add_argument("--build", action="store_true", help="Compila React antes de iniciar.")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Perfil de entorno; por defecto .env o el valor de ERP_ENV_FILE.",
    )
    args = parser.parse_args()

    env_file = args.env_file or Path(os.getenv("ERP_ENV_FILE", str(DEFAULT_ENV_FILE)))
    env_file = env_file if env_file.is_absolute() else ROOT / env_file

    if args.command == "start":
        return do_start(env_file, args.build)
    if args.command == "stop":
        return do_stop(env_file)
    if args.command == "restart":
        stopped = do_stop(env_file)
        return do_start(env_file, args.build) if stopped == 0 else 1
    return do_status(env_file)


if __name__ == "__main__":
    raise SystemExit(main())
