"use client";

import { LogOut, UserCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AuthGuard } from "../../components/AuthGuard";
import { ChatInterface } from "../../components/ChatInterface";
import { ChatSidebar } from "../../components/ChatSidebar";
import useAuth from "../../hooks/useAuth";
import { getUserIdFromToken } from "../../lib/auth";
import { fetchCurrentUser } from "../../services/authService";
import { fetchChatSessions } from "../../services/chatSessionService";

export default function DashboardPage() {
  const router = useRouter();
  const logout = useAuth((state) => state.logout);
  const token = useAuth((state) => state.token);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const userId = getUserIdFromToken(token);

  const profileQuery = useQuery({
    queryKey: ["current-user"],
    queryFn: fetchCurrentUser,
    enabled: Boolean(token),
    staleTime: 60_000,
  });
  const sessionsQuery = useQuery({
    queryKey: ["chat-sessions", userId],
    queryFn: () => fetchChatSessions(userId as number),
    enabled: Boolean(userId),
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!selectedSessionId && sessionsQuery.data?.items[0]) {
      setSelectedSessionId(sessionsQuery.data.items[0].id);
    }
  }, [selectedSessionId, sessionsQuery.data]);

  function handleLogout() {
    logout();
    router.push("/login");
  }

  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 md:px-8">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Dashboard</p>
            <h1 className="text-xl font-bold text-black">Workspace</h1>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-2 text-right sm:flex">
              <UserCircle size={24} className="text-slate-500" aria-hidden="true" />
              <div>
                {profileQuery.isLoading ? <p className="text-sm text-slate-500">Loading profile...</p> : profileQuery.isError ? <p className="text-sm text-red-600">Profile unavailable</p> : <p className="text-sm font-semibold text-black">{profileQuery.data?.name}</p>}
                {profileQuery.data?.email && <p className="text-xs text-slate-500">{profileQuery.data.email}</p>}
              </div>
            </div>
            <button type="button" onClick={handleLogout} className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-black transition hover:bg-slate-100" aria-label="Logout">
              <LogOut size={16} aria-hidden="true" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </header>

        <div className="flex flex-1 flex-col md:flex-row">
          <ChatSidebar selectedSessionId={selectedSessionId} onSelectSession={(sessionId) => setSelectedSessionId(sessionId || null)} />
          <ChatInterface sessionId={selectedSessionId} sessionTitle={sessionsQuery.data?.items.find((session) => session.id === selectedSessionId)?.title} />
        </div>
      </div>
    </AuthGuard>
  );
}