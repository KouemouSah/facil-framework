-- Migration 174: Add embedding column to agent_query_logs for pgvector similarity search.
--
-- Architecture: Each logged query gets a 768-dim embedding from Vertex AI
-- (textembedding-gecko-multilingual@001), stored as vector(768).
-- The few-shot retriever uses pgvector cosine distance (<=> operator)
-- for semantic similarity search, falling back to TF-IDF if embeddings
-- are not yet available (cold start).
--
-- Depends on: pgvector extension (already enabled), migration 173

-- 1. Add embedding column (nullable — populated async, fire-and-forget)
ALTER TABLE agent_query_logs
ADD COLUMN IF NOT EXISTS embedding vector(768);

-- 2. IVFFlat index for fast cosine similarity search
-- Lists=10 is appropriate for < 10K rows; bump to 100 when > 50K.
-- Only indexes non-null embeddings (partial index saves space during cold start).
CREATE INDEX IF NOT EXISTS idx_agent_query_logs_embedding
ON agent_query_logs
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 10)
WHERE embedding IS NOT NULL;

-- 3. Composite index for filtered similarity search (agent_type + has embedding)
CREATE INDEX IF NOT EXISTS idx_agent_query_logs_embedding_agent
ON agent_query_logs (agent_type)
WHERE embedding IS NOT NULL
  AND was_successful = TRUE
  AND ground_truth_intent IS NOT NULL;
