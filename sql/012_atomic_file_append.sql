-- 012: Atomic file append + update to prevent race conditions
-- Run in Supabase SQL Editor
--
-- Problem: add_file_to_session() does read-modify-write in Python,
-- causing data loss when 2 files arrive simultaneously for same session.
-- Solution: PostgreSQL RPC that appends atomically.

-- Atomic append: adds a file entry to raw_files in a single UPDATE
CREATE OR REPLACE FUNCTION append_file_to_session(
  p_session_id uuid,
  p_file_meta jsonb
) RETURNS void AS $$
BEGIN
  UPDATE sessions
  SET raw_files = COALESCE(raw_files, '[]'::jsonb) || p_file_meta,
      updated_at = now()
  WHERE id = p_session_id;
END;
$$ LANGUAGE plpgsql;

-- Atomic update: patches a specific file entry in raw_files by filename
CREATE OR REPLACE FUNCTION update_file_in_session(
  p_session_id uuid,
  p_filename text,
  p_updates jsonb
) RETURNS void AS $$
DECLARE
  i int;
  files jsonb;
BEGIN
  SELECT raw_files INTO files FROM sessions WHERE id = p_session_id;
  IF files IS NULL THEN RETURN; END IF;

  FOR i IN 0..jsonb_array_length(files) - 1 LOOP
    IF files->i->>'filename' = p_filename THEN
      files = jsonb_set(files, ARRAY[i::text], (files->i) || p_updates);
      UPDATE sessions
      SET raw_files = files, updated_at = now()
      WHERE id = p_session_id;
      RETURN;
    END IF;
  END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Add index on sessions(implementation) for RLS performance
CREATE INDEX IF NOT EXISTS idx_sessions_implementation_text
ON sessions(implementation);
