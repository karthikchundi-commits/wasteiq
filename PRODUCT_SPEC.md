# WasteIQ — AI Material Waste Prediction for Construction
## Product Specification v1.0 | March 2026

---

## 1. Product Vision

WasteIQ is a web application that predicts material waste percentages for construction projects **before materials are ordered**, enabling contractors to right-size procurement, reduce waste costs, and improve project margins.

**Core Patent Claim:**
A machine learning system that generates per-material waste probability distributions by combining project blueprint metadata, crew behavioral profiles, historical waste actuals, environmental signals, and project phase indicators — with a self-improving feedback loop that updates predictions using post-delivery waste actuals.

---

## 2. Problem Statement

- Contractors add a flat 10–15% waste buffer to all material orders — based on gut feel
- No tool differentiates waste by material type, crew experience, project phase, or weather
- Over-ordering wastes money; under-ordering causes delays
- After a project, waste data is never captured or reused to improve future estimates

**WasteIQ solves this by making waste prediction data-driven and project-specific.**

---

## 3. User Personas

### Primary: Site/Procurement Manager
- Responsible for ordering materials before each project phase
- Pain: over-orders to be safe, eats into margin
- Goal: accurate per-material quantities with confidence intervals

### Secondary: Project Manager / Cost Engineer
- Tracks project budget and variance
- Pain: material cost overruns are unpredictable
- Goal: early visibility into likely waste costs

### Admin: Company Owner / Operations Head
- Wants to compare waste performance across projects and crews
- Goal: identify which teams or project types have highest waste

---

## 4. Core Features

### 4.1 Project Setup (Input)
- Create a project with: type (residential/commercial/industrial), location, start date, total area (sqft/sqm)
- Upload or manually enter: material list (type, estimated quantity, unit)
- Assign crew profile: crew size, average experience level (junior/mid/senior)
- Link to project schedule: phase start dates (foundation, framing, MEP, finishing, etc.)

### 4.2 Waste Prediction Engine (Core Patent)
For each material line item, the system outputs:
- Predicted waste % (point estimate)
- Confidence interval (low / mid / high scenario)
- Key drivers affecting the prediction (explainability)
- Recommended order quantity = estimated need + predicted waste buffer

**Signal inputs to the ML model:**
| Signal | Example Values |
|---|---|
| Material type | Concrete, Steel rebar, Lumber, Drywall, Tiles, Pipe |
| Project type | Residential, Commercial, Infrastructure |
| Project phase | Foundation, Framing, MEP, Finishing |
| Crew experience index | 0–1 score derived from avg years of experience |
| Crew size | Number of workers on site |
| Season / weather zone | Hot-dry, Cold-wet, Tropical, Temperate |
| Site accessibility | Urban constrained vs open site |
| Supplier reliability score | Based on historical delivery accuracy |
| Company historical waste | Avg waste % for this material in past projects |

### 4.3 Feedback Loop (Patent-Critical)
- After each project phase, user enters actual waste quantities
- System compares predicted vs actual waste
- Delta is used to retrain the company-specific model layer
- Over time, predictions become personalized to each company's patterns

### 4.4 Dashboard & Reports
- Per-project waste prediction summary table
- Phase-by-phase material breakdown
- Predicted cost of waste (unit price × predicted waste quantity)
- Historical accuracy chart: predicted vs actual over time
- Company benchmarks vs industry averages

### 4.5 Procurement Integration (Phase 2)
- Export adjusted order quantities to CSV / Excel
- API integration with common procurement tools (future)

---

## 5. Data Model

### Project
- id, company_id, name, type, location, area_sqm, start_date, status

### ProjectPhase
- id, project_id, phase_name (enum), planned_start, planned_end

### MaterialLineItem
- id, project_id, phase_id, material_type (enum), estimated_quantity, unit, unit_price

### WastePrediction
- id, material_line_item_id, predicted_waste_pct, ci_low, ci_high, model_version, prediction_date
- feature_snapshot (JSON) — stores all signal values used for this prediction

### WasteActual
- id, material_line_item_id, actual_waste_qty, recorded_by, recorded_at, notes

### CrewProfile
- id, company_id, name, size, avg_experience_years, experience_index (computed)

### Company
- id, name, industry_segment, country, created_at

### ModelFeedbackLog
- id, company_id, prediction_id, actual_id, delta_pct, used_in_retraining, retrain_date

---

## 6. ML Architecture

### Model Type
- **Base model**: XGBoost Regressor (fast, interpretable, handles tabular data well)
- **Target variable**: Waste percentage per material line item
- **Output**: Point prediction + prediction interval (via quantile regression)

### Training Data Strategy
- **Cold start**: Pre-train on publicly available construction waste research datasets + synthetic data
- **Company layer**: Fine-tune a company-specific model after sufficient actuals (>20 projects)
- **Global layer**: Federated learning concept — learn across all companies without sharing raw data

### Feature Engineering (Patent-Critical)
1. `crew_experience_index` = weighted average of crew years, normalized 0–1
2. `phase_complexity_score` = ordinal encoding of phase difficulty
3. `material_workability_index` = material-specific property (e.g., tiles harder to cut precisely than lumber)
4. `weather_risk_score` = derived from location + season + material type (e.g., concrete in cold weather)
5. `supplier_reliability_score` = historical on-time delivery %, quality complaints
6. `site_constraint_score` = urban vs open site encoding

### Explainability
- SHAP values for each prediction — tells user: "Crew experience is the #1 driver of your concrete waste"

### Feedback Retraining
- Triggered when: company accumulates 5+ new actuals since last retrain
- Retrain runs asynchronously, new model version stored with metadata
- A/B comparison before deploying new model version

---

## 7. Tech Stack (Recommended)

| Layer | Technology | Reason |
|---|---|---|
| Frontend | Next.js 14 (React) | File-based routing, server components, easy deployment |
| Styling | Tailwind CSS + shadcn/ui | Fast, professional UI without custom CSS |
| Backend API | FastAPI (Python) | Async, fast, native Python ML integration |
| ML | XGBoost + scikit-learn | Best for tabular prediction, interpretable |
| Explainability | SHAP | Industry standard for ML feature attribution |
| Database | PostgreSQL (via Supabase) | Relational, scales well, free tier available |
| ORM | SQLAlchemy + Alembic | Python-native, migration support |
| Auth | Supabase Auth | JWT-based, handles multi-tenant company accounts |
| ML Model Storage | MLflow (local) → S3 | Version tracking for models |
| Deployment | Vercel (frontend) + Railway (backend) | Simple, low-cost for MVP |
| Background Jobs | Celery + Redis | Async retraining jobs |

---

## 8. User Flows

### Flow 1: New Project Prediction
1. Login → Dashboard → "New Project"
2. Enter project details (type, location, area, phase schedule)
3. Add crew profile or select existing
4. Add material list (manually or CSV upload)
5. Click "Generate Waste Predictions"
6. View predictions table with confidence intervals and explanations
7. Export adjusted order quantities

### Flow 2: Record Actuals (Feedback Loop)
1. Open existing project → select phase
2. Click "Record Waste Actuals"
3. Enter actual waste quantity per material
4. System logs delta and queues retraining if threshold met
5. Dashboard shows updated model accuracy

### Flow 3: Company Performance Review
1. Dashboard → "Analytics"
2. View: waste % trend over time, best/worst performing materials, crew comparison
3. Compare predicted vs actual accuracy over last N projects

---

## 9. MVP Scope (What to Build First)

### In MVP:
- [ ] User auth + company setup
- [ ] Project creation with material list input
- [ ] Waste prediction (rule-based + pre-trained XGBoost model with synthetic data)
- [ ] Predictions table with confidence intervals
- [ ] Actual waste recording (feedback input)
- [ ] Basic dashboard (project list + prediction vs actual chart)

### Post-MVP:
- [ ] Company-specific model fine-tuning
- [ ] SHAP explainability UI
- [ ] CSV export for procurement
- [ ] Supplier reliability scoring
- [ ] Mobile-responsive field view

---

## 10. Patent Filing Strategy

### Claims to File:
1. **Method claim**: The process of predicting per-material construction waste using the specific combination of crew behavioral signals + project phase + environmental factors
2. **System claim**: The feedback loop architecture that updates waste predictions using post-delivery actuals
3. **Data structure claim**: The feature snapshot schema that enables reproducible, auditable predictions

### Before Filing:
- Do USPTO prior art search on: "construction material waste prediction neural network", "material procurement optimization machine learning"
- File a **Provisional Patent Application** first (~$320 USD) to lock the priority date while building
- Convert to full utility patent within 12 months

### Recommended: File provisional BEFORE launching publicly (public disclosure starts 1-year clock in the US)

---

## 11. Go-to-Market

- **Target**: Mid-size contractors ($5M–$50M annual revenue) — large enough to care about waste costs, small enough to lack in-house data science
- **Pricing**: SaaS, per-project or per-seat, $99–$299/month
- **Entry point**: Free trial with first 3 projects, no credit card
- **Channels**: Construction industry LinkedIn, trade shows (World of Concrete, ConExpo), partnerships with quantity surveyors

---

*Next step: Build the MVP following this spec.*
