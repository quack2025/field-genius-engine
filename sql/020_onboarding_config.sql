-- 020: Onboarding config — configurable WhatsApp messages per implementation
-- Run in Supabase SQL Editor

-- 1. Add accepted_terms + onboarded_at to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS accepted_terms boolean DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarded_at timestamptz;

-- 2. Add onboarding_config JSONB to implementations
ALTER TABLE implementations
  ADD COLUMN IF NOT EXISTS onboarding_config jsonb DEFAULT '{}'::jsonb;

-- 3. Set Telecable onboarding config
UPDATE implementations SET onboarding_config = '{
  "welcome_message": "Bienvenido a Field Genius! Soy tu asistente de inteligencia de campo para *Telecable*.\n\n📸 Envíame fotos de tus visitas (instalaciones, equipos, puntos de venta)\n🎤 Envía notas de voz con observaciones\n📍 Comparte tu ubicación al llegar al punto\n\nCuando termines tu visita, escribe *reporte* y generaré tu análisis.\n\n⚠️ Tus fotos y audios serán procesados por IA. No envíes contenido personal, confidencial o inapropiado.\n\nPara continuar, responde *acepto* confirmando que entiendes estas condiciones.",
  "terms_accepted_message": "Perfecto! Ya puedes empezar. Envía tus fotos y audios de campo.",
  "rejection_message": "Este servicio es exclusivo para el equipo de campo de *Telecable*.\n\nSi eres parte del equipo, pide a tu supervisor que te registre en el sistema con tu número de WhatsApp.\n\nSoporte: soporte@xponencial.net",
  "first_photo_hint": "Recibido ({count} archivo(s) hoy). Sigue enviando o escribe *reporte* cuando termines.",
  "require_terms": true
}'::jsonb
WHERE id = 'telecable';

-- 4. Set laundry_care onboarding config (demo — no terms required)
UPDATE implementations SET onboarding_config = '{
  "welcome_message": "Bienvenido a Field Genius! 📸\n\nSoy tu asistente de inteligencia de campo para *Cuidado de la Ropa*.\n\n📸 Envía fotos de góndolas, anaqueles y precios\n🎤 Notas de voz con observaciones\n📍 Ubicación del punto de venta\n\nCuando termines, escribe *reporte*.",
  "terms_accepted_message": "Listo! Envía tus fotos y audios.",
  "rejection_message": "No tienes acceso a este servicio. Contacta al administrador.",
  "first_photo_hint": "Recibido ({count} archivo(s) hoy). Sigue enviando o escribe *reporte* cuando termines.",
  "require_terms": false
}'::jsonb
WHERE id = 'laundry_care';

-- 5. Verify
SELECT id, name, onboarding_config->>'require_terms' as requires_terms FROM implementations ORDER BY id;
