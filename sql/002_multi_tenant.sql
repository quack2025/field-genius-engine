-- Field Genius Engine — Multi-tenant migration
-- Run this AFTER schema.sql in Supabase SQL Editor

-- 1. Implementations table (client configurations)
CREATE TABLE IF NOT EXISTS implementations (
    id text PRIMARY KEY,
    name text NOT NULL,
    industry text,
    country text DEFAULT 'CO',
    language text DEFAULT 'es',
    logo_url text,
    primary_color text DEFAULT '#003366',
    status text DEFAULT 'active' CHECK (status IN ('active', 'paused', 'archived')),
    vision_system_prompt text NOT NULL,
    segmentation_prompt_template text,
    google_spreadsheet_id text,
    trigger_words jsonb DEFAULT '["reporte","generar","listo","fin"]'::jsonb,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- 2. Visit types per implementation (replaces JSON files)
CREATE TABLE IF NOT EXISTS visit_types (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    implementation_id text NOT NULL REFERENCES implementations(id),
    slug text NOT NULL,
    display_name text NOT NULL,
    description text,
    schema_json jsonb NOT NULL,
    sheets_tab text,
    confidence_threshold float DEFAULT 0.7,
    is_active boolean DEFAULT true,
    sort_order int DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE(implementation_id, slug)
);

-- 3. Backoffice admin users
CREATE TABLE IF NOT EXISTS backoffice_users (
    id uuid PRIMARY KEY REFERENCES auth.users(id),
    email text NOT NULL,
    name text NOT NULL,
    role text DEFAULT 'admin' CHECK (role IN ('superadmin', 'admin', 'viewer')),
    allowed_implementations text[],
    created_at timestamptz DEFAULT now()
);

-- 4. Add implementation_id FK to existing tables (nullable for backward compat)
ALTER TABLE users ADD COLUMN IF NOT EXISTS implementation_id text REFERENCES implementations(id);
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS implementation_id text REFERENCES implementations(id);
ALTER TABLE visit_reports ADD COLUMN IF NOT EXISTS implementation_id text REFERENCES implementations(id);

-- 5. Update generating_outputs to be valid in sessions CHECK constraint
-- First drop the old constraint, then add the new one
ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_status_check;
ALTER TABLE sessions ADD CONSTRAINT sessions_status_check CHECK (
    status IN ('accumulating', 'segmenting', 'processing', 'generating_outputs', 'completed', 'needs_clarification', 'failed')
);

-- 6. Seed Argos implementation
INSERT INTO implementations (id, name, industry, country, language, primary_color, vision_system_prompt, segmentation_prompt_template)
VALUES (
    'argos',
    'Argos Cementos',
    'construction',
    'CO',
    'es',
    '#003366',
    E'Eres un analista de campo experto para {implementation_name} ({industry}).\nAnaliza esta imagen de un punto de venta con ojo de auditor comercial.\n\nDescribe en detalle lo que observas, organizado en estas dimensiones:\n\n1. TIPO DE TOMA: ¿Es exterior (fachada), interior (góndola/mostrador), o detalle (producto/precio)?\n\n2. PRESENCIA INSTITUCIONAL:\n   - ¿Hay logos, avisos o letreros de la marca en fachada o interior?\n   - ¿Hay material POP? (banners, cenefas, exhibidores, stickers)\n   - ¿Es distribuidor oficial o punto independiente?\n\n3. PRESENCIA DE PRODUCTO:\n   - ¿Hay producto físico de la marca visible?\n   - ¿Cuánto espacio ocupa vs competencia?\n   - ALERTA: Si hay presencia institucional pero NO hay producto visible, marcarlo explícitamente.\n\n4. PRODUCTOS Y PRECIOS:\n   - Productos visibles (marcas, referencias, presentaciones)\n   - Precios visibles (etiquetas, letreros)\n   - Organizar por categoría\n\n5. COMPETENCIA:\n   - Marcas competidoras presentes y en qué categorías\n   - Promociones o material POP de competidores\n   - Marca dominante en espacio visual\n\n6. PERFIL DEL PUNTO:\n   - Categorías que maneja\n   - Nivel de surtido y organización (alto/medio/bajo)\n   - Señales de actividad comercial\n   - Tamaño estimado del punto (pequeño/mediano/grande)\n\nSé específico y objetivo. Si no puedes ver algo claramente, dilo.\nResponde en español, en párrafos cortos y concretos.',
    E'Eres un analista que debe identificar cuántas visitas de campo distintas\nhay en este conjunto de capturas enviadas por un representante de {implementation_name}.\n\nUna visita = un punto físico visitado.\nTipos de visita posibles: {visit_type_options}\n\nArchivos disponibles: {filenames}\n\nContexto capturado durante el día:\n{consolidated_context}\n\nIdentifica:\n1. Cuántas visitas distintas hay\n2. Qué archivos pertenecen a cada visita\n3. El tipo de cada visita ({visit_type_options})\n4. El nombre/ubicación inferida de cada punto\n5. Tu nivel de confianza (0-1) para cada agrupación\n6. Si hay archivos que no puedes asignar con confianza\n\nResponde SOLO en JSON siguiendo este schema exacto:\n{segmentation_schema}\n\nSi alguna visita tiene confidence < 0.75 o hay archivos sin asignar, pon needs_clarification: true\ny en clarification_message explica qué necesitas saber.'
)
ON CONFLICT (id) DO NOTHING;

-- 7. Backfill implementation_id on existing rows
UPDATE users SET implementation_id = implementation WHERE implementation_id IS NULL;
UPDATE sessions SET implementation_id = implementation WHERE implementation_id IS NULL;
UPDATE visit_reports SET implementation_id = implementation WHERE implementation_id IS NULL;

-- 8. Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_visit_types_impl ON visit_types(implementation_id);
CREATE INDEX IF NOT EXISTS idx_sessions_impl ON sessions(implementation_id);
CREATE INDEX IF NOT EXISTS idx_visit_reports_impl ON visit_reports(implementation_id);
