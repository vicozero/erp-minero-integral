# Manual de acceso y administración de usuarios — Fase 3

**Fecha:** 2026-11-18
**Audiencia:** administradores del ERP y personal de seguridad.
**Alcance:** acceso web local, gestión de cuentas, roles, departamentos, contraseñas, sesiones y bitácora.

> **Aviso:** este entorno es local (`127.0.0.1`) y usa **datos sintéticos**. La contraseña de las cuentas demo se define en la variable `DEMO_PASSWORD` del archivo `.env`, que no se versiona. CONTPAQi sigue siendo el inventario oficial; el ERP mantiene un espejo operativo.

---

## 1. Puesta en marcha

### 1.1 Backend

```powershell
cd E:\ERP_MINERO
.\scripts\iniciar_backend.cmd
```

El servicio escucha solo en `http://127.0.0.1:8000`. Verificación rápida:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/health/db
```

Si la base está vacía, aplicar migraciones y sembrar datos sintéticos:

```powershell
cd E:\ERP_MINERO\backend
python -m alembic upgrade head
cd E:\ERP_MINERO
.\scripts\sembrar_datos_demo.cmd
```

### 1.2 Frontend

```powershell
cd E:\ERP_MINERO\frontend
npm.cmd run dev
```

Abrir `http://127.0.0.1:5173`. En este entorno PowerShell bloquea `npm.ps1`; usar siempre `npm.cmd`.

### 1.3 Variables de sesión (`.env`)

| Variable | Valor local | Uso |
|---|---|---|
| `SESSION_COOKIE_SECURE` | `false` | Poner `true` **solo** cuando el portal se sirva por HTTPS |
| `SESSION_COOKIE_SAMESITE` | `lax` | `lax`, `strict` o `none` (`none` exige `Secure=true`) |
| `SESSION_COOKIE_DOMAIN` | vacío | Dominio de la cookie; vacío = host exacto |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Vigencia de sesión y JWT |
| `DEMO_PASSWORD` | (valor ficticio) | Contraseña inicial de las cuentas demo |

No modificar `DATABASE_URL` para apuntar a CONTPAQi ni a servicios externos: el validador solo acepta `127.0.0.1`/`localhost` con driver `postgresql+psycopg`.

---

## 2. Iniciar sesión

1. En `http://127.0.0.1:5173`, escribir el usuario y la contraseña.
2. El campo usuario sugiere las cuentas ficticias disponibles; la contraseña es la misma `DEMO_PASSWORD` para todas salvo `demo.temporal` tras el restablecimiento.
3. Pulse **Ingresar**. El backend:
   - verifica la contraseña con **Argon2id**;
   - crea una sesión opaca y guarda solo su hash SHA-256;
   - envía la cookie `erp_session` (HttpOnly) y la cookie legible `erp_csrf`;
   - devuelve el perfil con roles, permisos y departamentos.
4. El frontend guarda el token CSRF **solo en memoria** y descubre la sesión con `GET /api/v1/auth/me`. No hay token en `localStorage`.

### Cuentas de demostración

| Usuario | Rol | Alcance | Uso principal |
|---|---|---|---|
| `demo.admin` | Administrador | Global | Alta de usuarios, roles, auditoría |
| `demo.solicitante` | Solicitante | DEMO-MINA, DEMO-MANT | Crear requisiciones |
| `demo.jefe` | Jefe de departamento | DEMO-MINA, DEMO-MANT | Autorizar requisiciones |
| `demo.aprobador` | Aprobador (compatible) | DEMO-MINA, DEMO-MANT | Autorizar (alias) |
| `demo.almacenista` | Almacén | DEMO-MINA, DEMO-MANT | Reservar y surtir |
| `demo.comprador` | Compras | DEMO-MINA, DEMO-MANT | Crear y autorizar OC |
| `demo.gerencia` | Gerencia | Mina, Mantenimiento y DEMO-OTRA | Solo lectura + auditoría + sesiones |
| `demo.auditor` | Auditor | Mina, Mantenimiento y DEMO-OTRA | Solo lectura + auditoría + usuarios |
| `demo.temporal` | Solicitante | DEMO-MINA, DEMO-MANT | Contraseña temporal obligatoria |

### Errores frecuentes de acceso

| Situación | Respuesta | Acción |
|---|---|---|
| Contraseña incorrecta | `401 Credenciales inválidas.` | Revisar `DEMO_PASSWORD`; 5 fallos bloquean 15 minutos |
| Cuenta inactiva | `401 La cuenta está inactiva.` | Un administrador debe reactivarla desde **Usuarios** |
| Contraseña temporal | `403 ... contraseña temporal` | Ir a **Cambiar contraseña** antes de operar |
| Sin sesión | `401` | Iniciar sesión de nuevo; la sesión caduca en 60 min |
| Falta CSRF | `403 ... CSRF` | Recargar la página para renovar la cookie `erp_csrf` |

---

## 3. Cambiar la contraseña

1. En la barra superior, pulse **Cambiar contraseña**.
2. Escriba la contraseña actual, la nueva y su confirmación.
3. Política: mínimo 12 caracteres, mayúscula, minúscula, número y carácter especial.
4. Al guardar se revocan las sesiones anteriores y se emite una nueva; el sistema avisa en pantalla.
5. Si la cuenta tenía contraseña temporal, el aviso desaparece y puede operar normalmente.

También disponible vía API:

```http
POST /api/v1/auth/change-password
Content-Type: application/json
X-CSRF-Token: <valor de erp_csrf>

{ "current_password": "...", "new_password": "..." }
```

---

## 4. Panel de administración de usuarios

Ruta: **Usuarios** en el menú lateral (`/usuarios`). Requiere `usuarios.administrar`; el menú se oculta a quienes no lo tienen y el backend devuelve `403` aunque intenten la ruta directamente.

### 4.1 Alta de usuarios

1. Pulse **Nuevo usuario** (el formulario ya está abajo).
2. Complete usuario, correo y nombre completo.
3. Deje **Contraseña** vacío para que el servidor genere una contraseña temporal segura; o escriba una contraseña que cumpla la política.
4. Marque los **roles** y los **departamentos** asignados.
5. Pulse **Crear usuario**.
6. Si se generó contraseña temporal, aparece un aviso amarillo con el valor **una sola vez**: cópiela y entréguela por canal seguro. No se guarda en la bitácora ni se vuelve a mostrar.

Equivalente API:

```http
POST /api/v1/admin/users
{
  "username": "usuario.nuevo",
  "email": "usuario.nuevo@example.invalid",
  "full_name": "Usuario Nuevo",
  "roles": ["SOLICITANTE"],
  "department_ids": ["<uuid>"]
}
```

Respuesta `201` con el campo `temporary_password` (cuando no se envió contraseña).

### 4.2 Edición y baja lógica

- **Editar** cambia correo, nombre y departamentos. El nombre de usuario no se modifica.
- **Inactivar/Activar** cambia el estado entre `ACTIVE` e `INACTIVE`.
- **Dar de baja** realiza baja lógica: marca `INACTIVE` y registra `deactivated_at/by`. **Nunca elimina** el registro, para conservar trazabilidad.
- La cuenta propia no puede inactivarse ni darse de baja desde el panel.

### 4.3 Roles

- Los chips azules son roles ya asignados; al pulsarlos se quita el rol.
- Los chips grises con `+` son roles disponibles; al pulsarlos se asignan.
- Un usuario puede tener **varios roles**: acumula los permisos de todos.
- **Un administrador no puede asignarse el rol ADMIN a sí mismo** ni escalar privilegios; el backend devuelve `403`.
- No se puede quitar el último rol ADMIN del sistema.

### 4.4 Departamentos

Las casillas de departamentos definen el alcance del usuario. Un solicitante solo ve sus requisiciones y las de sus departamentos; un aprobador limita su autorización al mismo conjunto. ADMIN tiene alcance global sin necesidad de filas.

### 4.5 Restablecimiento de contraseña

1. En la fila del usuario, pulse **Restablecer**.
2. El servidor genera una contraseña temporal, marca `must_change_password=true`, revoca las sesiones activas del usuario y auditoriza `PASSWORD_RESET` **sin guardar la contraseña**.
3. El panel muestra la contraseña temporal una sola vez.
4. El usuario debe iniciar sesión con ella y cambiarla en el primer acceso.

### 4.6 Sesiones

- **Cambiar contraseña** revoca todas las sesiones anteriores.
- Cada usuario puede ver y revocar sus propias sesiones en `GET/POST /api/v1/auth/sessions...`.
- Un administrador puede consultar las sesiones activas con `GET /api/v1/admin/sessions` (`sesiones.consultar`; GERENCIA también lo tiene).

---

## 5. Auditoría

Ruta: **Auditoría** (`/auditoria`). Requiere `auditoria.consultar`.

- La tabla muestra fecha, actor, acción, entidad, detalle e identificador de solicitud.
- El filtro por acción acepta valores como `USER_CREATED`, `PASSWORD_RESET`, `LOGIN_FAILED`, `LOGOUT`, `SESSION_REVOKED`.
- **Solo lectura:** no hay endpoints para editar o borrar registros. La base de datos tiene el trigger `trg_audit_log_immutable`, que bloquea `UPDATE` y `DELETE` en `aud.audit_log` incluso para administradores.
- GERENCIA y AUDITOR ven la bitácora; los permisos de moderación no existen en la aplicación.

---

## 6. Consideraciones de seguridad

1. La sesión viaja en cookie **HttpOnly**; el JavaScript del portal no puede leerla. El CSRF viaja en cookie legible y en cabecera `X-CSRF-Token`, y el backend exige que coincidan en escrituras.
2. Con `Bearer` (integraciones heredadas) no se exige CSRF; la cookie no se usa en ese caso.
3. Solo IPv4 local: no exponer el puerto 8000 ni 5173 a la red, no usar `0.0.0.0`, no publicar en Docker.
4. Para intranet con TLS: definir `SESSION_COOKIE_SECURE=true` y, si aplica, `SESSION_COOKIE_SAMESITE=strict`. Con `SameSite=none`, `Secure` es obligatorio.
5. Nunca compartir `SECRET_KEY`, `DEMO_PASSWORD` ni cadenas de conexión; `.env` está excluido de Git.
6. Los hashes Argon2id y los hashes de sesión no aparecen en respuestas ni en bitácora.

---

## 7. Verificación posterior a un cambio

```powershell
cd E:\ERP_MINERO\backend
pytest -q
ruff check .
mypy app

cd E:\ERP_MINERO\frontend
npm.cmd run build
npm.cmd run test -- --run
```

Resultado esperado: 42 pruebas backend, 7 frontend, sin hallazgos de lint/type-check.
