-- 026: Add sample_report to onboarding_config for demo impls
-- Also update post_switch_message to mention the "ejemplo" command
-- This lets curious visitors see the output before committing to send their own photo.

BEGIN;

-- ============================================
-- Retail / CPG demo sample report
-- ============================================
UPDATE implementations
SET onboarding_config = onboarding_config
    || jsonb_build_object(
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
        E'¿Listo para probarlo con tus propias fotos? 📸'
    )
WHERE id = 'laundry_care';

-- ============================================
-- Telecom demo sample report
-- ============================================
UPDATE implementations
SET onboarding_config = onboarding_config
    || jsonb_build_object(
        'post_switch_message',
        E'¡Perfecto! Empezamos con el *Demo Telecom* 📡\n\n' ||
        E'Estás por ver cómo funciona Radar para *ejecutivos de telecomunicaciones* que capturan inteligencia de calle mientras están en ruta.\n\n' ||
        E'📍 *Escenario:* Sos un ejecutivo o analista de una operadora telecom. Mientras manejás o caminás por la ciudad, ves publicidad, promociones y POP de la competencia. Sacás una foto rápida y listo.\n\n' ||
        E'Tomá o enviá una foto de:\n' ||
        E'• Publicidad de competidores (Claro, Movistar, Liberty, Tigo, etc.)\n' ||
        E'• Promociones en calle, vallas, banners\n' ||
        E'• Material POP en fachadas\n' ||
        E'• Puntos de venta o kioscos de otras operadoras\n' ||
        E'• Ofertas publicadas en puntos físicos\n\n' ||
        E'En ~15-20 segundos te devuelvo un análisis con:\n' ||
        E'✓ Competidor identificado y su oferta\n' ||
        E'✓ Precios y condiciones promocionales detectadas\n' ||
        E'✓ Amenazas competitivas relevantes\n' ||
        E'✓ Insights de posicionamiento de marca\n\n' ||
        E'👉 Escribe *ejemplo* si primero querés ver cómo luce un reporte de muestra\n' ||
        E'📸 O enviame directamente tu foto',

        'sample_report',
        E'*📡 Reporte de Muestra — Demo Telecom*\n' ||
        E'_Ejecutivo: Carlos Ruiz · Captura: Av. Central, San José_\n' ||
        E'━━━━━━━━━━━━━━━━━━━━\n\n' ||
        E'*Resumen ejecutivo*\n' ||
        E'Valla publicitaria de *Claro Costa Rica* con oferta agresiva detectada. Amenaza competitiva ALTA en zona Heredia. 2 ofertas de competencia identificadas.\n\n' ||
        E'*🎯 Competidor detectado*\n' ||
        E'• *Claro* — Valla outdoor 3x6m, Av. Central con San Pedro\n' ||
        E'• Material bilingüe (español + inglés turístico)\n' ||
        E'• Branding consistente con campaña nacional\n\n' ||
        E'*💵 Ofertas publicadas*\n\n' ||
        E'*1. Internet Hogar Claro*\n' ||
        E'• 300 Mbps + TV\n' ||
        E'• ₡15,900/mes (6 meses)\n' ||
        E'• Instalación gratis\n' ||
        E'• Vigencia: 30 días\n\n' ||
        E'*2. Móvil Pospago Claro*\n' ||
        E'• 50GB + llamadas ilimitadas\n' ||
        E'• ₡11,500/mes\n' ||
        E'• 12 meses de fidelización\n\n' ||
        E'*⚠️ Amenazas competitivas*\n' ||
        E'🔴 *HIGH:* Precio Claro Internet es 28% menor que el plan equivalente en la zona. Recomendación: activar retención preventiva Heredia.\n' ||
        E'🟡 *MEDIUM:* Incluyen TV en el bundle — diferenciación que tu oferta actual no comunica.\n\n' ||
        E'*💡 Insights*\n' ||
        E'1. Claro ejecuta campaña intensiva en Heredia (zona de crecimiento)\n' ||
        E'2. Comunicación enfocada en precio, no en calidad de servicio\n' ||
        E'3. Oportunidad: contracampaña en calidad de señal y soporte técnico\n' ||
        E'4. Revisar si tu fuerza comercial conoce la promo (brief a retail)\n\n' ||
        E'━━━━━━━━━━━━━━━━━━━━\n' ||
        E'_Este es un reporte de muestra generado desde una foto real._\n\n' ||
        E'¿Listo para probarlo con tus propias fotos? 📸'
    )
WHERE id = 'demo_telecom';

COMMIT;

-- Verify
SELECT id, name,
       LENGTH(onboarding_config->>'sample_report') as sample_chars,
       LENGTH(onboarding_config->>'post_switch_message') as post_switch_chars
FROM implementations
WHERE id IN ('laundry_care', 'demo_telecom')
ORDER BY id;
