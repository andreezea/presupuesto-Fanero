-- ============================================================================
-- MIGRACIÓN: renombrar el tipo de gasto "AACC" a "Acciones Comerciales"
--
-- Ejecuta esto en Supabase → SQL Editor SOLO SI ya habías corrido
-- supabase_setup.sql antes (es decir, si la tabla gastos_diarios_dep ya
-- existía). Si es tu primera vez configurando el proyecto, no necesitas
-- este archivo — usa directamente el supabase_setup.sql actualizado.
-- ============================================================================

-- 1) Actualiza cualquier gasto ya registrado como "AACC" al nuevo nombre
update public.gastos_diarios_dep
   set tipo = 'Acciones Comerciales'
 where tipo = 'AACC';

-- 2) Reemplaza la restricción (constraint) para aceptar el nuevo nombre
alter table public.gastos_diarios_dep
  drop constraint if exists gastos_diarios_dep_tipo_check;

alter table public.gastos_diarios_dep
  add constraint gastos_diarios_dep_tipo_check
  check (tipo in ('Activaciones','Merch','Acciones Comerciales'));
