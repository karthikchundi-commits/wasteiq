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
          <div className="space-y-3">
            {/* Industry buffer row — always full width reference */}
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500 w-28 shrink-0">Industry 15%</span>
              <div className="flex-1 bg-red-100 rounded-full h-5 flex items-center px-2.5">
                <span className="text-xs text-red-700 font-semibold">{fmt(report.total_flat_buffer_cost)}</span>
              </div>
            </div>
            {/* WasteIQ row — proportional to flat buffer */}
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500 w-28 shrink-0">WasteIQ AI</span>
              <div className="flex-1 relative h-5">
                <div
                  className="absolute left-0 top-0 h-5 bg-green-400 rounded-full flex items-center px-2.5 min-w-fit"
                  style={{
                    width: `${Math.max(15, Math.min(100, (report.total_ai_recommended_cost / report.total_flat_buffer_cost) * 100))}%`
                  }}
                >
                  <span className="text-xs text-white font-semibold whitespace-nowrap">{fmt(report.total_ai_recommended_cost)}</span>
                </div>
              </div>
            </div>
          </div>
          {report.total_savings_amount != null && report.total_savings_amount > 0 && (
            <p className="text-xs text-green-600 font-medium mt-3">
              You save {fmt(report.total_savings_amount)} ({report.total_savings_pct?.toFixed(1)}% less) by using AI-optimized quantities
            </p>
          )}
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

      {/* Model evidence footer */}
      <div className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 space-y-1.5">
        <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Model Evidence</p>
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-500">
          <span>
            <span className="font-medium text-gray-700">Actuals recorded:</span>{" "}
            {report.actuals_recorded} material{report.actuals_recorded !== 1 ? "s" : ""}
          </span>
          {report.avg_prediction_error_pct != null ? (
            <span>
              <span className="font-medium text-gray-700">Avg prediction error:</span>{" "}
              <span className={report.avg_prediction_error_pct < 3 ? "text-green-600 font-semibold" : report.avg_prediction_error_pct < 6 ? "text-amber-600" : "text-red-600"}>
                {report.avg_prediction_error_pct.toFixed(1)}%
                {report.avg_prediction_error_pct < 3 ? " — excellent" : report.avg_prediction_error_pct < 6 ? " — good" : " — improving"}
              </span>
            </span>
          ) : (
            <span className="text-gray-400">Record actuals to measure prediction accuracy</span>
          )}
        </div>
        <p className="text-xs text-gray-400">
          {report.actuals_recorded === 0
            ? "These recommendations are based on the global model trained on industry-wide construction data. Record actual waste after each phase to personalise predictions to your company."
            : `These recommendations incorporate ${report.actuals_recorded} actual waste measurement${report.actuals_recorded !== 1 ? "s" : ""} from this project. Each recorded actual improves future predictions.`}
        </p>
      </div>
    </div>
  );
}
