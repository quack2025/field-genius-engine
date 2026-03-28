-- 009: Add country_config to implementations + role/country to users
-- Run in Supabase SQL Editor

-- 1. Add country_config JSONB to implementations
ALTER TABLE implementations ADD COLUMN IF NOT EXISTS country_config jsonb DEFAULT '{}'::jsonb;

-- 2. Add role and country to users
ALTER TABLE users ADD COLUMN IF NOT EXISTS role text DEFAULT 'field_agent';
ALTER TABLE users ADD COLUMN IF NOT EXISTS country text DEFAULT 'CO';
ALTER TABLE users ADD COLUMN IF NOT EXISTS allowed_frameworks text[] DEFAULT '{}';

-- 3. Add country to sessions (denormalized for fast filtering)
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS country text;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS user_role text;

-- 4. Seed country_config for telecable
UPDATE implementations SET country_config = '{
  "CR": {
    "currency": "CRC",
    "currency_symbol": "₡",
    "country_name": "Costa Rica",
    "competitors": ["Claro", "Movistar", "Liberty", "Kolbi (ICE)"],
    "products": ["Internet Fibra", "TV Digital", "Telefonia", "Triple Play", "Internet Inalambrico"],
    "context": "Telecable es un operador de cable, internet y telefonia con cobertura urbana en Costa Rica. Compite principalmente contra Claro (America Movil), Liberty (ex Cable Tica) y Kolbi (ICE, operador estatal)."
  },
  "GT": {
    "currency": "GTQ",
    "currency_symbol": "Q",
    "country_name": "Guatemala",
    "competitors": ["Claro", "Tigo", "Movistar"],
    "products": ["Internet Fibra", "TV Digital", "Telefonia", "Triple Play"],
    "context": "Mercado guatemalteco dominado por Claro y Tigo. Telecable busca posicionarse con calidad de servicio y fibra optica."
  },
  "HN": {
    "currency": "HNL",
    "currency_symbol": "L",
    "country_name": "Honduras",
    "competitors": ["Claro", "Tigo"],
    "products": ["Internet Fibra", "TV Digital", "Telefonia", "Triple Play"],
    "context": "Mercado hondureno con fuerte presencia de Tigo y Claro. Telecable ofrece diferenciacion via servicio al cliente."
  }
}'::jsonb
WHERE id = 'telecable';

-- 5. Seed country_config for laundry_care
UPDATE implementations SET country_config = '{
  "CO": {
    "currency": "COP",
    "currency_symbol": "$",
    "country_name": "Colombia",
    "competitors": ["Ariel (P&G)", "Fab (Henkel)", "Dersa", "Top (Henkel)", "ACE (P&G)", "Omo (Unilever)"],
    "products": ["Detergente polvo", "Detergente liquido", "Suavizante", "Quitamanchas", "Jabon barra", "Pods/capsulas"],
    "context": "Mercado colombiano de cuidado de ropa dominado por P&G (Ariel) y Henkel (Fab). Canal moderno (Exito, Jumbo, D1, Ara) y tradicional (tiendas de barrio) coexisten."
  }
}'::jsonb
WHERE id = 'laundry_care';

-- 6. Define standard roles
COMMENT ON COLUMN users.role IS 'Standard roles: field_agent (default), sales, operator, marketing, supervisor, manager';

-- 7. Update existing users with default role
UPDATE users SET role = 'field_agent' WHERE role IS NULL;
