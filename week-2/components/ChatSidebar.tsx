"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Edit3, MessageSquarePlus, Trash2 } from "lucide-react";
import { getUserIdFromToken } from "../lib/auth";
import useAuth from "../hooks/useAuth";
import {
  createChatSession,
  deleteChatSession,
  fetchChatSessions,
  updateChatSession,
} from "../services/chatSessionService";

interface ChatSidebarProps {
  selectedSessionId: number | null;
  onSelectSession: (sessionId: number) => void;
}

export function ChatSidebar({ selectedSessionId, onSelectSession }: ChatSidebarProps) {
  const queryClient = useQueryClient();
  const token = useAuth((state) => state.token);
  const [newSessionTitle, setNewSessionTitle] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [editingSessionId, setEditingSessionId] = useState<number | null>(null);
  const [editingTitle, setEditingTitle] = useState("");

  const userId = getUserIdFromToken(token);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["chat-sessions", userId],
    queryFn: () => {
      if (!userId) throw new Error("User not authenticated");
      return fetchChatSessions(userId);
    },
    enabled: Boolean(userId),
    staleTime: 30_000,
  });

  const createSessionMutation = useMutation({
    mutationFn: ({ title, userId }: { title: string; userId: number }) => createChatSession(title, userId),
    onSuccess: (createdSession) => {
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
      onSelectSession(createdSession.id);
      setNewSessionTitle("");
      setIsCreating(false);
    },
  });

  const updateSessionMutation = useMutation({
    mutationFn: ({ sessionId, title }: { sessionId: number; title: string }) =>
      updateChatSession(sessionId, title),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
      setEditingSessionId(null);
    },
  });

  const deleteSessionMutation = useMutation({
    mutationFn: deleteChatSession,
    onSuccess: (_, deletedSessionId) => {
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
      if (selectedSessionId === deletedSessionId) {
        onSelectSession(0);
      }
    },
  });

  function handleCreateSession() {
    const title = newSessionTitle.trim();
    if (!title || !userId) return;

    createSessionMutation.mutate({
      title,
      userId,
    });
  }

  function startEditing(sessionId: number, title: string) {
    setEditingSessionId(sessionId);
    setEditingTitle(title);
  }

  function saveTitle(sessionId: number) {
    const title = editingTitle.trim();
    if (!title) return;
    updateSessionMutation.mutate({ sessionId, title });
  }

  const mutationError = createSessionMutation.isError || updateSessionMutation.isError || deleteSessionMutation.isError;

  return (
    <aside className="flex w-full flex-col border-b border-slate-200 bg-white p-4 md:max-w-sm md:border-b-0 md:border-r">
      <div className="flex items-center justify-between gap-3 border-b border-slate-200 pb-4">
        <h2 className="text-lg font-semibold text-slate-900">Chat Sessions</h2>
        <button
          type="button"
          className="rounded-lg bg-slate-900 px-2.5 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
          onClick={() => setIsCreating((value) => !value)}
          aria-label="Create new chat session"
        >
          <MessageSquarePlus size={16} aria-hidden="true" />
        </button>
      </div>

      {isCreating && (
        <div className="mt-4 flex gap-2">
          <input
            value={newSessionTitle}
            onChange={(event) => setNewSessionTitle(event.target.value)}
            placeholder="Session title"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-900"
          />
          <button
            type="button"
            disabled={createSessionMutation.isPending}
            onClick={handleCreateSession}
            className="rounded-lg bg-slate-800 px-3 py-2 text-sm font-medium text-white"
          >
            {createSessionMutation.isPending ? "Adding..." : "Add"}
          </button>
        </div>
      )}

      <div className="mt-4 max-h-[36vh] space-y-2 overflow-y-auto pr-1 md:max-h-none md:flex-1">
        {mutationError && <p className="rounded-lg bg-red-50 p-2 text-sm text-red-700">Could not update sessions. Please try again.</p>}
        {isLoading && <p className="text-sm text-slate-500">Loading sessions...</p>}
        {isError && <p className="rounded-lg bg-red-50 p-2 text-sm text-red-700">Unable to load sessions. Check your connection and retry.</p>}

        {!isLoading && data?.items.map((session) => (
          <div key={session.id} className={`group rounded-xl border p-3 transition ${selectedSessionId === session.id ? "border-slate-900 bg-slate-100" : "border-slate-200 bg-slate-50 hover:border-slate-300"}`}>
            {editingSessionId === session.id ? (
              <input
                autoFocus
                value={editingTitle}
                onChange={(event) => setEditingTitle(event.target.value)}
                onBlur={() => saveTitle(session.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") saveTitle(session.id);
                  if (event.key === "Escape") setEditingSessionId(null);
                }}
                className="w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm text-black outline-none"
              />
            ) : (
              <button type="button" onClick={() => onSelectSession(session.id)} className="w-full text-left">
                <p className="font-medium text-black">{session.title}</p>
                <p className="mt-1 text-xs text-slate-500">Updated {new Date(session.updated_at).toLocaleDateString()}</p>
              </button>
            )}
            <div className="mt-2 flex gap-2 text-xs text-slate-600">
              <button type="button" onClick={() => startEditing(session.id, session.title)} className="rounded p-1 hover:bg-slate-200 hover:text-black" aria-label={`Rename ${session.title}`} title="Rename session">
                <Edit3 size={15} aria-hidden="true" />
              </button>
              <button type="button" onClick={() => deleteSessionMutation.mutate(session.id)} className="rounded p-1 hover:bg-red-100 hover:text-red-600" aria-label={`Delete ${session.title}`} title="Delete session">
                <Trash2 size={15} aria-hidden="true" />
              </button>
            </div>
          </div>
        ))}

        {!isLoading && data?.items.length === 0 && (
          <p className="text-sm text-slate-500">No sessions yet.</p>
        )}
      </div>
    </aside>
  );
}
