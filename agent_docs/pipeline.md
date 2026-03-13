# Pipeline — How Sessions Become Reports

File: `src/engine/pipeline.py`

## Daily Batch Flow

```
DURING THE DAY (accumulation)
─────────────────────────────
User sends media via WhatsApp → engine responds "Recibido"
Nothing is processed. Files accumulate in session.raw_files.

END OF DAY (trigger)
────────────────────
User sends: "reporte" | "generar" | "listo" | "fin"
→ session_manager detects trigger word
→ pipeline.process_session(session_id) runs
```

## Pipeline Steps (process_session)

### Step 1: Load Session
- Fetch session from Supabase by ID
- Read raw_files array (all accumulated media)

### Step 2: Phase 1 — Segmentation
- Status → `segmenting`
- For each file in raw_files:
  - Audio → Whisper transcription
  - Image → Claude Sonnet vision analysis
  - Video → ffmpeg frame extraction → Sonnet analysis
- Claude Sonnet receives all context and produces visit map:

```json
{
  "sessions": [
    {
      "id": "session-1",
      "inferred_location": "Ferreteria El Constructor",
      "visit_type": "ferreteria",
      "confidence": 0.92,
      "files": ["img_001.jpg", "audio_01.ogg"],
      "time_range": "10:15 - 10:52"
    }
  ],
  "needs_clarification": false
}
```

### Step 3: Clarification Check
- If `needs_clarification: true`:
  - Status → `needs_clarification`
  - Send question to user via WhatsApp
  - Pipeline pauses, awaits user response
  - User reply triggers `resume_after_clarification()`

### Step 4: Phase 2 — Extraction
- Status → `processing`
- For each identified visit:
  1. Load visit type schema (via ConfigLoader)
  2. `schema_builder.build_system_prompt(schema_json)` → dynamic prompt
  3. Claude Haiku extracts structured data
  4. Parse and validate JSON response

### Step 5: Save Reports
- One `visit_reports` row per identified visit
- `extracted_data` contains full Claude JSON output

### Step 6: Outputs (fire-and-forget)
- **Google Sheets**: One tab per visit type, columns from schema
- **PDF**: WeasyPrint (currently disabled — needs cairo/pango on Railway)
- **Gamma**: Auto-generated presentation (currently disabled)

### Step 7: WhatsApp Delivery
- Text summary sent to executive
- PDF attached if available
- Status → `completed`

## AI Models Used

| Model | ID | Purpose |
|-------|----|---------|
| Claude Sonnet | `claude-sonnet-4-20250514` | Vision analysis, segmentation |
| Claude Haiku | `claude-haiku-4-5-20251001` | Structured extraction (fast, cheap) |
| Whisper | OpenAI API | Audio transcription |

## ConfigLoader (`src/engine/config_loader.py`)

DB-first, file-fallback pattern:
1. Check in-memory cache
2. Try Supabase `implementations` + `visit_types` tables
3. Fallback to `src/implementations/{id}/schemas/*.json`

Cache cleared via `POST /api/admin/reload-config`

## Session Manager (`src/channels/whatsapp/session_manager.py`)

- `handle_media(phone, file_metadata)` → append to today's session
- `handle_text(phone, body)` → detect trigger OR save as text note
- Trigger words: `{"reporte", "generar", "listo", "fin", "report", "done"}`
  - NOTE: Currently hardcoded, should read from `implementations.trigger_words`
- Guards: empty session, already processing, already completed, failed (allows retry)
- Clarification: if session status is `needs_clarification`, any text = clarification response
