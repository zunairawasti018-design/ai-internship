import api from "./api";
import { getClientToken } from "../lib/auth";

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

export interface DocumentStatus {
  id: number;
  filename: string;
  session_id: number;
  user_id: number;
  ingestion_status: "pending" | "processing" | "done" | "failed";
  ingestion_error: string | null;
  created_at: string;
}

export interface DocumentListResponse {
  total: number;
  count: number;
  items: DocumentStatus[];
}

export async function uploadDocument(sessionId: number, file: File): Promise<DocumentStatus> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post<DocumentStatus>(
    `/documents/sessions/${sessionId}/upload`,
    formData,
  );
  return response.data;
}

export async function fetchDocuments(sessionId: number): Promise<DocumentListResponse> {
  const response = await api.get<DocumentListResponse>(`/documents/sessions/${sessionId}`);
  return response.data;
}

export async function createStreamingMessage(
  sessionId: number,
  content: string,
  onChunk: (chunk: string) => void,
  signal?: AbortSignal
) {
  const token = getClientToken();
  const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

  const response = await fetch(`${baseUrl}/chat-sessions/${sessionId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      session_id: sessionId,
      content,
      role: "user",
    }),
    signal
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("The server did not return a readable response stream.");

  const decoder = new TextDecoder();
  let buffer = "";

  function dispatchEvent(event: string): boolean {
    const data = event
      .split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n");
    if (!data) return false;
    if (data === "[DONE]") return true;

    let parsed: { text?: string; error?: string };
    try {
      parsed = JSON.parse(data) as { text?: string; error?: string };
    } catch {
      throw new Error("The server returned an invalid streaming response.");
    }
    if (parsed.error) throw new Error(parsed.error);
    if (parsed.text) onChunk(parsed.text);
    return false;
  }

  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const events = buffer.split(/\r?\n\r?\n/);
      buffer = events.pop() ?? "";

      for (const event of events) {
        if (dispatchEvent(event)) return;
      }

      if (done) {
        if (buffer && dispatchEvent(buffer)) return;
        break;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
