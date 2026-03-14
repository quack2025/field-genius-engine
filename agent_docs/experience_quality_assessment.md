# Field Genius Engine — Experience Quality Assessment (Phase 1)

**Date:** 2026-03-14
**Assessor:** Claude (code review of session_manager.py, webhook.py, pipeline.py, sender.py, pdf.py, segmenter.py)
**Framework:** 5 criteria — Discoverability, Clarity, Efficiency, Error Recovery, Trust

---

## Journey A: Field Executive (WhatsApp-only)

### Step 1: Send Media

| Criterion | Score | Evidence from Code | Gap |
|---|---|---|---|
| **Discoverability** | 1/5 | No onboarding message exists. `sender.py` has only `send_message()` and `send_media()` — no welcome or instruction flow. A new exec added via `/api/admin/.../users` gets ZERO guidance on what to capture or how. | **CRITICAL** — New user has no idea what to do |
| **Clarity** | 3/5 | `webhook.py:113` sends "Recibido" per file. Simple and clear. But no confirmation of file TYPE received (photo vs audio vs video). Location gets "Ubicacion recibida" (good). | Could say "Foto recibida" / "Audio recibido" for specificity |
| **Efficiency** | 4/5 | One acknowledgment per file. WhatsApp handles batching natively. No unnecessary round-trips. | Minor: if exec sends 10 photos, gets 10 "Recibido" messages — could be noisy |
| **Error Recovery** | 2/5 | `webhook.py:115-116` catches media processing errors but does NOT notify the user. `logger.error()` only. Exec thinks file arrived, but it didn't get stored. | **HIGH** — Silent failure. Exec loses data without knowing |
| **Trust** | 2/5 | "Recibido" confirms arrival but not storage. If Supabase upload fails after download, the "Recibido" was already sent (line 113 runs before error could occur... actually line 110 `handle_media` runs first, then 113). Looking closer: `download_and_store` (line 102) runs first, then `handle_media` (110), then `send_message` (113) — so "Recibido" is sent AFTER successful storage. **Good.** But if `download_and_store` fails, the except on line 115 silently drops it. | Trust OK on happy path. Broken on error path |

**Accumulated file count is invisible.** The exec has no way to know "I've sent 7 files today" without counting manually. No running tally.

---

### Step 2: Trigger Word ("reporte")

| Criterion | Score | Evidence from Code | Gap |
|---|---|---|---|
| **Discoverability** | 1/5 | Trigger words are `{"reporte", "generar", "listo", "fin", "report", "done"}` (session_manager.py:19). But exec is NEVER told these words. No onboarding, no help command. | **CRITICAL** — If exec writes "informe", "enviar", "procesar" → nothing happens, no feedback |
| **Clarity** | 4/5 | `session_manager.py:113` responds "Procesando X archivo(s). Te notifico cuando este listo." — clear message with file count. Empty session guard (line 97-101) returns "No tienes archivos acumulados hoy." — helpful. Already processing guard (line 73-79) returns "Tu reporte se esta procesando." — prevents double-trigger. | Good clarity on happy path |
| **Efficiency** | 5/5 | Single word triggers full pipeline. Can't be more efficient. | — |
| **Error Recovery** | 2/5 | If exec types a non-trigger word like "informe", it's saved as a text note (`session_manager.py:142-158`) with **no response** (action="text_added", message=None → webhook.py:141-143 does nothing). Exec thinks system is broken. | **HIGH** — Exec types wrong word, gets silence, doesn't know why |
| **Trust** | 3/5 | The "Procesando X archivo(s)" message is reassuring. But the wait time is unknown. | Exec doesn't know if 2 min or 20 min |

**Fuzzy trigger matching is missing.** "informe", "reportar", "listo!" (with punctuation), "Reporte!" all fail silently. `body.strip().lower()` handles case but not punctuation or near-matches.

---

### Step 3: Wait for Processing

| Criterion | Score | Evidence from Code | Gap |
|---|---|---|---|
| **Discoverability** | 1/5 | No progress indicators at all. `pipeline.py` goes through 7 steps (segmentation, extraction per visit, sheets, whatsapp delivery) with ZERO intermediate messages to the user. | **CRITICAL** — Black hole of 2-10 minutes |
| **Clarity** | 1/5 | The only message is "Procesando X archivo(s)" at the start. Then silence until the final summary. For a session with 15 files and 4 visits, this could be 5-10 minutes of silence. | Exec doesn't know: is it segmenting? extracting? writing to sheets? |
| **Efficiency** | 3/5 | Pipeline processes sequentially (visit by visit in `pipeline.py:204`). Vision + transcription are per-file, not parallelized within segmenter. Video extraction is sequential too. | Could parallelize vision analysis of multiple images |
| **Error Recovery** | 1/5 | If pipeline fails (`pipeline.py:285-293`), session status is set to "failed" but **NO message is sent to the user.** The exec waits forever. The `_send_whatsapp_delivery` only runs on success (line 265-266, inside the try block before the except). | **CRITICAL** — Pipeline failure = silent abandonment |
| **Trust** | 1/5 | Complete opacity. No progress, no ETA, no error notification. | Exec has no way to know if system is alive |

**This is the single biggest UX gap.** Pipeline failure is invisible to the user.

---

### Step 4: Receive Summary

| Criterion | Score | Evidence from Code | Gap |
|---|---|---|---|
| **Discoverability** | 4/5 | Summary arrives as WhatsApp message via `_send_whatsapp_delivery` (pipeline.py:102-123). If PDF is available, it's attached. Currently PDF is disabled (line 266 passes `None`). | Summary arrives in the same chat — easy to find |
| **Clarity** | 3/5 | `build_whatsapp_summary` (pdf.py:259-316) produces structured text: header with counts, then per-visit details with category summaries. Uses WhatsApp bold formatting (`*text*`). Shows first 3 items per array category. | Good structure but dense. Could benefit from emojis for scan-ability. Confidence % shown but not explained ("82% — is that good?") |
| **Efficiency** | 4/5 | Single message with all visits. Links to "Detalle completo en Google Sheets" (line 314). | No clickable link to the actual Sheet |
| **Error Recovery** | 1/5 | **No correction mechanism.** If AI extracted wrong prices or wrong visit type, exec has ZERO recourse. No "reply with correction" flow. No "this is wrong" handler. | **CRITICAL** — Wrong data goes to Sheets unchallenged |
| **Trust** | 2/5 | Confidence score is shown per visit but the exec doesn't know what it means. No explanation of "Confianza: 78%". No way to validate if prices/brands are correct without going to Sheets. | Exec must trust blindly or open Sheets to verify |

**The summary message has no GPS/location link.** Even though we now capture location, the summary doesn't include a Google Maps link for verification.

---

### Step 5: Post-Completion

| Criterion | Score | Evidence from Code | Gap |
|---|---|---|---|
| **Discoverability** | 1/5 | `session_manager.py:82-88`: if status is "completed" and exec sends trigger again: "Ya generaste tu reporte de hoy. Los archivos nuevos se incluiran en el reporte de manana." But this is misleading — files ARE accumulated but NEVER processed. | **CRITICAL** — Data loss. Promise of "tomorrow" never fulfilled (no cron/auto-process) |
| **Clarity** | 2/5 | The message implies tomorrow's report will include them, but there's no auto-trigger mechanism. | False promise |
| **Efficiency** | N/A | — | — |
| **Error Recovery** | 1/5 | No way to reopen a completed session. No way to append and re-process. The `failed` status allows retry (line 91-92) but `completed` does not. | **HIGH** — Exec who forgot photos is stuck |
| **Trust** | 1/5 | If exec discovers their report is incomplete, they have no recourse. | Trust-breaking moment |

---

## Journey A — Consolidated Score Card

| Step | Disc. | Clarity | Effic. | Error Rec. | Trust | **Avg** |
|---|---|---|---|---|---|---|
| Send Media | 1 | 3 | 4 | 2 | 2 | **2.4** |
| Trigger Word | 1 | 4 | 5 | 2 | 3 | **3.0** |
| Wait for Processing | 1 | 1 | 3 | 1 | 1 | **1.4** |
| Receive Summary | 4 | 3 | 4 | 1 | 2 | **2.8** |
| Post-Completion | 1 | 2 | — | 1 | 1 | **1.3** |
| **Step Average** | **1.6** | **2.6** | **4.0** | **1.4** | **1.8** | **2.2** |

**Overall Journey A Score: 2.2 / 5**

---

## Top 10 Findings (Ranked by Severity)

| # | Finding | Severity | Code Location | Fix Effort |
|---|---|---|---|---|
| **F1** | **Pipeline failure sends NO message to user** — exec waits forever | CRITICAL | `pipeline.py:285-293` — sets status=failed but no WhatsApp message | LOW — add `send_message()` in except block |
| **F2** | **No onboarding** — new exec gets zero guidance | CRITICAL | No code exists for this | MEDIUM — welcome message on first interaction |
| **F3** | **Non-trigger words get silence** — "informe" → no response | HIGH | `session_manager.py:141-143` — text_added returns message=None | LOW — add "No entendi. Escribe 'reporte' para generar tu informe" |
| **F4** | **No progress during pipeline** — 2-10 min black hole | HIGH | `pipeline.py:126-283` — no intermediate WhatsApp messages | MEDIUM — add messages at key milestones |
| **F5** | **Post-completion media is lost** — files accumulate but never process | HIGH | `session_manager.py:82-88` — misleading "tomorrow" message | MEDIUM — allow reopen or auto-process next day |
| **F6** | **No correction mechanism** — wrong data can't be fixed | HIGH | No code exists | HIGH — new correction flow needed |
| **F7** | **Media error is silent** — download failure not reported to user | MEDIUM | `webhook.py:115-116` — logs error but doesn't notify | LOW — add error message to user |
| **F8** | **Trigger word matching too strict** — no fuzzy match, no punctuation handling | MEDIUM | `session_manager.py:72` — exact match only | LOW — strip punctuation, add common aliases |
| **F9** | **No file count feedback** — exec can't see accumulated total | MEDIUM | `session_manager.py:47-53` — logs but doesn't tell user | LOW — include count in "Recibido" |
| **F10** | **Confidence score unexplained** — "78%" means nothing to exec | LOW | `pdf.py:285` — shows number without context | LOW — add interpretation text |

---

## Quick Wins (can implement in <30 min each)

### QW1: Notify on pipeline failure
```python
# pipeline.py, in the except block (line 285+):
from src.channels.whatsapp.sender import send_message
phone = session.get("user_phone", "")
if phone:
    await send_message(phone, "Hubo un error procesando tu reporte. Intenta enviar 'reporte' de nuevo. Si el problema persiste, contacta soporte.")
```

### QW2: Respond to non-trigger text
```python
# webhook.py, after the text_added case (line 141-143):
elif result["action"] == "text_added":
    # Hint about trigger words if the message looks like an intent to generate
    lower_body = body.lower().strip("!.?")
    intent_words = {"informe", "reportar", "enviar", "procesar", "generar reporte", "hacer reporte"}
    if lower_body in intent_words:
        await send_message(from_phone, "Para generar tu reporte escribe: reporte")
```

### QW3: Notify on media download failure
```python
# webhook.py, in the except block (line 115-116):
except Exception as e:
    logger.error("media_processing_failed", phone=phone, error=str(e))
    await send_message(from_phone, "No pude procesar ese archivo. Intenta enviarlo de nuevo.")
```

### QW4: File count in acknowledgment
```python
# webhook.py, replace line 113:
file_count = len(session.get("raw_files", [])) + 1
await send_message(from_phone, f"Recibido ({file_count} archivos hoy)")
```

### QW5: Progress message at pipeline milestones
```python
# pipeline.py, after Phase 1 completes (line 168):
phone = session.get("user_phone", "")
if phone and not segmentation.needs_clarification:
    from src.channels.whatsapp.sender import send_message
    await send_message(
        phone,
        f"Identifique {len(segmentation.visits)} visita(s). Extrayendo datos..."
    )
```

---

## Summary

La Journey A tiene una experiencia funcional en el happy path pero **falla gravemente en todos los edge cases y estados de error.** Los 3 problemas mas criticos son:

1. **Falla silenciosa del pipeline** (F1) — el ejecutivo queda esperando para siempre
2. **Cero onboarding** (F2) — un ejecutivo nuevo no sabe que hacer
3. **Texto no reconocido = silencio** (F3) — el ejecutivo piensa que el sistema no funciona

Los 5 quick wins (QW1-QW5) resuelven los 3 primeros findings con cambios menores al codigo existente.
