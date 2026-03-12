-- Seed data: 3 ejecutivos de prueba para Argos (Colombia)

INSERT INTO users (implementation, phone, name, role, notification_group)
VALUES
    ('argos', '+573001234567', 'Carlos Andrés Restrepo', 'executive', NULL),
    ('argos', '+573109876543', 'María Fernanda López', 'executive', NULL),
    ('argos', '+573205551234', 'Juan Pablo Herrera', 'manager', NULL)
ON CONFLICT (phone) DO NOTHING;

-- 1 sesión de prueba completada para Carlos
INSERT INTO sessions (implementation, user_phone, user_name, date, status, raw_files)
VALUES (
    'argos',
    '+573001234567',
    'Carlos Andrés Restrepo',
    CURRENT_DATE,
    'completed',
    '[
        {"filename": "img_001.jpg", "type": "image", "timestamp": "2026-03-12T10:15:00-05:00"},
        {"filename": "audio_01.ogg", "type": "audio", "timestamp": "2026-03-12T10:30:00-05:00"},
        {"filename": "img_002.jpg", "type": "image", "timestamp": "2026-03-12T10:45:00-05:00"}
    ]'::jsonb
);
