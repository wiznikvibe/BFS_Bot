-- PostgreSQL bootstrap for hybrid RAG payments PoC.
CREATE EXTENSION IF NOT EXISTS vector;

COMMENT ON EXTENSION vector IS 'Optional pgvector; PolicyChunk.embedding uses JSON in SQLAlchemy for portable ranking.';

-- Table/column comments are applied via SQLAlchemy create_all (models.py).
-- Example for manual psql init after tables exist:
-- COMMENT ON TABLE customers IS 'Demo customers; membership length and plan drive discount eligibility.';
-- COMMENT ON TABLE invoices IS 'Invoices billed to customers; links discounts and fees to line items.';
-- COMMENT ON TABLE payments IS 'Payments received; timing vs due date drives late-fee scenarios.';
-- COMMENT ON TABLE discount_codes IS 'Discount codes link applied invoice codes to policy doc_id for hybrid Q&A.';
-- COMMENT ON TABLE policy_chunks IS 'Chunked policy documents for RAG; metadata supports version and date filtering.';
-- COMMENT ON TABLE audit_events IS 'Query routing, tool use, and outcomes for compliance demo.';
