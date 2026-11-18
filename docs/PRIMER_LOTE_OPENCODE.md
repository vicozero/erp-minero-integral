# Primer lote de desarrollo para OpenCode

**Lote:** 1 — Cimientos técnicos  
**Estado:** Listo para ejecutar  
**Alcance:** Base técnica verificable. **No** implementa ERP completo.  
**Ubicación:** `E:\ERP_MINERO` (ruta real detectada; `C:\ERP_MINERO` no existe).

---

## 1. Objetivo del lote

Dejar un proyecto mínimo, ejecutable y probado que sirva de cimiento para los dominios de requisiciones, inventario, compras, equipos y costos.

Al terminar este lote debe existir:

- backend FastAPI con configuración, salud, autenticación local mínima, RBAC y bitácora;
- esquema PostgreSQL inicial con convenciones y numeración documental;
- frontend React/TypeScript con pantalla de estado y login básico;
- pruebas automáticas que demuestren lo anterior;
- cero secretos, cero datos reales, cero exposición de red.

**No incluir:** requisiciones funcionales, movimientos de inventario, compras, costos, integraciones con CONTPAQi/GMAO ni despliegue.

---

## 2. Condiciones previas

Antes de iniciar, OpenCode debe verificar:

1. Estar en `E:\ERP_MINERO`.
2. No sobrescribir `AGENTS.md` ni `docs/*.md`.
3. Existencia de `DATABASE_URL` local provista por el entorno.
4. PostgreSQL accesible solo en `127.0.0.1`.
5. Git disponible. Si no hay repositorio, inicializarlo sin borrar nada.

Si no hay PostgreSQL local, **no instalar servidor, no crear usuario, no abrir puerto**. Preparar código y migración, reportar bloqueo para ejecutar `alembic upgrade head`.

---

## 3. Tareas del lote

### Tarea 1.1 — Estructura y control de versiones

**Prompt para OpenCode:**

> Crea la estructura inicial del repositorio en `E:\ERP_MINERO` sin modificar los documentos existentes. Genera `README.md`, `.gitignore`, `.env.example`, `backend/pyproject.toml`, `frontend/package.json`, `frontend/vite.config.ts` y `frontend/tsconfig.json`. Inicializa Git solo si aún no existe repositorio. El `.gitignore` debe excluir `.env`, `.venv`, `node_modules`, `dist`, `*.pyc`, `.pytest_cache`, cobertura, dumps `.sql` y archivos de exportación. `.env.example` debe contener solo nombres de variables con valores vacíos o ejemplos claramente ficticios, nunca credenciales reales. El README debe explicar que el servicio corre solo en `127.0.0.1` y que CONTPAQi/GMAO no se modifican.

**Verificación:**

- `git status` muestra archivos nuevos, ninguno borrado.
- `Get-Content .env.example` no contiene contraseñas.
- `README.md` menciona `127.0.0.1`.

---

### Tarea 1.2 — Configuración central del backend

**Prompt:**

> Implementa `backend/app/core/config.py` con Pydantic Settings. Variables requeridas: `DATABASE_URL`, `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`. Variables opcionales: `APP_NAME`, `API_V1_PREFIX` con valor `/api/v1`, `TIMEZONE` con valor `America/Mexico_City`, `ENV` con valor `local`. Se debe fallar con mensaje claro si falta una variable requerida. No incluir valores reales en código. Agrega pruebas unitarias que validen valores por defecto y error ante variable faltante.

**Verificación:**

```powershell
cd backend
pytest -q tests/unit/test_config.py
```

---

### Tarea 1.3 — Base declarativa y naming convention

**Prompt:**

> Implementa `backend/app/db/base.py` con `DeclarativeBase` de SQLAlchemy 2 y un `metadata` con `naming_convention` para `pk`, `fk`, `ix`, `uq` y `ck`. Implementa `backend/app/db/session.py` con `engine`, `SessionLocal` y dependencia `get_db` que cierre la sesión. Usa `pool_pre_ping=True`. No crees tablas con `create_all`; Alembic es la única fuente de esquema. Agrega una prueba que verifique los nombres generados para una tabla temporal en metadata.

**Verificación:**

```powershell
pytest -q tests/unit/test_db_conventions.py
```

---

### Tarea 1.4 — Alembic inicial

**Prompt:**

> Configura Alembic en `backend/migrations` con `env.py` apuntando a la metadata declarativa. Crea una migración inicial `0001_initial_schema` que: (1) habilite extensión `pgcrypto` si no existe, (2) cree los esquemas `seg`, `org`, `mdm`, `doc`, `req`, `wfl`, `inv`, `pur`, `mnt`, `cost`, `intg`, `aud`, (3) cree las tablas transversales `seg.app_user`, `seg.role`, `seg.permission`, `seg.user_role`, `seg.role_permission`, `seg.login_audit`, `doc.document_type`, `doc.document_numbering`, `doc.document_registry`, `doc.document_event`, `aud.audit_log`, `intg.outbox_event`, `intg.inbox_event`. Usa UUID, `TIMESTAMPTZ`, `NUMERIC` donde aplique y claves foráneas con `ondelete='RESTRICT'`. La migración debe ser aditiva y no contener `DROP` ni `TRUNCATE`. El `downgrade` debe documentar que no se usa sobre datos reales y solo revertir lo creado en entorno vacío. Agrega una prueba de integración que ejecute `alembic upgrade head` sobre una base local provista por `DATABASE_URL` y consulte los 12 esquemas.

**Verificación:**

```powershell
alembic upgrade head
pytest -q tests/integration/test_migrations.py
```

Si no hay base local, reportar bloqueo; no crear infraestructura.

---

### Tarea 1.5 — Salud y contrato API

**Prompt:**

> Implementa `backend/app/main.py` con FastAPI, prefijo `/api/v1`, título `ERP MINERO INTEGRAL` y routers de salud. Expón `GET /health` sin autenticación que responda `{"status":"ok","env":"local"}` y `GET /api/v1/status` que responda versión y zona horaria desde configuración. Incluye Manejo de excepciones consistente con errores `{"detail": ...}` y no expongas stack traces. Agrega pruebas HTTP con `TestClient`.

**Verificación:**

```powershell
pytest -q tests/integration/test_health.py
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---

### Tarea 1.6 — Identidad mínima y login local

**Prompt:**

> Implementa el módulo `identity` con modelos/esquemas ya migrados en 1.4, repositorio y servicio. Registra roles sintéticos `ADMIN`, `SOLICITANTE`, `ALMACENISTA`, `APROBADOR`, `COMPRADOR` y permisos sintéticos de ejemplo (`requisition.create`, `inventory.issue`, `purchase.order.approve`, `audit.view`, `admin.users.manage`) mediante semilla idempotente. Implementa hash de contraseña con Argon2id (o bcrypt si Argon2 no está disponible) y endpoint `POST /api/v1/auth/login` que devuelva token JWT firmado con `SECRET_KEY`. Nunca devolver `password_hash`. Crear usuario demo `admin.demo` con contraseña definida solo en variable de entorno local `DEMO_ADMIN_PASSWORD`; si no existe, la semilla se omite y lo reporta. Agrega pruebas de login correcto, login incorrecto y ausencia de hash en respuesta.

**Verificación:**

```powershell
pytest -q tests/integration/test_auth.py
```

---

### Tarea 1.7 — RBAC y bitácora

**Prompt:**

> Implementa dependencia `require_permission(code)` que valide permisos del usuario autenticado considerando `valid_from`/`valid_to` y alcance opcional. Implementa middleware que agregue `request_id` a cada petición y lo devuelva en header `X-Request-ID`. Implementa `AuditService.record(...)` que inserte en `aud.audit_log` dentro de la misma transacción del caso de uso. Registra login fallido, login exitoso y cambio de rol como eventos sensibles. La bitácora debe incluir `actor_id`, `action`, `entity_type`, `entity_id`, `before`, `after`, `request_id`, `correlation_id`, `ip_hash` y `occurred_at`. Nunca guardar contraseñas ni tokens. Agrega prueba de que usuario sin permiso recibe 403 y que se escribe auditoría.

**Verificación:**

```powershell
pytest -q tests/integration/test_rbac_audit.py
```

---

### Tarea 1.8 — Numeración documental

**Prompt:**

> Implementa `shared/numbering.py` con servicio `next_document_number(document_type_code, company_code=None, mining_unit_code=None, series='')`. Debe bloquear la fila de `doc.document_numbering` con `SELECT ... FOR UPDATE`, incrementar `next_number`, insertar en `doc.document_registry` con `full_number` legible y retornar UUID de registro más número. El número debe ser único aunque dos transacciones concurrentes lo soliciten. Crea tipos iniciales `REQ`, `AUTH`, `OC`, `GRN`, `INV_MOV`, `WO`, `ADJ`, `COST_POST` de forma idempotente. Agrega prueba concurrente con dos sesiones y verifica unicidad. Agrega evento `DOCUMENT_NUMBER_ISSUED` en `doc.document_event`.

**Verificación:**

```powershell
pytest -q tests/integration/test_numbering.py
```

---

### Tarea 1.9 — Frontend mínimo

**Prompt:**

> Crea el esqueleto React + TypeScript + Vite. Debe incluir layout con encabezado, menú lateral y página `Estado del sistema` que consuma `GET /health` mediante cliente API tipado en `src/lib/api.ts`. Agrega formulario de login que llame a `POST /api/v1/auth/login`, guarde el token solo en memoria y muestre mensaje de error claro. No uses `localStorage` para credenciales. Configura Vite para escuchar solo en localhost; no establezcas `host: '0.0.0.0'`. Agrega prueba de render con Vitest + Testing Library.

**Verificación:**

```powershell
cd frontend
npm run build
npm run test -- --run
npm run dev
```

---

### Tarea 1.10 — Cierre y documentación local

**Prompt:**

> Actualiza `README.md` con comandos exactos de instalación, migración, pruebas y arranque local usando siempre `127.0.0.1`. Agrega sección `Restricciones` que indique: no CONTPAQi directo, no GMAO, no datos reales, no puertos externos, no credenciales en repo. No modifiques `AGENTS.md` ni los documentos de `docs/`. Genera un reporte final indicando pruebas ejecutadas, archivos creados, migraciones aplicadas y pendientes.

**Verificación:**

- README contiene `127.0.0.1`.
- No hay fuerza de push ni borrados.
- Reporte sigue la plantilla de la sección 5.

---

## 4. Árbol esperado al terminar

```text
ERP_MINERO/
├── AGENTS.md                         # no modificado
├── README.md
├── .gitignore
├── .env.example
├── docs/                             # no modificado en este lote
│   ├── ARQUITECTURA.md
│   ├── MODELO_DATOS.md
│   ├── PLAN_IMPLEMENTACION.md
│   └── PRIMER_LOTE_OPENCODE.md
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/0001_initial_schema.py
│   ├── app/
│   │   ├── main.py
│   │   ├── core/config.py
│   │   ├── db/base.py
│   │   ├── db/session.py
│   │   ├── api/v1/routers/health.py
│   │   ├── api/v1/routers/auth.py
│   │   ├── modules/identity/
│   │   ├── modules/audit/
│   │   └── shared/numbering.py
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── factories/
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    └── src/
        ├── app/
        ├── features/auth/
        ├── components/ui/
        ├── lib/api.ts
        └── types/
```

---

## 5. Plantilla de reporte de cierre

```text
Lote: 1 — Cimientos técnicos
Estado: terminado / parcial / bloqueado
Cambios:
- ...

Pruebas ejecutadas:
- pytest -q: NN passed
- alembic upgrade head: OK / BLOQUEADO (sin DATABASE_URL local)
- npm run build: OK
- npm run test -- --run: NN passed

Migraciones:
- 0001_initial_schema (aditiva)

Seguridad:
- Sin secretos en diffs
- Sin datos reales
- Servidor ejecutado solo en 127.0.0.1

Riesgos detectados:
- ...

Pendiente para Lote 2:
- ...
```

---

## 6. Criterios de rechazo del lote

Rechazar el lote si ocurre cualquiera de lo siguiente:

- Se modificó CONTPAQi, GMAO o archivos de otros sistemas.
- Se usó una cadena de conexión real o una credencial en el repositorio.
- Se abrieron puertos o se usó `0.0.0.0`.
- Se ejecutó `DROP`, `TRUNCATE` o borrado masivo.
- Se afirmó “terminado” sin pruebas ejecutadas.
- Se implementaron flujos de inventario/compras fuera de este alcance.
- Se cambiaron documentos de diseño sin aprobación.

---

## 7. Siguiente lote

Una vez aprobado este lote, continuar con **Lote 2 — Organización y datos maestros** del `PLAN_IMPLEMENTACION.md`.
