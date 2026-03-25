"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Navbar from "@/components/navbar";
import PredictionTable from "@/components/prediction-table";
import RecommendationPanel from "@/components/recommendation-panel";
import ProcurementGrid, { type ProcurementRequisition } from "@/components/procurement-grid";
import { projectsApi, predictionsApi, actualsApi, recommendationsApi, procurementApi } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

type Tab = "predictions" | "recommendations" | "procurement";

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

  // Procurement state
  const [requisition, setRequisition] = useState<ProcurementRequisition | null>(null);
  const [stagingReq, setStagingReq] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [pushResult, setPushResult] = useState<any>(null);

  useEffect(() => {
    if (!isAuthenticated()) { router.push("/login"); return; }
    Promise.all([
      projectsApi.get(id),
      predictionsApi.get(id),
    ]).then(([projRes, predRes]) => {
      setProject(projRes.data);
      setPredictions(predRes.data);
      if (predRes.data.length > 0) {
        loadReport();
        loadRequisition();
      }
    }).finally(() => setLoading(false));
  }, [id, router]);

  async function loadReport() {
    try {
      const res = await recommendationsApi.get(id);
      setReport(res.data);
    } catch {}
  }

  async function loadRequisition() {
    try {
      const res = await procurementApi.get(id);
      setRequisition(res.data);
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

  async function stageRequisition() {
    setStagingReq(true);
    setPushResult(null);
    try {
      const res = await procurementApi.stage(id);
      setRequisition(res.data);
    } finally {
      setStagingReq(false);
    }
  }

  async function pushToErp(pushUrl: string, erpType: string, authHeader: string) {
    if (!requisition) return;
    setPushing(true);
    setPushResult(null);
    try {
      const res = await procurementApi.push(requisition.id, {
        push_url: pushUrl || undefined,
        erp_type: erpType !== "custom" ? erpType : undefined,
        auth_header: authHeader || undefined,
      });
      setPushResult(res.data);
      setRequisition((prev) => prev ? { ...prev, status: res.data.dry_run ? prev.status : "pushed" } : prev);
    } catch (err: any) {
      setPushResult({ success: false, error: err?.response?.data?.detail || "Push failed" });
    } finally {
      setPushing(false);
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
              { key: "procurement",     label: "Procurement" },
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

        {/* Tab: Procurement */}
        {tab === "procurement" && (
          <div className="mb-6 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="font-semibold text-gray-800 text-lg">ERP Procurement</h2>
                <p className="text-sm text-gray-500 mt-1">
                  Stage AI-optimized quantities as a requisition, edit inline, then push to any ERP or middleware endpoint.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full font-medium">ERP-Agnostic</span>
                <button
                  onClick={stageRequisition}
                  disabled={stagingReq || predictions.length === 0}
                  className="btn-secondary text-sm"
                >
                  {stagingReq ? "Staging..." : requisition ? "Re-stage from AI" : "Stage Requisition"}
                </button>
              </div>
            </div>

            {predictions.length === 0 && (
              <div className="card text-center py-8 text-gray-400">
                Generate predictions first to enable procurement staging.
              </div>
            )}

            {predictions.length > 0 && !requisition && (
              <div className="card text-center py-10 text-gray-400">
                <p className="mb-4 text-gray-500">No requisition staged yet.<br />
                  Click <strong>Stage Requisition</strong> to create an editable procurement grid from AI predictions.
                </p>
                <button onClick={stageRequisition} disabled={stagingReq} className="btn-primary">
                  {stagingReq ? "Staging..." : "Stage Requisition"}
                </button>
              </div>
            )}

            {requisition && (
              <ProcurementGrid
                requisition={requisition}
                onRequisitionChange={setRequisition}
                onPush={pushToErp}
                pushing={pushing}
              />
            )}

            {/* Push result */}
            {pushResult && (
              <div className={`rounded-xl p-4 border ${
                pushResult.success ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"
              }`}>
                {pushResult.success ? (
                  <div className="space-y-2 text-sm">
                    {pushResult.dry_run ? (
                      <>
                        <p className="font-semibold text-green-700">Dry Run — No ERP endpoint configured</p>
                        <p className="text-green-600 text-xs">This is the standard WasteIQ middleware payload that would be sent:</p>
                        <pre className="bg-white rounded-lg p-3 text-xs overflow-auto text-gray-700 max-h-72">
                          {JSON.stringify(pushResult.payload, null, 2)}
                        </pre>
                        <p className="text-gray-500 text-xs">
                          Configure a Push URL in the Push to ERP dialog to go live. Supports Oracle Fusion, SAP, MS Dynamics, or any custom REST endpoint.
                        </p>
                      </>
                    ) : (
                      <>
                        <p className="font-semibold text-green-700">Successfully pushed to ERP</p>
                        {pushResult.erp_requisition_number && (
                          <p className="text-green-600">Requisition: <strong>{pushResult.erp_requisition_number}</strong></p>
                        )}
                        <p className="text-green-600">{pushResult.lines_pushed} lines pushed</p>
                        {pushResult.total_amount > 0 && (
                          <p className="text-green-600">Total: ${pushResult.total_amount.toLocaleString()}</p>
                        )}
                      </>
                    )}
                  </div>
                ) : (
                  <p className="text-red-700 text-sm font-medium">{pushResult.error}</p>
                )}
              </div>
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
