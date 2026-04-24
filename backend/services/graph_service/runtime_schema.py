from __future__ import annotations

import sqlite3

def _ensure_schema(self, conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS facts (
            signature TEXT PRIMARY KEY,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            subject_type TEXT NOT NULL DEFAULT 'other',
            object_type TEXT NOT NULL DEFAULT 'other',
            source_book TEXT NOT NULL DEFAULT '',
            source_chapter TEXT NOT NULL DEFAULT '',
            dataset_scope TEXT NOT NULL DEFAULT 'runtime',
            fact_id TEXT NOT NULL DEFAULT '',
            fact_ids_text TEXT NOT NULL DEFAULT '',
            best_source_text TEXT NOT NULL DEFAULT '',
            best_confidence REAL NOT NULL DEFAULT 0.0
        );
        CREATE TABLE IF NOT EXISTS fact_members (
            signature TEXT NOT NULL,
            fact_id TEXT NOT NULL,
            PRIMARY KEY (signature, fact_id),
            FOREIGN KEY (signature) REFERENCES facts(signature) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS evidence (
            fact_id TEXT PRIMARY KEY,
            source_book TEXT NOT NULL DEFAULT '',
            source_chapter TEXT NOT NULL DEFAULT '',
            source_text TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 0.0
        );
        CREATE TABLE IF NOT EXISTS entities (
            name TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL DEFAULT 'other'
        );
        CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(subject);
        CREATE INDEX IF NOT EXISTS idx_facts_object ON facts(object);
        CREATE INDEX IF NOT EXISTS idx_facts_book ON facts(source_book);
        CREATE INDEX IF NOT EXISTS idx_facts_predicate ON facts(predicate);
        CREATE INDEX IF NOT EXISTS idx_fact_members_fact_id ON fact_members(fact_id);
        CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
        """
    )
    conn.commit()
