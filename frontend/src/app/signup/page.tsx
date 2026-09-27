"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { signupUser, loginUser } from "@/lib/api";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  setError("");

  try {
    await signupUser(email, password, companyName);
    const loginData = await loginUser(email, password);
    localStorage.setItem("token", loginData.access_token);
    router.push("/dashboard");
  } catch (err: any) {
    setError(err.message || "Something went wrong");
  }
};

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-900">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-xl bg-gray-800 p-8 shadow-lg"
      >
        <h1 className="mb-6 text-2xl font-bold text-white">
          Create your ReqMind AI account
        </h1>

        {error && (
          <p className="mb-4 rounded bg-red-500/20 p-2 text-sm text-red-400">
            {error}
          </p>
        )}

        <label className="mb-2 block text-sm text-gray-300">Company Name</label>
        <input
          type="text"
          value={companyName}
          onChange={(e) => setCompanyName(e.target.value)}
          className="mb-4 w-full rounded-md bg-gray-700 p-2 text-white outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Acme Corp"
        />

        <label className="mb-2 block text-sm text-gray-300">Email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-4 w-full rounded-md bg-gray-700 p-2 text-white outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="you@company.com"
        />

        <label className="mb-2 block text-sm text-gray-300">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-6 w-full rounded-md bg-gray-700 p-2 text-white outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="••••••••"
        />

        <button
          type="submit"
          className="w-full rounded-md bg-blue-600 p-2 font-semibold text-white hover:bg-blue-700"
        >
          Sign Up
        </button>

        <p className="mt-4 text-center text-sm text-gray-400">
          Already have an account?{" "}
          <Link href="/login" className="text-blue-400 hover:underline">
            Log in
          </Link>
        </p>
      </form>
    </div>
  );
}
