-- 014: Add vision_strategy column to implementations + create tiered test implementation
-- Run in Supabase SQL Editor

-- 1. Add vision_strategy column (default: sonnet_only for existing implementations)
ALTER TABLE implementations
  ADD COLUMN IF NOT EXISTS vision_strategy text NOT NULL DEFAULT 'sonnet_only';

-- 2. Add CHECK constraint
ALTER TABLE implementations
  ADD CONSTRAINT implementations_vision_strategy_check
  CHECK (vision_strategy IN ('sonnet_only', 'tiered'));

-- 3. Create tiered test implementation (copy of laundry_care with tiered vision)
INSERT INTO implementations (
  id, name, industry, country, language, primary_color, status,
  vision_system_prompt, segmentation_prompt_template, trigger_words,
  analysis_framework, vision_strategy
)
SELECT
  'laundry_care_tiered',
  'Cuidado de la Ropa (Tiered Vision)',
  industry, country, language, primary_color, 'active',
  vision_system_prompt, segmentation_prompt_template, trigger_words,
  analysis_framework,
  'tiered'
FROM implementations
WHERE id = 'laundry_care'
ON CONFLICT (id) DO UPDATE SET
  vision_strategy = 'tiered',
  status = 'active',
  name = 'Cuidado de la Ropa (Tiered Vision)';

-- 4. Copy visit types from laundry_care to laundry_care_tiered
INSERT INTO visit_types (implementation_id, slug, display_name, schema_json, sheets_tab, confidence_threshold, sort_order, is_active)
SELECT
  'laundry_care_tiered', slug, display_name, schema_json, sheets_tab, confidence_threshold, sort_order, is_active
FROM visit_types
WHERE implementation_id = 'laundry_care'
ON CONFLICT DO NOTHING;

-- 5. Verify
SELECT id, name, vision_strategy, status FROM implementations WHERE id IN ('laundry_care', 'laundry_care_tiered');
