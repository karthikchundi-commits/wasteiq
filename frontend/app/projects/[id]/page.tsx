"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Navbar from "@/components/navbar";
import PredictionTable from "@/components/prediction-table";
import { projectsApi, predictionsApi, actualsApi } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [project, setProject] = useState<any>(null);
  const [predictions, setPredictions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [showActualsForm, setShowActualsForm] = useState(false);
  const [actuals, setActuals] = useState<Record<string, string>>({});
  const [savingActuals, setSavingActuals] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) { router.push("/login"); return; }
    Promise.all([
      projectsApi.get(id),
      predictionsApi.get(id),
    ]).then(([projRes, predRes]) => {
      setProject(projRes.data);
      setPredictions(predRes.data);
    }).finally(() => setLoading(false));
  }, [id, router]);

  async function generatePredictions() {
    setGenerating(true);
    try {
      const res = await predictionsApi.generate(id);
      setPredictions(res.data);
    } finally {
      setGenerating(false);
    }
  }

  async function saveActuals() {
    setSavingActuals(true);
    try {
      const entries = Object.entries(actuals).filter(([, v]) => v !== "");
      await Promise.all(
        entries.map(([material_id, qty]) =>
          actualsApi.record({ material_line_item_id: material_id, actual_waste_qty: parseFloat(qty) })
        )
      );
      setShowActualsForm(false);
      setActuals({});
      alert("Actuals saved. Your model will improve with this data.");
    } finally {
      setSavingActuals(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="text-center py-24 text-gray-400">Loading project...</div>
      </div>
    );
  }

  if (!project) return null;

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="max-w-6xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">{project.name}</h1>
            <p className="text-gray-500 text-sm mt-1">
              {project.type} · {project.location || "No location"} · {project.materials.length} materials
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => setShowActualsForm(!showActualsForm)}
              className="btn-secondary text-sm"
            >
              Record Actuals
            </button>
            <button
              onClick={generatePredictions}
              disabled={generating}
              className="btn-primary text-sm"
            >
              {generating ? "Generating..." : predictions.length > 0 ? "Re-run Predictions" : "Generate Predictions"}
            </button>
          </div>
        </div>

        {/* Predictions */}
        <div className="card mb-6">
          <h2 className="font-semibold text-gray-800 mb-4">Waste Predictions</h2>
          {predictions.length === 0 ? (
            <div className="text-center py-8 text-gray-400">
              <p className="mb-3">No predictions yet.</p>
              <button onClick={generatePredictions} disabled={generating} className="btn-primary">
                {generating ? "Generating..." : "Generate Predictions"}
              </button>
            </div>
          ) : (
            <PredictionTable predictions={predictions} />
          )}
        </div>

        {/* Record Actuals */}
        {showActualsForm && (
          <div className="card">
            <h2 className="font-semibold text-gray-800 mb-1">Record Actual Waste</h2>
            <p className="text-sm text-gray-500 mb-4">
              Enter how much material was actually wasted. This trains the AI to improve future predictions.
            </p>
            <div className="space-y-3">
              {project.materials.map((mat: any) => (
                <div key={mat.id} className="flex items-center gap-4">
                  <span className="w-40 text-sm capitalize">{mat.material_type.replace("_", " ")}</span>
                  <span className="text-sm text-gray-400 w-32">
                    Est: {mat.estimated_quantity} {mat.unit}
                  </span>
                  <input
                    className="input w-40"
                    type="number"
                    step="0.01"
                    placeholder={`Actual waste (${mat.unit})`}
                    value={actuals[mat.id] || ""}
                    onChange={(e) => setActuals((a) => ({ ...a, [mat.id]: e.target.value }))}
                  />
                </div>
              ))}
            </div>
            <div className="flex gap-3 mt-4">
              <button onClick={saveActuals} disabled={savingActuals} className="btn-primary">
                {savingActuals ? "Saving..." : "Save Actuals"}
              </button>
              <button onClick={() => setShowActualsForm(false)} className="btn-secondary">Cancel</button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
