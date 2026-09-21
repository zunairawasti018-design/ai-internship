"use client";

import axios from "axios";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { AuthGuard } from "../../components/AuthGuard";
import useAuth from "../../hooks/useAuth";
import { loginUser } from "../../services/authService";

export default function LoginPage() {
  const router = useRouter();
  const login = useAuth((state) => state.login);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    useAuth.getState().hydrate();
  }, []);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const normalizedEmail = email.trim().toLowerCase();

    if (!normalizedEmail) {
      setError("Email is required");
      return;
    }

    if (!password.trim()) {
      setError("Password is required");
      return;
    }

    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailPattern.test(normalizedEmail)) {
      setError("Enter a valid email address");
      return;
    }

    try {
      setLoading(true);
      const response = await loginUser({ email: normalizedEmail, password });
      login(response.access_token);
      router.push("/dashboard");
    } catch (error) {
      if (axios.isAxiosError(error)) {
        if (!error.response) {
          setError("Backend is not reachable. Start the week-1 API on port 8000.");
        } else if (error.response.status === 401) {
          setError("Email or password is incorrect. Register this email first if you do not have an account.");
        } else {
          setError("Login failed. Please try again.");
        }
      } else {
        setError("Login failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthGuard requireAuth={false}>
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
        <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <p className="text-sm font-medium uppercase tracking-[0.2em] text-black">
                Welcome back
              </p>
              <h1 className="mt-2 text-3xl font-bold text-black">Login</h1>
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-medium text-black">Email</label>
              <input
                type="email"
                placeholder="Email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none transition focus:border-slate-900 focus:ring-2 focus:ring-slate-200"
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

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-slate-900 px-4 py-2.5 font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Logging in..." : "Login"}
            </button>

            <p className="text-center text-sm text-black">
              Don&apos;t have an account? {" "}
              <Link href="/register" className="font-semibold text-black underline underline-offset-4">
                Create one
              </Link>
            </p>
          </form>
        </div>
      </main>
    </AuthGuard>
  );
}