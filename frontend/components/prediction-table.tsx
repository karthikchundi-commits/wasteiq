"use client";

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
  top_drivers: { feature: string; impact: number }[];
}

interface Props {
  predictions: Prediction[];
}

function WasteBar({ pct }: { pct: number }) {
  const color = pct < 8 ? "bg-green-500" : pct < 15 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-2">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${Math.min(pct * 2, 100)}%` }} />
      </div>
      <span className="text-sm font-semibold w-12 text-right">{pct.toFixed(1)}%</span>
    </div>
  );
}

export default function PredictionTable({ predictions }: Props) {
  if (predictions.length === 0) {
    return <p className="text-gray-400 text-sm py-4">No predictions generated yet.</p>;
  }

  const totalWasteCost = predictions.reduce((s, p) => s + (p.predicted_waste_cost || 0), 0);

  return (
    <div>
      {totalWasteCost > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4 flex items-center justify-between">
          <span className="text-amber-800 font-medium text-sm">Total predicted waste cost</span>
          <span className="text-amber-900 font-bold text-lg">
            ${totalWasteCost.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </span>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-xs text-gray-500 uppercase tracking-wide">
              <th className="pb-3 pr-4">Material</th>
              <th className="pb-3 pr-4">Est. Qty</th>
              <th className="pb-3 pr-4 min-w-[180px]">Predicted Waste</th>
              <th className="pb-3 pr-4">CI Range</th>
              <th className="pb-3 pr-4">Order Qty</th>
              <th className="pb-3 pr-4">Waste Cost</th>
              <th className="pb-3">Top Driver</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {predictions.map((p) => (
              <tr key={p.material_id} className="py-3">
                <td className="py-3 pr-4 font-medium capitalize">{p.material_type.replace("_", " ")}</td>
                <td className="py-3 pr-4 text-gray-600">{p.estimated_quantity} {p.unit}</td>
                <td className="py-3 pr-4">
                  <WasteBar pct={p.predicted_waste_pct} />
                </td>
                <td className="py-3 pr-4 text-gray-500 text-xs">
                  {p.ci_low.toFixed(1)}% – {p.ci_high.toFixed(1)}%
                </td>
                <td className="py-3 pr-4 font-semibold text-brand-700">
                  {p.recommended_order_qty} {p.unit}
                </td>
                <td className="py-3 pr-4 text-gray-600">
                  {p.predicted_waste_cost
                    ? `$${p.predicted_waste_cost.toLocaleString()}`
                    : "—"}
                </td>
                <td className="py-3 text-xs text-gray-500">
                  {p.top_drivers[0]
                    ? `${p.top_drivers[0].feature.replace(/_/g, " ")}`
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
