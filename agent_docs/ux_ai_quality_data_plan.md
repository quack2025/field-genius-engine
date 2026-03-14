# Field Genius Engine — UX Research + AI Product + Data Analytics Plan

**Created:** 2026-03-14
**Scope:** Improve user experience, AI pipeline reliability, and data quality monitoring
**Source frameworks:** `product-plugins` by alexe-ev (ux-research, ai-product, data-analytics skills)

---

## Context & Problem

Field Genius Engine converts unstructured WhatsApp media (photos, audio, video) into structured
field visit reports via a 7-step AI pipeline. Two implementations exist:
- **Argos** (cement/construction): 3 visit types (ferreteria, obra_civil, obra_pequena)
- **Eficacia** (FMCG/retail): 3 visit types (supermarket_visit, tienda_barrio, wholesale_visit)

**Current state after Sprints 1-4 + A-D:**
- Pipeline works end-to-end (WhatsApp → segmentation → extraction → Sheets)
- PDF and Gamma outputs disabled (infrastructure issues)
- Admin API has NO authentication
- No tests running in CI
- Clarification flow framework exists but untested with real users
- No monitoring, no quality metrics, no data validation
- Zero real-world usage yet — only simulated sessions

**What makes this product unique (and risky):**
- The user is a field executive who sends media via WhatsApp. They have ZERO visibility into what the AI does.
- There is NO UI for the field user — only WhatsApp messages ("Recibido", trigger word, summary).
- All quality problems are invisible until someone checks Google Sheets or the backoffice.
- Errors compound: wrong segmentation → wrong visit type → wrong schema → wrong extraction → wrong Sheets row.
- The user cannot correct the AI mid-process (unlike Survey Coder's Refine step or Talk2Data's chat follow-ups).

---

## Phase 1: Assess Experience Quality (Week 1)

**Skill:** `assess-experience-quality`
**Goal:** Evaluate the 3 user journeys (field exec, manager, admin) against 5 quality criteria

### Journey A: Field Executive (primary user)

The field executive interacts ONLY via WhatsApp. Their entire journey:

```
[Morning] Start day → Visit point 1 → Take photos, record voice notes → Send to WhatsApp
→ Engine replies "Recibido" per file → Visit point 2 → More media → ...
→ [End of day] Send "reporte" → Wait → Receive summary + PDF
```

**Quality criteria per step:**

| Step | Discoverability | Clarity | Efficiency | Error Recovery | Trust |
|---|---|---|---|---|---|
| **Send media** | Does exec know what to capture? Any guidance? | "Recibido" — does exec trust files arrived safely? | 1 message per file (OK) or batch? | What if send fails? WhatsApp retry handles it | N/A — no AI yet |
| **Trigger word** | Does exec know the magic words? | What if they type "informe" (not in trigger list)? | Single message (efficient) | What if triggered accidentally mid-day? | N/A |
| **Wait for processing** | How long? Any progress indicator? | Exec doesn't know if it's working or stuck | Pipeline can take 2-10 min depending on media count | If pipeline fails, does exec know? | "Is it working?" anxiety |
| **Receive summary** | Is the summary in the WhatsApp chat? | Can exec understand the structured output? | One message with summary + PDF attachment | If data is wrong, how does exec correct it? | **CRITICAL** — exec sees result but can't edit |
| **Post-completion** | What if exec forgot to send some photos? | Can they add to a completed session? | Currently: files accumulate but don't process | No mechanism to reopen or append | Trust broken if data is incomplete |

**Known gaps (from PENDING_NOTES.md):**

| Gap | Impact | Severity |
|---|---|---|
| Post-completion media ignored | Exec sends late photos → data lost | CRITICAL |
| No processing indicator | Exec doesn't know if pipeline is running | HIGH |
| No correction mechanism | Wrong data in Sheets → manual fix required | HIGH |
| Trigger word miss | "informe" not recognized → nothing happens, exec confused | MEDIUM |
| Clarification flow untested | AI asks question → exec answers → but is UX natural? | MEDIUM |
| No onboarding | New exec doesn't know what to capture or how | HIGH |

### Journey B: Manager (secondary user — reads reports)

```
[Daily/Weekly] Open Google Sheets → Review visit reports → Spot anomalies
→ Check backoffice for session details → View media timeline
→ Identify action items → Follow up with executives
```

**Quality criteria:**

| Step | Gap |
|---|---|
| Google Sheets | Are column names understandable? Is data consistent across rows? |
| Backoffice dashboard | Stats are basic — no quality metrics, no trends, no alerts |
| Session detail | Media timeline exists, but no annotation showing what AI extracted from each file |
| Anomaly detection | Manager must manually spot bad data — no automated flags |
| Cross-executive comparison | No way to compare performance across executives |

### Journey C: Admin (backoffice — configures implementations)

```
[Setup] Create implementation → Define visit types → Configure schemas
→ Add users → Test with simulated session → Monitor sessions
```

**Quality criteria:**

| Step | Gap |
|---|---|
| Create implementation | Works but no validation — can create with empty prompts |
| Define schemas | JSON editor only — no visual schema builder |
| Test extraction | `/api/admin/test-extraction` exists but requires raw JSON input |
| Monitor sessions | List view exists, no quality scoring or success rate |
| No auth | Anyone with the URL can access admin API | CRITICAL security |

**Deliverable:** Quality assessment matrix for all 3 journeys.

---

## Phase 2: Usability Test Design (Week 1-2)

**Skill:** `run-usability-testing`
**Goal:** Design 8 goal-based test tasks for real field conditions

### Critical difference from Survey Coder / Talk2Data:
- The user has NO screen (only WhatsApp)
- Testing requires REAL WhatsApp interaction (or /api/simulate)
- Test environment: actual phone, actual photos from a real location
- Must test in Spanish (all prompts and messages are in Spanish)

### Test Tasks

**Field Executive Tasks (5):**

| # | Task (goal-based) | Tests what | Success criteria | Simulated? |
|---|---|---|---|---|
| T1 | "Visit a hardware store. Document what cement brands they sell, their prices, and how much shelf space Argos has." | Photo capture guidance + extraction accuracy | Sheets row has correct prices, brands, share_of_shelf | No — needs real store visit or staged photos |
| T2 | "You visited 3 places today — a hardware store, a construction site, and another hardware store. Send all your media and generate your report." | Multi-visit segmentation (Phase 1) | 3 separate visit_reports with correct types and file assignments | Can simulate with /api/simulate |
| T3 | "You forgot to send the photos from your second store. Add them after you already triggered the report." | Post-completion append (currently broken) | Additional photos processed and merged into existing report | Tests known gap |
| T4 | "The AI asks you a clarification question about one of your photos. Answer it." | Clarification flow UX | Exec understands question, answers naturally, pipeline resumes | Requires clarification trigger |
| T5 | "You're a new executive. It's your first day. Figure out how to use the system." | Onboarding (currently non-existent) | Exec can send media and trigger report without prior training | Tests absence of guidance |

**Manager Tasks (2):**

| # | Task | Tests what | Success criteria |
|---|---|---|---|
| T6 | "Review today's reports from your team of 5 executives. Find which executive had the most competitive activity alerts." | Sheets readability + cross-exec comparison | Manager can identify the right executive in <5 min |
| T7 | "One executive's report seems incomplete — only 2 of 5 visits captured. Investigate why." | Backoffice session detail + media timeline | Manager can see which visits were segmented and which files are unassigned |

**Admin Task (1):**

| # | Task | Tests what | Success criteria |
|---|---|---|---|
| T8 | "Add a new type of visit for Eficacia: 'pharmacy_visit'. Define what data to capture and test it." | Schema creation + test-extraction endpoint | New visit type works end-to-end with simulated data |

### Test Protocol
- **Method:** Field observation (T1, T5) + moderated remote (T2-T4, T6-T8)
- **Participants:** 3 field executives (Argos or similar), 1 manager, 1 admin
- **Duration:** T1/T5: 60 min in field. T2-T4: 30 min remote. T6-T8: 30 min remote.
- **Language:** Spanish only
- **Metrics:** Completion, time, errors, WhatsApp message count, extraction accuracy

**Deliverable:** Test script + field test logistics plan.

---

## Phase 3: AI Pipeline Evaluation (Week 2)

**Skill:** `run-ai-prototype-evaluation`
**Goal:** Measure quality of segmentation (Phase 1) and extraction (Phase 2)

### 3A: Segmentation Accuracy

**Test set: 10 simulated sessions with known ground truth**

| Session | Files | Expected visits | Difficulty |
|---|---|---|---|
| S1 | 3 photos (same store) | 1 ferreteria | Easy |
| S2 | 6 photos + 2 audios (2 stores) | 2 ferreterias | Medium — same type, different locations |
| S3 | 4 photos + 1 video (store + construction site) | 1 ferreteria + 1 obra_civil | Medium — different types |
| S4 | 10 photos + 3 audios (3 locations) | 3 visits | Hard — high volume |
| S5 | 2 photos (unclear location) | 1 visit + needs_clarification | Edge case — ambiguous |
| S6 | 1 audio only (describes visit verbally) | 1 visit | Edge case — no visual evidence |
| S7 | 8 photos from same visit but 4-hour gap | 1 visit (not 2) | Edge case — time gap |
| S8 | 0 files (trigger word only) | Error / empty session | Adversarial |
| S9 | 20 photos + 5 audios (5 locations) | 5 visits | Stress test |
| S10 | Mix of relevant photos + personal photos (food, selfie) | Visits only, personal filtered | Edge case — noise |

**Metrics:**
- Visit count accuracy: % of sessions where correct number of visits identified
- File assignment accuracy: % of files assigned to correct visit
- Visit type accuracy: % of visits classified to correct type
- Clarification trigger accuracy: did it ask when it should? Did it NOT ask when it shouldn't?
- False split rate: % of single visits incorrectly split into 2+
- False merge rate: % of distinct visits incorrectly merged into 1

### 3B: Extraction Accuracy

**Golden test set: 15 visit extractions with human-verified expected output**

For each of the 3 Argos visit types (5 per type), create:
```json
{
  "visit_type": "ferreteria",
  "input_context": "Transcription: 'Aqui en Ferretería El Constructor, tienen cemento Argos a 32 mil y Holcim a 30 mil...' + Image descriptions: 'Shelf with 3 brands visible...'",
  "expected_extraction": {
    "precios": [
      {"producto": "Cemento gris", "marca": "Argos", "precio": 32000, "presentacion": "Bolsa 50kg"},
      {"producto": "Cemento gris", "marca": "Holcim", "precio": 30000, "presentacion": "Bolsa 50kg"}
    ],
    "share_of_shelf": {
      "argos_facing": "medio",
      "competencia_dominante": "Holcim"
    }
  },
  "difficulty": "standard"
}
```

**Metrics:**
- Field extraction rate: % of expected fields correctly extracted
- Price accuracy: exact match on numeric values
- Brand recognition: % of brands correctly identified (including slang/abbreviations)
- Array completeness: % of expected array items captured (prices, competitors)
- Hallucination rate: % of extracted values not present in input context
- Confidence calibration: does confidence_score correlate with actual accuracy?

### 3C: Vision Analysis Quality

Test Claude Sonnet's image analysis specifically:
- Can it read prices from photos of shelves? (often blurry, handwritten)
- Can it estimate share_of_shelf from a photo? (subjective)
- Can it detect brand logos vs generic products?
- Can it distinguish Argos products from competitors by packaging color?

**Method:** 20 real store photos → Claude vision → human verification of observations

**Deliverable:** Test sets + accuracy report for segmentation, extraction, and vision.

---

## Phase 4: Data Analytics — Metrics Framework (Week 2-3)

**Skill:** `design-product-metrics` + `define-ai-success-metrics`
**Goal:** Define what to measure at every level

### Level 1: Pipeline Health Metrics (operational)

| Metric | How to measure | Source | Alert threshold |
|---|---|---|---|
| Sessions processed/day | COUNT sessions WHERE status='completed' AND date=today | Supabase | <expected_executives (all should report daily) |
| Pipeline success rate | completed / (completed + failed) | Supabase | <90% |
| Avg processing time | AVG(processing_time_ms) from visit_reports | Supabase | >120s per visit |
| Segmentation accuracy | Manual review sample (weekly) | Human | <80% |
| Extraction completeness | % of schema fields populated (not null) per visit_report | Supabase JSON query | <60% |
| Media accumulation rate | COUNT raw_files per session | Supabase | <3 (exec may not be capturing enough) |
| Trigger word usage | Distribution of trigger words used | Supabase sessions | New unrecognized words appearing |
| Whisper transcription quality | Manual review of 5 transcriptions/week | Human | Unintelligible segments >20% |

### Level 2: Data Quality Metrics (analytical)

| Metric | How to measure | Why it matters |
|---|---|---|
| Price consistency | Same product at same store ± 10% across visits | Detects transcription/extraction errors |
| Share_of_shelf distribution | % of visits where share is "alto" vs "medio" vs "bajo" | Should vary — if all "medio" something is wrong |
| Competitor activity alerts | % of visits with alerta=true | Track competitive intelligence yield |
| Confidence score distribution | Histogram of confidence_score across all visit_reports | Should be normal-ish around 0.7-0.9 |
| Empty field rate per category | % of visits where entire category is null | Identifies schema categories that don't match reality |
| Cross-executive variance | Std dev of metrics per executive | Low variance = possible copy-paste behavior |
| Temporal patterns | Visits per day of week, time of day | Identifies gaming (all reports at 5pm = not real-time) |

### Level 3: Business Impact Metrics (strategic)

| Metric | How to measure | Target |
|---|---|---|
| Executive adoption | % of registered executives who report daily | >80% |
| Visit coverage | Visits reported / Visits planned (from route plan) | >90% |
| Data actionability | % of reports with at least 1 competitive alert or opportunity | >30% |
| Time saved | Hours saved vs paper forms (estimate) | >2h/day per executive |
| Manager engagement | Sheets views per week per manager | >3 views/week |
| Implementation onboarding time | Days from implementation creation to first real session | <5 days |
| Schema iteration count | How many times schemas are modified after launch | Stabilize within 3 iterations |

### Level 4: Per-Implementation Dashboards

**Argos-specific:**
| Metric | Query |
|---|---|
| Avg prices by product by region | GROUP BY inferred_location, extracted_data->precios->producto |
| Share of shelf trend (weekly) | AVG share over rolling 7 days |
| Competitive activity heatmap | COUNT alertas by competencia by location |
| Executive visit frequency | COUNT sessions per user per week |

**Eficacia-specific:**
| Metric | Query |
|---|---|
| SKU distribution by store type | extracted_data->inventario by visit_type |
| Promo compliance | % of visits where exhibiciones_especiales is not empty |
| Price gap vs recommended | Extracted price vs reference price list |

**Deliverable:** Metrics spec + SQL queries for Supabase + backoffice dashboard wireframe.

---

## Phase 5: Data Analytics — Monitoring & Alerting (Week 3)

**Skills:** `build-decision-dashboard` + `design-metric-alert-system` + `detect-performance-signals`
**Goal:** Build monitoring that catches problems before the client notices

### Dashboard Design (Backoffice)

Current backoffice has basic stats. Upgrade to:

**Dashboard Tab 1: Pipeline Health**
- Sessions today vs expected (gauge)
- Success/failure rate (7-day trend line)
- Avg processing time (trend)
- Failed sessions list with error details

**Dashboard Tab 2: Data Quality**
- Extraction completeness heatmap (visit_type x category → % populated)
- Confidence score distribution (histogram)
- Empty field rate by category (bar chart — identify unused schema fields)
- Price anomaly flags (values outside 2 std dev)

**Dashboard Tab 3: Executive Activity**
- Activity table: executive x day → visits count (heatmap)
- Media volume per executive (are they capturing enough?)
- Trigger word timing (when do they generate reports? End of day? Real-time?)
- Inactive executives (no session in >2 days)

### Alert System

| Alert | Trigger | Channel | Recipient |
|---|---|---|---|
| Pipeline failure | Session status='failed' | WhatsApp + Backoffice | Admin |
| Executive inactive | No session from registered user in >2 days | WhatsApp to manager | Manager |
| Low extraction quality | confidence_score < 0.5 on any visit_report | Backoffice flag | Admin |
| Schema mismatch | >50% of visits have entire category empty | Backoffice alert | Admin |
| Price anomaly | Price deviates >30% from 7-day avg for same product | Sheets highlight | Manager |
| High unassigned files | >3 files unassigned after segmentation | Backoffice flag | Admin |

### Signal Detection Rules

| Signal | Real change vs noise |
|---|---|
| Confidence scores dropping | Check: did Anthropic update model? Did schema change? Or is data quality actually worse? |
| Fewer visits per session | Check: fewer actual visits, or segmentation splitting too aggressively? |
| More clarification requests | Check: new exec with unclear capture habits, or segmentation prompt degraded? |
| Empty category across all visits | Schema category doesn't match real-world field conditions — modify schema |

**Deliverable:** Dashboard specs + alert implementation plan.

---

## Phase 6: HITL Workflow Design (Week 3-4)

**Skill:** `design-human-in-loop-workflow`
**Goal:** Add human checkpoints without breaking the WhatsApp-only flow

### Current State: Near-zero HITL

| Checkpoint | Exists? | Quality |
|---|---|---|
| Clarification question (Phase 1) | Framework built, not tested | Unknown |
| Post-extraction review | No | — |
| Manager approval before Sheets write | No | — |
| Executive confirmation of summary | No | — |
| Schema validation on config change | No | — |

### The core HITL challenge for Field Genius

The field executive uses ONLY WhatsApp. Any human checkpoint must work as a WhatsApp message exchange:

```
Engine: "Encontre 3 visitas en tu reporte de hoy:
1. Ferreteria El Constructor (5 fotos, 1 audio)
2. Obra Centro Comercial (3 fotos, 1 video)
3. Ferreteria La Esquina (2 fotos)
¿Es correcto? Responde SI para continuar o corrige."

Executive: "si" → proceed
Executive: "la 3 es una obra no una ferreteria" → correct and re-extract
```

### Recommended HITL Interventions (by priority)

**1. Segmentation confirmation (HIGH priority, MEDIUM effort)**

After Phase 1, send the executive a WhatsApp summary of identified visits.
Wait for "si" / correction before proceeding to Phase 2.

- **Why:** Wrong segmentation cascades into wrong extraction. Catching it here saves everything downstream.
- **Implementation:** New state `awaiting_confirmation` between `segmenting` and `processing`. `session_manager.py` handles response. Timeout: 30 min → auto-proceed with warning flag.
- **Risk:** Adds friction. Executive might not respond for hours. Need timeout + auto-proceed.
- **Impact on code:** `session_manager.py` (new handler), `pipeline.py` (new state), DB (new status value)

**2. Low-confidence review flag (HIGH priority, LOW effort)**

When confidence_score < 0.6 on any visit_report, mark it `needs_review` in Supabase
and highlight the row in Google Sheets (yellow background).

- **Why:** Manager can spot-check low-confidence rows instead of reviewing everything.
- **Implementation:** Already partially built — `visit_reports.status` supports `needs_review`. Just need to trigger it based on threshold.
- **Impact on code:** `pipeline.py` (add threshold check after extraction), `sheets.py` (conditional formatting)

**3. Post-extraction summary to executive (MEDIUM priority, LOW effort)**

After all visits are extracted, send a WhatsApp summary:
```
Reporte procesado:
- Ferreteria El Constructor: 4 precios, 2 marcas competencia, share Argos: medio
- Obra Centro Comercial: 3 materiales, 1 alerta competencia
Detalle completo en tu reporte adjunto.
```

- **Why:** Executive gets immediate confirmation that data was captured correctly. Can flag errors early.
- **Implementation:** Already partially built in pipeline step 7. Enrich the summary message.
- **Impact on code:** `pipeline.py` (enrich summary builder), `sender.py` (format message)

**4. Manager approval gate for alerts (LOW priority, MEDIUM effort)**

When competitive activity alert is detected, notify manager via WhatsApp before adding to Sheets.
Manager replies "confirmar" → row added. Manager replies "falso" → row flagged.

- **Why:** Reduces false alerts reaching client stakeholders.
- **Implementation:** New manager notification flow. Requires manager phone in `users` table with role='manager'.
- **Impact on code:** New module `src/channels/whatsapp/manager_flow.py`

**5. Schema test-before-deploy (MEDIUM priority, LOW effort)**

When admin creates or modifies a visit_type schema, auto-run `test-extraction` with a sample input
and show the result before activating.

- **Why:** Prevents deploying broken schemas that produce empty extractions.
- **Implementation:** `admin.py` POST visit_type → auto-run test → return preview. Frontend shows preview before confirm.
- **Impact on code:** `admin.py` (add test step), backoffice (preview component)

**Deliverable:** HITL flow diagrams + WhatsApp message templates + state machine updates.

---

## Phase 7: Funnel Analysis — Executive Adoption (Week 4)

**Skill:** `analyze-funnel-retention-cohorts`
**Goal:** Understand where executives drop off and why

### Executive Adoption Funnel

```
[Registered in users table]         ← How many executives are registered?
        ↓
[Sent first media to WhatsApp]      ← How many actually start using it?
        ↓
[Triggered first report]            ← How many complete the flow?
        ↓
[Report processed successfully]     ← How many get usable results?
        ↓
[Sent media again next day]         ← How many come back?
        ↓
[Active weekly reporter]            ← How many become habitual?
```

**Drop-off hypotheses:**

| Stage | Why they drop | How to detect | How to fix |
|---|---|---|---|
| Registered → First media | Don't know how to start | users with 0 sessions | Onboarding WhatsApp message with instructions |
| First media → First trigger | Don't know trigger words | sessions stuck in 'accumulating' forever | Auto-prompt at 5pm: "Tienes X archivos hoy. Escribe 'reporte' para procesarlos" |
| First trigger → Success | Pipeline fails or takes too long | sessions with status='failed' | Better error messages + faster processing |
| Success → Next day | Results weren't useful or process was painful | gap in session dates | Post-report feedback: "¿Te fue util? Responde 1-5" |
| Next day → Weekly | Habit not formed | declining session frequency | Daily reminder at configurable time |

### Retention Cohort Analysis

Group executives by registration week. Track weekly active rate:

| Cohort | Week 1 | Week 2 | Week 3 | Week 4 |
|---|---|---|---|---|
| Mar 3 (5 execs) | 100% | ?% | ?% | ?% |
| Mar 10 (3 execs) | 100% | ?% | — | — |

**Query:**
```sql
SELECT
  date_trunc('week', u.created_at) as cohort_week,
  date_trunc('week', s.date) as activity_week,
  COUNT(DISTINCT s.user_phone) as active_users
FROM users u
LEFT JOIN sessions s ON s.user_phone = u.phone AND s.status = 'completed'
GROUP BY 1, 2
ORDER BY 1, 2;
```

**Deliverable:** Funnel definition + cohort query + drop-off intervention plan.

---

## Implementation Priority (Sorted by Impact / Effort)

| # | Action | Phase | Impact | Effort | Touches code? |
|---|---|---|---|---|---|
| 1 | Assess experience quality (3 journeys) | 1 | Maps ALL gaps | Document only | No |
| 2 | Low-confidence review flag (needs_review) | 6 | Catches bad extractions | 1 threshold check | pipeline.py, sheets.py |
| 3 | Post-extraction summary enrichment | 6 | Executive trust + error detection | Message formatting | pipeline.py |
| 4 | Create segmentation test set (10 sessions) | 3A | Quantifies Phase 1 accuracy | JSON test data | Test files only |
| 5 | Create extraction golden set (15 visits) | 3B | Quantifies Phase 2 accuracy | JSON test data | Test files only |
| 6 | Auto-prompt at 5pm for pending sessions | 7 | Fixes biggest funnel drop-off | Cron + WhatsApp message | New cron job |
| 7 | Pipeline health dashboard (backoffice) | 5 | Admin visibility | Backoffice components | Frontend only |
| 8 | Design 8 usability test tasks | 2 | Systematic QA framework | Document only | No |
| 9 | Segmentation confirmation via WhatsApp | 6 | Prevents cascade errors | New state + handler | session_manager.py, pipeline.py |
| 10 | Executive adoption funnel queries | 7 | Retention data | SQL queries | No backend changes |
| 11 | Price anomaly detection | 5 | Data quality for manager | SQL + Sheets formatting | sheets.py |
| 12 | Schema test-before-deploy | 6 | Prevents broken configs | Admin API enhancement | admin.py |
| 13 | Vision quality test (20 photos) | 3C | Validates image analysis | Manual test | No |
| 14 | Admin API authentication | — | Security (CRITICAL) | JWT middleware | admin.py, middleware |
| 15 | Run field usability test | 2 | Real user feedback | Coordination + field visit | No |

---

## Key Differences from Survey Coder & Talk2Data Plans

| Aspect | Survey Coder | Talk2Data | Field Genius |
|---|---|---|---|
| User interface | Web app (full UI) | Web app (chat + dashboards) | WhatsApp only (no UI) |
| HITL checkpoints | 4 existing | 0 (fully automated) | 1 framework (untested) |
| Error visibility | User sees results and can edit | User sees charts and can follow up | User sees summary, CANNOT edit |
| Quality feedback loop | Refine step + recode | Chat follow-up + reformulation | None — errors are invisible |
| Test method | Screen share usability test | Screen share + think aloud | Field observation + real WhatsApp |
| Primary risk | Bad codebook → bad classification | Wrong analysis type → misleading results | Wrong segmentation → cascading extraction errors |
| Data analytics need | Product metrics (GA4) | Chat quality metrics | Operational metrics (pipeline health + executive adoption) |
| Monitoring urgency | Medium (product is live) | Medium (product is live) | HIGH (product has ZERO monitoring) |
| Unique challenge | 15 coding types | 20 analysis types | Multi-modal (photo + audio + video) in field conditions |

---

## Files to Create

| File | Purpose | Repo |
|---|---|---|
| `agent_docs/ux_ai_quality_data_plan.md` | This plan (reference document) | Engine |
| `agent_docs/experience_quality_assessment.md` | Phase 1 output | Engine |
| `agent_docs/usability_test_protocol.md` | Phase 2 output | Engine |
| `tests/segmentation_test_cases.json` | 10 sessions with ground truth | Engine |
| `tests/extraction_golden_set.json` | 15 visits with expected output | Engine |
| `tests/test_segmentation_accuracy.py` | Automated segmentation test | Engine |
| `tests/test_extraction_accuracy.py` | Automated extraction test | Engine |
| `agent_docs/metrics_framework.md` | Phase 4 output (4 levels) | Engine |
| `agent_docs/monitoring_dashboard_spec.md` | Phase 5 output | Engine |
| `agent_docs/executive_adoption_funnel.md` | Phase 7 output | Engine |

---

## Rules for Execution

1. **No breaking changes** — Pipeline must continue working end-to-end. Test with /api/simulate after any change.
2. **WhatsApp-first HITL** — Any human checkpoint must work as a WhatsApp message exchange, not a web form.
3. **Document first, code second** — Phases 1-2 produce documents. Code starts at Phase 3.
4. **Test sets before monitoring** — Build golden test sets before adding monitoring that relies on baselines.
5. **Security before multi-client** — Admin API auth (item #14) must happen before onboarding Eficacia users.
6. **Spanish everything** — All user-facing messages, prompts, and test data must be in Spanish.
7. **Fire-and-forget principle** — New monitoring/alerting must not block the pipeline. Log and continue.
8. **Backoffice for admins, WhatsApp for execs** — Never ask a field executive to open a web browser.
9. **Confidence threshold from DB** — `visit_types.confidence_threshold` (default 0.7) drives review flags. Don't hardcode.
10. **Existing tests must pass** — `tests/test_segmenter.py`, `test_extractor.py`, `test_pipeline.py` must remain green.
