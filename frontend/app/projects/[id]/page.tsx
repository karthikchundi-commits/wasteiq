"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Navbar from "@/components/navbar";
import PredictionTable from "@/components/prediction-table";
import RecommendationPanel from "@/components/recommendation-panel";
import { projectsApi, predictionsApi, actualsApi, recommendationsApi, oracleApi } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

type Tab = "predictions" | "recommendations" | "oracle";

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [project, setProject] = useState<any>(null);
  const [predictions, setPredictions] = useState<any[]>([]);
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [tab, setTab] = useState<Tab>("predictions");
  const [showActualsForm, setShowActualsForm] = useState(false);
  const [actuals, setActuals] = useState<Record<string, string>>({});
  const [savingActuals, setSavingActuals] = useState(false);
  const [oracleLoading, setOracleLoading] = useState(false);
  const [oracleResult, setOracleResult] = useState<any>(null);

  useEffect(() => {
    if (!isAuthenticated()) { router.push("/login"); return; }
    Promise.all([
      projectsApi.get(id),
      predictionsApi.get(id),
    ]).then(([projRes, predRes]) => {
      setProject(projRes.data);
      setPredictions(predRes.data);
      if (predRes.data.length > 0) loadReport();
    }).finally(() => setLoading(false));
  }, [id, router]);

  async function loadReport() {
    try {
      const res = await recommendationsApi.get(id);
      setReport(res.data);
    } catch {}
  }

  async function generatePredictions() {
    setGenerating(true);
    try {
      const res = await predictionsApi.generate(id);
      setPredictions(res.data);
      const recRes = await recommendationsApi.get(id);
      setReport(recRes.data);
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
      await loadReport();
    } finally {
      setSavingActuals(false);
    }
  }

  async function pushToOracle() {
    setOracleLoading(true);
    setOracleResult(null);
    try {
      const res = await oracleApi.pushRequisition(id);
      setOracleResult(res.data);
    } catch (err: any) {
      setOracleResult({ success: false, error: err?.response?.data?.detail || "Oracle push failed" });
    } finally {
      setOracleLoading(false);
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
            <button onClick={() => setShowActualsForm(!showActualsForm)} className="btn-secondary text-sm">
              Record Actuals
            </button>
            <button onClick={generatePredictions} disabled={generating} className="btn-primary text-sm">
              {generating ? "Running AI..." : predictions.length > 0 ? "Re-run Predictions" : "Generate Predictions"}
            </button>
          </div>
        </div>

        {/* Tabs */}
        {predictions.length > 0 && (
          <div className="flex gap-1 bg-gray-100 p-1 rounded-lg mb-6 w-fit">
            {([
              { key: "predictions",     label: "Predictions" },
              { key: "recommendations", label: "Recommendations & Savings" },
              { key: "oracle",          label: "Oracle Fusion" },
            ] as { key: Tab; label: string }[]).map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`px-4 py-2 text-sm rounded-md font-medium transition-colors ${
                  tab === key ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        )}

        {/* Tab: Predictions */}
        {(tab === "predictions" || predictions.length === 0) && (
          <div className="card mb-6">
            <h2 className="font-semibold text-gray-800 mb-4">Waste Predictions</h2>
            {predictions.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <p className="mb-3">No predictions yet.</p>
                <button onClick={generatePredictions} disabled={generating} className="btn-primary">
                  {generating ? "Running AI..." : "Generate Predictions"}
                </button>
              </div>
            ) : (
              <PredictionTable predictions={predictions} />
            )}
          </div>
        )}

        {/* Tab: Recommendations */}
        {tab === "recommendations" && (
          <div className="mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-800 text-lg">AI Recommendations & Cost Savings</h2>
              <span className="text-xs text-gray-400">vs industry-standard 15% flat buffer</span>
            </div>
            {report ? (
              <RecommendationPanel report={report} />
            ) : (
              <div className="card text-center py-8 text-gray-400">
                Generate predictions first to see recommendations.
              </div>
            )}
          </div>
        )}

        {/* Tab: Oracle Fusion */}
        {tab === "oracle" && (
          <div className="card mb-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="font-semibold text-gray-800 text-lg">Oracle Fusion Procurement</h2>
                <p className="text-sm text-gray-500 mt-1">
                  Push WasteIQ-optimized quantities directly as a Purchase Requisition in Oracle Fusion.
                </p>
              </div>
              <span className="text-xs bg-orange-100 text-orange-700 px-2 py-1 rounded-full font-medium">Oracle ERP</span>
            </div>

            {predictions.length === 0 ? (
              <p className="text-gray-400 text-sm">Generate predictions first to enable Oracle push.</p>
            ) : (
              <>
                <div className="bg-gray-50 rounded-lg p-4 mb-4 text-sm space-y-1">
                  <p className="font-medium text-gray-700">What will be created in Oracle:</p>
                  <ul className="text-gray-500 space-y-1 ml-4 list-disc">
                    <li>Purchase Requisition for <strong>{project.name}</strong></li>
                    <li><strong>{predictions.length}</strong> line items with AI-optimized quantities</li>
                    <li>Each line includes predicted waste % and savings vs flat buffer in notes</li>
                  </ul>
                </div>

                <button
                  onClick={pushToOracle}
                  disabled={oracleLoading}
                  className="btn-primary"
                >
                  {oracleLoading ? "Pushing to Oracle..." : "Push Purchase Requisition to Oracle Fusion"}
                </button>

                {oracleResult && (
                  <div className={`mt-4 rounded-lg p-4 ${
                    oracleResult.success ? "bg-green-50 border border-green-200" : "bg-red-50 border border-red-200"
                  }`}>
                    {oracleResult.success ? (
                      <div className="space-y-2 text-sm">
                        {oracleResult.dry_run ? (
                          <>
                            <p className="font-semibold text-green-700">Dry Run — Oracle credentials not configured</p>
                            <p className="text-green-600">This is the payload that would be sent to Oracle Fusion:</p>
                            <pre className="bg-white rounded p-3 text-xs overflow-auto text-gray-700 max-h-64">
                              {JSON.stringify(oracleResult.payload_preview, null, 2)}
                            </pre>
                            <p className="text-gray-500 text-xs">
                              Add ORACLE_HOST, ORACLE_CLIENT_ID, ORACLE_CLIENT_SECRET, and ORACLE_TOKEN_URL to Vercel environment variables to go live.
                            </p>
                          </>
                        ) : (
                          <>
                            <p className="font-semibold text-green-700">Successfully pushed to Oracle Fusion</p>
                            <p className="text-green-600">Requisition: <strong>{oracleResult.requisition_number}</strong></p>
                            <p className="text-green-600">{oracleResult.lines_created} lines created</p>
                            {oracleResult.total_amount && (
                              <p className="text-green-600">Total: ${oracleResult.total_amount.toLocaleString()}</p>
                            )}
                            {oracleResult.oracle_url && (
                              <a href={oracleResult.oracle_url} target="_blank" rel="noreferrer"
                                className="text-blue-600 underline">View in Oracle Fusion</a>
                            )}
                          </>
                        )}
                      </div>
                    ) : (
                      <p className="text-red-700 text-sm font-medium">{oracleResult.error}</p>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Record Actuals */}
        {showActualsForm && (
          <div className="card">
            <h2 className="font-semibold text-gray-800 mb-1">Record Actual Waste</h2>
            <p className="text-sm text-gray-500 mb-4">
              Enter actual waste quantities to improve future predictions.
            </p>
            <div className="space-y-3">
              {project.materials.map((mat: any) => (
                <div key={mat.id} className="flex items-center gap-4">
                  <span className="w-40 text-sm capitalize">{mat.material_type.replace("_", " ")}</span>
                  <span className="text-sm text-gray-400 w-32">Est: {mat.estimated_quantity} {mat.unit}</span>
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
