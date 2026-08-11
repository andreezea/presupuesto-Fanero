-- ============================================================================
-- CONTROL DE PRESUPUESTO REGIONAL (App de Streamlit)
-- Ejecutar en: Supabase → SQL Editor → New query
--
-- Estas tablas son independientes de las que ya usa tu otra app
-- (presupuesto-backoffice). Puedes ejecutar esto en el MISMO proyecto de
-- Supabase sin ningún conflicto, los nombres no se repiten.
-- ============================================================================

create extension if not exists "pgcrypto";

-- ============================================================================
-- 1. PRESUPUESTO Y GASTOS
-- ============================================================================

create table if not exists public.presupuesto_mensual_dep (
  id             uuid primary key default gen_random_uuid(),
  departamento   text not null,
  anio           int  not null check (anio between 2000 and 2100),
  mes            int  not null check (mes between 1 and 12),
  monto          numeric(14,2) not null default 0 check (monto >= 0),
  actualizado_en timestamptz not null default now(),
  unique (departamento, anio, mes)
);

create table if not exists public.gastos_diarios_dep (
  id            uuid primary key default gen_random_uuid(),
  departamento  text not null,
  fecha         date not null,
  tipo          text not null check (tipo in ('Activaciones','Merch','Acciones Comerciales')),
  subtipo       text check (subtipo is null or subtipo in ('Dispersión','Incentivos')),
  monto         numeric(14,2) not null default 0 check (monto >= 0),
  descripcion   text,
  creado_en     timestamptz not null default now()
);

create index if not exists idx_gastos_dep_fecha on public.gastos_diarios_dep (fecha);
create index if not exists idx_gastos_dep_depto on public.gastos_diarios_dep (departamento);

-- ============================================================================
-- 2. USUARIOS (Back Office) Y ASIGNACIÓN DE DEPARTAMENTOS
--
-- Esta app maneja su propio login simple (usuario + contraseña), separado
-- del sistema de Supabase Auth que usa tu otra app. Las contraseñas se
-- guardan con hash (nunca en texto plano).
-- ============================================================================

create table if not exists public.usuarios_regional (
  id             uuid primary key default gen_random_uuid(),
  nombre         text not null,
  usuario        text not null unique,   -- nombre de usuario para iniciar sesión
  password_hash  text not null,
  salt           text not null,
  es_admin       boolean not null default false,
  activo         boolean not null default true,
  creado_en      timestamptz not null default now()
);

create table if not exists public.usuario_departamentos (
  usuario_id    uuid not null references public.usuarios_regional(id) on delete cascade,
  departamento  text not null,
  primary key (usuario_id, departamento)
);

-- ============================================================================
-- SEGURIDAD (RLS)
--
-- El control de acceso (quién puede ver/editar qué departamento) lo maneja
-- la propia app de Streamlit con su sistema de login. Por eso las políticas
-- de la base de datos permiten leer y escribir con la clave pública
-- (anon/publishable) — es la misma clave que ya usas en Vercel.
--
-- ⚠️ Importante: esto significa que la seguridad depende de la app, no de
-- la base de datos en sí. Es una solución simple y adecuada para un equipo
-- interno de confianza. Si más adelante quieres seguridad reforzada a nivel
-- de base de datos (como en tu otra app con Supabase Auth + RLS por rol),
-- avísame y migramos a ese modelo.
-- ============================================================================

alter table public.presupuesto_mensual_dep enable row level security;
alter table public.gastos_diarios_dep      enable row level security;
alter table public.usuarios_regional       enable row level security;
alter table public.usuario_departamentos   enable row level security;

drop policy if exists presupuesto_dep_all on public.presupuesto_mensual_dep;
create policy presupuesto_dep_all on public.presupuesto_mensual_dep
  for all using (true) with check (true);

drop policy if exists gastos_dep_all on public.gastos_diarios_dep;
create policy gastos_dep_all on public.gastos_diarios_dep
  for all using (true) with check (true);

drop policy if exists usuarios_regional_all on public.usuarios_regional;
create policy usuarios_regional_all on public.usuarios_regional
  for all using (true) with check (true);

drop policy if exists usuario_departamentos_all on public.usuario_departamentos;
create policy usuario_departamentos_all on public.usuario_departamentos
  for all using (true) with check (true);
