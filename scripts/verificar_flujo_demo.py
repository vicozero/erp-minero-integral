"""Verificación en vivo del circuito requisición -> autorización parcial -> historial.

Usa exclusivamente PostgreSQL local de desarrollo, cuentas sintéticas y la
contraseña ficticia definida en .env (nunca se imprime). No modifica
CONTPAQi, GMAO ni datos reales de producción.
"""

from __future__ import annotations

import argparse
import json
import os
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ROOT / ".env"


def load_env_file(path: Path) -> dict[str, str]:
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


class Session:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.jar = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.jar))

    def request(self, method: str, path: str, payload: dict | None = None) -> tuple[int, bytes]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers: dict[str, str] = {}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if method not in {"GET", "HEAD", "OPTIONS"}:
            csrf = next((c.value for c in self.jar if c.name == "erp_csrf"), None)
            if csrf:
                headers["X-CSRF-Token"] = csrf
        req = Request(f"{self.base_url}{path}", data=data, method=method, headers=headers)
        try:
            with self.opener.open(req, timeout=20) as response:
                return response.status, response.read()
        except HTTPError as exc:
            return exc.code, exc.read()

    def login(self, username: str, password: str) -> bool:
        status, _ = self.request(
            "POST",
            "/api/v1/auth/login",
            {"username": username, "password": password},
        )
        return status == 200

    def json(self, method: str, path: str, payload: dict | None = None) -> tuple[int, object]:
        status, body = self.request(method, path, payload)
        try:
            return status, json.loads(body) if body else None
        except json.JSONDecodeError:
            return status, None


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica el circuito demo de requisiciones y autorizaciones.")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--env-file", type=Path, default=None)
    args = parser.parse_args()

    env_file = args.env_file or Path(os.getenv("ERP_ENV_FILE", str(DEFAULT_ENV_FILE)))
    env_file = env_file if env_file.is_absolute() else ROOT / env_file
    env = os.environ.copy()
    for key, value in load_env_file(env_file).items():
        env.setdefault(key, value)

    password = env.get("DEMO_PASSWORD")
    if not password:
        print("ERROR: DEMO_PASSWORD no está disponible en el perfil activo.")
        return 1
    port = env.get("PORTAL_PORT", "8080")
    base_url = (args.base_url or f"http://127.0.0.1:{port}").rstrip("/")

    checks: list[tuple[str, bool, str]] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        checks.append((label, bool(condition), detail))

    solicitante = Session(base_url)
    aprobador = Session(base_url)
    admin = Session(base_url)

    check("Login solicitante demo", solicitante.login("demo.solicitante", password))
    check("Login aprobador demo", aprobador.login("demo.aprobador", password))
    check("Login administrador demo", admin.login("demo.admin", password))

    status, catalogs = solicitante.json("GET", "/api/v1/catalogs")
    if status != 200 or not isinstance(catalogs, dict):
        check("Catálogos para la captura", False, f"HTTP {status}")
        _print(checks)
        return 1

    department = catalogs["departments"][0]["id"]
    warehouse = catalogs["warehouses"][0]["id"]
    cost_center = catalogs["cost_centers"][0]["id"]
    uom = catalogs["uoms"][0]["id"]
    item = catalogs["items"][0]["id"]
    check("Catálogos para la captura", True, f"{len(catalogs['items'])} artículos disponibles")

    payload = {
        "department_id": department,
        "warehouse_id": warehouse,
        "equipment_id": None,
        "cost_center_id": cost_center,
        "requisition_type": "STOCK",
        "priority": "NORMAL",
        "justification": "Verificación automatizada del circuito demo",
        "observations": "Datos sintéticos aislados",
        "needed_at": None,
        "work_order_no": None,
        "lines": [
            {
                "item_id": item,
                "description": "Partida A - verificación demo",
                "uom_id": uom,
                "requested_qty": "10",
                "notes": None,
            },
            {
                "item_id": item,
                "description": "Partida B - verificación demo",
                "uom_id": uom,
                "requested_qty": "6",
                "notes": None,
            },
        ],
    }
    status, created = solicitante.json("POST", "/api/v1/requisitions", payload)
    ok_create = status == 201 and isinstance(created, dict) and bool(created.get("id"))
    check("Creación de requisición de prueba", ok_create, f"HTTP {status}")
    if not ok_create:
        _print(checks)
        return 1

    requisition_id = created["id"]
    document_no = created["document_no"]
    status, submitted = solicitante.json("POST", f"/api/v1/requisitions/{requisition_id}/submit")
    check("Envío a autorización", status == 200 and submitted.get("status") == "SUBMITTED", f"HTTP {status}")

    lines = submitted.get("lines", []) if isinstance(submitted, dict) else []
    decisions = [
        {
            "requisition_line_id": lines[0]["id"],
            "decision": "APPROVE",
            "approved_qty": "4",
        },
        {
            "requisition_line_id": lines[1]["id"],
            "decision": "APPROVE",
            "approved_qty": "6",
        },
    ] if len(lines) >= 2 else []
    check("Dos partidas disponibles para decisión", len(decisions) == 2, f"{len(lines)} partida(s)")

    if decisions:
        status, decided = aprobador.json(
            "POST",
            f"/api/v1/requisitions/{requisition_id}/decide",
            {"decisions": decisions, "reason": "Autorización parcial de verificación"},
        )
        check(
            "Autorización parcial por partida",
            status == 200 and decided.get("status") == "PARTIALLY_APPROVED",
            f"HTTP {status} · {decided.get('status') if isinstance(decided, dict) else ''}",
        )
        line_statuses = [line.get("status") for line in decided.get("lines", [])] if isinstance(decided, dict) else []
        check("Estados de partida derivados", "PARTIAL" in line_statuses and "AUTHORISED" in line_statuses,
              ", ".join(str(value) for value in line_statuses))

    status, tracked = admin.json("GET", f"/api/v1/requisitions/{requisition_id}")
    tracked_lines = tracked.get("lines", []) if isinstance(tracked, dict) else []
    pending = [line for line in tracked_lines if float(line.get("pending_qty", "0")) > 0]
    check("Seguimiento por partida", status == 200 and len(pending) >= 1, f"{len(pending)} partida(s) pendiente(s)")

    status, events = admin.json("GET", f"/api/v1/requisitions/{requisition_id}/history")
    event_types = [event.get("event_type") for event in events] if isinstance(events, list) else []
    check("Historial del documento", status == 200 and len(event_types) >= 2, ", ".join(str(value) for value in event_types))

    print(f"Documento sintético verificado: {document_no}")
    _print(checks)
    return 1 if any(not ok for _, ok, _ in checks) else 0


def _print(checks: list[tuple[str, bool, str]]) -> None:
    for label, ok, detail in checks:
        print(f"[{'OK' if ok else 'ERROR'}] {label}" + (f" — {detail}" if detail else ""))
    passed = sum(1 for _, ok, _ in checks if ok)
    print(f"\nResultado: {passed}/{len(checks)} verificaciones del circuito correctas.")


if __name__ == "__main__":
    raise SystemExit(main())
