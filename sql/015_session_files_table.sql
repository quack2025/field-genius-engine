-- 015: Normalize raw_files JSONB array → session_files table
-- Run in Supabase SQL Editor
--
-- This is an ADDITIVE migration — raw_files column stays for backward compatibility.
-- New writes go to session_files table. Reads check session_files first, fall back to raw_files.

-- 1. Create session_files table
CREATE TABLE IF NOT EXISTS session_files (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    filename text,
    storage_path text,
    type text NOT NULL DEFAULT 'unknown',  -- image, audio, video, text, location
    content_type text,
    size_bytes integer DEFAULT 0,
    -- Pre-processing results (populated by preprocessor.py)
    transcription text,
    image_description text,
    content_category text,  -- BUSINESS, PERSONAL, NSFW, CONFIDENTIAL, UNCLEAR
    blocked boolean DEFAULT false,
    flagged boolean DEFAULT false,
    pii_scrubbed integer DEFAULT 0,
    -- Location data
    latitude double precision,
    longitude double precision,
    address text,
    label text,
    -- Metadata
    public_url text,
    timestamp timestamptz DEFAULT now(),
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- 2. Indexes for hot queries
CREATE INDEX IF NOT EXISTS idx_session_files_session_id ON session_files(session_id);
CREATE INDEX IF NOT EXISTS idx_session_files_type ON session_files(session_id, type);

-- 3. RLS policies (match sessions pattern)
ALTER TABLE session_files ENABLE ROW LEVEL SECURITY;

CREATE POLICY session_files_select ON session_files FOR SELECT
  USING (true);  -- service_role bypasses RLS; restrict in app layer

CREATE POLICY session_files_insert ON session_files FOR INSERT
  WITH CHECK (true);

CREATE POLICY session_files_update ON session_files FOR UPDATE
  USING (true);

-- 4. Trigger for updated_at
CREATE TRIGGER session_files_updated_at
  BEFORE UPDATE ON session_files
  FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- 5. Migrate existing raw_files data (one-time backfill)
-- This inserts rows from the JSONB array into the new table
INSERT INTO session_files (session_id, filename, storage_path, type, content_type, size_bytes,
    transcription, image_description, content_category, blocked, flagged, pii_scrubbed,
    latitude, longitude, address, label, public_url, timestamp)
SELECT
    s.id AS session_id,
    f->>'filename' AS filename,
    f->>'storage_path' AS storage_path,
    COALESCE(f->>'type', 'unknown') AS type,
    f->>'content_type' AS content_type,
    COALESCE((f->>'size_bytes')::integer, 0) AS size_bytes,
    f->>'transcription' AS transcription,
    f->>'image_description' AS image_description,
    f->>'content_category' AS content_category,
    COALESCE((f->>'blocked')::boolean, false) AS blocked,
    COALESCE((f->>'flagged')::boolean, false) AS flagged,
    COALESCE((f->>'pii_scrubbed')::integer, 0) AS pii_scrubbed,
    (f->>'latitude')::double precision AS latitude,
    (f->>'longitude')::double precision AS longitude,
    f->>'address' AS address,
    f->>'label' AS label,
    f->>'public_url' AS public_url,
    COALESCE((f->>'timestamp')::timestamptz, s.created_at) AS timestamp
FROM sessions s, jsonb_array_elements(s.raw_files) AS f
WHERE jsonb_array_length(s.raw_files) > 0
ON CONFLICT DO NOTHING;

-- 6. Verify
SELECT
    (SELECT count(*) FROM session_files) AS files_migrated,
    (SELECT count(*) FROM sessions WHERE jsonb_array_length(raw_files) > 0) AS sessions_with_files;
