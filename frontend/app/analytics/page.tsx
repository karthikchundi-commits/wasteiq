"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/navbar";
import { analyticsApi } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface Summary {
  total_projects: number;
  projects_with_actuals: number;
  total_predictions: number;
  total_actuals: number;
  avg_model_accuracy_pct: number | null;
  total_predicted_waste_cost: number | null;
}

interface MaterialAccuracy {
  material_type: string;
  avg_predicted_pct: number;
  avg_actual_pct: number | null;
  count_predictions: number;
  count_actuals: number;
}

interface CrewPerformance {
  crew_name: string;
  avg_actual_pct: number;
  count: number;
}

interface ProjectAccuracy {
  project_name: string;
  project_type: string;
  avg_predicted_pct: number | null;
  avg_actual_pct: number | null;
  material_count: number;
  actuals_count: number;
}

interface AnalyticsOverview {
  summary: Summary;
  material_accuracy: MaterialAccuracy[];
  crew_performance: CrewPerformance[];
  project_accuracy: ProjectAccuracy[];
}

function fmt(val: number | null | undefined, suffix = "%") {
  if (val == null) return "—";
  return `${val.toFixed(1)}${suffix}`;
}

function fmtCurrency(val: number | null | undefined) {
  if (val == null) return "—";
  return "$" + val.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function DeltaBadge({ predicted, actual }: { predicted: number | null; actual: number | null }) {
  if (predicted == null || actual == null) return <span className="text-gray-400 text-xs">no actuals</span>;
  const delta = actual - predicted;
  const color = Math.abs(delta) <= 2 ? "text-green-600" : delta > 0 ? "text-red-600" : "text-blue-600";
  return (
    <span className={`text-xs font-medium ${color}`}>
      {delta > 0 ? "+" : ""}{delta.toFixed(1)}%
    </span>
  );
}

export default function AnalyticsPage() {
  const router = useRouter();
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAuthenticated()) { router.push("/login"); return; }
    analyticsApi.overview()
      .then((res) => setData(res.data))
      .catch((err) => setError(err?.response?.data?.detail || err?.message || "Failed to load analytics"))
      .finally(() => setLoading(false));
  }, [router]);

  const materialChartData = data?.material_accuracy.map((m) => ({
    name: m.material_type.replace("_", " "),
    "Predicted %": m.avg_predicted_pct,
    ...(m.avg_actual_pct != null ? { "Actual %": m.avg_actual_pct } : {}),
  })) ?? [];

  const crewChartData = data?.crew_performance.map((c) => ({
    name: c.crew_name,
    "Avg Actual Waste %": c.avg_actual_pct,
    samples: c.count,
  })) ?? [];

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-gray-500 text-sm mt-1">Waste prediction accuracy and company performance</p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-6">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-16 text-gray-400">Loading analytics...</div>
        ) : data ? (
          <div className="space-y-8">

            {/* Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              <StatCard label="Total Projects" value={String(data.summary.total_projects)} />
              <StatCard label="With Actuals" value={String(data.summary.projects_with_actuals)} />
              <StatCard label="Predictions" value={String(data.summary.total_predictions)} />
              <StatCard label="Actuals Recorded" value={String(data.summary.total_actuals)} />
              <StatCard
                label="Model Accuracy"
                value={fmt(data.summary.avg_model_accuracy_pct)}
                highlight={data.summary.avg_model_accuracy_pct != null && data.summary.avg_model_accuracy_pct >= 85}
              />
              <StatCard
                label="Total Waste Cost"
                value={fmtCurrency(data.summary.total_predicted_waste_cost)}
              />
            </div>

            {/* Material Accuracy Chart */}
            <div className="card">
              <h2 className="text-lg font-semibold mb-1">Predicted vs Actual Waste % by Material</h2>
              <p className="text-sm text-gray-500 mb-4">
                Average waste percentage across all projects. Actual bars only appear when actuals have been recorded.
              </p>
              {materialChartData.length === 0 ? (
                <p className="text-gray-400 text-sm py-8 text-center">No predictions yet.</p>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={materialChartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(value: number) => `${value.toFixed(1)}%`} />
                    <Legend />
                    <Bar dataKey="Predicted %" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="Actual %" fill="#10b981" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

              {/* Crew Performance */}
              <div className="card">
                <h2 className="text-lg font-semibold mb-1">Crew Waste Performance</h2>
                <p className="text-sm text-gray-500 mb-4">Average actual waste % per crew (lower is better)</p>
                {crewChartData.length === 0 ? (
                  <p className="text-gray-400 text-sm py-8 text-center">Record actuals to see crew performance.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={crewChartData} layout="vertical" margin={{ top: 5, right: 20, left: 60, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12 }} />
                      <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={55} />
                      <Tooltip formatter={(value: number) => `${value.toFixed(1)}%`} />
                      <Bar dataKey="Avg Actual Waste %" fill="#8b5cf6" radius={[0, 3, 3, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>

              {/* Material Detail Table */}
              <div className="card">
                <h2 className="text-lg font-semibold mb-4">Material Accuracy Detail</h2>
                {data.material_accuracy.length === 0 ? (
                  <p className="text-gray-400 text-sm py-8 text-center">No data yet.</p>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500 border-b border-gray-100">
                        <th className="pb-2 font-medium">Material</th>
                        <th className="pb-2 font-medium text-right">Predicted</th>
                        <th className="pb-2 font-medium text-right">Actual</th>
                        <th className="pb-2 font-medium text-right">Delta</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {data.material_accuracy.map((m) => (
                        <tr key={m.material_type}>
                          <td className="py-2 capitalize">{m.material_type.replace("_", " ")}</td>
                          <td className="py-2 text-right text-blue-600">{fmt(m.avg_predicted_pct)}</td>
                          <td className="py-2 text-right text-emerald-600">{fmt(m.avg_actual_pct)}</td>
                          <td className="py-2 text-right">
                            <DeltaBadge predicted={m.avg_predicted_pct} actual={m.avg_actual_pct} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* Project Accuracy Table */}
            <div className="card">
              <h2 className="text-lg font-semibold mb-4">Per-Project Accuracy</h2>
              {data.project_accuracy.length === 0 ? (
                <p className="text-gray-400 text-sm py-8 text-center">No projects found.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b border-gray-100">
                      <th className="pb-2 font-medium">Project</th>
                      <th className="pb-2 font-medium">Type</th>
                      <th className="pb-2 font-medium text-right">Materials</th>
                      <th className="pb-2 font-medium text-right">Predicted %</th>
                      <th className="pb-2 font-medium text-right">Actual %</th>
                      <th className="pb-2 font-medium text-right">Delta</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {data.project_accuracy.map((p, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="py-2.5 font-medium text-gray-900">{p.project_name}</td>
                        <td className="py-2.5 capitalize text-gray-500">{p.project_type}</td>
                        <td className="py-2.5 text-right text-gray-500">
                          {p.actuals_count}/{p.material_count}
                        </td>
                        <td className="py-2.5 text-right text-blue-600">{fmt(p.avg_predicted_pct)}</td>
                        <td className="py-2.5 text-right text-emerald-600">{fmt(p.avg_actual_pct)}</td>
                        <td className="py-2.5 text-right">
                          <DeltaBadge predicted={p.avg_predicted_pct} actual={p.avg_actual_pct} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <p className="text-xs text-gray-400 mt-3">Materials column shows actuals recorded / total materials.</p>
            </div>

          </div>
        ) : null}
      </main>
    </div>
  );
}

function StatCard({ label, value, highlight = false }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="card text-center">
      <div className={`text-2xl font-bold ${highlight ? "text-green-600" : "text-brand-600"}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-1 leading-tight">{label}</div>
    </div>
  );
}
