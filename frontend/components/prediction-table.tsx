"use client";

interface Driver {
  feature: string;
  impact: number;
}

interface Prediction {
  material_id: string;
  material_type: string;
  estimated_quantity: number;
  unit: string;
  predicted_waste_pct: number;
  ci_low: number;
  ci_high: number;
  recommended_order_qty: number;
  predicted_waste_cost?: number;
  top_drivers: Driver[];
  model_version?: string;
}

interface Props {
  predictions: Prediction[];
}

const FEATURE_LABELS: Record<string, string> = {
  material_workability: "Material workability",
  experience_index: "Crew experience",
  phase_complexity: "Phase complexity",
  environmental_risk: "Weather / environment",
  historical_waste: "Historical data",
  site_constraint: "Site constraints",
  material_workability_index: "Material workability",
  phase_complexity_score: "Phase complexity",
  environmental_risk_score: "Weather / environment",
  company_historical_waste_pct: "Historical data",
  site_constraint_score: "Site constraints",
};

function humanizeFeature(f: string) {
  return FEATURE_LABELS[f] ?? f.replace(/_/g, " ");
}

function getModelInfo(version?: string): { label: string; color: string; desc: string } {
  if (!version || version === "base_v1") {
    return {
      label: "Global model",
      color: "bg-blue-100 text-blue-700",
      desc: "Trained on industry-wide construction data. Record actuals to build your company model.",
    };
  }
  if (version.startsWith("company_")) {
    return {
      label: "Company model",
      color: "bg-green-100 text-green-700",
      desc: "Fine-tuned on your company's historical actuals. Higher accuracy.",
    };
  }
  return {
    label: "Heuristic",
    color: "bg-gray-100 text-gray-600",
    desc: "Rule-based estimate. Generate predictions after adding materials to get ML-backed results.",
  };
}

function getConfidence(ciLow: number, ciHigh: number): { label: string; color: string; desc: string } {
  const width = ciHigh - ciLow;
  if (width < 5) return { label: "High confidence", color: "text-green-700 bg-green-50 border-green-200", desc: `±${(width / 2).toFixed(1)}% range` };
  if (width < 12) return { label: "Medium confidence", color: "text-amber-700 bg-amber-50 border-amber-200", desc: `±${(width / 2).toFixed(1)}% range` };
  return { label: "Low confidence", color: "text-orange-700 bg-orange-50 border-orange-200", desc: `±${(width / 2).toFixed(1)}% range — needs more data` };
}

function WasteGauge({ pct, ciLow, ciHigh }: { pct: number; ciLow: number; ciHigh: number }) {
  const MAX = 30; // gauge max %
  const pointX = Math.min((pct / MAX) * 100, 100);
  const ciLowX = Math.min((ciLow / MAX) * 100, 100);
  const ciHighX = Math.min((ciHigh / MAX) * 100, 100);
  const barColor = pct < 8 ? "bg-green-500" : pct < 15 ? "bg-amber-500" : "bg-red-500";
  const ciColor = pct < 8 ? "bg-green-200" : pct < 15 ? "bg-amber-200" : "bg-red-200";

  return (
    <div className="space-y-1">
      <div className="relative h-3 bg-gray-100 rounded-full overflow-hidden">
        {/* CI range band */}
        <div
          className={`absolute h-full ${ciColor} rounded-full`}
          style={{ left: `${ciLowX}%`, width: `${ciHighX - ciLowX}%` }}
        />
        {/* Point estimate bar */}
        <div
          className={`absolute h-full ${barColor} rounded-full`}
          style={{ width: `${pointX}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-gray-400">
        <span>0%</span>
        <span className="font-semibold text-gray-700">{pct.toFixed(1)}%</span>
        <span>{MAX}%+</span>
      </div>
      <div className="text-xs text-gray-400">
        Range: {ciLow.toFixed(1)}% – {ciHigh.toFixed(1)}%
      </div>
    </div>
  );
}

function ShapDrivers({ drivers }: { drivers: Driver[] }) {
  if (!drivers || drivers.length === 0) return null;

  const maxAbs = Math.max(...drivers.map((d) => Math.abs(d.impact)), 0.001);

  return (
    <div className="mt-3 pt-3 border-t border-gray-100">
      <p className="text-xs font-medium text-gray-500 mb-2">Why this prediction:</p>
      <div className="space-y-1.5">
        {drivers.slice(0, 4).map((d, i) => {
          const width = Math.round((Math.abs(d.impact) / maxAbs) * 100);
          const isUp = d.impact > 0;
          return (
            <div key={i} className="flex items-center gap-2">
              <span className="text-xs text-gray-500 w-36 shrink-0">{humanizeFeature(d.feature)}</span>
              <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-2 rounded-full ${isUp ? "bg-red-400" : "bg-green-400"}`}
                  style={{ width: `${width}%` }}
                />
              </div>
              <span className={`text-xs font-medium w-16 text-right ${isUp ? "text-red-600" : "text-green-600"}`}>
                {isUp ? "▲ increases" : "▼ reduces"}
              </span>
            </div>
          );
        })}
      </div>
      <p className="text-xs text-gray-400 mt-1.5">
        Red = increases waste &nbsp;·&nbsp; Green = reduces waste
      </p>
    </div>
  );
}

export default function PredictionTable({ predictions }: Props) {
  if (predictions.length === 0) {
    return <p className="text-gray-400 text-sm py-4">No predictions generated yet.</p>;
  }

  const totalWasteCost = predictions.reduce((s, p) => s + (p.predicted_waste_cost || 0), 0);
  const modelVersion = predictions[0]?.model_version;
  const modelInfo = getModelInfo(modelVersion);

  return (
    <div className="space-y-4">
      {/* Model + cost header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${modelInfo.color}`}>
            {modelInfo.label}
          </span>
          <span className="text-xs text-gray-400">{modelInfo.desc}</span>
        </div>
        {totalWasteCost > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-1.5 flex items-center gap-2">
            <span className="text-amber-700 text-xs font-medium">Total predicted waste cost</span>
            <span className="text-amber-900 font-bold text-sm">
              ${totalWasteCost.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </span>
          </div>
        )}
      </div>

      {/* Prediction cards */}
      {predictions.map((p) => {
        const confidence = getConfidence(p.ci_low, p.ci_high);
        const wasteQty = (p.recommended_order_qty - p.estimated_quantity).toFixed(2);
        const action =
          p.predicted_waste_pct < 8 ? { label: "Low waste", color: "bg-green-100 text-green-700" }
          : p.predicted_waste_pct < 15 ? { label: "Moderate waste", color: "bg-amber-100 text-amber-700" }
          : { label: "High waste", color: "bg-red-100 text-red-700" };

        return (
          <div key={p.material_id} className="border border-gray-200 rounded-xl p-4 bg-white">
            {/* Card header */}
            <div className="flex items-start justify-between gap-2 mb-4">
              <div>
                <h3 className="font-semibold text-gray-900 capitalize text-base">
                  {p.material_type.replace("_", " ")}
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Estimated need: {p.estimated_quantity} {p.unit}
                </p>
              </div>
              <div className="flex items-center gap-2 flex-wrap justify-end">
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${action.color}`}>
                  {action.label}
                </span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${confidence.color}`}>
                  {confidence.label} · {confidence.desc}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Left: waste gauge */}
              <div>
                <p className="text-xs font-medium text-gray-500 mb-2">Predicted waste</p>
                <WasteGauge pct={p.predicted_waste_pct} ciLow={p.ci_low} ciHigh={p.ci_high} />
              </div>

              {/* Right: order recommendation */}
              <div className="flex flex-col gap-2">
                <p className="text-xs font-medium text-gray-500">Recommended order</p>
                <div className="flex items-baseline gap-1.5">
                  <span className="text-2xl font-bold text-brand-700">{p.recommended_order_qty}</span>
                  <span className="text-gray-500 text-sm">{p.unit}</span>
                </div>
                <div className="text-xs text-gray-400 space-y-0.5">
                  <div>Waste buffer: +{wasteQty} {p.unit}</div>
                  {p.predicted_waste_cost != null && (
                    <div className="text-amber-700 font-medium">
                      Waste cost: ${p.predicted_waste_cost.toLocaleString()}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* SHAP drivers */}
            <ShapDrivers drivers={p.top_drivers} />
          </div>
        );
      })}
    </div>
  );
}
