-- 029: Restore proper demo state after onboarding_config got partially wiped
-- by backoffice saves that replaced (not merged) the JSONB column.
-- Also restores telecable access_mode to whitelist so fallback fires.

BEGIN;

-- ═══════════════════════════════════════════════════════════════
-- 1. TELECABLE: restore whitelist mode + add content_sid as safety net
-- ═══════════════════════════════════════════════════════════════
UPDATE implementations
SET access_mode = 'whitelist',
    onboarding_config = onboarding_config || jsonb_build_object(
        'require_terms', false,
        'welcome_content_sid', 'HX456f8262c556340d0c9ecee2c549dedb'
    )
WHERE id = 'telecable';

-- ═══════════════════════════════════════════════════════════════
-- 2. LAUNDRY_CARE: restore post_switch_message + sample_report
-- ═══════════════════════════════════════════════════════════════
UPDATE implementations
SET onboarding_config = onboarding_config || jsonb_build_object(
    'post_switch_message',
    E'¡Perfecto! Empezamos con el *Demo Retail / CPG* 📸\n\n' ||
    E'Estás por ver cómo funciona Radar para equipos de *trade marketing y mercadería* que hacen visitas a puntos de venta.\n\n' ||
    E'📍 *Escenario:* Sos una persona de mercadeo o trade marketing visitando un supermercado, farmacia o punto de venta. Querés capturar rápido el estado del anaquel sin llenar formularios.\n\n' ||
    E'Tomá o enviá una foto de:\n' ||
    E'• Una góndola de supermercado o hipermercado\n' ||
    E'• Un anaquel de farmacia o droguería\n' ||
    E'• Exhibición con precios y promociones\n' ||
    E'• Punto de venta de tu categoría o la competencia\n\n' ||
    E'En ~15-20 segundos te devuelvo un análisis con:\n' ||
    E'✓ Marcas identificadas y share of shelf\n' ||
    E'✓ Precios y promociones visibles\n' ||
    E'✓ Estado del anaquel (agotados, desorden)\n' ||
    E'✓ Oportunidades de ejecución en punto\n\n' ||
    E'👉 Escribe *ejemplo* si primero querés ver cómo luce un reporte de muestra\n' ||
    E'📸 O enviame directamente tu foto',

    'sample_report',
    E'*📊 Reporte de Muestra — Demo Retail CPG*\n' ||
    E'_Ejecutivo: María López · Visita: Supermercado La Colonia, San José_\n' ||
    E'━━━━━━━━━━━━━━━━━━━━\n\n' ||
    E'*Resumen ejecutivo*\n' ||
    E'Anaquel de cuidado personal en buen estado general (9/10). Dominan 3 marcas: Rexona, Dove y Axe. Precios promedio ₡2,800–₡3,500. Se detectaron 2 agotados críticos y 1 oportunidad de ejecución.\n\n' ||
    E'*🏷️ Share of Shelf*\n' ||
    E'• *Rexona* — 38% (líder, 12 SKUs)\n' ||
    E'• *Dove* — 24% (8 SKUs)\n' ||
    E'• *Axe* — 18% (6 SKUs, nivel manos)\n' ||
    E'• *Nivea* — 12% (4 SKUs, nivel ojos)\n' ||
    E'• Otras — 8%\n\n' ||
    E'*💰 Precios detectados*\n' ||
    E'• Rexona Men Clinical 50ml — ₡3,195\n' ||
    E'• Dove Invisible Dry 150ml — ₡2,890\n' ||
    E'• Axe Apollo 150ml — ₡2,750\n' ||
    E'• Nivea Black & White 150ml — ₡3,450\n\n' ||
    E'*⚠️ Alertas*\n' ||
    E'🔴 *AGOTADO crítico:* Rexona Women Crystal Clear 150ml — estante vacío nivel ojos\n' ||
    E'🔴 *Facing incorrecto:* Dove Original volteado, etiqueta no visible\n' ||
    E'🟡 *Promoción sin comunicación:* Axe 2x1 sin cenefa\n\n' ||
    E'*💡 Oportunidades de ejecución*\n' ||
    E'1. Reponer Rexona Women (nivel ojos = alta rotación)\n' ||
    E'2. Reorientar 3 facings de Dove Original\n' ||
    E'3. Instalar cenefa Axe 2x1 (impacto visual 0 actual)\n' ||
    E'4. Evaluar cross-merchandising categoría femenina (espacio vacío nivel medio)\n\n' ||
    E'━━━━━━━━━━━━━━━━━━━━\n' ||
    E'_Este es un reporte de muestra generado desde una foto real._\n\n' ||
    E'¿Listo para probarlo con tus propias fotos? 📸',

    'require_terms', false
)
WHERE id = 'laundry_care';

-- ═══════════════════════════════════════════════════════════════
-- 3. Verify
-- ═══════════════════════════════════════════════════════════════
SELECT id,
       whatsapp_number,
       access_mode,
       fallback_implementation,
       onboarding_config->>'welcome_content_sid' AS content_sid,
       onboarding_config->>'require_terms' AS require_terms,
       onboarding_config->>'post_switch_message' IS NOT NULL AS has_post_switch,
       onboarding_config->>'sample_report' IS NOT NULL AS has_sample
FROM implementations
WHERE id IN ('laundry_care', 'telecable', 'demo_telecom')
ORDER BY id;

COMMIT;
