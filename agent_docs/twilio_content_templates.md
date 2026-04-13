# Twilio Content Templates — Interactive WhatsApp Messages

## Context

Radar Xponencial sends interactive messages (quick-reply buttons, list pickers) via **Twilio Content Templates**. These replace plain-text welcome messages with tappable options, which is much better UX than asking users to type keywords.

**Why Content Templates?**
- Users tap instead of typing ("Retail" button vs. typing "retail")
- Professional card-style appearance in WhatsApp
- Works within the 24-hour customer service window without Meta pre-approval
- Pre-approved templates (business-initiated) also supported when needed later

## Setup — Demo Menu for +17792284312

### Step 1: Create a Quick Reply template in Twilio Console

1. Go to Twilio Console → **Messaging** → **Content Editor**
2. Click **Create new content template**
3. Configure:
   - **Name:** `radar_demo_menu`
   - **Language:** `es_MX` (or `es`)
   - **Channel:** WhatsApp
   - **Content type:** **Quick Reply**
4. Body:
   ```
   Bienvenido a *Radar Xponencial*.
   Este número ofrece demos de nuestra plataforma de inteligencia de campo con IA.

   ¿Qué demo te gustaría ver?
   ```
5. Quick Reply buttons (title = what user sees, must match the target impl's demo_keyword):
   - Button 1: title = `Retail`, id = `retail`
   - Button 2: title = `Telecom`, id = `telecom`
6. Save. Get the **Content SID** (format: `HXxxxxxxxxxxxxxxxxxxxxxxxxxxx`)

### Step 2: Configure the implementation in backoffice

1. Open backoffice → Proyectos → `laundry_care` (o el proyecto que owns el número demo)
2. Config tab → Mensajes de Onboarding → **Welcome Content SID**
3. Paste the `HX...` SID
4. Save

### Step 3: Test

Send "hola" to the demo number from a non-registered phone. You should receive a card with tappable "Retail" and "Telecom" buttons instead of the plain text welcome.

When a user taps "Retail":
- Twilio sends a webhook with `Body=Retail` (the button title)
- The webhook's keyword-routing logic matches `retail` → switches user to `laundry_care`
- ACK is sent

## How the code handles interactive replies

When a user taps a quick-reply button, Twilio sends a webhook just like a normal text message but with `Body` equal to the button's **title**. Our existing keyword routing handles this:

```python
# webhook.py — Step 1: Keyword override
if body and body.strip():
    first_token = body.strip().lower().split()[0]
    matched_impl = await get_impl_by_keyword(first_token)
    if matched_impl and matched_impl != resolved_impl:
        # ... switch user + ACK
```

**Important:** button titles must start with a word that matches a `demo_keywords` entry of the target implementation. So for the demo menu above:
- `laundry_care.demo_keywords = ['retail', 'cpg', 'shopper']` → button title "Retail" matches
- `demo_telecom.demo_keywords = ['telecom', 'telco', 'demo']` → button title "Telecom" matches

## Advanced: List Picker (more than 3 options)

Quick Reply supports max 3 buttons. For more options, use **List Picker**:

1. Content Editor → Create → Content type: **List Picker**
2. Body + footer text
3. Button text (e.g., "Ver demos")
4. Sections with items:
   - Section: "Demos Disponibles"
     - Item 1: `Retail` — "CPG, góndolas, precios"
     - Item 2: `Telecom` — "Competencia, cliente, cobertura"
     - Item 3: `Manufactura` — "Procesos, calidad, seguridad"

Same webhook handling applies — when user taps an item, `Body=<item title>`.

## Fallback behavior

If `welcome_content_sid` is NOT set OR the Content API call fails, the webhook falls back to sending the plain-text `welcome_message` from `onboarding_config`. This means:
- You can configure a Content SID later without changing code
- If Twilio's Content API is down, users still get a (less pretty) text welcome
- Dev/test environments without templates still work with plain text

## Gotchas

- **Template creation takes a few seconds** — not instant after saving in Console
- **Content SID is per-account** — different Twilio accounts have different SIDs
- **Button payloads:** Twilio sends `Body=<button title>` in the inbound webhook. There's no separate "payload" field for WhatsApp. Design titles to match keywords.
- **Rate limits:** Content API calls count against Twilio messaging rate limits
- **24h window:** Content templates can be sent to a user within 24h of their last inbound message WITHOUT template approval. For business-initiated messages after 24h, the template must be pre-approved by Meta
- **Media URLs** in content templates require HTTPS

## Related files

- `src/channels/whatsapp/sender.py` — `send_content_template()` function
- `src/channels/whatsapp/webhook.py` — `_send_welcome()` helper (uses content_sid if set)
- `src/engine/config_loader.py` — `onboarding_config.welcome_content_sid`
