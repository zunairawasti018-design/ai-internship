"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { FormEvent, useEffect, useRef, useState } from "react";
import { createMessage, fetchMessages } from "../services/messageService";

function CodeBlock({ language, value }: { language: string; value: string }) {
  const [copied, setCopied] = useState(false);

  async function copyCode() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="relative my-3 overflow-hidden rounded-xl border border-slate-700 bg-[#1e1e1e]">
      <div className="flex items-center justify-between border-b border-slate-700 px-3 py-2 text-xs text-slate-300">
        <span>{language || "code"}</span>
        <button type="button" onClick={copyCode} className="rounded-md border border-slate-600 px-2 py-1 hover:bg-slate-700">
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <SyntaxHighlighter language={language || "text"} style={vscDarkPlus} PreTag="div" customStyle={{ margin: 0, padding: "1rem", background: "transparent" }}>
        {value}
      </SyntaxHighlighter>
    </div>
  );
}

export function ChatInterface({ sessionId, sessionTitle }: { sessionId: number | null; sessionTitle?: string }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["messages", sessionId],
    queryFn: () => fetchMessages(sessionId as number),
    enabled: Boolean(sessionId),
    staleTime: 15_000,
  });

  const sendMutation = useMutation({
    mutationFn: (content: string) => createMessage(sessionId as number, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["messages", sessionId] });
      setDraft("");
    },
  });

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
  }, [draft]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || !sessionId || sendMutation.isPending) return;
    sendMutation.mutate(content);
  }

  if (!sessionId) {
    return (
      <main className="flex min-h-[44vh] flex-1 items-center justify-center bg-slate-50 p-6 text-center md:min-h-0">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">No chat selected</p>
          <h2 className="mt-2 text-2xl font-bold text-black">Choose a session to begin</h2>
          <p className="mt-2 text-sm text-slate-600">Create a new chat or select one from the sidebar.</p>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-[52vh] flex-1 flex-col bg-slate-50 md:min-h-0">
      <header className="border-b border-slate-200 bg-white px-4 py-4 md:px-8">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Active conversation</p>
        <h1 className="mt-1 text-xl font-bold text-black">{sessionTitle || `Session #${sessionId}`}</h1>
      </header>

      <section className="flex-1 space-y-4 overflow-y-auto px-4 py-5 md:px-8">
        {isLoading && <p className="text-sm text-slate-500">Loading messages...</p>}
        {isError && <p className="text-sm text-red-600">Unable to load messages.</p>}
        {!isLoading && data?.items.length === 0 && <p className="text-sm text-slate-500">No messages yet. Send the first one.</p>}
        {data?.items.map((message) => (
          <article key={message.id} className={`max-w-3xl rounded-2xl border p-4 ${message.role === "user" ? "ml-auto border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-black"}`}>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider opacity-60">{message.role}</p>
            <div className="markdown-body max-w-none break-words">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || "");
                    const value = String(children).replace(/\n$/, "");
                    const isBlock = Boolean(match) || value.includes("\n");

                    return isBlock ? (
                      <CodeBlock language={match?.[1] ?? "text"} value={value} />
                    ) : <code className="markdown-inline-code" {...props}>{children}</code>;
                  },
                  table({ children }) { return <div className="markdown-table-wrap"><table>{children}</table></div>; },
                  thead({ children }) { return <thead>{children}</thead>; },
                  th({ children }) { return <th>{children}</th>; },
                  td({ children }) { return <td>{children}</td>; },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          </article>
        ))}
      </section>

      <form onSubmit={handleSubmit} className="border-t border-slate-200 bg-white p-4 md:px-8">
        <div className="flex items-end gap-3 rounded-2xl border border-slate-300 bg-white p-2 focus-within:border-slate-900">
          <textarea
            ref={textareaRef}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            rows={2}
            placeholder="Write a message..."
            className="max-h-[180px] min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-black outline-none"
          />
          <button type="submit" disabled={!draft.trim() || sendMutation.isPending} className="rounded-xl bg-slate-900 px-4 py-2 font-medium text-white disabled:cursor-not-allowed disabled:opacity-40">
            {sendMutation.isPending ? "Sending" : "Send"}
          </button>
        </div>
        {sendMutation.isError && <p className="mt-2 text-sm text-red-600">Message could not be sent.</p>}
      </form>
    </main>
  );
}
