"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/navbar";
import { projectsApi } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

const MATERIAL_TYPES = [
  "concrete", "steel_rebar", "lumber", "drywall",
  "tiles", "pipe", "insulation", "brick", "glass", "other",
];
const PHASES = ["foundation", "framing", "mep", "finishing", "landscaping"];
const PROJECT_TYPES = ["residential", "commercial", "industrial", "infrastructure"];

interface MaterialRow {
  material_type: string;
  estimated_quantity: string;
  unit: string;
  unit_price: string;
  phase_name: string;
  crew_profile_id: string;
}

export default function NewProjectPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    name: "", type: "residential", location: "", area_sqm: "",
  });
  const [materials, setMaterials] = useState<MaterialRow[]>([
    { material_type: "concrete", estimated_quantity: "", unit: "m3", unit_price: "", phase_name: "foundation", crew_profile_id: "" },
  ]);
  const [crews, setCrews] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) { router.push("/login"); return; }
    projectsApi.listCrews().then((res) => setCrews(res.data)).catch(() => {});
  }, [router]);

  const setField = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const setMatField = (i: number, key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setMaterials((ms) => ms.map((m, idx) => idx === i ? { ...m, [key]: e.target.value } : m));
  };

  const addMaterial = () =>
    setMaterials((ms) => [...ms, {
      material_type: "lumber", estimated_quantity: "", unit: "m3",
      unit_price: "", phase_name: "framing", crew_profile_id: "",
    }]);

  const removeMaterial = (i: number) =>
    setMaterials((ms) => ms.filter((_, idx) => idx !== i));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const phases = Array.from(new Set(materials.map((m) => m.phase_name))).map((phase_name) => ({
      phase_name,
    }));

    const payload = {
      ...form,
      area_sqm: form.area_sqm ? parseFloat(form.area_sqm) : null,
      phases,
      materials: materials.map((m) => ({
        material_type: m.material_type,
        estimated_quantity: parseFloat(m.estimated_quantity),
        unit: m.unit,
        unit_price: m.unit_price ? parseFloat(m.unit_price) : null,
        phase_name: m.phase_name || null,
        crew_profile_id: m.crew_profile_id || null,
      })),
    };

    try {
      const res = await projectsApi.create(payload);
      router.push(`/projects/${res.data.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to create project");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="max-w-3xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold mb-6">New Project</h1>
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Project Details */}
          <div className="card space-y-4">
            <h2 className="font-semibold text-gray-800">Project Details</h2>
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <label className="label">Project Name</label>
                <input className="input" value={form.name} onChange={setField("name")} required />
              </div>
              <div>
                <label className="label">Project Type</label>
                <select className="input" value={form.type} onChange={setField("type")}>
                  {PROJECT_TYPES.map((t) => (
                    <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Location</label>
                <input className="input" placeholder="City, Country" value={form.location} onChange={setField("location")} />
              </div>
              <div>
                <label className="label">Total Area (sqm)</label>
                <input className="input" type="number" value={form.area_sqm} onChange={setField("area_sqm")} />
              </div>
            </div>
          </div>

          {/* Materials */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-800">Materials</h2>
              <button type="button" onClick={addMaterial} className="btn-secondary text-sm py-1">
                + Add Material
              </button>
            </div>
            <div className="space-y-4">
              {materials.map((mat, i) => (
                <div key={i} className="border border-gray-200 rounded-lg p-4 space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium text-gray-700">Material {i + 1}</span>
                    {materials.length > 1 && (
                      <button type="button" onClick={() => removeMaterial(i)}
                        className="text-red-500 text-sm hover:text-red-700">Remove</button>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="label">Material Type</label>
                      <select className="input" value={mat.material_type} onChange={setMatField(i, "material_type")}>
                        {MATERIAL_TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="label">Phase</label>
                      <select className="input" value={mat.phase_name} onChange={setMatField(i, "phase_name")}>
                        {PHASES.map((p) => <option key={p} value={p}>{p}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="label">Estimated Quantity</label>
                      <input className="input" type="number" step="0.01" value={mat.estimated_quantity}
                        onChange={setMatField(i, "estimated_quantity")} required />
                    </div>
                    <div>
                      <label className="label">Unit</label>
                      <input className="input" placeholder="m3, kg, pcs" value={mat.unit}
                        onChange={setMatField(i, "unit")} required />
                    </div>
                    <div>
                      <label className="label">Unit Price (optional)</label>
                      <input className="input" type="number" step="0.01" placeholder="0.00"
                        value={mat.unit_price} onChange={setMatField(i, "unit_price")} />
                    </div>
                    <div>
                      <label className="label">Crew Profile</label>
                      <select className="input" value={mat.crew_profile_id} onChange={setMatField(i, "crew_profile_id")}>
                        <option value="">-- None --</option>
                        {crews.map((c) => (
                          <option key={c.id} value={c.id}>{c.name} ({c.size} workers)</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {error && <p className="text-red-600 text-sm">{error}</p>}
          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? "Creating..." : "Create Project & Get Predictions"}
          </button>
        </form>
      </main>
    </div>
  );
}
