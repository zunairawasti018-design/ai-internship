import api from "./api";

export interface ChatSessionItem {
  id: number;
  title: string;
  user_id: number;
  created_at: string;
  updated_at: string;
}

export interface ChatSessionsResponse {
  total: number;
  count: number;
  items: ChatSessionItem[];
}

export async function fetchChatSessions(userId?: number): Promise<ChatSessionsResponse> {
  const response = await api.get<ChatSessionsResponse>("/chat-sessions", {
    params: userId ? { user_id: userId } : undefined,
  });

  return response.data;
}

export async function createChatSession(title: string, userId: number) {
  const response = await api.post<ChatSessionItem>("/chat-sessions", {
    title,
    user_id: userId,
  });

  return response.data;
}

export async function updateChatSession(sessionId: number, title: string) {
  const response = await api.patch<ChatSessionItem>(`/chat-sessions/${sessionId}`, {
    title,
  });

  return response.data;
}

export async function deleteChatSession(sessionId: number) {
  await api.delete(`/chat-sessions/${sessionId}`);
}
