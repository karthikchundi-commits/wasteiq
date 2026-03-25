"use client";

interface MaterialRec {
  material_id: string;
  material_type: string;
  unit: string;
  estimated_quantity: number;
  unit_price?: number;
  predicted_waste_pct: number;
  recommended_order_qty: number;
  flat_buffer_qty: number;
  ai_waste_qty: number;
  savings_qty: number;
  savings_amount?: number;
  savings_pct: number;
  action: string;
  recommendation: string;
  insight: string;
  actual_waste_pct?: number;
  prediction_accuracy?: string;
}

interface ReportData {
  project_name: string;
  total_estimated_cost?: number;
  total_flat_buffer_cost?: number;
  total_ai_recommended_cost?: number;
  total_savings_amount?: number;
  total_savings_pct?: number;
  co2_reduction_kg?: number;
  materials: MaterialRec[];
  actuals_recorded: number;
  avg_prediction_error_pct?: number;
}

interface Props {
  report: ReportData;
}

const ACTION_STYLE: Record<string, string> = {
  reduce:   "bg-green-100 text-green-700",
  increase: "bg-amber-100 text-amber-700",
  maintain: "bg-blue-100 text-blue-700",
};

const ACTION_LABEL: Record<string, string> = {
  reduce:   "Reduce order",
  increase: "Increase order",
  maintain: "Maintain order",
};

export default function RecommendationPanel({ report }: Props) {
  const fmt = (n?: number) =>
    n != null ? `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "—";

  return (
    <div className="space-y-6">
      {/* Savings Summary */}
      {report.total_savings_amount != null && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-center">
            <div className="text-2xl font-bold text-green-700">{fmt(report.total_savings_amount)}</div>
            <div className="text-xs text-green-600 mt-1">Total savings vs 15% buffer</div>
          </div>
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center">
            <div className="text-2xl font-bold text-blue-700">{report.total_savings_pct?.toFixed(1)}%</div>
            <div className="text-xs text-blue-600 mt-1">Cost reduction</div>
          </div>
          <div className="bg-purple-50 border border-purple-200 rounded-xl p-4 text-center">
            <div className="text-2xl font-bold text-purple-700">{fmt(report.total_ai_recommended_cost)}</div>
            <div className="text-xs text-purple-600 mt-1">AI-recommended spend</div>
          </div>
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center">
            <div className="text-2xl font-bold text-emerald-700">{report.co2_reduction_kg?.toLocaleString()} kg</div>
            <div className="text-xs text-emerald-600 mt-1">Est. CO₂ reduction</div>
          </div>
        </div>
      )}

      {/* vs flat buffer comparison bar */}
      {report.total_flat_buffer_cost != null && report.total_ai_recommended_cost != null && (
        <div className="card">
          <p className="text-sm font-medium text-gray-700 mb-3">Cost comparison vs industry flat 15% buffer</p>
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500 w-32">Industry buffer</span>
              <div className="flex-1 bg-red-100 rounded-full h-4 flex items-center px-2">
                <span className="text-xs text-red-700 font-medium">{fmt(report.total_flat_buffer_cost)}</span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500 w-32">WasteIQ AI</span>
              <div
                className="bg-green-400 rounded-full h-4 flex items-center px-2"
                style={{
                  width: `${Math.max(20, ((report.total_ai_recommended_cost / report.total_flat_buffer_cost) * 100))}%`
                }}
              >
                <span className="text-xs text-white font-medium">{fmt(report.total_ai_recommended_cost)}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Per-material recommendations */}
      <div className="space-y-3">
        {report.materials.map((rec) => (
          <div key={rec.material_id} className="card">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h4 className="font-semibold capitalize">{rec.material_type.replace("_", " ")}</h4>
                <p className="text-sm text-gray-500 mt-0.5">{rec.insight}</p>
              </div>
              <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${ACTION_STYLE[rec.action]}`}>
                {ACTION_LABEL[rec.action]}
              </span>
            </div>

            <div className="bg-gray-50 rounded-lg px-4 py-3 text-sm font-medium text-gray-800 mb-3">
              {rec.recommendation}
              {rec.savings_amount != null && rec.savings_amount > 0 && (
                <span className="ml-2 text-green-600 font-semibold">→ save {fmt(rec.savings_amount)}</span>
              )}
            </div>

            <div className="grid grid-cols-3 gap-3 text-center text-xs text-gray-500">
              <div>
                <div className="font-semibold text-gray-800">{rec.flat_buffer_qty} {rec.unit}</div>
                <div>15% flat buffer</div>
              </div>
              <div>
                <div className="font-semibold text-brand-700 text-sm">{rec.recommended_order_qty} {rec.unit}</div>
                <div className="text-brand-600">WasteIQ recommended</div>
              </div>
              <div>
                <div className="font-semibold text-green-600">{rec.savings_pct}% less</div>
                <div>{rec.savings_qty} {rec.unit} saved</div>
              </div>
            </div>

            {rec.prediction_accuracy && (
              <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-500">
                Prediction accuracy: <span className="font-medium text-gray-700">{rec.prediction_accuracy}</span>
                {rec.actual_waste_pct != null && ` (actual: ${rec.actual_waste_pct.toFixed(1)}%)`}
              </div>
            )}
          </div>
        ))}
      </div>

      {report.actuals_recorded > 0 && report.avg_prediction_error_pct != null && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm text-blue-700">
          Model accuracy on this project: avg error {report.avg_prediction_error_pct.toFixed(1)}% across {report.actuals_recorded} recorded actuals.
          {report.avg_prediction_error_pct < 3 && " Excellent accuracy."}
        </div>
      )}
    </div>
  );
}
