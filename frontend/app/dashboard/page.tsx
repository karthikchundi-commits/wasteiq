"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/navbar";
import { projectsApi } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

interface Project {
  id: string;
  name: string;
  type: string;
  location: string;
  status: string;
  created_at: string;
  materials: any[];
}

export default function DashboardPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated()) { router.push("/login"); return; }
    projectsApi.list()
      .then((res) => setProjects(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [router]);

  const totalMaterials = projects.reduce((sum, p) => sum + (p.materials?.length || 0), 0);
  const predictedProjects = projects.filter((p) =>
    p.materials?.some((m: any) => m.prediction)
  ).length;

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold">Dashboard</h1>
            <p className="text-gray-500 text-sm mt-1">Your projects and waste predictions</p>
          </div>
          <Link href="/projects/new" className="btn-primary">+ New Project</Link>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="card text-center">
            <div className="text-3xl font-bold text-brand-600">{projects.length}</div>
            <div className="text-sm text-gray-500 mt-1">Total Projects</div>
          </div>
          <div className="card text-center">
            <div className="text-3xl font-bold text-brand-600">{totalMaterials}</div>
            <div className="text-sm text-gray-500 mt-1">Material Items</div>
          </div>
          <div className="card text-center">
            <div className="text-3xl font-bold text-brand-600">{predictedProjects}</div>
            <div className="text-sm text-gray-500 mt-1">Predictions Generated</div>
          </div>
        </div>

        {/* Project List */}
        {loading ? (
          <div className="text-center py-16 text-gray-400">Loading projects...</div>
        ) : projects.length === 0 ? (
          <div className="card text-center py-16">
            <p className="text-gray-500 mb-4">No projects yet. Create your first project to get predictions.</p>
            <Link href="/projects/new" className="btn-primary inline-block">Create first project</Link>
          </div>
        ) : (
          <div className="space-y-3">
            {projects.map((project) => (
              <Link key={project.id} href={`/projects/${project.id}`}>
                <div className="card hover:shadow-md transition-shadow cursor-pointer flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-gray-900">{project.name}</h3>
                    <p className="text-sm text-gray-500 mt-0.5">
                      {project.type} {project.location ? `· ${project.location}` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-4 text-sm text-gray-500">
                    <span>{project.materials?.length || 0} materials</span>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      project.status === "active"
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-600"
                    }`}>
                      {project.status}
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
