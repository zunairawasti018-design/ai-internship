"use client";

import axios from "axios";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { AuthGuard } from "../../components/AuthGuard";
import { registerUser } from "../../services/authService";

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function handleRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuccess("");

    if (!name.trim()) {
      setError("Name is required");
      return;
    }

    if (!email.trim()) {
      setError("Email is required");
      return;
    }

    if (!password.trim()) {
      setError("Password is required");
      return;
    }

    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailPattern.test(email)) {
      setError("Enter a valid email address");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters long");
      return;
    }

    try {
      await registerUser({ name, email, password });
      setSuccess("Account created successfully. Redirecting to login...");
      setTimeout(() => router.push("/login"), 900);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 409) {
        setError("An account with this email already exists. Please login instead.");
      } else if (axios.isAxiosError(error) && !error.response) {
        setError("Backend is not reachable. Start the week-1 API on port 8000.");
      } else {
        setError("Unable to create account. Please try again.");
      }
    }
  }

  return (
    <AuthGuard requireAuth={false}>
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
        <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
          <form onSubmit={handleRegister} className="space-y-5">
            <div>
              <p className="text-sm font-medium uppercase tracking-[0.2em] text-black">
                Create account
              </p>
              <h1 className="mt-2 text-3xl font-bold text-black">Register</h1>
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-medium text-black">Name</label>
              <input
                type="text"
                placeholder="Full name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none transition focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
              />
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-medium text-black">Email</label>
              <input
                type="email"
                placeholder="Email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-black outline-none transition focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
              />
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-medium text-black">Password</label>
              <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-black outline-none transition focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
              />
            </div>

            {error && <p className="text-sm font-medium text-red-600">{error}</p>}
            {success && <p className="text-sm font-medium text-emerald-600">{success}</p>}

            <button
              type="submit"
              className="w-full rounded-lg bg-slate-900 px-4 py-2.5 font-medium text-white transition hover:bg-slate-800"
            >
              Register
            </button>

            <p className="text-center text-sm text-black">
              Already have an account? {" "}
              <Link href="/login" className="font-semibold text-black underline underline-offset-4">
                Login
              </Link>
            </p>
          </form>
        </div>
      </main>
    </AuthGuard>
  );
}