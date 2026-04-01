# Product Readiness Audit — 2026-04-01

## Scores

| Auditor | Score | Key Finding |
|---------|-------|-------------|
| Frontend Developer (UX) | 4/10 | No mobile, no progress feedback, alert() everywhere, no export |
| AI Engineer (Quality + Safety) | 4/10 | Zero content moderation, no PII scrubbing, no output validation |
| Growth Hacker (PMF) | 4.5/10 | Adoption risk 85%, cost model off by 30x, single-person dependency |
| **Promedio** | **4.2/10** | |

---

## TOP 15 BLOCKERS (cross-auditor, sorted by business impact)

### BUSINESS-ENDING (fix before ANY demo or pilot)

| # | Finding | Auditors | Impact |
|---|---------|----------|--------|
| 1 | **Zero content moderation** — NSFW/personal photos processed, described, stored | AI Eng | Lawsuit, lost client |
| 2 | **No PII scrubbing** — audio transcriptions capture customer names, cedulas, addresses | AI Eng | Legal liability (data protection laws CR/CO) |
| 3 | **AI cost model off by 30x** — $450 vs $15,400/month for 1,000 active users | PMF | Business loses money at $8K/month |

### CRITICAL UX (fix before enterprise demo)

| # | Finding | Auditors | Impact |
|---|---------|----------|--------|
| 4 | **No mobile responsive** — field supervisors can't use on phone | UX | 40%+ of target users blocked |
| 5 | **Report generation: no progress, no persistence, no export** — 60s blank wait, lost on nav | UX | Core value prop feels broken |
| 6 | **alert() and console.error everywhere** — looks like student project | UX | Immediate credibility loss in demo |
| 7 | **Reports overlap 40%+** — tactical/strategic/innovation repeat same shelf analysis | AI Eng | Paying for redundant AI calls |

### HIGH (fix before pilot)

| # | Finding | Auditors | Impact |
|---|---------|----------|--------|
| 8 | **Sync Anthropic client in vision.py/extractor.py** — blocks event loop | AI Eng | Server stalls under load |
| 9 | **Sonnet for every Vision call** — should be Haiku (60% cost reduction) | AI Eng | Unsustainable API costs |
| 10 | **No retry on AI calls** — single 529 loses entire report | AI Eng | Data loss |
| 11 | **Whisper hardcoded to Spanish** — English/Creole zones produce garbage | AI Eng | Wrong data in pipeline |
| 12 | **1,000 agents won't spontaneously adopt** — no personal benefit for field user | PMF | Adoption collapses to 10-15% |
| 13 | **No signed contract** — "approved" pricing is not a purchase order | PMF | Zero committed revenue |

### MEDIUM (fix before scale)

| # | Finding | Auditors | Impact |
|---|---------|----------|--------|
| 14 | **No search anywhere** — manager can't find specific session | UX | Daily frustration |
| 15 | **No pagination on sessions** — 100-row cap invisible to user | UX | Unusable at scale |

---

## Hardening Sprints (Product)

### Sprint P-1: CONTENT SAFETY (P0, 1-2 days)
- [ ] Content moderation: pre-screen images with Haiku before Vision analysis
  - Categories: business_relevant, personal, nsfw, confidential_document, unclear
  - Flag/reject non-business content before storing description
  - Notify user: "Esta foto no parece ser de una visita de campo"
- [ ] PII scrubbing: regex + Haiku pass on audio transcriptions
  - Detect: phone numbers, emails, cedulas, addresses, credit card numbers
  - Redact before transcription enters pipeline
  - Store original in encrypted field (for compliance audit), show redacted
- [ ] File size limits: max 5MB per file, 50 files per session, 100 files per day
- [ ] User notification on failed/rejected media

### Sprint P-2: AI COST OPTIMIZATION (P0, 1 day)
- [ ] Switch Vision preprocessing from Sonnet to Haiku (60% cost reduction)
- [ ] Enable Anthropic prompt caching on system prompts
- [ ] Build cost calculator: files/user/day x cost/call = monthly cost
- [ ] Add token tracking per session (log usage.input_tokens + output_tokens)
- [ ] Validate cost model with real pilot data before committing to price

### Sprint P-3: UX CRITICAL (P1, 2-3 days)
- [ ] Mobile responsive: collapsible sidebar + hamburger menu
- [ ] Report generation progress: multi-step indicator + elapsed timer
- [ ] Replace ALL alert() with toast notifications
- [ ] Persist generated reports to backend (survive page navigation)
- [ ] PDF export for reports
- [ ] Status labels in Spanish (accumulating -> "Acumulando")

### Sprint P-4: AI QUALITY (P1, 1-2 days)
- [ ] Fix sync Anthropic client in vision.py + extractor.py (use AsyncAnthropic)
- [ ] Add retry logic with exponential backoff on all AI calls
- [ ] Remove hardcoded language="es" from Whisper (use auto-detect or config)
- [ ] Add output validation: JSON schema check + range validation on prices
- [ ] Reduce framework overlap: scope each to non-overlapping concerns
- [ ] Structured Vision output format (consistent sections)

### Sprint P-5: UX POLISH (P2, 2-3 days)
- [ ] Global search bar
- [ ] Pagination with total count and page controls
- [ ] Session detail: breadcrumbs
- [ ] Skeleton loading states
- [ ] Empty state illustrations
- [ ] RBAC in UI (hide destructive actions for non-admins)
- [ ] Report history (persist + list previously generated reports)

### Sprint P-6: PMF HARDENING (P2, ongoing)
- [ ] Create immediate value for field agent (auto-generate daily visit log)
- [ ] Build telecom-specific demo (not laundry care)
- [ ] Define 3 ROI metrics with Telecable upfront
- [ ] Price per active user, not registered user
- [ ] Get signed contract with 12-month minimum
- [ ] Competitive teardown: GoSpotCheck, Repsly trial

---

## Cost Model Validation Needed

| Scenario | Files/user/day | Active users | Monthly files | Vision (Haiku) | Whisper | Reports | Total AI/month |
|----------|---------------|-------------|--------------|----------------|---------|---------|---------------|
| Conservative | 3 | 200 | 12,000 | $120 | $36 | $100 | ~$256 |
| Moderate | 5 | 500 | 50,000 | $500 | $150 | $250 | ~$900 |
| Aggressive | 10 | 800 | 160,000 | $1,600 | $480 | $500 | ~$2,580 |
| Full scale | 10 | 1,000 | 200,000 | $2,000 | $600 | $800 | ~$3,400 |

Note: Assumes Vision switched to Haiku ($0.80/M tokens vs $3/M for Sonnet).
With Sonnet Vision, multiply Vision column by 3.75x.

At $8K/month revenue and "Full scale" with Haiku: $3,400 AI + $130 infra = $3,530 cost. Margin: 56%.
At $8K/month revenue and "Full scale" with Sonnet: $7,500 AI + $130 infra = $7,630 cost. Margin: 5%. NOT VIABLE.

**Conclusion: Switching Vision to Haiku is not optional. It's a business requirement.**
