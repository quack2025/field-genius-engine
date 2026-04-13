-- 032: POC gating — Retail (general) + POC (Argos/Telecable) + location pending state
-- Sprint: Demo POC
--
-- Cambios:
-- 1. Nuevas columnas de estado en users: pending_poc_selection_at, pending_location_request_at
-- 2. telecable deja de ser whitelist — es un POC abierto accedido por keyword
-- 3. argos se activa con sus frameworks existentes de construcción
-- 4. demo_telecom se desactiva (absorbido por telecable)

BEGIN;

-- ═══════════════════════════════════════════════════════════════
-- 1. Estado pending en users (TTL lógico en Python, 10 min)
-- ═══════════════════════════════════════════════════════════════
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS pending_poc_selection_at timestamptz,
  ADD COLUMN IF NOT EXISTS pending_location_request_at timestamptz;

-- ═══════════════════════════════════════════════════════════════
-- 2. telecable → POC abierto (access_mode=open, sin fallback)
-- ═══════════════════════════════════════════════════════════════
UPDATE implementations
SET access_mode = 'open',
    demo_keywords = ARRAY['telecable'],
    fallback_implementation = NULL,
    onboarding_config = COALESCE(onboarding_config, '{}'::jsonb) || jsonb_build_object(
      'demo_mode', true,
      'demo_batch_mode', 'explicit',
      'is_poc', true,
      'poc_company_label', 'Telecable'
    )
WHERE id = 'telecable';

-- ═══════════════════════════════════════════════════════════════
-- 3. argos → activar como POC con frameworks de construcción existentes
-- ═══════════════════════════════════════════════════════════════
UPDATE implementations
SET status = 'active',
    access_mode = 'open',
    demo_keywords = ARRAY['argos'],
    onboarding_config = COALESCE(onboarding_config, '{}'::jsonb) || jsonb_build_object(
      'demo_mode', true,
      'demo_batch_mode', 'explicit',
      'is_poc', true,
      'poc_company_label', 'Argos',
      'post_switch_message',
      E'¡Perfecto! Activaste el *POC de Argos* 🏗️\n\n' ||
      E'Estás por ver cómo Radar Xponencial analiza visitas de campo para una empresa de cementos y materiales de construcción.\n\n' ||
      E'📍 *Casos que puedo analizar:*\n' ||
      E'• *Ferreterías*: exhibición, surtido Argos vs competencia, precios, relación con el ferretero\n' ||
      E'• *Obras civiles*: avance, materiales en uso, marcas dominantes\n' ||
      E'• *Obras pequeñas*: tipo de proyecto, intensidad de uso de cemento, oportunidad comercial\n\n' ||
      E'Enviame fotos, audios o videos de lo que veas en el punto. Puedo consolidar varias piezas en un solo análisis.\n\n' ||
      E'Al final escribe *generar* para ver el reporte consolidado.'
    )
WHERE id = 'argos';

-- ═══════════════════════════════════════════════════════════════
-- 4. demo_telecom → inactivo (absorbido por telecable como POC)
-- ═══════════════════════════════════════════════════════════════
UPDATE implementations
SET status = 'inactive'
WHERE id = 'demo_telecom';

-- ═══════════════════════════════════════════════════════════════
-- 5. Verificación
-- ═══════════════════════════════════════════════════════════════
SELECT id,
       status,
       access_mode,
       demo_keywords,
       fallback_implementation,
       onboarding_config->>'demo_mode' AS demo_mode,
       onboarding_config->>'is_poc' AS is_poc,
       onboarding_config->>'poc_company_label' AS poc_label
FROM implementations
WHERE id IN ('laundry_care', 'telecable', 'argos', 'demo_telecom')
ORDER BY id;

-- Verificar columnas nuevas en users
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'users'
  AND column_name IN ('pending_poc_selection_at', 'pending_location_request_at')
ORDER BY column_name;

COMMIT;
