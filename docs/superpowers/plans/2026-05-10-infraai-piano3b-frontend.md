# InfraAI Piano 3b: Frontend Next.js Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Next.js web interface with login, streaming chat, server inventory list, and CSV import for RDM.

**Architecture:** Next.js 14 App Router with React Server Components where possible. The frontend calls the FastAPI backend via HTTP (on the same Docker network the backend is at `http://backend:8000`). Authentication uses a simple password stored in a cookie-based session (Next.js middleware enforces it). SSE streaming from the backend is piped through a Next.js API route to avoid CORS and expose auth headers. No database access from the frontend — everything goes through the backend API.

**Tech Stack:** Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, shadcn/ui components, Vitest + React Testing Library for unit tests, Playwright for E2E.

---

## File Structure

```
frontend/
  app/
    layout.tsx             — root layout, Tailwind, font
    page.tsx               — redirects to /chat if logged in, else /login
    login/
      page.tsx             — login form
      actions.ts           — server action: validate password, set cookie
    chat/
      page.tsx             — chat page layout
      ChatInterface.tsx    — client component: input, message list, SSE consumer
      useChat.ts           — custom hook: manages messages, sends to /api/chat
    inventory/
      page.tsx             — server list with client/source filters
      ServerTable.tsx      — client component: filterable table
      ImportCSV.tsx        — CSV file upload form (calls backend)
  api/
    chat/
      route.ts             — POST: forward to backend SSE, stream back to client
    inventory/
      servers/
        route.ts           — GET: proxy to backend /api/inventory/servers
      import-rdm-csv/
        route.ts           — POST: proxy multipart to backend
  middleware.ts            — protect /chat and /inventory routes, redirect to /login
  lib/
    session.ts             — read/write auth cookie helpers
    api.ts                 — typed fetch wrappers for backend calls
  components/
    NavBar.tsx             — top navigation: Chat | Inventario | Logout
  public/                  — (empty, Next.js default)
  next.config.ts           — BACKEND_URL env var
  tailwind.config.ts
  tsconfig.json
  package.json
  Dockerfile
  tests/
    login.test.tsx         — login action validation
    useChat.test.ts        — hook message state
    ServerTable.test.tsx   — filter logic
    middleware.test.ts     — redirect behavior
```

---

### Task 1: Next.js Project Bootstrap

Creates the Next.js project with TypeScript, Tailwind, and shadcn/ui. No logic — just the working scaffold with a test runner configured.

**Files:**
- Create: `frontend/` (entire Next.js project)

- [ ] **Step 1: Bootstrap the Next.js app**

```bash
cd D:\Claude_Code\infraai
npx create-next-app@14 frontend --typescript --tailwind --eslint --app --src-dir no --import-alias "@/*" --use-npm
```

When prompted: accept all defaults.

- [ ] **Step 2: Install shadcn/ui and additional deps**

```bash
cd D:\Claude_Code\infraai\frontend
npx shadcn-ui@latest init
```

Accept defaults (style: Default, base color: Slate, CSS variables: yes).

Then add the components we'll use:

```bash
npx shadcn-ui@latest add button input card badge table
```

- [ ] **Step 3: Install testing dependencies**

```bash
npm install --save-dev vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

- [ ] **Step 4: Configure Vitest**

Create `frontend/vitest.config.ts`:

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
  },
});
```

Create `frontend/tests/setup.ts`:

```typescript
import "@testing-library/jest-dom";
```

- [ ] **Step 5: Add test script to `package.json`**

In `frontend/package.json`, add to `"scripts"`:

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 6: Create `frontend/next.config.ts`**

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  env: {
    BACKEND_URL: process.env.BACKEND_URL ?? "http://backend:8000",
  },
};

export default nextConfig;
```

- [ ] **Step 7: Create `frontend/Dockerfile`**

```dockerfile
FROM node:20-alpine AS base
WORKDIR /app

FROM base AS deps
COPY package.json package-lock.json ./
RUN npm ci

FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM base AS runner
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

- [ ] **Step 8: Add `output: "standalone"` to next.config.ts**

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  env: {
    BACKEND_URL: process.env.BACKEND_URL ?? "http://backend:8000",
  },
};

export default nextConfig;
```

- [ ] **Step 9: Add frontend service to `docker-compose.yml`**

Add alongside `infra-ai-backend`:

```yaml
  infra-ai-frontend:
    build: ./frontend
    restart: unless-stopped
    env_file: .env
    environment:
      - BACKEND_URL=http://infra-ai-backend:8000
    depends_on:
      - infra-ai-backend
    ports:
      - "3000:3000"
```

- [ ] **Step 10: Verify the scaffold runs**

```bash
cd D:\Claude_Code\infraai\frontend
npm run dev
```

Expected: Next.js server starts on http://localhost:3000, shows default Next.js page.

Stop with Ctrl+C.

- [ ] **Step 11: Commit**

```bash
git -C D:\Claude_Code\infraai add frontend/ docker-compose.yml
git -C D:\Claude_Code\infraai commit -m "feat: next.js 14 frontend scaffold with tailwind, shadcn/ui, vitest"
```

---

### Task 2: Session Middleware + Login Page

Implements cookie-based password auth. Protected routes (`/chat`, `/inventory`) redirect to `/login` if the cookie is absent. Login sets the cookie.

**Files:**
- Create: `frontend/lib/session.ts`
- Create: `frontend/middleware.ts`
- Create: `frontend/app/login/page.tsx`
- Create: `frontend/app/login/actions.ts`
- Create: `frontend/tests/middleware.test.ts`
- Create: `frontend/tests/login.test.tsx`

- [ ] **Step 1: Write failing middleware test**

Create `frontend/tests/middleware.test.ts`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { NextRequest, NextResponse } from "next/server";

// We test the logic, not Next.js internals
function isProtectedPath(pathname: string): boolean {
  return pathname.startsWith("/chat") || pathname.startsWith("/inventory");
}

function hasAuthCookie(request: NextRequest): boolean {
  return request.cookies.has("infraai_auth");
}

describe("middleware logic", () => {
  it("allows access to login page without cookie", () => {
    expect(isProtectedPath("/login")).toBe(false);
  });

  it("marks /chat as protected", () => {
    expect(isProtectedPath("/chat")).toBe(true);
  });

  it("marks /inventory as protected", () => {
    expect(isProtectedPath("/inventory")).toBe(true);
  });

  it("marks /api routes as not protected", () => {
    expect(isProtectedPath("/api/chat")).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd D:\Claude_Code\infraai\frontend
npm test -- middleware
```

Expected: all 4 PASS immediately (these test pure functions, will pass once the test runs). If the test runner itself fails to start, fix Vitest config first.

- [ ] **Step 3: Create `frontend/lib/session.ts`**

```typescript
import { cookies } from "next/headers";

const COOKIE_NAME = "infraai_auth";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 7; // 7 days

export async function setAuthCookie(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, "authenticated", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: COOKIE_MAX_AGE,
    path: "/",
  });
}

export async function clearAuthCookie(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(COOKIE_NAME);
}

export async function isAuthenticated(): Promise<boolean> {
  const cookieStore = await cookies();
  return cookieStore.has(COOKIE_NAME);
}
```

- [ ] **Step 4: Create `frontend/middleware.ts`**

```typescript
import { NextRequest, NextResponse } from "next/server";

const PROTECTED_PREFIXES = ["/chat", "/inventory"];

export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_PREFIXES.some((p) => pathname.startsWith(p));
  if (!isProtected) {
    return NextResponse.next();
  }

  const hasAuth = request.cookies.has("infraai_auth");
  if (!hasAuth) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/).*)"],
};
```

- [ ] **Step 5: Create `frontend/app/login/actions.ts`**

```typescript
"use server";

import { redirect } from "next/navigation";
import { setAuthCookie } from "@/lib/session";

export async function loginAction(
  _prevState: { error: string } | null,
  formData: FormData
): Promise<{ error: string }> {
  const password = formData.get("password") as string;
  const correctPassword = process.env.AUTH_PASSWORD ?? "changeme";

  if (password !== correctPassword) {
    return { error: "Password errata." };
  }

  await setAuthCookie();
  redirect("/chat");
}
```

- [ ] **Step 6: Create `frontend/app/login/page.tsx`**

```tsx
"use client";

import { useActionState } from "react";
import { loginAction } from "./actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
  const [state, formAction, isPending] = useActionState(loginAction, null);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-center text-2xl">InfraAI</CardTitle>
        </CardHeader>
        <CardContent>
          <form action={formAction} className="flex flex-col gap-4">
            <Input
              type="password"
              name="password"
              placeholder="Password"
              autoFocus
              required
            />
            {state?.error && (
              <p className="text-sm text-red-600">{state.error}</p>
            )}
            <Button type="submit" disabled={isPending}>
              {isPending ? "Accesso…" : "Accedi"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 7: Create `frontend/app/page.tsx`** (root redirect)

```tsx
import { redirect } from "next/navigation";
import { isAuthenticated } from "@/lib/session";

export default async function RootPage() {
  const authed = await isAuthenticated();
  redirect(authed ? "/chat" : "/login");
}
```

- [ ] **Step 8: Create `frontend/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "InfraAI",
  description: "AI Infrastructure Management",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="it">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
```

- [ ] **Step 9: Add AUTH_PASSWORD to `.env.example`**

```
AUTH_PASSWORD=changeme
```

Also add to `frontend/next.config.ts` so it's available as a server env var:

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  env: {
    BACKEND_URL: process.env.BACKEND_URL ?? "http://backend:8000",
  },
  // AUTH_PASSWORD is a server-only env var, not exposed to the browser
};

export default nextConfig;
```

- [ ] **Step 10: Run tests**

```bash
cd D:\Claude_Code\infraai\frontend
npm test
```

Expected: middleware tests pass. Build check:

```bash
npm run build
```

Expected: build succeeds.

- [ ] **Step 11: Commit**

```bash
git -C D:\Claude_Code\infraai add frontend/lib/session.ts frontend/middleware.ts frontend/app/login/ frontend/app/page.tsx frontend/app/layout.tsx frontend/tests/ .env.example
git -C D:\Claude_Code\infraai commit -m "feat: password login with cookie session and protected route middleware"
```

---

### Task 3: Backend API Proxy Routes

Next.js API routes that proxy requests to the FastAPI backend. This isolates the frontend from CORS issues and injects the auth header.

**Files:**
- Create: `frontend/lib/api.ts`
- Create: `frontend/app/api/chat/route.ts`
- Create: `frontend/app/api/inventory/servers/route.ts`
- Create: `frontend/app/api/inventory/import-rdm-csv/route.ts`
- Create: `frontend/app/api/auth/logout/route.ts`

- [ ] **Step 1: Create `frontend/lib/api.ts`**

```typescript
const BACKEND_URL = process.env.BACKEND_URL ?? "http://backend:8000";
const AUTH_PASSWORD = process.env.AUTH_PASSWORD ?? "changeme";

export function backendUrl(path: string): string {
  return `${BACKEND_URL}${path}`;
}

export function backendHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return {
    Authorization: `Bearer ${AUTH_PASSWORD}`,
    ...extra,
  };
}
```

- [ ] **Step 2: Create `frontend/app/api/chat/route.ts`**

```typescript
import { NextRequest } from "next/server";
import { backendHeaders, backendUrl } from "@/lib/api";

export async function POST(request: NextRequest): Promise<Response> {
  const body = await request.json();

  const backendResponse = await fetch(backendUrl("/api/chat/message"), {
    method: "POST",
    headers: backendHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });

  // Pipe the SSE stream directly back to the browser
  return new Response(backendResponse.body, {
    status: backendResponse.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
```

- [ ] **Step 3: Create `frontend/app/api/inventory/servers/route.ts`**

```typescript
import { NextRequest } from "next/server";
import { backendHeaders, backendUrl } from "@/lib/api";

export async function GET(request: NextRequest): Promise<Response> {
  const { searchParams } = new URL(request.url);
  const params = new URLSearchParams();
  ["cliente", "source"].forEach((key) => {
    const val = searchParams.get(key);
    if (val) params.set(key, val);
  });

  const url = `${backendUrl("/api/inventory/servers")}${params.size ? "?" + params : ""}`;
  const res = await fetch(url, { headers: backendHeaders() });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
```

- [ ] **Step 4: Create `frontend/app/api/inventory/import-rdm-csv/route.ts`**

```typescript
import { NextRequest } from "next/server";
import { backendHeaders, backendUrl } from "@/lib/api";

export async function POST(request: NextRequest): Promise<Response> {
  const formData = await request.formData();

  const res = await fetch(backendUrl("/api/inventory/import-rdm-csv"), {
    method: "POST",
    headers: backendHeaders(),
    body: formData,
  });

  const data = await res.json();
  return Response.json(data, { status: res.status });
}
```

- [ ] **Step 5: Create `frontend/app/api/auth/logout/route.ts`**

```typescript
import { NextResponse } from "next/server";

export async function POST(): Promise<NextResponse> {
  const response = NextResponse.redirect(new URL("/login", "http://localhost"));
  response.cookies.delete("infraai_auth");
  return response;
}
```

- [ ] **Step 6: Verify TypeScript compiles cleanly**

```bash
cd D:\Claude_Code\infraai\frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git -C D:\Claude_Code\infraai add frontend/lib/api.ts frontend/app/api/
git -C D:\Claude_Code\infraai commit -m "feat: next.js api routes proxy to fastapi backend with auth header"
```

---

### Task 4: Chat Interface with SSE Streaming

The main chat UI. A client component that sends messages, receives SSE chunks, and renders them in a scrolling message list.

**Files:**
- Create: `frontend/app/chat/useChat.ts`
- Create: `frontend/app/chat/ChatInterface.tsx`
- Create: `frontend/app/chat/page.tsx`
- Create: `frontend/components/NavBar.tsx`
- Create: `frontend/tests/useChat.test.ts`

- [ ] **Step 1: Write failing test for useChat hook**

Create `frontend/tests/useChat.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useChat } from "@/app/chat/useChat";

// Mock fetch to return an SSE stream
function makeSseResponse(lines: string[]): Response {
  const body = lines.join("\n") + "\n";
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

describe("useChat", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("starts with empty messages", () => {
    const { result } = renderHook(() => useChat());
    expect(result.current.messages).toEqual([]);
  });

  it("adds user message immediately on send", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      makeSseResponse(["data: risposta\n"])
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("ciao");
    });

    expect(result.current.messages[0]).toMatchObject({
      role: "user",
      content: "ciao",
    });
  });

  it("adds assistant message from SSE data lines", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      makeSseResponse(["data: Prima riga\n", "data: Seconda riga\n"])
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("aggiorna srv-01");
    });

    const assistantMsg = result.current.messages.find((m) => m.role === "assistant");
    expect(assistantMsg).toBeDefined();
    expect(assistantMsg?.content).toContain("Prima riga");
  });

  it("sets isLoading true during fetch and false after", async () => {
    let resolveFetch!: () => void;
    const fetchPromise = new Promise<Response>((resolve) => {
      resolveFetch = () => resolve(makeSseResponse(["data: done\n"]));
    });
    vi.spyOn(global, "fetch").mockReturnValue(fetchPromise);

    const { result } = renderHook(() => useChat());

    let sendPromise: Promise<void>;
    act(() => {
      sendPromise = result.current.sendMessage("test");
    });

    expect(result.current.isLoading).toBe(true);

    await act(async () => {
      resolveFetch();
      await sendPromise;
    });

    expect(result.current.isLoading).toBe(false);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd D:\Claude_Code\infraai\frontend
npm test -- useChat
```

Expected: `Cannot find module '@/app/chat/useChat'`

- [ ] **Step 3: Create `frontend/app/chat/useChat.ts`**

```typescript
"use client";

import { useState } from "react";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  async function sendMessage(text: string): Promise<void> {
    if (!text.trim() || isLoading) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text.trim(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    const assistantId = crypto.randomUUID();
    let accumulated = "";

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text.trim() }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: "assistant", content: "" },
      ]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split("\n")) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6).trim();
            if (data) {
              accumulated += (accumulated ? "\n" : "") + data;
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, content: accumulated } : m
                )
              );
            }
          }
        }
      }
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: `❌ Errore: ${String(err)}` }
            : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  }

  return { messages, isLoading, sendMessage };
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd D:\Claude_Code\infraai\frontend
npm test -- useChat
```

Expected: 4 passed.

- [ ] **Step 5: Create `frontend/components/NavBar.tsx`**

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";

export function NavBar() {
  const pathname = usePathname();

  const links = [
    { href: "/chat", label: "Chat" },
    { href: "/inventory", label: "Inventario" },
  ];

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    window.location.href = "/login";
  }

  return (
    <nav className="border-b bg-white px-6 py-3 flex items-center gap-6">
      <span className="font-bold text-lg text-slate-800">InfraAI</span>
      <div className="flex gap-4 flex-1">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={
              pathname.startsWith(link.href)
                ? "text-blue-600 font-medium"
                : "text-slate-600 hover:text-slate-900"
            }
          >
            {link.label}
          </Link>
        ))}
      </div>
      <Button variant="outline" size="sm" onClick={handleLogout}>
        Esci
      </Button>
    </nav>
  );
}
```

- [ ] **Step 6: Create `frontend/app/chat/ChatInterface.tsx`**

```tsx
"use client";

import { useRef, useEffect, useState } from "react";
import { useChat } from "./useChat";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function ChatInterface() {
  const { messages, isLoading, sendMessage } = useChat();
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    const text = input;
    setInput("");
    await sendMessage(text);
  }

  return (
    <div className="flex flex-col h-full">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <p className="text-center text-slate-400 mt-8">
            Scrivi un comando in italiano per iniziare.
            <br />
            Esempio: <em>Aggiorna tutti i server Ubuntu 22.04 del cliente Rossi</em>
          </p>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 whitespace-pre-wrap text-sm ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-slate-100 text-slate-900"
              }`}
            >
              {msg.content || (isLoading ? "…" : "")}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input form */}
      <form
        onSubmit={handleSubmit}
        className="border-t p-4 flex gap-2"
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Scrivi un comando…"
          disabled={isLoading}
          className="flex-1"
          autoFocus
        />
        <Button type="submit" disabled={isLoading || !input.trim()}>
          {isLoading ? "…" : "Invia"}
        </Button>
      </form>
    </div>
  );
}
```

- [ ] **Step 7: Create `frontend/app/chat/page.tsx`**

```tsx
import { NavBar } from "@/components/NavBar";
import { ChatInterface } from "./ChatInterface";

export default function ChatPage() {
  return (
    <div className="flex flex-col h-screen">
      <NavBar />
      <main className="flex-1 overflow-hidden">
        <ChatInterface />
      </main>
    </div>
  );
}
```

- [ ] **Step 8: Run all tests**

```bash
cd D:\Claude_Code\infraai\frontend
npm test
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git -C D:\Claude_Code\infraai add frontend/app/chat/ frontend/components/NavBar.tsx frontend/tests/useChat.test.ts
git -C D:\Claude_Code\infraai commit -m "feat: chat interface with SSE streaming and message history"
```

---

### Task 5: Inventory Page + CSV Import

Shows a filterable table of servers from the backend API. Includes a CSV upload form for importing from RDM.

**Files:**
- Create: `frontend/app/inventory/ServerTable.tsx`
- Create: `frontend/app/inventory/ImportCSV.tsx`
- Create: `frontend/app/inventory/page.tsx`
- Create: `frontend/tests/ServerTable.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/tests/ServerTable.test.tsx`:

```typescript
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ServerTable } from "@/app/inventory/ServerTable";

const mockServers = [
  {
    id: 1,
    hostname: "srv-web-01",
    ip: "1.2.3.4",
    os_family: "ubuntu",
    os_version: "22.04",
    cliente: "Rossi Srl",
    ruolo: "webserver",
    source: "rdm",
    is_active: true,
    ansible_controller: "auto",
  },
  {
    id: 2,
    hostname: "db-01",
    ip: "1.2.3.5",
    os_family: "ubuntu",
    os_version: "24.04",
    cliente: "Bianchi SpA",
    ruolo: "database",
    source: "zabbix",
    is_active: true,
    ansible_controller: "new",
  },
];

describe("ServerTable", () => {
  it("renders all servers", () => {
    render(<ServerTable servers={mockServers} />);
    expect(screen.getByText("srv-web-01")).toBeInTheDocument();
    expect(screen.getByText("db-01")).toBeInTheDocument();
  });

  it("filters by hostname search", async () => {
    const user = userEvent.setup();
    render(<ServerTable servers={mockServers} />);

    const input = screen.getByPlaceholderText(/cerca/i);
    await user.type(input, "web");

    expect(screen.getByText("srv-web-01")).toBeInTheDocument();
    expect(screen.queryByText("db-01")).not.toBeInTheDocument();
  });

  it("shows controller badge", () => {
    render(<ServerTable servers={mockServers} />);
    expect(screen.getByText("new")).toBeInTheDocument();
    expect(screen.getByText("auto")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd D:\Claude_Code\infraai\frontend
npm test -- ServerTable
```

Expected: `Cannot find module '@/app/inventory/ServerTable'`

- [ ] **Step 3: Create `frontend/app/inventory/ServerTable.tsx`**

```tsx
"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface Server {
  id: number;
  hostname: string;
  ip: string | null;
  os_family: string | null;
  os_version: string | null;
  cliente: string | null;
  ruolo: string | null;
  source: string;
  is_active: boolean;
  ansible_controller: string;
}

interface Props {
  servers: Server[];
}

export function ServerTable({ servers }: Props) {
  const [search, setSearch] = useState("");

  const filtered = servers.filter(
    (s) =>
      !search ||
      s.hostname.toLowerCase().includes(search.toLowerCase()) ||
      (s.cliente ?? "").toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-4">
      <Input
        placeholder="Cerca hostname o cliente…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-sm"
      />
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Hostname</TableHead>
              <TableHead>IP</TableHead>
              <TableHead>OS</TableHead>
              <TableHead>Cliente</TableHead>
              <TableHead>Ruolo</TableHead>
              <TableHead>Controller</TableHead>
              <TableHead>Fonte</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((server) => (
              <TableRow key={server.id}>
                <TableCell className="font-mono text-sm">{server.hostname}</TableCell>
                <TableCell className="font-mono text-sm text-slate-500">
                  {server.ip ?? "—"}
                </TableCell>
                <TableCell>
                  {server.os_family ?? "—"} {server.os_version ?? ""}
                </TableCell>
                <TableCell>{server.cliente ?? "—"}</TableCell>
                <TableCell>{server.ruolo ?? "—"}</TableCell>
                <TableCell>
                  <Badge
                    variant={server.ansible_controller === "new" ? "default" : "secondary"}
                  >
                    {server.ansible_controller}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{server.source}</Badge>
                </TableCell>
              </TableRow>
            ))}
            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-slate-400 py-8">
                  Nessun server trovato.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <p className="text-sm text-slate-500">
        {filtered.length} di {servers.length} server
      </p>
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/app/inventory/ImportCSV.tsx`**

```tsx
"use client";

import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";

interface ImportResult {
  imported: number;
  error?: string;
}

export function ImportCSV({ onImported }: { onImported: () => void }) {
  const [result, setResult] = useState<ImportResult | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/inventory/import-rdm-csv", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) {
        setResult({ imported: 0, error: data.detail ?? "Errore durante l'import" });
      } else {
        setResult({ imported: data.imported });
        onImported();
      }
    } catch {
      setResult({ imported: 0, error: "Errore di rete" });
    } finally {
      setIsUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="flex items-center gap-4">
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        className="hidden"
        id="csv-upload"
        onChange={handleUpload}
        disabled={isUploading}
      />
      <Button
        variant="outline"
        asChild
        disabled={isUploading}
      >
        <label htmlFor="csv-upload" className="cursor-pointer">
          {isUploading ? "Importando…" : "Importa CSV (RDM)"}
        </label>
      </Button>
      {result && (
        <span className={result.error ? "text-red-600 text-sm" : "text-green-600 text-sm"}>
          {result.error ?? `✅ ${result.imported} server importati`}
        </span>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Create `frontend/app/inventory/page.tsx`**

```tsx
import { NavBar } from "@/components/NavBar";
import { ServerTable } from "./ServerTable";
import { ImportCSV } from "./ImportCSV";
import { backendHeaders, backendUrl } from "@/lib/api";

async function getServers() {
  try {
    const res = await fetch(backendUrl("/api/inventory/servers"), {
      headers: backendHeaders(),
      cache: "no-store",
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function InventoryPage() {
  const servers = await getServers();

  return (
    <div className="flex flex-col h-screen">
      <NavBar />
      <main className="flex-1 overflow-auto p-6">
        <div className="max-w-7xl mx-auto space-y-6">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold">Inventario Server</h1>
            <ImportCSV onImported={() => {}} />
          </div>
          <ServerTable servers={servers} />
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 6: Run all tests**

```bash
cd D:\Claude_Code\infraai\frontend
npm test
```

Expected: all tests pass.

- [ ] **Step 7: TypeScript check**

```bash
cd D:\Claude_Code\infraai\frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git -C D:\Claude_Code\infraai add frontend/app/inventory/ frontend/tests/ServerTable.test.tsx
git -C D:\Claude_Code\infraai commit -m "feat: inventory page with filterable server table and CSV import"
```

---

### Task 6: Build Verification + Docker Compose Integration

Verifies the full Next.js build succeeds, and updates the Nginx config template to serve the frontend.

**Files:**
- Modify: `nginx/nginx.conf` (already exists as template)
- Create: `frontend/tests/login.test.tsx` (login action unit test)

- [ ] **Step 1: Write login action test**

Create `frontend/tests/login.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock Next.js server modules
vi.mock("next/headers", () => ({
  cookies: vi.fn().mockResolvedValue({
    set: vi.fn(),
    has: vi.fn().mockReturnValue(false),
    delete: vi.fn(),
  }),
}));
vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
}));

describe("loginAction", () => {
  beforeEach(() => {
    vi.resetModules();
    process.env.AUTH_PASSWORD = "secret123";
  });

  it("returns error on wrong password", async () => {
    const { loginAction } = await import("@/app/login/actions");
    const formData = new FormData();
    formData.set("password", "wrong");

    const result = await loginAction(null, formData);
    expect(result.error).toMatch(/errata/i);
  });

  it("redirects on correct password", async () => {
    const { redirect } = await import("next/navigation");
    const { loginAction } = await import("@/app/login/actions");
    const formData = new FormData();
    formData.set("password", "secret123");

    try {
      await loginAction(null, formData);
    } catch {
      // redirect() throws in tests
    }

    expect(redirect).toHaveBeenCalledWith("/chat");
  });
});
```

- [ ] **Step 2: Run the full test suite**

```bash
cd D:\Claude_Code\infraai\frontend
npm test
```

Expected: all tests pass (7+ tests).

- [ ] **Step 3: Run production build**

```bash
cd D:\Claude_Code\infraai\frontend
npm run build
```

Expected: build completes with no errors. Output: `.next/` directory created.

- [ ] **Step 4: Verify Nginx config routes to frontend**

Read `nginx/nginx.conf`. It should already have a `proxy_pass` to `http://localhost:3000` for the frontend. If it has a placeholder, update it to:

```nginx
location / {
    proxy_pass http://localhost:3000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

The backend API continues to be proxied at `/api/` to port 8000.

- [ ] **Step 5: Final commit**

```bash
git -C D:\Claude_Code\infraai add frontend/ nginx/nginx.conf
git -C D:\Claude_Code\infraai commit -m "feat: frontend build verified, nginx routes to next.js frontend"
```

---

## Self-Review

**Spec coverage (from `2026-05-09-infraai-design.md`):**

| Requisito spec | Task |
|---|---|
| Chat Web (Next.js) con streaming risposte | Task 4 (ChatInterface + useChat SSE) |
| Autenticazione con password + whitelist IP | Task 2 (login/cookie), IP whitelist è Nginx già esistente |
| HTTPS obbligatorio (Let's Encrypt) | Nginx esistente, fuori scope frontend |
| Pagina import CSV per inventario Linux da RDM | Task 5 (ImportCSV.tsx) |
| Lista server inventario | Task 5 (ServerTable.tsx con filtri) |
| SSE streaming risposte chat | Task 3 (API route proxy) + Task 4 (useChat reader) |
| Next.js 14 (React) | Task 1 (bootstrap) |

**Placeholder scan:** Nessun TBD. Tutti i blocchi di codice sono completi.

**Type consistency:**
- `Server` interface in `ServerTable.tsx` usata solo in Task 5 ✅
- `ChatMessage` in `useChat.ts` usata in `ChatInterface.tsx` ✅
- `backendUrl` / `backendHeaders` da `lib/api.ts` usate in Tasks 3 e 5 ✅
- `/api/chat` route (Task 3) chiamata da `useChat.ts` come `/api/chat` (Task 4) ✅
