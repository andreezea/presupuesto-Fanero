"""
Control de Presupuesto - Back Office Regional
------------------------------------------------
App en Streamlit para que cada Back Office registre su presupuesto mensual y
sus gastos diarios (Activaciones, Merch, Acciones Comerciales) en el/los departamento(s) que
le corresponden, con un resumen consolidado (incluyendo "Fanero" = todos los
departamentos juntos, visible solo para el administrador).

Login: sistema simple propio (usuario + contraseña), independiente de la
otra app. El administrador registra cada Back Office y le asigna uno o más
departamentos de los que es responsable.

Persistencia: Supabase (PostgreSQL en la nube) — los datos NO se pierden
aunque la app se "duerma" o se reinicie.

Configuración requerida (ver README.md):
  .streamlit/secrets.toml (local) o "Secrets" en Streamlit Cloud, con:
    SUPABASE_URL = "https://TU-PROYECTO.supabase.co"
    SUPABASE_KEY = "tu-clave-anon-publica"
"""

import hashlib
import secrets as pysecrets
from datetime import date, datetime
from textwrap import dedent

import pandas as pd
import streamlit as st
from supabase import create_client, Client

# ============================================================================
# CONFIGURACIÓN GENERAL
# ============================================================================

st.set_page_config(
    page_title="Control de Presupuesto · Back Office",
    page_icon="📊",
    layout="wide",
)

DEPARTAMENTOS = [
    "Amazonas", "Cajamarca", "Huancavelica", "Huanuco", "Junin",
    "Loreto", "Pasco", "San Martín", "Ucayali",
]
FANERO = "Fanero"

TIPOS_GASTO = ["Activaciones", "Merch", "Acciones Comerciales"]
SUBTIPOS_ACCIONES_COMERCIALES = ["Dispersión", "Incentivos"]

MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

# ============================================================================
# CONEXIÓN A SUPABASE
# ============================================================================

@st.cache_resource
def get_client() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except (KeyError, FileNotFoundError):
        st.error(
            "⚠️ Falta configurar la conexión a Supabase.\n\n"
            "Crea el archivo `.streamlit/secrets.toml` (en local) o configura "
            "los 'Secrets' en Streamlit Cloud con las claves `SUPABASE_URL` "
            "y `SUPABASE_KEY`. Revisa el README.md para el detalle."
        )
        st.stop()
    return create_client(url, key)


supabase = get_client()

# ============================================================================
# CONTRASEÑAS (hash con salt — sin dependencias externas)
# ============================================================================

def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    if salt is None:
        salt = pysecrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return h, salt


def verificar_password(password: str, password_hash: str, salt: str) -> bool:
    h, _ = hash_password(password, salt)
    return pysecrets.compare_digest(h, password_hash)


# ============================================================================
# FUNCIONES DE DATOS: USUARIOS
# ============================================================================

def contar_usuarios() -> int:
    res = supabase.table("usuarios_regional").select("id", count="exact").execute()
    return res.count or 0


def obtener_usuario_por_login(usuario: str) -> dict | None:
    res = (
        supabase.table("usuarios_regional")
        .select("*")
        .eq("usuario", usuario)
        .eq("activo", True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def obtener_departamentos_de(usuario_id: str) -> list[str]:
    res = (
        supabase.table("usuario_departamentos")
        .select("departamento")
        .eq("usuario_id", usuario_id)
        .execute()
    )
    return [r["departamento"] for r in res.data]


def crear_usuario(nombre: str, usuario: str, password: str, rol: str, departamentos: list[str]) -> None:
    h, salt = hash_password(password)
    res = (
        supabase.table("usuarios_regional")
        .insert(
            {
                "nombre": nombre,
                "usuario": usuario,
                "password_hash": h,
                "salt": salt,
                "rol": rol,
            }
        )
        .execute()
    )
    nuevo_id = res.data[0]["id"]
    if rol == "BACKOFFICE" and departamentos:
        supabase.table("usuario_departamentos").insert(
            [{"usuario_id": nuevo_id, "departamento": d} for d in departamentos]
        ).execute()


def actualizar_departamentos(usuario_id: str, departamentos: list[str]) -> None:
    supabase.table("usuario_departamentos").delete().eq("usuario_id", usuario_id).execute()
    if departamentos:
        supabase.table("usuario_departamentos").insert(
            [{"usuario_id": usuario_id, "departamento": d} for d in departamentos]
        ).execute()


def alternar_activo(usuario_id: str, activo: bool) -> None:
    supabase.table("usuarios_regional").update({"activo": activo}).eq("id", usuario_id).execute()


def resetear_password(usuario_id: str, nueva_password: str) -> None:
    h, salt = hash_password(nueva_password)
    supabase.table("usuarios_regional").update({"password_hash": h, "salt": salt}).eq("id", usuario_id).execute()


def listar_usuarios() -> list[dict]:
    res = supabase.table("usuarios_regional").select("*").order("creado_en").execute()
    usuarios = res.data
    for u in usuarios:
        u["departamentos"] = obtener_departamentos_de(u["id"]) if u["rol"] == "BACKOFFICE" else []
    return usuarios


# ============================================================================
# FUNCIONES DE DATOS: PRESUPUESTO Y GASTOS
# ============================================================================

def guardar_presupuesto(departamento: str, anio: int, mes: int, tipo: str, subtipo: str | None, monto: float) -> None:
    supabase.table("presupuesto_mensual_dep").upsert(
        {
            "departamento": departamento,
            "anio": anio,
            "mes": mes,
            "tipo": tipo,
            "subtipo": subtipo or "",
            "monto": monto,
            "actualizado_en": datetime.now().isoformat(),
        },
        on_conflict="departamento,anio,mes,tipo,subtipo",
    ).execute()


def guardar_gasto(departamento, fecha, tipo, subtipo, monto, descripcion) -> None:
    supabase.table("gastos_diarios_dep").insert(
        {
            "departamento": departamento,
            "fecha": fecha,
            "tipo": tipo,
            "subtipo": subtipo,
            "monto": monto,
            "descripcion": descripcion,
        }
    ).execute()


def eliminar_gasto(gasto_id: str) -> None:
    supabase.table("gastos_diarios_dep").delete().eq("id", gasto_id).execute()


def df_presupuesto(anio: int, mes: int, departamento: str | None = None) -> pd.DataFrame:
    query = (
        supabase.table("presupuesto_mensual_dep")
        .select("departamento, anio, mes, tipo, subtipo, monto")
        .eq("anio", anio)
        .eq("mes", mes)
    )
    if departamento:
        query = query.eq("departamento", departamento)
    data = query.execute().data
    if not data:
        return pd.DataFrame(columns=["departamento", "anio", "mes", "tipo", "subtipo", "monto"])
    return pd.DataFrame(data)


def df_gastos(anio: int, mes: int, departamento: str | None = None) -> pd.DataFrame:
    primer_dia = f"{anio:04d}-{mes:02d}-01"
    if mes == 12:
        siguiente = f"{anio + 1:04d}-01-01"
    else:
        siguiente = f"{anio:04d}-{mes + 1:02d}-01"

    query = (
        supabase.table("gastos_diarios_dep")
        .select("id, departamento, fecha, tipo, subtipo, monto, descripcion")
        .gte("fecha", primer_dia)
        .lt("fecha", siguiente)
        .order("fecha", desc=True)
    )
    if departamento:
        query = query.eq("departamento", departamento)
    data = query.execute().data
    if not data:
        return pd.DataFrame(columns=["id", "departamento", "fecha", "tipo", "subtipo", "monto", "descripcion"])
    return pd.DataFrame(data)


def formato_soles(valor: float) -> str:
    return f"S/ {valor:,.2f}"


def semaforo(pct: float) -> str:
    if pct > 100:
        return "🔴"
    if pct > 80:
        return "🟡"
    return "🟢"


# ============================================================================
# BOOTSTRAP: crear el primer administrador si no existe ningún usuario
# ============================================================================

if contar_usuarios() == 0:
    st.title("👋 Configuración inicial")
    st.info(
        "Todavía no hay ningún usuario creado. Crea la cuenta del "
        "**Administrador** para poder empezar (luego podrás registrar a "
        "cada Back Office desde el menú 'Gestionar Back Office')."
    )
    with st.form("form_primer_admin"):
        nombre = st.text_input("Tu nombre completo")
        usuario = st.text_input("Nombre de usuario (para iniciar sesión)")
        password = st.text_input("Contraseña", type="password")
        password2 = st.text_input("Confirma la contraseña", type="password")
        enviado = st.form_submit_button("Crear administrador", type="primary")

        if enviado:
            if not nombre or not usuario or not password:
                st.warning("Completa todos los campos.")
            elif password != password2:
                st.warning("Las contraseñas no coinciden.")
            elif len(password) < 4:
                st.warning("La contraseña debe tener al menos 4 caracteres.")
            else:
                crear_usuario(nombre, usuario, password, rol="ADMIN", departamentos=[])
                st.success("Administrador creado. Recarga la página e inicia sesión.")
                st.rerun()
    st.stop()

# ============================================================================
# LOGIN
# ============================================================================

if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = None

if st.session_state.usuario_actual is None:
    st.title("📊 Control de Presupuesto")
    st.caption("Back Office Regional — Inicia sesión")

    with st.form("form_login"):
        usuario_in = st.text_input("Usuario")
        password_in = st.text_input("Contraseña", type="password")
        entrar = st.form_submit_button("Ingresar", type="primary")

        if entrar:
            u = obtener_usuario_por_login(usuario_in.strip())
            if u and verificar_password(password_in, u["password_hash"], u["salt"]):
                st.session_state.usuario_actual = {
                    "id": u["id"],
                    "nombre": u["nombre"],
                    "usuario": u["usuario"],
                    "rol": u["rol"],
                    "departamentos": obtener_departamentos_de(u["id"]) if u["rol"] == "BACKOFFICE" else [],
                }
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    st.stop()

usuario_actual = st.session_state.usuario_actual
rol_actual = usuario_actual["rol"]
es_admin = rol_actual == "ADMIN"
es_visor = rol_actual == "VISOR"
mis_departamentos = DEPARTAMENTOS if rol_actual in ("ADMIN", "VISOR") else usuario_actual["departamentos"]

# ============================================================================
# BARRA LATERAL
# ============================================================================

st.sidebar.title("📊 Control de Presupuesto")
st.sidebar.caption("Back Office Regional")
st.sidebar.markdown(f"**{usuario_actual['nombre']}**")
if es_admin:
    st.sidebar.caption("Administrador")
elif es_visor:
    st.sidebar.caption("Visor (solo lectura)")
else:
    st.sidebar.caption(" · ".join(mis_departamentos) or "Sin departamento asignado")

if st.sidebar.button("Cerrar sesión"):
    st.session_state.usuario_actual = None
    st.rerun()

st.sidebar.markdown("---")

opciones_menu = ["📊 Cuadro Consolidado"]
if rol_actual in ("ADMIN", "BACKOFFICE"):
    opciones_menu += ["💰 Registrar presupuesto mensual", "🧾 Registrar gasto diario"]
opciones_menu.append("📋 Historial de gastos")
if es_admin:
    opciones_menu.append("👥 Gestionar Back Office")

pagina = st.sidebar.radio("Menú", opciones_menu)

st.sidebar.markdown("---")
hoy = date.today()
anio_sel = st.sidebar.selectbox("Año", options=[hoy.year - 1, hoy.year, hoy.year + 1], index=1)
mes_sel = st.sidebar.selectbox("Mes", options=list(range(1, 13)), format_func=lambda m: MESES[m - 1], index=hoy.month - 1)

st.sidebar.markdown("---")
st.sidebar.caption(
    "🟢 Dentro del presupuesto (≤80%) · 🟡 Cerca del límite (80–100%) · 🔴 Presupuesto excedido (>100%)"
)

if not mis_departamentos and rol_actual == "BACKOFFICE":
    st.warning(
        "Todavía no tienes ningún departamento asignado. Comunícate con tu "
        "administrador para que te asigne uno o más desde 'Gestionar Back Office'."
    )
    st.stop()

# ============================================================================
# PÁGINA: RESUMEN
# ============================================================================

TIPOS_DETALLE = [
    ("Activaciones", "Activaciones", None),
    ("Merch", "Merch", None),
    ("Acciones Comerciales - Dispersión", "Acciones Comerciales", "Dispersión"),
    ("Acciones Comerciales - Incentivos", "Acciones Comerciales", "Incentivos"),
]


def gastado_por_tipo(df_gastos_depto: pd.DataFrame, tipo: str, subtipo: str | None) -> float:
    if df_gastos_depto.empty:
        return 0
    filtro = df_gastos_depto["tipo"] == tipo
    if subtipo is not None:
        filtro = filtro & (df_gastos_depto["subtipo"] == subtipo)
    return df_gastos_depto.loc[filtro, "monto"].sum()


def presupuesto_por_tipo(df_pres_depto: pd.DataFrame, tipo: str, subtipo: str | None) -> float:
    if df_pres_depto.empty:
        return 0
    filtro = df_pres_depto["tipo"] == tipo
    filtro = filtro & (df_pres_depto["subtipo"] == (subtipo or ""))
    return df_pres_depto.loc[filtro, "monto"].sum()


TABLA_CSS = """
<style>
.tabla-pivote-wrap { overflow-x: auto; margin: 0.5rem 0 1.5rem 0; }
.tabla-pivote {
    border-collapse: collapse;
    width: 100%;
    font-size: 0.85rem;
    font-family: inherit;
}
.tabla-pivote th, .tabla-pivote td {
    border: 1px solid #d9dee3;
    padding: 6px 10px;
    text-align: right;
    white-space: nowrap;
}
.tabla-pivote thead th {
    background-color: #1e3a5f;
    color: #ffffff;
    text-align: center;
    font-weight: 600;
    position: sticky;
    top: 0;
}
.tabla-pivote thead tr:first-child th {
    border-bottom: 1px solid #14283f;
}
.tabla-pivote td.col-depto, .tabla-pivote th.col-depto {
    text-align: left;
    font-weight: 600;
    color: #1e293b;
    background-color: #f1f5f9;
    position: sticky;
    left: 0;
    z-index: 1;
}
.tabla-pivote tbody tr:nth-child(even) td:not(.col-depto) { background-color: #f8fafc; }
.tabla-pivote tbody tr:hover td:not(.col-depto) { background-color: #eef2ff; }
.tabla-pivote tr.fila-total td {
    background-color: #dbeafe !important;
    font-weight: 700;
    color: #1e3a5f;
    border-top: 2px solid #1e3a5f;
}
.tabla-pivote td.negativo { color: #dc2626; font-weight: 600; }
.tabla-pivote td.celda-pct { text-align: center; font-weight: 600; }
.tabla-pivote th.col-total { background-color: #0f2038 !important; }
.tabla-pivote tbody tr td:nth-last-child(-n+4) { background-color: #eef2ff; }
.tabla-pivote tr.fila-total td:nth-last-child(-n+4) { background-color: #bfdbfe !important; }
</style>
"""


def _fmt(v: float) -> str:
    return f"S/ {v:,.2f}"


def _celda_disponible(v: float) -> str:
    clase = " negativo" if v < 0 else ""
    return f'<td class="{clase}">{_fmt(v)}</td>'


def _celda_pct(gastado: float, presupuesto: float) -> str:
    pct = (gastado / presupuesto * 100) if presupuesto > 0 else 0
    return f'<td class="celda-pct">{semaforo(pct)} {pct:.1f}%</td>'


def construir_tabla_pivote_html(departamentos: list[str], pres_df: pd.DataFrame, gas_df: pd.DataFrame, etiqueta_total: str = "FANERO") -> str:
    filas_html = []
    totales = {etq: {"pres": 0.0, "gas": 0.0} for etq, _, _ in TIPOS_DETALLE}
    total_general = {"pres": 0.0, "gas": 0.0}

    for depto in departamentos:
        pres_depto_df = pres_df[pres_df["departamento"] == depto] if not pres_df.empty else pres_df
        gas_depto_df = gas_df[gas_df["departamento"] == depto] if not gas_df.empty else gas_df
        pres_depto_total = 0.0
        gas_depto_total = 0.0
        celdas = f'<td class="col-depto">{depto.upper()}</td>'
        for etiqueta, tipo, subtipo in TIPOS_DETALLE:
            pres = presupuesto_por_tipo(pres_depto_df, tipo, subtipo)
            gas = gastado_por_tipo(gas_depto_df, tipo, subtipo)
            disp = pres - gas
            totales[etiqueta]["pres"] += pres
            totales[etiqueta]["gas"] += gas
            pres_depto_total += pres
            gas_depto_total += gas
            celdas += f"<td>{_fmt(pres)}</td><td>{_fmt(gas)}</td>{_celda_disponible(disp)}{_celda_pct(gas, pres)}"
        # columna final TOTAL: suma de los 4 presupuestos y de los 4 gastos de este departamento
        disp_depto_total = pres_depto_total - gas_depto_total
        celdas += f"<td>{_fmt(pres_depto_total)}</td><td>{_fmt(gas_depto_total)}</td>{_celda_disponible(disp_depto_total)}{_celda_pct(gas_depto_total, pres_depto_total)}"
        total_general["pres"] += pres_depto_total
        total_general["gas"] += gas_depto_total
        filas_html.append(f"<tr>{celdas}</tr>")

    celdas_total = f'<td class="col-depto">{etiqueta_total}</td>'
    for etiqueta, _, _ in TIPOS_DETALLE:
        pres_t = totales[etiqueta]["pres"]
        gas_t = totales[etiqueta]["gas"]
        disp_t = pres_t - gas_t
        celdas_total += f"<td>{_fmt(pres_t)}</td><td>{_fmt(gas_t)}</td>{_celda_disponible(disp_t)}{_celda_pct(gas_t, pres_t)}"
    disp_general = total_general["pres"] - total_general["gas"]
    celdas_total += (
        f"<td>{_fmt(total_general['pres'])}</td><td>{_fmt(total_general['gas'])}</td>"
        f"{_celda_disponible(disp_general)}{_celda_pct(total_general['gas'], total_general['pres'])}"
    )
    fila_total_html = f'<tr class="fila-total">{celdas_total}</tr>'

    etiquetas_columnas = [etq for etq, _, _ in TIPOS_DETALLE] + ["TOTAL"]
    encabezado_top = '<th class="col-depto" rowspan="2">DEPARTAMENTO</th>' + "".join(
        f'<th colspan="4"{" class=\"col-total\"" if etq == "TOTAL" else ""}>{etq.upper()}</th>' for etq in etiquetas_columnas
    )
    encabezado_sub = "".join(
        f'<th{" class=\"col-total\"" if etq == "TOTAL" else ""}>PRESUPUESTO</th>'
        f'<th{" class=\"col-total\"" if etq == "TOTAL" else ""}>GASTADO</th>'
        f'<th{" class=\"col-total\"" if etq == "TOTAL" else ""}>DISPONIBLE</th>'
        f'<th{" class=\"col-total\"" if etq == "TOTAL" else ""}>% EJECUCIÓN</th>'
        for etq in etiquetas_columnas
    )

    html = f"""{TABLA_CSS}
<div class="tabla-pivote-wrap">
<table class="tabla-pivote">
<thead>
<tr>{encabezado_top}</tr>
<tr>{encabezado_sub}</tr>
</thead>
<tbody>
{''.join(filas_html)}
{fila_total_html}
</tbody>
</table>
</div>
"""
    return dedent(html)


if pagina == "📊 Cuadro Consolidado":
    st.title("Cuadro Consolidado")
    st.caption(f"{MESES[mes_sel - 1]} {anio_sel} — Activaciones · Merch · Acciones Comerciales (Dispersión / Incentivos)")

    opciones_vista = list(mis_departamentos)
    if es_admin or es_visor:
        opciones_vista = [FANERO] + opciones_vista
    elif len(mis_departamentos) > 1:
        opciones_vista = ["Mis departamentos (Total)"] + opciones_vista

    depto_vista = st.selectbox("Departamento", options=opciones_vista)

    pres_df = df_presupuesto(anio_sel, mes_sel)
    gas_df = df_gastos(anio_sel, mes_sel)

    if depto_vista in (FANERO, "Mis departamentos (Total)"):
        alcance = DEPARTAMENTOS if depto_vista == FANERO else mis_departamentos
        etiqueta_total = FANERO if depto_vista == FANERO else "TOTAL"
        presupuesto_total = pres_df.loc[pres_df["departamento"].isin(alcance), "monto"].sum() if not pres_df.empty else 0
        gastado_total = gas_df.loc[gas_df["departamento"].isin(alcance), "monto"].sum() if not gas_df.empty else 0
    else:
        alcance = [depto_vista]
        etiqueta_total = "TOTAL"
        presupuesto_total = pres_df.loc[pres_df["departamento"] == depto_vista, "monto"].sum() if not pres_df.empty else 0
        gastado_total = gas_df.loc[gas_df["departamento"] == depto_vista, "monto"].sum() if not gas_df.empty else 0

    disponible = presupuesto_total - gastado_total
    pct = (gastado_total / presupuesto_total * 100) if presupuesto_total > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Presupuesto Asignado", formato_soles(presupuesto_total))
    col2.metric("Gastado", formato_soles(gastado_total))
    col3.metric("Disponible", formato_soles(disponible), delta=None)
    col4.metric("% Ejecución", f"{semaforo(pct)} {pct:.1f}%")

    if gastado_total > presupuesto_total and presupuesto_total > 0:
        st.error("⚠ SOBREPASO PRESUPUESTAL: el gasto supera el presupuesto asignado.")

    st.markdown("---")

    html_pivote = construir_tabla_pivote_html(alcance, pres_df, gas_df, etiqueta_total=etiqueta_total)
    st.markdown(html_pivote, unsafe_allow_html=True)

# ============================================================================
# PÁGINA: REGISTRAR PRESUPUESTO MENSUAL
# ============================================================================

elif pagina == "💰 Registrar presupuesto mensual":
    st.title("Registrar presupuesto mensual")
    st.caption("Asigna o actualiza el presupuesto del mes para cada tipo de gasto de tu departamento.")

    with st.form("form_presupuesto"):
        col1, col2 = st.columns(2)
        with col1:
            departamento = st.selectbox("Departamento", options=mis_departamentos)
            anio = st.number_input("Año", min_value=2000, max_value=2100, value=anio_sel, step=1)
            mes = st.selectbox("Mes", options=list(range(1, 13)), format_func=lambda m: MESES[m - 1], index=mes_sel - 1)
        with col2:
            tipo = st.selectbox("Tipo de gasto", options=TIPOS_GASTO)
            subtipo = None
            if tipo == "Acciones Comerciales":
                subtipo = st.selectbox("Subtipo de Acciones Comerciales", options=SUBTIPOS_ACCIONES_COMERCIALES)
            monto = st.number_input("Presupuesto Asignado (S/)", min_value=0.0, step=100.0, format="%.2f")

        enviado = st.form_submit_button("Guardar presupuesto", type="primary")

        if enviado:
            if monto <= 0:
                st.warning("Ingresa un monto de presupuesto mayor a cero.")
            else:
                guardar_presupuesto(departamento, int(anio), int(mes), tipo, subtipo, float(monto))
                etiqueta_tipo = f"{tipo} - {subtipo}" if subtipo else tipo
                st.success(
                    f"Presupuesto guardado: {departamento} — {etiqueta_tipo} — {MESES[mes - 1]} {anio} — {formato_soles(monto)}"
                )
                st.rerun()

    st.markdown("---")
    st.subheader(f"Presupuestos registrados — {MESES[mes_sel - 1]} {anio_sel}")
    tabla = df_presupuesto(anio_sel, mes_sel)
    if not tabla.empty:
        tabla = tabla[tabla["departamento"].isin(mis_departamentos)]
    if tabla.empty:
        st.info("Todavía no hay presupuestos registrados para este mes.")
    else:
        tabla = tabla.copy()
        tabla["Tipo de gasto"] = tabla.apply(
            lambda r: f"{r['tipo']} - {r['subtipo']}" if r["subtipo"] else r["tipo"], axis=1
        )
        tabla = tabla.rename(columns={"departamento": "Departamento", "monto": "Presupuesto"})
        st.dataframe(
            tabla[["Departamento", "Tipo de gasto", "Presupuesto"]]
            .sort_values(["Departamento", "Tipo de gasto"])
            .style.format({"Presupuesto": "S/ {:,.2f}"}),
            use_container_width=True,
            hide_index=True,
        )

# ============================================================================
# PÁGINA: REGISTRAR GASTO DIARIO
# ============================================================================

elif pagina == "🧾 Registrar gasto diario":
    st.title("Registrar gasto diario")
    st.caption("Registra activaciones, merch o acciones comerciales (dispersión / incentivos) del día.")

    with st.form("form_gasto", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            departamento = st.selectbox("Departamento", options=mis_departamentos)
            fecha = st.date_input("Fecha", value=hoy, format="YYYY-MM-DD")
            tipo = st.selectbox("Tipo de gasto", options=TIPOS_GASTO)
        with col2:
            subtipo = None
            if tipo == "Acciones Comerciales":
                subtipo = st.selectbox("Subtipo de Acciones Comerciales", options=SUBTIPOS_ACCIONES_COMERCIALES)
            monto = st.number_input("Monto gastado (S/)", min_value=0.0, step=10.0, format="%.2f")
            descripcion = st.text_input("Descripción / detalle (opcional)")

        enviado = st.form_submit_button("Guardar gasto", type="primary")

        if enviado:
            if monto <= 0:
                st.warning("Ingresa un monto de gasto mayor a cero.")
            else:
                guardar_gasto(departamento, fecha.isoformat(), tipo, subtipo, float(monto), descripcion or None)
                st.success(f"Gasto guardado: {departamento} — {tipo}{f' ({subtipo})' if subtipo else ''} — {formato_soles(monto)}")
                st.rerun()

    st.markdown("---")
    st.subheader("Últimos gastos registrados")
    ultimos = df_gastos(anio_sel, mes_sel)
    if not ultimos.empty:
        ultimos = ultimos[ultimos["departamento"].isin(mis_departamentos)].head(10)
    if ultimos.empty:
        st.info("Aún no hay gastos registrados este mes.")
    else:
        vista = ultimos.rename(
            columns={
                "departamento": "Departamento", "fecha": "Fecha", "tipo": "Tipo",
                "subtipo": "Subtipo", "monto": "Monto", "descripcion": "Descripción",
            }
        )
        st.dataframe(
            vista[["Fecha", "Departamento", "Tipo", "Subtipo", "Monto", "Descripción"]].style.format(
                {"Monto": "S/ {:,.2f}"}
            ),
            use_container_width=True,
            hide_index=True,
        )

# ============================================================================
# PÁGINA: HISTORIAL DE GASTOS
# ============================================================================

elif pagina == "📋 Historial de gastos":
    st.title("Historial de gastos")
    if es_visor:
        st.caption("Vista de solo lectura — fecha, tipo de gasto, descripción y monto registrados por cada Back Office.")

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        depto_filtro = st.selectbox("Filtrar por departamento", options=["Todos"] + list(mis_departamentos))
    with col_f2:
        tipo_filtro = st.selectbox("Filtrar por tipo de gasto", options=["Todos"] + TIPOS_GASTO)
    with col_f3:
        subtipo_filtro = "Todos"
        if tipo_filtro == "Acciones Comerciales":
            subtipo_filtro = st.selectbox("Filtrar por subtipo", options=["Todos"] + SUBTIPOS_ACCIONES_COMERCIALES)

    depto_query = None if depto_filtro == "Todos" else depto_filtro

    tabla = df_gastos(anio_sel, mes_sel, depto_query)
    if not tabla.empty:
        tabla = tabla[tabla["departamento"].isin(mis_departamentos)]
        if tipo_filtro != "Todos":
            tabla = tabla[tabla["tipo"] == tipo_filtro]
        if subtipo_filtro != "Todos":
            tabla = tabla[tabla["subtipo"] == subtipo_filtro]
    st.caption(f"{len(tabla)} registro(s) — {MESES[mes_sel - 1]} {anio_sel}")

    if tabla.empty:
        st.info("No hay gastos para los filtros seleccionados.")
    else:
        vista = tabla.rename(
            columns={
                "departamento": "Departamento", "fecha": "Fecha", "tipo": "Tipo",
                "subtipo": "Subtipo", "monto": "Monto", "descripcion": "Descripción",
            }
        )
        st.dataframe(
            vista[["Fecha", "Departamento", "Tipo", "Subtipo", "Monto", "Descripción"]].style.format(
                {"Monto": "S/ {:,.2f}"}
            ),
            use_container_width=True,
            hide_index=True,
        )

        if not es_visor:
            st.markdown("---")
            st.subheader("Eliminar un registro")
            opciones = {
                f"#{str(row.id)[:8]} · {row.fecha} · {row.departamento} · {row.tipo} · S/ {row.monto:,.2f}": row.id
                for row in tabla.itertuples()
            }
            seleccion = st.selectbox("Selecciona el registro a eliminar", options=list(opciones.keys()))
            if st.button("🗑️ Eliminar registro seleccionado"):
                eliminar_gasto(opciones[seleccion])
                st.success("Registro eliminado.")
                st.rerun()

        st.markdown("---")
        csv = tabla.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Descargar historial (CSV)", data=csv, file_name=f"gastos_{anio_sel}_{mes_sel:02d}.csv", mime="text/csv")

# ============================================================================
# PÁGINA: GESTIONAR BACK OFFICE (solo Admin)
# ============================================================================

elif pagina == "👥 Gestionar Back Office":
    st.title("Gestionar Back Office")
    st.caption("Registra cada usuario, su rol, y (si es Back Office) sus departamentos.")

    with st.expander("➕ Registrar nuevo usuario", expanded=True):
        with st.form("form_nuevo_usuario"):
            col1, col2 = st.columns(2)
            with col1:
                nombre = st.text_input("Nombre completo")
                usuario_login = st.text_input("Nombre de usuario (para iniciar sesión)")
                password = st.text_input("Contraseña", type="password")
            with col2:
                rol_nuevo = st.selectbox(
                    "Rol",
                    options=["BACKOFFICE", "VISOR", "ADMIN"],
                    format_func=lambda r: {
                        "BACKOFFICE": "👤 Back Office (registra su(s) departamento(s))",
                        "VISOR": "👁️ Visor (solo ve el Cuadro Consolidado, sin editar)",
                        "ADMIN": "🛡️ Administrador (acceso total)",
                    }[r],
                )
                deptos_nuevo = []
                if rol_nuevo == "BACKOFFICE":
                    deptos_nuevo = st.multiselect(
                        "Departamento(s) del que es responsable", options=DEPARTAMENTOS
                    )

            crear = st.form_submit_button("Crear usuario", type="primary")

            if crear:
                if not nombre or not usuario_login or not password:
                    st.warning("Completa nombre, usuario y contraseña.")
                elif len(password) < 4:
                    st.warning("La contraseña debe tener al menos 4 caracteres.")
                elif rol_nuevo == "BACKOFFICE" and not deptos_nuevo:
                    st.warning("Asigna al menos un departamento para un Back Office.")
                else:
                    try:
                        crear_usuario(nombre, usuario_login.strip(), password, rol_nuevo, deptos_nuevo)
                        st.success(f"Usuario '{nombre}' creado correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo crear el usuario (¿nombre de usuario repetido?): {e}")

    st.markdown("---")
    st.subheader("Usuarios registrados")

    ETIQUETA_ROL = {
        "ADMIN": "🛡️ Administrador",
        "BACKOFFICE": "👤 Back Office",
        "VISOR": "👁️ Visor",
    }

    usuarios = listar_usuarios()
    if not usuarios:
        st.info("Aún no hay usuarios registrados.")
    else:
        for u in usuarios:
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 3, 2])
                with c1:
                    st.markdown(f"**{u['nombre']}**")
                    st.caption(f"{ETIQUETA_ROL.get(u['rol'], u['rol'])} · usuario: `{u['usuario']}`")
                with c2:
                    if u["rol"] == "BACKOFFICE":
                        nuevos_deptos = st.multiselect(
                            "Departamentos asignados",
                            options=DEPARTAMENTOS,
                            default=u["departamentos"],
                            key=f"deptos_{u['id']}",
                            label_visibility="collapsed",
                        )
                        if nuevos_deptos != u["departamentos"]:
                            if st.button("Guardar cambios", key=f"guardar_{u['id']}"):
                                actualizar_departamentos(u["id"], nuevos_deptos)
                                st.success("Departamentos actualizados.")
                                st.rerun()
                    elif u["rol"] == "VISOR":
                        st.caption("Solo lectura del Cuadro Consolidado (todos los departamentos)")
                    else:
                        st.caption("Acceso a todos los departamentos")
                with c3:
                    if u["usuario"] != usuario_actual["usuario"]:
                        nuevo_estado = st.toggle("Activo", value=u["activo"], key=f"activo_{u['id']}")
                        if nuevo_estado != u["activo"]:
                            alternar_activo(u["id"], nuevo_estado)
                            st.rerun()
                    else:
                        st.caption("(tu cuenta)")

                with st.expander("🔑 Restablecer contraseña"):
                    nueva_pw = st.text_input(
                        "Nueva contraseña", type="password", key=f"pw_{u['id']}"
                    )
                    if st.button("Actualizar contraseña", key=f"pwbtn_{u['id']}"):
                        if len(nueva_pw) < 4:
                            st.warning("La contraseña debe tener al menos 4 caracteres.")
                        else:
                            resetear_password(u["id"], nueva_pw)
                            st.success("Contraseña actualizada.")
