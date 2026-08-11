# Control de Presupuesto · Back Office Regional (Streamlit + Supabase)

App para que cada Back Office registre su presupuesto mensual y sus gastos
diarios en el o los departamentos que le corresponden. Con login propio y
un administrador que registra a cada Back Office y le asigna sus
departamentos. Los datos se guardan en Supabase (nube), no en un archivo
local, así que persisten aunque la app se "duerma" o se reinicie.

## ¿Qué hace?

- **Login simple** (usuario + contraseña, sin necesidad de correo).
- El **Administrador**:
  - Ve y gestiona todos los departamentos, incluida la vista **"Fanero
    (Total)"** (suma de los 9 departamentos).
  - Desde **👥 Gestionar Back Office** registra cada Back Office: nombre,
    usuario, contraseña, y le asigna **uno o más departamentos** de los que
    es responsable (o lo marca como otro Administrador).
  - Puede activar/desactivar cuentas, cambiar los departamentos asignados o
    restablecer contraseñas en cualquier momento.
- Cada **Back Office**:
  - Solo ve y registra información de **sus propios departamentos**
    asignados (Amazonas, Cajamarca, Huancavelica, Huánuco, Junín, Loreto,
    Pasco, San Martín o Ucayali).
  - Si tiene más de uno asignado, en el Resumen puede ver también
    **"Mis departamentos (Total)"**.
- **Registrar presupuesto mensual**: monto asignado por departamento, año y
  mes (si se vuelve a guardar el mismo mes, actualiza en vez de duplicar).
- **Registrar gasto diario**: Activaciones, Merch o Acciones Comerciales
  (con subtipo Dispersión / Incentivos).
- **Resumen**: presupuesto, gastado, disponible y % de ejecución con
  semáforo (🟢 ≤80% · 🟡 80–100% · 🔴 &gt;100%).
- **Historial de gastos**: tabla filtrable, eliminar registros, descarga en
  CSV.

## 1. Crear las tablas en Supabase (una sola vez)

Puedes usar el **mismo proyecto de Supabase** que ya tienes de tu otra app —
estas tablas son independientes y no chocan con las que ya existen.

1. Ve a tu proyecto en [supabase.com](https://supabase.com) → **SQL Editor**
   → **New query**.
2. Copia todo el contenido de `supabase_setup.sql` (incluido en esta
   carpeta), pégalo y dale **Run**.
3. Debe decir "Success. No rows returned".

> Si ya habías corrido `supabase_setup.sql` antes (versión anterior con
> "AACC" en vez de "Acciones Comerciales"), ejecuta también
> `migracion_acciones_comerciales.sql` una sola vez para actualizar la base
> de datos existente sin perder los gastos ya registrados.

## 2. Configurar las credenciales de conexión

Necesitas el mismo **Project URL** y clave **anon/publishable** que usaste
en Vercel para la otra app (Supabase → Project Settings → API Keys).

### En tu computadora (para probar localmente)

Crea el archivo `.streamlit/secrets.toml` dentro de esta carpeta con:

```toml
SUPABASE_URL = "https://TU-PROYECTO.supabase.co"
SUPABASE_KEY = "tu-clave-anon-publica"
```

Luego:

```bash
pip install -r requirements.txt
streamlit run app.py
```

### En Streamlit Community Cloud (para publicarla en internet)

1. Sube esta carpeta a un repositorio de GitHub (`app.py`,
   `requirements.txt`, `supabase_setup.sql` — **no subas**
   `.streamlit/secrets.toml`, eso se configura directo en Streamlit Cloud).
2. Ve a [share.streamlit.io](https://share.streamlit.io) → inicia sesión con
   GitHub → **"New app"** → elige tu repositorio → **"Deploy"**.
3. En **⚙️ Settings → Secrets** de tu app, pega:
   ```toml
   SUPABASE_URL = "https://TU-PROYECTO.supabase.co"
   SUPABASE_KEY = "tu-clave-anon-publica"
   ```
4. Guarda — la app se reinicia sola.

## 3. Primer uso: crear tu cuenta de Administrador

La primera vez que alguien abre la app (sin ningún usuario creado todavía),
aparece automáticamente una pantalla de **"Configuración inicial"** para
crear la cuenta de Administrador — no necesitas tocar SQL para esto.

Después de crearla:

1. Inicia sesión con ese usuario y contraseña.
2. Ve a **👥 Gestionar Back Office**.
3. Registra cada Back Office: nombre, usuario, contraseña, y elige el o los
   departamentos de los que es responsable.
4. Comparte a cada uno su usuario y contraseña — ya pueden entrar y
   registrar solo en lo suyo.

## ⚠️ Nota de seguridad

El control de acceso (quién ve/edita qué departamento) lo maneja la propia
app con este sistema de login simple — es independiente de Supabase Auth.
Las contraseñas se guardan con hash (nunca en texto plano), pero este es un
sistema pensado para ser **simple y práctico para un equipo interno**, no
tiene el mismo nivel de robustez que un sistema de autenticación
empresarial. Si más adelante necesitas mayor seguridad (recuperación de
contraseña por correo, doble factor, etc.), se puede evolucionar.

## ¿Por qué los datos no se pierden?

Todo (presupuestos, gastos, usuarios y departamentos asignados) vive en
Supabase, un servicio de base de datos independiente de Streamlit. Aunque la
app se reinicie, se "duerma" por inactividad, o se vuelva a desplegar, los
datos siguen intactos.
