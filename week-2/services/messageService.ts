import api from "./api";

export interface MessageItem {
  id: number;
  content: string;
  role: "user" | "assistant" | "system";
  session_id: number;
}

export interface MessagesResponse {
  total: number;
  count: number;
  items: MessageItem[];
}

export async function fetchMessages(sessionId: number): Promise<MessagesResponse> {
  const response = await api.get<MessagesResponse>(`/chat-sessions/${sessionId}/messages`);
  return response.data;
}

export async function createMessage(sessionId: number, content: string) {
  const response = await api.post<MessageItem>(`/chat-sessions/${sessionId}/messages`, {
    session_id: sessionId,
    content,
    role: "user",
  });

  return response.data;
}
