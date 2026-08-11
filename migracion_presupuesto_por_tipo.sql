-- ============================================================================
-- MIGRACIÓN: presupuesto independiente por Tipo de gasto
--
-- Antes: cada departamento tenía UN solo presupuesto total por mes.
-- Ahora: cada departamento tiene un presupuesto SEPARADO para cada tipo
-- (Activaciones, Merch, Acciones Comerciales - Dispersión, Acciones
-- Comerciales - Incentivos).
--
-- Ejecuta esto en Supabase → SQL Editor. Si es la primera vez que instalas
-- el proyecto, usa directamente supabase_setup.sql (ya actualizado) en vez
-- de este archivo.
-- ============================================================================

-- 1) Agregar las columnas nuevas
alter table public.presupuesto_mensual_dep
  add column if not exists tipo text,
  add column if not exists subtipo text default '';

-- 2) Los presupuestos ya registrados (con el modelo viejo, un solo total)
--    se reclasifican como "Activaciones" por defecto. IMPORTANTE: revisa y
--    vuelve a registrar el monto correcto en cada tipo desde
--    "💰 Registrar presupuesto mensual" — el sistema anterior no guardaba
--    cuánto correspondía a cada tipo, así que no se puede dividir
--    automáticamente.
update public.presupuesto_mensual_dep
   set tipo = 'Activaciones', subtipo = ''
 where tipo is null;

-- 3) Hacer las columnas obligatorias
alter table public.presupuesto_mensual_dep
  alter column tipo set not null,
  alter column subtipo set not null;

-- 4) Reemplazar la restricción de unicidad (antes era por departamento+mes,
--    ahora es por departamento+mes+tipo+subtipo)
alter table public.presupuesto_mensual_dep
  drop constraint if exists presupuesto_mensual_dep_departamento_anio_mes_key;

alter table public.presupuesto_mensual_dep
  drop constraint if exists presupuesto_mensual_dep_unique;

alter table public.presupuesto_mensual_dep
  add constraint presupuesto_mensual_dep_unique
  unique (departamento, anio, mes, tipo, subtipo);

-- 5) Validaciones de datos correctos
alter table public.presupuesto_mensual_dep
  drop constraint if exists presupuesto_mensual_dep_tipo_check;
alter table public.presupuesto_mensual_dep
  add constraint presupuesto_mensual_dep_tipo_check
  check (tipo in ('Activaciones','Merch','Acciones Comerciales'));

alter table public.presupuesto_mensual_dep
  drop constraint if exists presupuesto_mensual_dep_subtipo_check;
alter table public.presupuesto_mensual_dep
  add constraint presupuesto_mensual_dep_subtipo_check
  check (
    (tipo = 'Acciones Comerciales' and subtipo in ('Dispersión','Incentivos'))
    or (tipo in ('Activaciones','Merch') and subtipo = '')
  );
