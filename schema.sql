-- WasteIQ Database Schema
-- Run this against your PostgreSQL database before starting the backend.
-- The backend (SQLAlchemy) will also auto-create tables on startup via Base.metadata.create_all()

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS companies (
    id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    name        TEXT NOT NULL,
    industry_segment TEXT,
    country     TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    company_id      TEXT NOT NULL REFERENCES companies(id),
    email           TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    full_name       TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crew_profiles (
    id                    TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    company_id            TEXT NOT NULL REFERENCES companies(id),
    name                  TEXT NOT NULL,
    size                  INTEGER NOT NULL,
    avg_experience_years  FLOAT NOT NULL,
    experience_index      FLOAT
);

CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    company_id  TEXT NOT NULL REFERENCES companies(id),
    name        TEXT NOT NULL,
    type        TEXT NOT NULL CHECK (type IN ('residential','commercial','industrial','infrastructure')),
    location    TEXT,
    area_sqm    FLOAT,
    start_date  TIMESTAMP,
    status      TEXT DEFAULT 'active',
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_phases (
    id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    phase_name    TEXT NOT NULL CHECK (phase_name IN ('foundation','framing','mep','finishing','landscaping')),
    planned_start TIMESTAMP,
    planned_end   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS material_line_items (
    id                  TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    project_id          TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    phase_id            TEXT REFERENCES project_phases(id),
    crew_profile_id     TEXT REFERENCES crew_profiles(id),
    material_type       TEXT NOT NULL,
    estimated_quantity  FLOAT NOT NULL,
    unit                TEXT NOT NULL,
    unit_price          FLOAT
);

CREATE TABLE IF NOT EXISTS waste_predictions (
    id                      TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    material_line_item_id   TEXT NOT NULL REFERENCES material_line_items(id),
    predicted_waste_pct     FLOAT NOT NULL,
    ci_low                  FLOAT NOT NULL,
    ci_high                 FLOAT NOT NULL,
    recommended_order_qty   FLOAT NOT NULL,
    model_version           TEXT,
    prediction_date         TIMESTAMP DEFAULT NOW(),
    feature_snapshot        JSONB,
    shap_values             JSONB
);

CREATE TABLE IF NOT EXISTS waste_actuals (
    id                      TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    material_line_item_id   TEXT NOT NULL REFERENCES material_line_items(id),
    actual_waste_qty        FLOAT NOT NULL,
    actual_waste_pct        FLOAT,
    recorded_by             TEXT,
    recorded_at             TIMESTAMP DEFAULT NOW(),
    notes                   TEXT
);

CREATE TABLE IF NOT EXISTS model_feedback_logs (
    id                  TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    company_id          TEXT NOT NULL REFERENCES companies(id),
    prediction_id       TEXT REFERENCES waste_predictions(id),
    actual_id           TEXT REFERENCES waste_actuals(id),
    delta_pct           FLOAT,
    used_in_retraining  BOOLEAN DEFAULT FALSE,
    retrain_date        TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_projects_company ON projects(company_id);
CREATE INDEX IF NOT EXISTS idx_materials_project ON material_line_items(project_id);
CREATE INDEX IF NOT EXISTS idx_predictions_material ON waste_predictions(material_line_item_id);
CREATE INDEX IF NOT EXISTS idx_actuals_material ON waste_actuals(material_line_item_id);
CREATE INDEX IF NOT EXISTS idx_feedback_company ON model_feedback_logs(company_id, used_in_retraining);
