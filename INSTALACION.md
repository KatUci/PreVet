# Manual de instalación de PreVet

Este manual explica cómo dejar PreVet funcionando en un computador con Windows o macOS.
Hay tres formas; la más simple es la **A**, con Docker, porque no hay que instalar Python
ni configurar nada a mano.

| Opción | Para qué sirve | Base de datos |
|---|---|---|
| **A. Docker** (recomendada) | Probar o presentar el sistema en cualquier equipo | PostgreSQL local, dentro de Docker |
| **B. Sin Docker** | Programar y correr las pruebas | SQLite local (un archivo) |
| **C. Con Supabase** | Trabajar sobre la base compartida del equipo | PostgreSQL en Supabase |

Los datos que trae el sistema son **datos de prueba**: 10 clientes, 15 mascotas y 255 citas de
ejemplo que crea el comando `cargar_demo`.

---

## Antes de empezar: descargar el proyecto

Con Git instalado, en una terminal (PowerShell en Windows, Terminal en macOS):

```bash
git clone https://github.com/KatUci/PreVet.git
cd PreVet/sistema
```

> **Windows:** clona en una carpeta de ruta corta, por ejemplo `C:\PreVet`. Si la ruta es
> muy larga, Windows no puede cargar algunos archivos de la librería de PostgreSQL.

---

## Opción A: con Docker (recomendada)

### 1. Instalar Docker Desktop

- **Windows:** descarga Docker Desktop desde <https://www.docker.com/products/docker-desktop/>,
  instálalo con las opciones por defecto (usa WSL 2) y reinicia si lo pide.
- **macOS:** descarga la versión para tu procesador (Apple Silicon o Intel) desde la misma
  página y arrástrala a Aplicaciones.

Abre Docker Desktop y espera a que diga **"Engine running"** (la ballena queda quieta).

### 2. Levantar PreVet

Dentro de la carpeta `sistema`:

```bash
docker compose up --build
```

La primera vez tarda unos minutos porque descarga Python y PostgreSQL. Está listo cuando aparece
`Starting development server at http://0.0.0.0:8000/`.

### 3. Cargar los datos de prueba y crear tu usuario

En **otra** terminal, también dentro de `sistema`:

```bash
docker compose run --rm web python manage.py cargar_demo
docker compose run --rm web python manage.py createsuperuser
```

El segundo comando pide un nombre de usuario, un correo (puede quedar vacío) y una contraseña.

### 4. Entrar

Abre <http://localhost:8000> en el navegador y entra con el usuario que creaste.

### Detener y volver a empezar

```bash
docker compose down          # detiene PreVet; los datos se conservan
docker compose up            # lo vuelve a levantar
docker compose down -v       # detiene y BORRA la base local, para partir de cero
```

---

## Opción B: sin Docker

Necesitas **Python 3.12**.

```bash
cd sistema
python -m venv .venv
```

Activa el entorno:

- **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
  (si da error de permisos, primero `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`)
- **macOS:** `source .venv/bin/activate`

Y luego:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py cargar_demo
python manage.py createsuperuser
python manage.py runserver
```

Abre <http://127.0.0.1:8000>. Sin archivo `.env`, el sistema guarda todo en `db.sqlite3`.

Para correr las pruebas automatizadas: `python manage.py test`.

---

## Opción C: con la base compartida de Supabase

1. En la carpeta `sistema`, copia `.env.example` con el nombre `.env`.
2. Escribe la contraseña de Supabase después de `DB_PASSWORD=` (sin espacios ni comillas).
   El `.env` **nunca** se sube a GitHub: ya está en el `.gitignore`.
3. Levanta el sistema:
   - **Sin Docker:** `python manage.py runserver` (con el entorno activado).
   - **Con Docker:**

     ```bash
     docker build -t prevet .
     docker run --rm --env-file .env -p 8000:8000 prevet
     ```

> ⚠️ **No corras `cargar_demo` contra Supabase:** borra todas las citas de la base compartida
> del equipo. Úsalo solo con las opciones A y B.

Si hay migraciones nuevas, el contenedor las aplica solo al arrancar; sin Docker, corre
`python manage.py migrate`.

---

## Problemas frecuentes

| Mensaje | Qué hacer |
|---|---|
| `Cannot connect to the Docker daemon` o `error during connect` | Docker Desktop no está abierto. Ábrelo y espera a "Engine running". |
| `port is already allocated` / `Ya existe un socket en uso` | Otro programa usa el puerto 8000 (por ejemplo, otro `runserver`). Ciérralo o cambia `"8000:8000"` por `"8001:8000"` en `docker-compose.yml` y entra a <http://localhost:8001>. |
| `no pq wrapper available` o `nombre del archivo o la extensión es demasiado largo` | La carpeta del proyecto está en una ruta muy larga (Windows). Muévela a una corta, como `C:\PreVet`. |
| `password authentication failed` | La contraseña de Supabase del `.env` no es la vigente. Pídela al equipo. |
| `Prohibido (403) · La verificación CSRF ha fallado` al iniciar sesión | La página de login quedó abierta de antes. Recárgala (F5) o ábrela en una ventana de incógnito. |
