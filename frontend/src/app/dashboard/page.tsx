"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getProjects, createProject } from "@/lib/api";

type Project = {
  id: number;
  name: string;
  description: string | null;
};

export default function DashboardPage() {
  const [user, setUser] = useState<{ email: string; role: string } | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();

  const loadProjects = async (token: string) => {
    try {
      const data = await getProjects(token);
      setProjects(data);
    } catch {
      setError("Failed to load projects");
    }
  };

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    fetch("http://localhost:8000/auth/me", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Unauthorized");
        return res.json();
      })
      .then((data) => {
        setUser(data);
        loadProjects(token);
      })
      .catch(() => {
        localStorage.removeItem("token");
        router.push("/login");
      });
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    router.push("/login");
  };

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const token = localStorage.getItem("token");
    if (!token) return;

    try {
      await createProject(token, name, description);
      setName("");
      setDescription("");
      loadProjects(token);
    } catch {
      setError("Failed to create project");
    }
  };

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-900 text-white">
        Loading...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 p-8 text-white">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Welcome, {user.email}</h1>
        <button
          onClick={handleLogout}
          className="rounded-md bg-red-600 px-4 py-2 text-sm font-semibold hover:bg-red-700"
        >
          Logout
        </button>
      </div>
      <p className="mt-2 text-gray-400">Role: {user.role}</p>

      <div className="mt-8 grid grid-cols-1 gap-8 md:grid-cols-2">
        <div>
          <h2 className="mb-4 text-lg font-semibold">Create Project</h2>
          <form onSubmit={handleCreateProject} className="rounded-xl bg-gray-800 p-6">
            {error && (
              <p className="mb-4 rounded bg-red-500/20 p-2 text-sm text-red-400">
                {error}
              </p>
            )}
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Project name"
              className="mb-4 w-full rounded-md bg-gray-700 p-2 text-white outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description (optional)"
              className="mb-4 w-full rounded-md bg-gray-700 p-2 text-white outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              className="w-full rounded-md bg-blue-600 p-2 font-semibold hover:bg-blue-700"
            >
              Create
            </button>
          </form>
        </div>

        <div>
          <h2 className="mb-4 text-lg font-semibold">Your Projects</h2>
          <div className="space-y-3">
            {projects.length === 0 && (
              <p className="text-gray-500">No projects yet.</p>
            )}
            {projects.map((project) => (
              <div key={project.id} className="rounded-xl bg-gray-800 p-4">
                <h3 className="font-semibold">{project.name}</h3>
                {project.description && (
                  <p className="mt-1 text-sm text-gray-400">{project.description}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
