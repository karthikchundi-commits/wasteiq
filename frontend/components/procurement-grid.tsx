"use client";

import { useState } from "react";
import { procurementApi } from "@/lib/api";

interface ProcurementLine {
  id: string;
  line_number: number;
  item_description: string;
  item_category: string | null;
  material_type: string;
  ai_recommended_qty: number | null;
  requested_qty: number;
  unit_of_measure: string | null;
  unit_price: number | null;
  total_amount: number | null;
  need_by_date: string | null;
  deliver_to_location: string | null;
  requester_name: string | null;
  erp_item_code: string | null;
  flat_buffer_qty: number | null;
  savings_qty: number | null;
  savings_amount: number | null;
}

export interface ProcurementRequisition {
  id: string;
  project_id: string;
  status: string;
  erp_type: string | null;
  erp_requisition_id: string | null;
  erp_requisition_number: string | null;
  push_url: string | null;
  created_at: string;
  pushed_at: string | null;
  notes: string | null;
  lines: ProcurementLine[];
}

interface Props {
  requisition: ProcurementRequisition;
  onRequisitionChange: (req: ProcurementRequisition) => void;
  onPush: (pushUrl: string, erpType: string, authHeader: string) => void;
  pushing: boolean;
}

const STATUS_STYLE: Record<string, string> = {
  draft:    "bg-gray-100 text-gray-600",
  reviewed: "bg-blue-100 text-blue-700",
  pushed:   "bg-green-100 text-green-700",
  failed:   "bg-red-100 text-red-700",
};

export default function ProcurementGrid({ requisition, onRequisitionChange, onPush, pushing }: Props) {
  const [editingLine, setEditingLine] = useState<string | null>(null);
  const [lineEdits, setLineEdits] = useState<Record<string, Partial<ProcurementLine>>>({});
  const [savingLine, setSavingLine] = useState<string | null>(null);

  // Push config state
  const [pushUrl, setPushUrl] = useState(requisition.push_url ?? "");
  const [erpType, setErpType] = useState(requisition.erp_type ?? "custom");
  const [authHeader, setAuthHeader] = useState("");
  const [showPushConfig, setShowPushConfig] = useState(false);

  const fmt = (n?: number | null) =>
    n != null ? `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "—";

  const fmtDate = (d?: string | null) => {
    if (!d) return "";
    return new Date(d).toISOString().split("T")[0];
  };

  function startEdit(line: ProcurementLine) {
    setEditingLine(line.id);
    setLineEdits((prev) => ({
      ...prev,
      [line.id]: {
        requested_qty: line.requested_qty,
        need_by_date: fmtDate(line.need_by_date),
        deliver_to_location: line.deliver_to_location ?? "",
        erp_item_code: line.erp_item_code ?? "",
      },
    }));
  }

  async function saveLine(lineId: string) {
    setSavingLine(lineId);
    try {
      const edits = lineEdits[lineId] ?? {};
      const payload: Record<string, unknown> = {};
      if (edits.requested_qty != null) payload.requested_qty = Number(edits.requested_qty);
      if (edits.need_by_date) payload.need_by_date = new Date(edits.need_by_date as string).toISOString();
      if (edits.deliver_to_location !== undefined) payload.deliver_to_location = edits.deliver_to_location;
      if (edits.erp_item_code !== undefined) payload.erp_item_code = edits.erp_item_code;

      const res = await procurementApi.updateLine(lineId, payload as Parameters<typeof procurementApi.updateLine>[1]);
      const updatedLine: ProcurementLine = res.data;

      const updatedLines = requisition.lines.map((l) => (l.id === lineId ? updatedLine : l));
      onRequisitionChange({ ...requisition, lines: updatedLines, status: "reviewed" });
      setEditingLine(null);
    } finally {
      setSavingLine(null);
    }
  }

  const totalAmount = requisition.lines.reduce((s, l) => s + (l.total_amount ?? 0), 0);
  const totalSavings = requisition.lines.reduce((s, l) => s + (l.savings_amount ?? 0), 0);

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className={`text-xs font-medium px-2.5 py-1 rounded-full capitalize ${STATUS_STYLE[requisition.status] ?? STATUS_STYLE.draft}`}>
            {requisition.status}
          </span>
          {requisition.erp_requisition_number && (
            <span className="text-xs text-gray-500">ERP Ref: <strong>{requisition.erp_requisition_number}</strong></span>
          )}
        </div>
        <div className="flex gap-2">
          <a
            href={procurementApi.exportUrl(requisition.id, "csv")}
            target="_blank"
            rel="noreferrer"
            className="btn-secondary text-xs"
          >
            Export CSV
          </a>
          <a
            href={procurementApi.exportUrl(requisition.id, "json")}
            target="_blank"
            rel="noreferrer"
            className="btn-secondary text-xs"
          >
            Export JSON
          </a>
          <button
            onClick={() => setShowPushConfig(!showPushConfig)}
            className="btn-primary text-xs"
            disabled={pushing}
          >
            {pushing ? "Pushing..." : "Push to ERP"}
          </button>
        </div>
      </div>

      {/* Push config panel */}
      {showPushConfig && (
        <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-3">
          <p className="text-sm font-medium text-gray-700">ERP / Middleware Push Configuration</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">ERP Type</label>
              <select
                className="input text-sm w-full"
                value={erpType}
                onChange={(e) => setErpType(e.target.value)}
              >
                <option value="custom">Custom / Middleware</option>
                <option value="oracle_fusion">Oracle Fusion</option>
                <option value="sap">SAP</option>
                <option value="ms_dynamics">MS Dynamics</option>
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs text-gray-500 mb-1">Push URL (leave blank for dry run)</label>
              <input
                className="input text-sm w-full"
                placeholder="https://your-erp.com/api/requisitions"
                value={pushUrl}
                onChange={(e) => setPushUrl(e.target.value)}
              />
            </div>
            <div className="md:col-span-3">
              <label className="block text-xs text-gray-500 mb-1">Authorization Header (optional)</label>
              <input
                className="input text-sm w-full"
                placeholder='Bearer <token>  or  Basic <base64>'
                value={authHeader}
                onChange={(e) => setAuthHeader(e.target.value)}
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowPushConfig(false)} className="btn-secondary text-xs">Cancel</button>
            <button
              onClick={() => { setShowPushConfig(false); onPush(pushUrl, erpType, authHeader); }}
              disabled={pushing}
              className="btn-primary text-xs"
            >
              {pushUrl ? "Push Now" : "Dry Run (preview payload)"}
            </button>
          </div>
        </div>
      )}

      {/* Savings summary */}
      {totalAmount > 0 && (
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 text-center">
            <div className="text-lg font-bold text-blue-700">{fmt(totalAmount)}</div>
            <div className="text-xs text-blue-500">Total requested amount</div>
          </div>
          <div className="bg-green-50 border border-green-100 rounded-lg p-3 text-center">
            <div className="text-lg font-bold text-green-700">{fmt(totalSavings)}</div>
            <div className="text-xs text-green-500">Savings vs 15% flat buffer</div>
          </div>
          <div className="bg-gray-50 border border-gray-100 rounded-lg p-3 text-center">
            <div className="text-lg font-bold text-gray-700">{requisition.lines.length}</div>
            <div className="text-xs text-gray-500">Line items</div>
          </div>
        </div>
      )}

      {/* Grid */}
      <div className="overflow-x-auto rounded-xl border border-gray-200">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
            <tr>
              <th className="px-3 py-2 text-left w-8">#</th>
              <th className="px-3 py-2 text-left min-w-[180px]">Item Description</th>
              <th className="px-3 py-2 text-left">Category</th>
              <th className="px-3 py-2 text-right">AI Rec. Qty</th>
              <th className="px-3 py-2 text-right">Requested Qty</th>
              <th className="px-3 py-2 text-left">UOM</th>
              <th className="px-3 py-2 text-right">Unit Price</th>
              <th className="px-3 py-2 text-right">Total</th>
              <th className="px-3 py-2 text-left min-w-[110px]">Need By Date</th>
              <th className="px-3 py-2 text-left">Deliver To</th>
              <th className="px-3 py-2 text-left">ERP Item Code</th>
              <th className="px-3 py-2 text-right text-green-600">Savings</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {requisition.lines.map((line) => {
              const isEditing = editingLine === line.id;
              const edits = lineEdits[line.id] ?? {};

              return (
                <tr key={line.id} className={isEditing ? "bg-blue-50" : "hover:bg-gray-50"}>
                  <td className="px-3 py-2 text-gray-400">{line.line_number}</td>
                  <td className="px-3 py-2 font-medium text-gray-800">{line.item_description}</td>
                  <td className="px-3 py-2 text-gray-500 text-xs">{line.item_category}</td>

                  {/* AI Recommended Qty */}
                  <td className="px-3 py-2 text-right text-purple-600 font-medium">
                    {line.ai_recommended_qty} <span className="text-xs text-gray-400">{line.unit_of_measure}</span>
                  </td>

                  {/* Requested Qty — editable */}
                  <td className="px-3 py-2 text-right">
                    {isEditing ? (
                      <input
                        type="number"
                        step="0.01"
                        className="input w-24 text-right text-sm"
                        value={edits.requested_qty ?? line.requested_qty}
                        onChange={(e) =>
                          setLineEdits((prev) => ({
                            ...prev,
                            [line.id]: { ...prev[line.id], requested_qty: parseFloat(e.target.value) || 0 },
                          }))
                        }
                      />
                    ) : (
                      <span className="font-semibold text-gray-800">
                        {line.requested_qty} <span className="text-xs text-gray-400">{line.unit_of_measure}</span>
                      </span>
                    )}
                  </td>

                  <td className="px-3 py-2 text-gray-500">{line.unit_of_measure}</td>
                  <td className="px-3 py-2 text-right text-gray-600">{line.unit_price ? fmt(line.unit_price) : "—"}</td>
                  <td className="px-3 py-2 text-right font-medium">{fmt(line.total_amount)}</td>

                  {/* Need By Date — editable */}
                  <td className="px-3 py-2">
                    {isEditing ? (
                      <input
                        type="date"
                        className="input text-sm w-36"
                        value={(edits.need_by_date as string) ?? fmtDate(line.need_by_date)}
                        onChange={(e) =>
                          setLineEdits((prev) => ({
                            ...prev,
                            [line.id]: { ...prev[line.id], need_by_date: e.target.value },
                          }))
                        }
                      />
                    ) : (
                      <span className="text-gray-600">{fmtDate(line.need_by_date)}</span>
                    )}
                  </td>

                  {/* Deliver To — editable */}
                  <td className="px-3 py-2">
                    {isEditing ? (
                      <input
                        className="input text-sm w-32"
                        value={(edits.deliver_to_location as string) ?? line.deliver_to_location ?? ""}
                        onChange={(e) =>
                          setLineEdits((prev) => ({
                            ...prev,
                            [line.id]: { ...prev[line.id], deliver_to_location: e.target.value },
                          }))
                        }
                      />
                    ) : (
                      <span className="text-gray-500 text-xs">{line.deliver_to_location || "—"}</span>
                    )}
                  </td>

                  {/* ERP Item Code — editable */}
                  <td className="px-3 py-2">
                    {isEditing ? (
                      <input
                        className="input text-sm w-28"
                        placeholder="Optional"
                        value={(edits.erp_item_code as string) ?? line.erp_item_code ?? ""}
                        onChange={(e) =>
                          setLineEdits((prev) => ({
                            ...prev,
                            [line.id]: { ...prev[line.id], erp_item_code: e.target.value },
                          }))
                        }
                      />
                    ) : (
                      <span className="text-gray-400 text-xs font-mono">{line.erp_item_code || "—"}</span>
                    )}
                  </td>

                  {/* Savings */}
                  <td className="px-3 py-2 text-right text-green-600 text-xs">
                    {line.savings_amount ? fmt(line.savings_amount) : "—"}
                  </td>

                  {/* Actions */}
                  <td className="px-3 py-2">
                    {isEditing ? (
                      <div className="flex gap-1">
                        <button
                          onClick={() => saveLine(line.id)}
                          disabled={savingLine === line.id}
                          className="text-xs text-white bg-brand-600 hover:bg-brand-700 px-2 py-1 rounded"
                        >
                          {savingLine === line.id ? "..." : "Save"}
                        </button>
                        <button
                          onClick={() => setEditingLine(null)}
                          className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => startEdit(line)}
                        className="text-xs text-blue-500 hover:text-blue-700 px-2 py-1 rounded"
                      >
                        Edit
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {requisition.pushed_at && (
        <p className="text-xs text-gray-400 text-right">
          Last pushed: {new Date(requisition.pushed_at).toLocaleString()}
          {requisition.erp_requisition_number && ` · ERP ref: ${requisition.erp_requisition_number}`}
        </p>
      )}
    </div>
  );
}
