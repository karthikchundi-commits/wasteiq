"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/navbar";
import { actualsApi, type HistoricalRecord } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import { useEffect } from "react";

const MATERIAL_TYPES = [
  "concrete", "steel_rebar", "lumber", "drywall", "tiles",
  "pipe", "insulation", "brick", "glass", "other",
];

const PHASE_NAMES = ["foundation", "framing", "mep", "finishing", "landscaping"];

const UNITS: Record<string, string[]> = {
  concrete:    ["m3", "yd3"],
  steel_rebar: ["kg", "tons", "lbs"],
  lumber:      ["m3", "board ft", "pieces"],
  drywall:     ["sheets", "sqm", "sqft"],
  tiles:       ["sqm", "sqft", "pieces"],
  pipe:        ["m", "ft", "pieces"],
  insulation:  ["sqm", "sqft", "rolls"],
  brick:       ["pcs", "thousands"],
  glass:       ["sqm", "sqft", "panes"],
  other:       ["units", "kg", "m", "sqm"],
};

type Row = HistoricalRecord & { _id: number };

const EMPTY_ROW = (): Row => ({
  _id: Date.now() + Math.random(),
  material_type: "concrete",
  phase_name: "foundation",
  crew_size: 8,
  avg_experience_years: 5,
  location: "",
  estimated_quantity: 0,
  unit: "m3",
  actual_waste_qty: 0,
  notes: "",
});

const EXAMPLE_ROWS: Row[] = [
  { _id: 1, material_type: "concrete",    phase_name: "foundation", crew_size: 10, avg_experience_years: 7,  location: "Chennai",  estimated_quantity: 120, unit: "m3",     actual_waste_qty: 7.8,  notes: "Column footing over-pour" },
  { _id: 2, material_type: "lumber",      phase_name: "framing",    crew_size: 6,  avg_experience_years: 3,  location: "Mumbai",   estimated_quantity: 85,  unit: "m3",     actual_waste_qty: 11.2, notes: "Off-cuts framing" },
  { _id: 3, material_type: "tiles",       phase_name: "finishing",  crew_size: 4,  avg_experience_years: 8,  location: "Delhi",    estimated_quantity: 320, unit: "sqm",    actual_waste_qty: 38.5, notes: "Corner cuts + breakage" },
  { _id: 4, material_type: "drywall",     phase_name: "finishing",  crew_size: 5,  avg_experience_years: 4,  location: "Chennai",  estimated_quantity: 280, unit: "sheets", actual_waste_qty: 28.0, notes: "Door/window cut-outs" },
  { _id: 5, material_type: "steel_rebar", phase_name: "foundation", crew_size: 12, avg_experience_years: 10, location: "Bangalore",estimated_quantity: 8500,unit: "kg",     actual_waste_qty: 425,  notes: "Pier reinforcement off-cuts" },
];

export default function ImportHistoricalPage() {
  const router = useRouter();
  const [rows, setRows] = useState<Row[]>([EMPTY_ROW()]);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAuthenticated()) router.push("/login");
  }, [router]);

  function addRow() {
    setRows((r) => [...r, EMPTY_ROW()]);
  }

  function removeRow(id: number) {
    setRows((r) => r.filter((row) => row._id !== id));
  }

  function updateRow(id: number, field: keyof Row, value: any) {
    setRows((r) =>
      r.map((row) => {
        if (row._id !== id) return row;
        const updated = { ...row, [field]: value };
        // Auto-set default unit when material changes
        if (field === "material_type") {
          updated.unit = UNITS[value]?.[0] ?? "units";
        }
        return updated;
      })
    );
  }

  function loadExamples() {
    setRows(EXAMPLE_ROWS.map((r) => ({ ...r, _id: Date.now() + Math.random() })));
  }

  async function handleSubmit() {
    const valid = rows.filter(
      (r) => r.estimated_quantity > 0 && r.actual_waste_qty >= 0
    );
    if (valid.length === 0) {
      setError("Add at least one record with a quantity > 0.");
      return;
    }
    setSubmitting(true);
    setError("");
    setResult(null);
    try {
      const payload = valid.map(({ _id, ...r }) => ({
        ...r,
        location: r.location || undefined,
        notes: r.notes || undefined,
      }));
      const res = await actualsApi.importHistorical(payload);
      setResult(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Import failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold">Import Historical Project Data</h1>
          <p className="text-gray-500 text-sm mt-1">
            Add past project waste actuals to train the AI model on your company's patterns.
            The more data you provide, the more accurate predictions become.
          </p>
        </div>

        {/* Info banner */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 mb-6 flex items-start gap-3">
          <span className="text-blue-500 text-lg mt-0.5">ℹ</span>
          <div className="text-sm text-blue-700 space-y-0.5">
            <p className="font-semibold">How this improves predictions</p>
            <p>
              After import, WasteIQ trains a <strong>company-specific model</strong> using your actual waste
              data. Future predictions will reflect your company's real patterns — crew behaviour, typical
              materials, and locations — instead of just industry averages.
            </p>
            <p className="text-blue-500">Recommended: import at least 10–20 records for meaningful improvement.</p>
          </div>
        </div>

        {result ? (
          <div className="card text-center py-10 space-y-3">
            <div className="text-4xl">✅</div>
            <h2 className="text-xl font-bold text-green-700">{result.imported} records imported</h2>
            <p className="text-gray-600">{result.message}</p>
            {result.retraining_triggered && (
              <div className="inline-flex items-center gap-2 bg-green-100 text-green-700 text-sm px-3 py-1.5 rounded-full font-medium">
                Company model trained — your next predictions will use it
              </div>
            )}
            <div className="flex gap-3 justify-center pt-2">
              <button onClick={() => router.push("/dashboard")} className="btn-primary">
                Go to Dashboard
              </button>
              <button
                onClick={() => { setResult(null); setRows([EMPTY_ROW()]); }}
                className="btn-secondary"
              >
                Import more data
              </button>
            </div>
          </div>
        ) : (
          <>
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-4">
                {error}
              </div>
            )}

            {/* Table */}
            <div className="card overflow-x-auto">
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm font-medium text-gray-700">
                  {rows.length} record{rows.length !== 1 ? "s" : ""}
                </p>
                <button
                  onClick={loadExamples}
                  className="text-xs text-blue-600 hover:text-blue-800 underline"
                >
                  Load example data
                </button>
              </div>

              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-500 border-b border-gray-200">
                    <th className="pb-2 pr-2 font-medium">Material</th>
                    <th className="pb-2 pr-2 font-medium">Phase</th>
                    <th className="pb-2 pr-2 font-medium">Crew size</th>
                    <th className="pb-2 pr-2 font-medium">Exp. (yrs)</th>
                    <th className="pb-2 pr-2 font-medium">Location</th>
                    <th className="pb-2 pr-2 font-medium">Est. Qty</th>
                    <th className="pb-2 pr-2 font-medium">Unit</th>
                    <th className="pb-2 pr-2 font-medium">Actual waste</th>
                    <th className="pb-2 pr-2 font-medium">Waste %</th>
                    <th className="pb-2 font-medium"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {rows.map((row) => {
                    const pct =
                      row.estimated_quantity > 0
                        ? ((row.actual_waste_qty / row.estimated_quantity) * 100).toFixed(1)
                        : "—";
                    return (
                      <tr key={row._id} className="group">
                        <td className="py-1.5 pr-2">
                          <select
                            className="input py-1 text-sm w-28"
                            value={row.material_type}
                            onChange={(e) => updateRow(row._id, "material_type", e.target.value)}
                          >
                            {MATERIAL_TYPES.map((m) => (
                              <option key={m} value={m}>{m.replace("_", " ")}</option>
                            ))}
                          </select>
                        </td>
                        <td className="py-1.5 pr-2">
                          <select
                            className="input py-1 text-sm w-28"
                            value={row.phase_name}
                            onChange={(e) => updateRow(row._id, "phase_name", e.target.value)}
                          >
                            {PHASE_NAMES.map((p) => (
                              <option key={p} value={p}>{p}</option>
                            ))}
                          </select>
                        </td>
                        <td className="py-1.5 pr-2">
                          <input
                            type="number" min="1" max="200"
                            className="input py-1 text-sm w-16"
                            value={row.crew_size}
                            onChange={(e) => updateRow(row._id, "crew_size", parseInt(e.target.value) || 1)}
                          />
                        </td>
                        <td className="py-1.5 pr-2">
                          <input
                            type="number" min="0" max="40" step="0.5"
                            className="input py-1 text-sm w-16"
                            value={row.avg_experience_years}
                            onChange={(e) => updateRow(row._id, "avg_experience_years", parseFloat(e.target.value) || 0)}
                          />
                        </td>
                        <td className="py-1.5 pr-2">
                          <input
                            type="text"
                            className="input py-1 text-sm w-24"
                            placeholder="City"
                            value={row.location ?? ""}
                            onChange={(e) => updateRow(row._id, "location", e.target.value)}
                          />
                        </td>
                        <td className="py-1.5 pr-2">
                          <input
                            type="number" min="0" step="any"
                            className="input py-1 text-sm w-20"
                            value={row.estimated_quantity || ""}
                            onChange={(e) => updateRow(row._id, "estimated_quantity", parseFloat(e.target.value) || 0)}
                          />
                        </td>
                        <td className="py-1.5 pr-2">
                          <select
                            className="input py-1 text-sm w-20"
                            value={row.unit}
                            onChange={(e) => updateRow(row._id, "unit", e.target.value)}
                          >
                            {(UNITS[row.material_type] ?? ["units"]).map((u) => (
                              <option key={u} value={u}>{u}</option>
                            ))}
                          </select>
                        </td>
                        <td className="py-1.5 pr-2">
                          <input
                            type="number" min="0" step="any"
                            className="input py-1 text-sm w-20"
                            value={row.actual_waste_qty || ""}
                            onChange={(e) => updateRow(row._id, "actual_waste_qty", parseFloat(e.target.value) || 0)}
                          />
                        </td>
                        <td className="py-1.5 pr-2">
                          <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                            pct === "—" ? "text-gray-400"
                            : parseFloat(pct) < 8 ? "bg-green-100 text-green-700"
                            : parseFloat(pct) < 15 ? "bg-amber-100 text-amber-700"
                            : "bg-red-100 text-red-700"
                          }`}>
                            {pct}{pct !== "—" ? "%" : ""}
                          </span>
                        </td>
                        <td className="py-1.5">
                          <button
                            onClick={() => removeRow(row._id)}
                            className="text-gray-300 hover:text-red-500 text-lg leading-none"
                            title="Remove row"
                          >
                            ×
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              <button
                onClick={addRow}
                className="mt-3 text-sm text-brand-600 hover:text-brand-800 font-medium"
              >
                + Add row
              </button>
            </div>

            <div className="flex items-center justify-between mt-4">
              <p className="text-xs text-gray-400">
                {rows.filter((r) => r.estimated_quantity > 0).length} valid record(s) ready to import
              </p>
              <div className="flex gap-3">
                <button onClick={() => router.back()} className="btn-secondary">
                  Cancel
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={submitting || rows.filter((r) => r.estimated_quantity > 0).length === 0}
                  className="btn-primary"
                >
                  {submitting
                    ? "Importing & training model..."
                    : `Import ${rows.filter((r) => r.estimated_quantity > 0).length} records`}
                </button>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
