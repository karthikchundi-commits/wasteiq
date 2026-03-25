"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearToken } from "@/lib/auth";

export default function Navbar() {
  const router = useRouter();

  function logout() {
    clearToken();
    router.push("/login");
  }

  return (
    <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
      <Link href="/dashboard" className="text-xl font-bold text-brand-600">
        WasteIQ
      </Link>
      <div className="flex items-center gap-4">
        <Link href="/dashboard" className="text-sm text-gray-600 hover:text-gray-900">
          Dashboard
        </Link>
        <Link href="/analytics" className="text-sm text-gray-600 hover:text-gray-900">
          Analytics
        </Link>
        <Link href="/projects/new" className="btn-primary text-sm py-1.5">
          + New Project
        </Link>
        <button onClick={logout} className="text-sm text-gray-500 hover:text-gray-700">
          Sign out
        </button>
      </div>
    </nav>
  );
}
