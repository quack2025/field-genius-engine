# Runbook — Sprint Demo POC (Retail + POC gating + Location capture)

> **Propósito:** pasos manuales que deben ejecutarse fuera del código para que Sprint Demo-POC quede completamente funcional en producción. El código y las migraciones SQL ya están desplegados. Esta guía es para un **analista** o cualquier persona con acceso a Twilio Console, Supabase SQL Editor y el backoffice de Radar Xponencial.
>
> **Tiempo estimado:** 15-25 min (depende de si ya conoces Twilio Content Editor).
>
> **Prerrequisitos:**
> - Acceso a [Twilio Console](https://console.twilio.com) con permisos de escritura sobre Messaging / Content Editor
> - Acceso a [app.xponencial.net](https://app.xponencial.net) como usuario `admin` o `superadmin`
> - (Opcional) Acceso al SQL Editor de Supabase del proyecto `vrkkafmbtonrpkjcrust` por si hay que verificar estado

---

## Contexto rápido

Antes de este sprint, el card inicial del WhatsApp público mostraba dos botones: **Retail** y **Telecom**. Ambos llevaban a demos abiertos a cualquier visitante.

Con el sprint:
- Los POCs (Argos y Telecable) ya **no son demos abiertos**. Son contenido personalizado para clientes específicos. Quien quiera acceder debe escribir el nombre de su empresa.
- El card nuevo debe mostrar **Retail** y **POC**. Al tapear POC, el bot pide al usuario escribir `argos` o `telecable`.
- Quien escriba otra palabra es redirigido al demo Retail con un mensaje amigable.
- Quien intente enviar una foto antes de escribir el nombre es bloqueado hasta que lo escriba.

Para que esto funcione completamente, hay que **crear el nuevo Content Template en Twilio** y **configurarlo en el backoffice**. El código ya reconoce las nuevas palabras clave, las nuevas columnas de estado en la base de datos ya están creadas, y los proyectos `telecable` y `argos` ya están convertidos a POCs abiertos vía keyword.

---

## Paso 1 — Crear el nuevo Content Template en Twilio Console

### 1.1 Entrar al Content Editor

- Ir a [console.twilio.com](https://console.twilio.com)
- Menú lateral: **Messaging** → **Content Editor**
- Click en **Create new** → **Quick Reply**

### 1.2 Rellenar el template

Usar exactamente estos valores:

| Campo | Valor |
|-------|-------|
| **Friendly name** | `radar_welcome_retail_poc_v1` |
| **Language** | `Spanish` |
| **Content type** | `Quick Reply` |
| **Body** | Ver bloque abajo |

**Body del mensaje** (copiar/pegar tal cual, respetando saltos de línea):

```
Bienvenido a Radar Xponencial 👋

Este demo convierte fotos, videos y audios en análisis de campo con IA.

¿Qué demo quieres ver?
```

### 1.3 Botones (Quick Reply)

| Posición | Title | Id |
|----------|-------|-----|
| Button 1 | `Retail` | `btn_retail` |
| Button 2 | `POC` | `btn_poc` |

**Importantes:**
- El campo **Title** es exactamente `Retail` y `POC` (con esa capitalización y sin espacios). El código reconoce ambos casos (mayúscula/minúscula), pero respetar esto evita confusiones.
- El **Id** es solo interno de Twilio, no importa mucho mientras sea único.
- **No** añadas un tercer botón.

### 1.4 Guardar y enviar a aprobación

- Click **Save** en la esquina superior derecha
- Click **Submit for WhatsApp approval**
- Esperar la aprobación (usualmente 5-15 min, a veces hasta algunas horas)
- Cuando el status cambie a **Approved**, volver al detalle del template

### 1.5 Copiar el Content SID

- En la pantalla del template aprobado, buscar el campo **Content SID**
- Tiene el formato `HXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` (32 caracteres después de `HX`)
- Copiar todo ese string

> ✅ **Anotar aquí el SID que copiaste**: `HX________________________________`

---

## Paso 2 — Configurar el nuevo SID en el backoffice

### 2.1 Abrir la configuración de Telecable

- Ir a [app.xponencial.net](https://app.xponencial.net)
- Click en **Proyectos** en el menú lateral
- Buscar **Telecable** y click en el proyecto (NO en Argos, NO en Laundry Care — Telecable es el que recibe el primer contacto por el número `+17792284312`)
- Asegurarte de estar en el tab **Configuración**

### 2.2 Pegar el SID

- Scroll hasta la sección **Mensajes de Onboarding (WhatsApp)**
- Buscar el campo **Content SID del welcome** (tiene un placeholder `HX...`)
- Pegar el SID que copiaste en el paso 1.5
- Click **Guardar** al final de la sección de Config
- Confirmar que aparece el mensaje "Guardado" sin errores

### 2.3 (Opcional pero recomendado) Repetir en Laundry Care y Argos

Solo por defensa — si un día Telecable se queda sin `+17792284312` y otro proyecto hereda el número, queremos que el welcome siga siendo el correcto.

- Abrir **Laundry Care** → Config → Mensajes de Onboarding → pegar el mismo SID → Guardar
- Abrir **Argos** → Config → Mensajes de Onboarding → pegar el mismo SID → Guardar

---

## Paso 3 — Recargar el cache del backend

El backend guarda la configuración de cada proyecto en memoria durante 5 minutos. Para que los cambios del backoffice tomen efecto inmediatamente, hay que invalidar el cache.

### Opción A — Desde el botón del sidebar (más fácil)

- En el backoffice, click en el ícono 🔄 **Recargar cache** en la parte inferior del menú lateral
- Debería aparecer un toast "Cache recargado"

### Opción B — Via curl / Postman (solo si la opción A no funciona)

```bash
curl -X POST https://zealous-endurance-production-f9b2.up.railway.app/api/admin/reload-config \
  -H "Authorization: Bearer <tu_token_de_supabase>"
```

(Usar el token de `localStorage.supabase.auth.token` si lo necesitas sacar del browser).

---

## Paso 4 — Verificación end-to-end en WhatsApp

Abre un chat de WhatsApp con el número **+1 (779) 228-4312** desde tu celular. Para cada escenario, si vas a repetir el flujo tenés que **borrar tu usuario** en Supabase (ver sección "Reset" al final).

### 4.1 Card de bienvenida

- Enviar: `hola`
- **Debe llegar:** un card con los botones **Retail** y **POC**
- Si llega texto plano en lugar del card → el SID no está bien configurado, volver al Paso 2
- Si llega el card viejo (Retail/Telecom) → el cache no se recargó, volver al Paso 3

### 4.2 Flujo Retail feliz

- Tapear **Retail** (o escribir "retail")
- **Debe llegar:** el post_switch_message de "Demo Retail CPG"
- Enviar una foto de una góndola o anaquel
- **Debe llegar:** dos mensajes
  1. "Recibí tu foto 📸 (1 archivo)..."
  2. "¿Dónde tomaste esto? 📍..." (el prompt de ubicación)
- Responder con texto: `Mercadona Madrid centro`
- **Debe llegar:** "Anotado 📍 _Mercadona Madrid centro_..."
- Enviar una segunda foto
- **Debe llegar:** ack normal, SIN volver a preguntar ubicación
- Escribir: `generar`
- **Debe llegar:** "Generando análisis..." + reporte (15-25s después) con **la ubicación mencionada en el header y en los hallazgos**

### 4.3 Flujo POC Argos

- Reset de usuario (ver abajo)
- `hola` → tapear **POC**
- **Debe llegar:** "Los POCs de Radar Xponencial están personalizados... Escribe *argos* o *telecable*"
- Escribir: `argos`
- **Debe llegar:** post_switch de Argos (menciona ferreterías y obras)
- Enviar foto de una ferretería o punto de venta de materiales de construcción
- Prompt de ubicación → responder con texto
- `generar` → reporte con frameworks de construcción (Cemex, Argos, cementos, ferreterías, obras)

### 4.4 Flujo POC Telecable

- Reset → `hola` → **POC** → escribir `telecable`
- **Debe llegar:** post_switch de Telecable
- Foto de publicidad/antena/tienda telecom → ubicación → `generar` → reporte telecom (competidor, cliente, cobertura)

### 4.5 Flujo POC con nombre incorrecto

- Reset → `hola` → **POC** → escribir `xponencial`
- **Debe llegar:** "No reconocí ese cliente como un POC disponible... Te llevo al Demo Retail general..." + el post_switch de Retail

### 4.6 Flujo POC con foto antes de escribir nombre

- Reset → `hola` → **POC** → enviar una foto sin escribir nada
- **Debe llegar:** "Primero dime el nombre de tu empresa: *argos* o *telecable*"
- La foto **NO** debe procesarse (verificar en Supabase: `SELECT count(*) FROM session_files WHERE session_id IN (SELECT id FROM sessions WHERE user_phone = 'TU_TELEFONO' AND date = CURRENT_DATE) AND type = 'image';` → debe ser 0)

### 4.7 Flujo de ubicación compartida por WhatsApp nativa

- Reset → tapear **Retail** → enviar foto
- Cuando llegue el prompt de ubicación, usar el 📎 de WhatsApp → **Ubicación** → **Enviar mi ubicación actual**
- **Debe llegar:** "Ubicación recibida 📍 Sigue enviando fotos..."
- Enviar `generar` → reporte que menciona las coordenadas o la dirección

---

## Reset de usuario para testing

Hay dos opciones, de fácil a más invasivo:

### Opción A — Comando WhatsApp `reset` (recomendado)

Desde tu chat de WhatsApp con el +17792284312, simplemente escribe:

```
reset
```

(También funcionan: `reiniciar`, `borrar todo`, `nueva conversación`, `empezar de cero`, `start over`.)

El bot:
1. Borra tu sesión del día y todos los archivos acumulados
2. Resetea tu user (implementation, accepted_terms, todos los pending_*)
3. Confirma "✅ Listo, empezamos de cero"
4. Re-envía el card de bienvenida inmediatamente

Después puedes empezar el flujo que quieras (Retail, POC, etc) sin tocar Supabase.

**Solo funciona en proyectos con `demo_mode=true`**. En un proyecto real (cuando algún día existan field-agents whitelisted), `reset` no hace nada para evitar que un usuario se borre su día por accidente.

### Opción B — SQL en Supabase (para casos extremos)

Si el comando WhatsApp falla por alguna razón o necesitas borrar el user row entero (no solo resetearlo), usa este SQL en el editor de Supabase:

```sql
-- Reemplazar el teléfono con el tuyo (formato +CCXXXXXXXXX)
DO $$
DECLARE
  target_phone text := '+34691146671';  -- ← CAMBIAR POR TU TELÉFONO
BEGIN
  DELETE FROM session_files
   WHERE session_id IN (
     SELECT id FROM sessions
     WHERE user_phone = target_phone AND date = CURRENT_DATE
   );
  DELETE FROM sessions WHERE user_phone = target_phone AND date = CURRENT_DATE;
  DELETE FROM users WHERE phone = target_phone;
END $$;
```

La diferencia con la Opción A: este SQL **borra completamente** el row del user, lo cual reescribe historial. La Opción A solo deja al user en estado "fresh visitor" sin perder el row.

---

## Rollback (si algo sale muy mal)

Si alguna de las verificaciones falla catastróficamente y necesitas revertir el gating de POCs:

### Revertir código (rara vez necesario)

```bash
cd field-genius-engine
git log --oneline -20
# Buscar el commit ANTES de "feat(demo): POC gating"
git revert <hash-del-commit-de-POC-gating>
git push
```

Railway re-desplegará automáticamente en ~2 min.

### Revertir configuración en DB

```sql
-- Restaurar telecable como whitelist (estado previo al sprint)
UPDATE implementations SET
  access_mode = 'whitelist',
  demo_keywords = ARRAY[]::text[],
  fallback_implementation = 'laundry_care',
  onboarding_config = onboarding_config - 'is_poc' - 'poc_company_label'
WHERE id = 'telecable';

-- Desactivar argos de nuevo
UPDATE implementations SET status = 'inactive' WHERE id = 'argos';

-- Reactivar demo_telecom
UPDATE implementations SET status = 'active' WHERE id = 'demo_telecom';
```

Llamar `reload-config` después.

### Volver al Content Template viejo

Si el nuevo template causa problemas:
- Editar telecable/laundry_care/argos en backoffice → Content SID del welcome → pegar el SID viejo: `HX456f8262c556340d0c9ecee2c549dedb`
- Recargar cache

---

## Contactos y troubleshooting

| Problema | Posible causa | Acción |
|----------|---------------|--------|
| El card no llega (llega texto) | SID no configurado o cache viejo | Paso 2 + Paso 3 |
| Llega el card viejo (Retail/Telecom) | Template viejo todavía linkeado | Paso 2 con el SID nuevo |
| "POC" no activa el prompt | Cache viejo del impl_config | Paso 3 |
| Escribir "argos" no cambia de demo | Cache del keyword index (5 min TTL) | Paso 3 |
| 500 en cualquier endpoint del backoffice | Error en el backend | Revisar Railway logs y reportar |
| "Error al generar reporte" después de `generar` | Probablemente un archivo corrupto en la sesión | Reset user + repetir el flujo |

Para cualquier cosa que no esté en esta lista, **pingar a Jorge** con:
1. El teléfono que estás usando para el test
2. El paso exacto donde se rompió
3. Screenshot del mensaje de WhatsApp
4. Timestamp aproximado (minuto + zona horaria)

---

## Referencia — Lo que YA está hecho por el desarrollador

No tocar nada de esto salvo que se indique en el rollback:

- ✅ Migración `sql/032_poc_gating.sql` ya corrió (columnas `pending_poc_selection_at`, `pending_location_request_at` en `users`; `telecable` y `argos` como POC abiertos; `demo_telecom` inactivo)
- ✅ Código nuevo en producción (commit `80f351a` + fix `eda7d90`)
- ✅ Post_switch_message de Argos configurado con texto de construcción/ferreterías
- ✅ Helpers en `supabase_client.py` para el estado pending
- ✅ Handlers en `webhook.py` para POC flow y location capture
