# Ansible Inventory UI — Piano 3: Next.js 15 Frontend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Next.js 15 frontend for ansible-inventory-ui that lets viewers browse servers, editors add/edit them via a 4-step wizard, and admins manage users, TOTP, Airtable sync, and audit logs.

**Architecture:** Single Next.js 15 App Router app running on port 3000, served by the existing nginx reverse proxy at `https://ansibleai.edminformatica.it`. All API calls hit `/api/*` on the same origin (nginx proxies them to FastAPI on port 8000). JWT is stored in localStorage and sent as `Authorization: Bearer <token>` on every request. Auth state lives in a React Context available to the entire app.

**Tech Stack:** Next.js 15 (App Router, TypeScript strict), Tailwind CSS 4, plain HTML (no UI component library), Jest + React Testing Library, Docker (Node 22 Alpine, standalone output).

---

## File Structure

```
ansible-inventory-ui/
├── docker-compose.yml              MODIFY — add frontend service
└── frontend/
    ├── .env.example                CREATE
    ├── Dockerfile                  CREATE
    ├── jest.config.ts              CREATE
    ├── jest.setup.ts               CREATE
    ├── next.config.mjs             CREATE
    ├── package.json                CREATE
    ├── tailwind.config.ts          CREATE
    ├── tsconfig.json               CREATE
    ├── app/
    │   ├── globals.css             CREATE
    │   ├── layout.tsx              CREATE — root layout, mounts AuthProvider
    │   ├── page.tsx                CREATE — redirects to /login
    │   ├── login/
    │   │   └── page.tsx            CREATE — step1 username+password, step2 TOTP
    │   ├── dashboard/
    │   │   ├── layout.tsx          CREATE — auth guard + NavSidebar shell
    │   │   ├── page.tsx            CREATE — server list
    │   │   └── servers/
    │   │       └── new/
    │   │           └── page.tsx    CREATE — renders ServerWizard
    │   └── admin/
    │       ├── page.tsx            CREATE — user management + Airtable section
    │       └── audit/
    │           └── page.tsx        CREATE — audit log
    ├── components/
    │   ├── AuthProvider.tsx        CREATE — Context: token, user, login(), logout()
    │   ├── NavSidebar.tsx          CREATE — sidebar links, role-aware
    │   ├── ServerTable.tsx         CREATE — table + filters + delete
    │   └── ServerWizard.tsx        CREATE — 4-step wizard
    └── lib/
        ├── api.ts                  CREATE — fetch wrapper + every API call
        └── types.ts                CREATE — all TypeScript interfaces
```

---

## Task 1: Scaffold + Docker

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.mjs`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/jest.config.ts`
- Create: `frontend/jest.setup.ts`
- Create: `frontend/Dockerfile`
- Create: `frontend/.env.example`
- Create: `frontend/app/globals.css`
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/page.tsx`
- Create: `frontend/lib/api.ts` (stub with `buildHeaders`)
- Create: `frontend/__tests__/api.test.ts`
- Modify: `docker-compose.yml`

---

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "ansible-inventory-ui-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev --port 3000",
    "build": "next build",
    "start": "node .next/standalone/server.js",
    "test": "jest --passWithNoTests"
  },
  "dependencies": {
    "next": "15.3.2",
    "react": "19.1.0",
    "react-dom": "19.1.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.3.0",
    "@types/node": "^22.15.18",
    "@types/react": "^19.1.4",
    "@types/react-dom": "^19.1.2",
    "jest": "^29.7.0",
    "jest-environment-jsdom": "^29.7.0",
    "tailwindcss": "^4.1.6",
    "@tailwindcss/postcss": "^4.1.6",
    "typescript": "^5.8.3",
    "ts-jest": "^29.3.4"
  }
}
```

- [ ] **Step 2: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": {
      "@/*": ["./*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create `frontend/next.config.mjs`**

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
};

export default nextConfig;
```

- [ ] **Step 4: Create `frontend/tailwind.config.ts`**

```ts
import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
  ],
};

export default config;
```

- [ ] **Step 5: Create `frontend/jest.config.ts`**

```ts
import type { Config } from 'jest';

const config: Config = {
  testEnvironment: 'jsdom',
  setupFilesAfterFramework: ['<rootDir>/jest.setup.ts'],
  transform: {
    '^.+\\.tsx?$': ['ts-jest', { tsconfig: { jsx: 'react-jsx' } }],
  },
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
  },
  setupFilesAfterFramework: undefined,
  setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
};

export default config;
```

- [ ] **Step 6: Create `frontend/jest.setup.ts`**

```ts
import '@testing-library/jest-dom';
```

- [ ] **Step 7: Create `frontend/app/globals.css`**

```css
@import "tailwindcss";
```

- [ ] **Step 8: Create stub `frontend/lib/api.ts`**

This is the minimal version needed for tests in Task 1. It will be expanded in Tasks 2–6.

```ts
const BASE = process.env.NEXT_PUBLIC_API_URL ?? '';

export function buildHeaders(token: string | null): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export async function apiFetch<T>(
  path: string,
  token: string | null,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      ...buildHeaders(token),
      ...(options.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
```

- [ ] **Step 9: Write the failing test `frontend/__tests__/api.test.ts`**

```ts
import { buildHeaders } from '@/lib/api';

describe('buildHeaders', () => {
  it('includes Authorization header when token is provided', () => {
    const headers = buildHeaders('my-jwt-token') as Record<string, string>;
    expect(headers['Authorization']).toBe('Bearer my-jwt-token');
    expect(headers['Content-Type']).toBe('application/json');
  });

  it('omits Authorization header when token is null', () => {
    const headers = buildHeaders(null) as Record<string, string>;
    expect(headers['Authorization']).toBeUndefined();
    expect(headers['Content-Type']).toBe('application/json');
  });
});
```

- [ ] **Step 10: Run test to verify it fails (module not found is expected)**

```bash
cd frontend && npm install && npm test -- --testPathPattern=api.test
```

Expected output contains: `PASS __tests__/api.test.ts` (or FAIL if api.ts path is wrong — fix import if needed).

- [ ] **Step 11: Create `frontend/app/layout.tsx`**

```tsx
import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Ansible Inventory UI',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="it">
      <body className="bg-gray-50 text-gray-900">{children}</body>
    </html>
  );
}
```

- [ ] **Step 12: Create `frontend/app/page.tsx`**

```tsx
import { redirect } from 'next/navigation';

export default function Home() {
  redirect('/login');
}
```

- [ ] **Step 13: Create `frontend/.env.example`**

```
NEXT_PUBLIC_API_URL=
```

- [ ] **Step 14: Create `frontend/Dockerfile`**

```dockerfile
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public 2>/dev/null || true
USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
```

- [ ] **Step 15: Add frontend service to `docker-compose.yml`**

Replace the entire file:

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: invui
      POSTGRES_PASSWORD: invui
      POSTGRES_DB: invui
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U invui"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=
    depends_on:
      - backend

volumes:
  pgdata:
```

- [ ] **Step 16: Run tests and build**

```bash
cd frontend
npm test
npm run build
```

Expected: all tests PASS, build completes with `.next/standalone` directory present.

- [ ] **Step 17: Commit**

```bash
git add frontend/ docker-compose.yml
git commit -m "feat: scaffold Next.js 15 frontend with Docker and base API helper"
```

---

## Task 2: Auth — Types, API layer, AuthProvider, Login page

**Files:**
- Create: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts` — add `loginStep1`, `loginStep2`, `getMe`
- Create: `frontend/components/AuthProvider.tsx`
- Create: `frontend/app/login/page.tsx`
- Modify: `frontend/app/layout.tsx` — wrap with AuthProvider
- Create: `frontend/__tests__/AuthProvider.test.tsx`

---

- [ ] **Step 1: Create `frontend/lib/types.ts`**

```ts
export type UserRole = 'viewer' | 'editor' | 'admin';

export interface User {
  id: number;
  username: string;
  email: string;
  role: UserRole;
  totp_enabled: boolean;
  is_active?: boolean;
}

export interface Server {
  id: number;
  hostname: string;
  fqdn: string | null;
  ip: string;
  nome_cliente: string | null;
  codice_cliente: string | null;
  ambiente: 'Produzione' | 'Sviluppo' | 'Staging' | 'Test' | null;
  tipo_asset: 'Server Dedicato' | 'VPS' | 'Macchina Virtuale' | null;
  sistema_operativo: 'Linux' | 'Windows' | null;
  distribuzione_os: string | null;
  versione_os: string | null;
  hypervisor: 'Proxmox' | 'VMware ESXi' | 'Hyper-V' | 'Nessuno' | null;
  cluster_hypervisor: string | null;
  awx_inventory_id: number | null;
  awx_inventory_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface ServerCreate {
  hostname: string;
  fqdn?: string;
  ip: string;
  nome_cliente?: string;
  codice_cliente?: string;
  ambiente?: 'Produzione' | 'Sviluppo' | 'Staging' | 'Test';
  tipo_asset?: 'Server Dedicato' | 'VPS' | 'Macchina Virtuale';
  sistema_operativo?: 'Linux' | 'Windows';
  distribuzione_os?: string;
  versione_os?: string;
  hypervisor?: 'Proxmox' | 'VMware ESXi' | 'Hyper-V' | 'Nessuno';
  cluster_hypervisor?: string;
  awx_inventory_id?: number;
}

export interface AwxInventory {
  id: number;
  name: string;
}

export interface AuditLog {
  id: number;
  user_id: number;
  action: string;
  server_hostname: string | null;
  detail: string | null;
  created_at: string;
}

export interface Conflict {
  server_id: number;
  hostname: string;
  airtable_record_id: string;
  diffs: Record<string, { db: unknown; airtable: unknown }>;
}

export interface LoginStep1Response {
  access_token?: string;
  requires_totp?: boolean;
  pre_auth_token?: string;
}

export interface DuplicateCheckResponse {
  available: boolean;
  existing?: Server;
}

export interface AirtableImportResponse {
  created: number;
  updated: number;
  conflicts: number;
}

export interface TotpSetupResponse {
  secret: string;
  qr_url: string;
  backup_codes: string[];
}
```

- [ ] **Step 2: Expand `frontend/lib/api.ts` with auth calls**

Replace the entire file:

```ts
import type {
  User,
  Server,
  ServerCreate,
  AwxInventory,
  AuditLog,
  Conflict,
  LoginStep1Response,
  DuplicateCheckResponse,
  AirtableImportResponse,
  TotpSetupResponse,
} from './types';

const BASE = process.env.NEXT_PUBLIC_API_URL ?? '';

export function buildHeaders(token: string | null): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export async function apiFetch<T>(
  path: string,
  token: string | null,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      ...buildHeaders(token),
      ...(options.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// Auth
export const loginStep1 = (username: string, password: string) =>
  apiFetch<LoginStep1Response>('/api/auth/login', null, {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });

export const loginStep2 = (pre_auth_token: string, totp_code: string) =>
  apiFetch<{ access_token: string }>('/api/auth/verify-totp', null, {
    method: 'POST',
    body: JSON.stringify({ pre_auth_token, totp_code }),
  });

export const getMe = (token: string) =>
  apiFetch<User>('/api/auth/me', token);

// Servers
export const listServers = (
  token: string,
  filters: { nome_cliente?: string; sistema_operativo?: string; awx_inventory_id?: number } = {},
) => {
  const params = new URLSearchParams();
  if (filters.nome_cliente) params.set('nome_cliente', filters.nome_cliente);
  if (filters.sistema_operativo) params.set('sistema_operativo', filters.sistema_operativo);
  if (filters.awx_inventory_id !== undefined)
    params.set('awx_inventory_id', String(filters.awx_inventory_id));
  const qs = params.toString();
  return apiFetch<Server[]>(`/api/servers/${qs ? `?${qs}` : ''}`, token);
};

export const checkDuplicate = (token: string, hostname: string) =>
  apiFetch<DuplicateCheckResponse>(
    `/api/servers/check-duplicate?hostname=${encodeURIComponent(hostname)}`,
    token,
  );

export const createServer = (token: string, body: ServerCreate) =>
  apiFetch<Server>('/api/servers/', token, {
    method: 'POST',
    body: JSON.stringify(body),
  });

export const updateServer = (token: string, id: number, body: Partial<ServerCreate>) =>
  apiFetch<Server>(`/api/servers/${id}`, token, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });

export const deleteServer = (token: string, id: number) =>
  apiFetch<void>(`/api/servers/${id}`, token, { method: 'DELETE' });

// AWX
export const listInventories = (token: string) =>
  apiFetch<AwxInventory[]>('/api/awx/inventories', token);

// Airtable
export const importAirtable = (token: string) =>
  apiFetch<AirtableImportResponse>('/api/airtable/import', token, { method: 'POST' });

export const getConflicts = (token: string) =>
  apiFetch<Conflict[]>('/api/airtable/conflicts', token);

export const resolveConflict = (
  token: string,
  server_id: number,
  source: 'db' | 'airtable',
) =>
  apiFetch<{ status: string; source: string }>('/api/airtable/conflicts/resolve', token, {
    method: 'POST',
    body: JSON.stringify({ server_id, source }),
  });

// Audit
export const getAuditLog = (token: string, limit = 200, offset = 0) =>
  apiFetch<AuditLog[]>(`/api/admin/audit?limit=${limit}&offset=${offset}`, token);

// Users
export const listUsers = (token: string) =>
  apiFetch<User[]>('/api/users/', token);

export const createUser = (
  token: string,
  body: { username: string; email: string; password: string; role: string },
) => apiFetch<User>('/api/users/', token, { method: 'POST', body: JSON.stringify(body) });

export const updateUser = (
  token: string,
  id: number,
  body: { role?: string; is_active?: boolean },
) =>
  apiFetch<User>(`/api/users/${id}`, token, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });

export const setupTotp = (token: string, userId: number) =>
  apiFetch<TotpSetupResponse>(`/api/users/${userId}/totp/setup`, token, { method: 'POST' });

export const deleteTotp = (token: string, userId: number) =>
  apiFetch<void>(`/api/users/${userId}/totp`, token, { method: 'DELETE' });
```

- [ ] **Step 3: Create `frontend/components/AuthProvider.tsx`**

```tsx
'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import type { User } from '@/lib/types';
import { getMe } from '@/lib/api';

interface AuthContextValue {
  token: string | null;
  user: User | null;
  login: (token: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  // Rehydrate from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem('jwt');
    if (stored) {
      getMe(stored)
        .then((u) => {
          setToken(stored);
          setUser(u);
        })
        .catch(() => {
          localStorage.removeItem('jwt');
        });
    }
  }, []);

  const login = useCallback(async (newToken: string) => {
    localStorage.setItem('jwt', newToken);
    setToken(newToken);
    const u = await getMe(newToken);
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('jwt');
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
```

- [ ] **Step 4: Update `frontend/app/layout.tsx` to wrap with AuthProvider**

```tsx
import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/components/AuthProvider';

export const metadata: Metadata = {
  title: 'Ansible Inventory UI',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="it">
      <body className="bg-gray-50 text-gray-900">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 5: Create `frontend/app/login/page.tsx`**

```tsx
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/AuthProvider';
import { loginStep1, loginStep2 } from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [preAuthToken, setPreAuthToken] = useState<string | null>(null);
  const [step, setStep] = useState<1 | 2>(1);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleStep1(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await loginStep1(username, password);
      if (res.access_token) {
        await login(res.access_token);
        router.push('/dashboard');
      } else if (res.requires_totp && res.pre_auth_token) {
        setPreAuthToken(res.pre_auth_token);
        setStep(2);
      } else {
        setError('Risposta non attesa dal server.');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Errore di login.');
    } finally {
      setLoading(false);
    }
  }

  async function handleStep2(e: React.FormEvent) {
    e.preventDefault();
    if (!preAuthToken) return;
    setError(null);
    setLoading(true);
    try {
      const res = await loginStep2(preAuthToken, totpCode);
      await login(res.access_token);
      router.push('/dashboard');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Codice TOTP non valido.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-sm">
        <h1 className="text-2xl font-bold mb-6 text-center">Ansible Inventory UI</h1>

        {step === 1 && (
          <form onSubmit={handleStep1} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1" htmlFor="username">
                Username
              </label>
              <input
                id="username"
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:border-blue-500"
              />
            </div>
            {error && <p className="text-red-600 text-sm">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Caricamento...' : 'Accedi'}
            </button>
          </form>
        )}

        {step === 2 && (
          <form onSubmit={handleStep2} className="space-y-4">
            <p className="text-sm text-gray-600">
              Inserisci il codice dalla tua app TOTP.
            </p>
            <div>
              <label className="block text-sm font-medium mb-1" htmlFor="totp">
                Codice TOTP
              </label>
              <input
                id="totp"
                type="text"
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                required
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:border-blue-500 tracking-widest text-center text-lg"
              />
            </div>
            {error && <p className="text-red-600 text-sm">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Caricamento...' : 'Verifica'}
            </button>
            <button
              type="button"
              onClick={() => { setStep(1); setError(null); }}
              className="w-full text-sm text-gray-500 underline"
            >
              Torna al login
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Write test `frontend/__tests__/AuthProvider.test.tsx`**

```tsx
import { render, screen, act } from '@testing-library/react';
import { AuthProvider, useAuth } from '@/components/AuthProvider';
import * as api from '@/lib/api';

// Mock getMe
jest.mock('@/lib/api', () => ({
  ...jest.requireActual('@/lib/api'),
  getMe: jest.fn(),
}));

const mockGetMe = api.getMe as jest.MockedFunction<typeof api.getMe>;

function TestConsumer() {
  const { token, user, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="token">{token ?? 'null'}</span>
      <span data-testid="user">{user ? user.username : 'null'}</span>
      <button onClick={() => login('test-token')}>login</button>
      <button onClick={logout}>logout</button>
    </div>
  );
}

beforeEach(() => {
  localStorage.clear();
  mockGetMe.mockResolvedValue({
    id: 1,
    username: 'admin',
    email: 'admin@test.com',
    role: 'admin',
    totp_enabled: false,
  });
});

test('starts with null token and user', () => {
  render(
    <AuthProvider>
      <TestConsumer />
    </AuthProvider>,
  );
  expect(screen.getByTestId('token').textContent).toBe('null');
  expect(screen.getByTestId('user').textContent).toBe('null');
});

test('login sets token and user', async () => {
  render(
    <AuthProvider>
      <TestConsumer />
    </AuthProvider>,
  );
  await act(async () => {
    screen.getByText('login').click();
  });
  expect(screen.getByTestId('token').textContent).toBe('test-token');
  expect(screen.getByTestId('user').textContent).toBe('admin');
  expect(localStorage.getItem('jwt')).toBe('test-token');
});

test('logout clears token and user', async () => {
  render(
    <AuthProvider>
      <TestConsumer />
    </AuthProvider>,
  );
  await act(async () => {
    screen.getByText('login').click();
  });
  await act(async () => {
    screen.getByText('logout').click();
  });
  expect(screen.getByTestId('token').textContent).toBe('null');
  expect(screen.getByTestId('user').textContent).toBe('null');
  expect(localStorage.getItem('jwt')).toBeNull();
});
```

- [ ] **Step 7: Run tests**

```bash
cd frontend && npm test
```

Expected: 5 tests pass (`api.test.ts` × 2, `AuthProvider.test.tsx` × 3).

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: add auth types, API layer, AuthProvider context, and login page"
```

---

## Task 3: Dashboard — server list

**Files:**
- Create: `frontend/app/dashboard/layout.tsx`
- Create: `frontend/components/NavSidebar.tsx`
- Create: `frontend/app/dashboard/page.tsx`
- Create: `frontend/components/ServerTable.tsx`

---

- [ ] **Step 1: Create `frontend/app/dashboard/layout.tsx`**

```tsx
'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/AuthProvider';
import { NavSidebar } from '@/components/NavSidebar';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { token } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (token === null) {
      // Give AuthProvider time to rehydrate from localStorage
      const id = setTimeout(() => {
        if (!localStorage.getItem('jwt')) {
          router.push('/login');
        }
      }, 100);
      return () => clearTimeout(id);
    }
  }, [token, router]);

  return (
    <div className="flex min-h-screen">
      <NavSidebar />
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/components/NavSidebar.tsx`**

```tsx
'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from './AuthProvider';

export function NavSidebar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  function handleLogout() {
    logout();
    router.push('/login');
  }

  const linkClass = (href: string) =>
    `block px-4 py-2 rounded hover:bg-gray-700 ${
      pathname === href ? 'bg-gray-700 font-semibold' : ''
    }`;

  return (
    <aside className="w-56 bg-gray-900 text-white flex flex-col min-h-screen">
      <div className="px-4 py-5 border-b border-gray-700">
        <p className="text-sm font-bold truncate">{user?.username ?? '...'}</p>
        <p className="text-xs text-gray-400 capitalize">{user?.role ?? ''}</p>
      </div>
      <nav className="flex-1 py-4 space-y-1 px-2 text-sm">
        <Link href="/dashboard" className={linkClass('/dashboard')}>
          Dashboard
        </Link>
        {(user?.role === 'editor' || user?.role === 'admin') && (
          <Link
            href="/dashboard/servers/new"
            className={linkClass('/dashboard/servers/new')}
          >
            + Aggiungi Server
          </Link>
        )}
        {user?.role === 'admin' && (
          <>
            <Link href="/admin" className={linkClass('/admin')}>
              Utenti
            </Link>
            <Link href="/admin/audit" className={linkClass('/admin/audit')}>
              Audit Log
            </Link>
          </>
        )}
      </nav>
      <div className="px-4 py-4 border-t border-gray-700">
        <button
          onClick={handleLogout}
          className="w-full text-left text-sm text-gray-400 hover:text-white"
        >
          Esci
        </button>
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: Create `frontend/components/ServerTable.tsx`**

```tsx
'use client';

import { useState } from 'react';
import type { Server } from '@/lib/types';
import { deleteServer } from '@/lib/api';
import { useAuth } from './AuthProvider';

interface Props {
  servers: Server[];
  onDeleted: (id: number) => void;
}

export function ServerTable({ servers, onDeleted }: Props) {
  const { token, user } = useAuth();
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete(id: number, hostname: string) {
    if (!confirm(`Eliminare il server "${hostname}"?`)) return;
    if (!token) return;
    setDeletingId(id);
    setError(null);
    try {
      await deleteServer(token, id);
      onDeleted(id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Errore durante l\'eliminazione.');
    } finally {
      setDeletingId(null);
    }
  }

  if (servers.length === 0) {
    return <p className="text-gray-500 text-sm">Nessun server trovato.</p>;
  }

  return (
    <div className="overflow-x-auto">
      {error && (
        <p className="mb-3 text-red-600 text-sm">{error}</p>
      )}
      <table className="min-w-full bg-white border border-gray-200 rounded-lg text-sm">
        <thead className="bg-gray-100">
          <tr>
            {['Hostname', 'IP', 'Ambiente', 'Tipo', 'OS', 'Cliente', 'Azioni'].map((h) => (
              <th
                key={h}
                className="px-4 py-3 text-left font-semibold text-gray-600 whitespace-nowrap"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {servers.map((s) => (
            <tr key={s.id} className="border-t border-gray-100 hover:bg-gray-50">
              <td className="px-4 py-3 font-mono">{s.hostname}</td>
              <td className="px-4 py-3 font-mono">{s.ip}</td>
              <td className="px-4 py-3">{s.ambiente ?? '—'}</td>
              <td className="px-4 py-3">{s.tipo_asset ?? '—'}</td>
              <td className="px-4 py-3">{s.sistema_operativo ?? '—'}</td>
              <td className="px-4 py-3">{s.nome_cliente ?? '—'}</td>
              <td className="px-4 py-3 space-x-2 whitespace-nowrap">
                {user?.role === 'admin' && (
                  <button
                    onClick={() => handleDelete(s.id, s.hostname)}
                    disabled={deletingId === s.id}
                    className="text-red-600 hover:underline disabled:opacity-50"
                  >
                    {deletingId === s.id ? 'Eliminazione...' : 'Elimina'}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/app/dashboard/page.tsx`**

```tsx
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/components/AuthProvider';
import { ServerTable } from '@/components/ServerTable';
import { listServers } from '@/lib/api';
import type { Server } from '@/lib/types';

export default function DashboardPage() {
  const { token, user } = useAuth();
  const [servers, setServers] = useState<Server[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [filterCliente, setFilterCliente] = useState('');
  const [filterOs, setFilterOs] = useState('');

  async function fetchServers() {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const data = await listServers(token, {
        nome_cliente: filterCliente || undefined,
        sistema_operativo: filterOs || undefined,
      });
      setServers(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Errore nel caricamento dei server.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchServers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function handleDeleted(id: number) {
    setServers((prev) => prev.filter((s) => s.id !== id));
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Server</h1>
        {(user?.role === 'editor' || user?.role === 'admin') && (
          <Link
            href="/dashboard/servers/new"
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm"
          >
            + Aggiungi Server
          </Link>
        )}
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          placeholder="Filtra per cliente..."
          value={filterCliente}
          onChange={(e) => setFilterCliente(e.target.value)}
          className="border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
        />
        <select
          value={filterOs}
          onChange={(e) => setFilterOs(e.target.value)}
          className="border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
        >
          <option value="">Tutti i SO</option>
          <option value="Linux">Linux</option>
          <option value="Windows">Windows</option>
        </select>
        <button
          onClick={fetchServers}
          className="bg-gray-200 px-4 py-2 rounded text-sm hover:bg-gray-300"
        >
          Filtra
        </button>
      </div>

      {loading && <p className="text-gray-500">Caricamento...</p>}
      {error && <p className="text-red-600 text-sm">{error}</p>}
      {!loading && !error && (
        <ServerTable servers={servers} onDeleted={handleDeleted} />
      )}
    </div>
  );
}
```

- [ ] **Step 5: Run build to verify no TypeScript errors**

```bash
cd frontend && npm run build
```

Expected: Build completes successfully. No TypeScript errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: add dashboard layout with auth guard, sidebar nav, and server list table"
```

---

## Task 4: Add Server — 4-step wizard

**Files:**
- Create: `frontend/app/dashboard/servers/new/page.tsx`
- Create: `frontend/components/ServerWizard.tsx`

---

- [ ] **Step 1: Create `frontend/app/dashboard/servers/new/page.tsx`**

```tsx
import { ServerWizard } from '@/components/ServerWizard';

export default function NewServerPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Aggiungi Server</h1>
      <ServerWizard />
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/components/ServerWizard.tsx`**

```tsx
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from './AuthProvider';
import {
  listInventories,
  checkDuplicate,
  createServer,
} from '@/lib/api';
import type { AwxInventory, ServerCreate, DuplicateCheckResponse } from '@/lib/types';

type Step = 1 | 2 | 3 | 4;

const AMBIENTI = ['Produzione', 'Sviluppo', 'Staging', 'Test'] as const;
const TIPI_ASSET = ['Server Dedicato', 'VPS', 'Macchina Virtuale'] as const;
const SISTEMI_OS = ['Linux', 'Windows'] as const;
const HYPERVISORS = ['Proxmox', 'VMware ESXi', 'Hyper-V', 'Nessuno'] as const;

export function ServerWizard() {
  const { token } = useAuth();
  const router = useRouter();

  const [step, setStep] = useState<Step>(1);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Step 1: AWX inventory
  const [inventories, setInventories] = useState<AwxInventory[]>([]);
  const [awxInventoryId, setAwxInventoryId] = useState<number | undefined>(undefined);
  const [awxUnavailable, setAwxUnavailable] = useState(false);

  // Step 2: hostname duplicate check
  const [hostname, setHostname] = useState('');
  const [duplicateResult, setDuplicateResult] = useState<DuplicateCheckResponse | null>(null);

  // Step 3: remaining fields
  const [fqdn, setFqdn] = useState('');
  const [ip, setIp] = useState('');
  const [nomeCliente, setNomeCliente] = useState('');
  const [codiceCliente, setCodiceCliente] = useState('');
  const [ambiente, setAmbiente] = useState('');
  const [tipoAsset, setTipoAsset] = useState('');
  const [sistemaOs, setSistemaOs] = useState('');
  const [distribuzioneOs, setDistribuzioneOs] = useState('');
  const [versioneOs, setVersioneOs] = useState('');
  const [hypervisor, setHypervisor] = useState('');
  const [clusterHypervisor, setClusterHypervisor] = useState('');

  useEffect(() => {
    if (!token) return;
    listInventories(token)
      .then(setInventories)
      .catch(() => setAwxUnavailable(true));
  }, [token]);

  // ── Step 1 ──────────────────────────────────────────────────────────────────
  function handleStep1Next() {
    setError(null);
    setStep(2);
  }

  // ── Step 2 ──────────────────────────────────────────────────────────────────
  async function handleCheckHostname(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !hostname.trim()) return;
    setError(null);
    setLoading(true);
    try {
      const result = await checkDuplicate(token, hostname.trim());
      setDuplicateResult(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Errore nel controllo hostname.');
    } finally {
      setLoading(false);
    }
  }

  function handleStep2Next() {
    if (!duplicateResult?.available) return;
    setError(null);
    setStep(3);
  }

  // ── Step 3 ──────────────────────────────────────────────────────────────────
  function handleStep3Next(e: React.FormEvent) {
    e.preventDefault();
    if (!ip.trim()) {
      setError("L'indirizzo IP è obbligatorio.");
      return;
    }
    setError(null);
    setStep(4);
  }

  // ── Step 4 — Submit ─────────────────────────────────────────────────────────
  async function handleSubmit() {
    if (!token) return;
    setError(null);
    setLoading(true);
    const body: ServerCreate = {
      hostname: hostname.trim(),
      ip: ip.trim(),
      ...(fqdn && { fqdn }),
      ...(nomeCliente && { nome_cliente: nomeCliente }),
      ...(codiceCliente && { codice_cliente: codiceCliente }),
      ...(ambiente && { ambiente: ambiente as ServerCreate['ambiente'] }),
      ...(tipoAsset && { tipo_asset: tipoAsset as ServerCreate['tipo_asset'] }),
      ...(sistemaOs && { sistema_operativo: sistemaOs as ServerCreate['sistema_operativo'] }),
      ...(distribuzioneOs && { distribuzione_os: distribuzioneOs }),
      ...(versioneOs && { versione_os: versioneOs }),
      ...(hypervisor && { hypervisor: hypervisor as ServerCreate['hypervisor'] }),
      ...(clusterHypervisor && { cluster_hypervisor: clusterHypervisor }),
      ...(awxInventoryId !== undefined && { awx_inventory_id: awxInventoryId }),
    };
    try {
      await createServer(token, body);
      router.push('/dashboard');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Errore durante la creazione.');
    } finally {
      setLoading(false);
    }
  }

  // ── Progress indicator ───────────────────────────────────────────────────────
  const stepLabels = ['Inventario AWX', 'Hostname', 'Dettagli', 'Riepilogo'];

  return (
    <div className="max-w-2xl">
      {/* Progress bar */}
      <div className="flex mb-8">
        {stepLabels.map((label, i) => {
          const n = (i + 1) as Step;
          const active = step === n;
          const done = step > n;
          return (
            <div key={label} className="flex-1 text-center">
              <div
                className={`mx-auto w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                  active
                    ? 'bg-blue-600 text-white'
                    : done
                    ? 'bg-green-500 text-white'
                    : 'bg-gray-200 text-gray-500'
                }`}
              >
                {n}
              </div>
              <p className="text-xs mt-1 text-gray-600">{label}</p>
            </div>
          );
        })}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        {error && <p className="mb-4 text-red-600 text-sm">{error}</p>}

        {/* ── STEP 1 ─────────────────────────────────────────────────────── */}
        {step === 1 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Seleziona Inventario AWX</h2>
            {awxUnavailable ? (
              <p className="text-yellow-700 bg-yellow-50 border border-yellow-200 rounded px-3 py-2 text-sm">
                AWX non configurato o non raggiungibile. Potrai assegnare un inventario in seguito.
              </p>
            ) : inventories.length === 0 ? (
              <p className="text-gray-500 text-sm">Caricamento inventari...</p>
            ) : (
              <select
                value={awxInventoryId ?? ''}
                onChange={(e) =>
                  setAwxInventoryId(e.target.value ? Number(e.target.value) : undefined)
                }
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
              >
                <option value="">— Nessun inventario —</option>
                {inventories.map((inv) => (
                  <option key={inv.id} value={inv.id}>
                    {inv.name}
                  </option>
                ))}
              </select>
            )}
            <div className="flex justify-end gap-3">
              <button
                onClick={handleStep1Next}
                className="bg-blue-600 text-white px-5 py-2 rounded hover:bg-blue-700 text-sm"
              >
                {awxUnavailable || !awxInventoryId ? 'Salta' : 'Avanti'}
              </button>
            </div>
          </div>
        )}

        {/* ── STEP 2 ─────────────────────────────────────────────────────── */}
        {step === 2 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Verifica Hostname</h2>
            <form onSubmit={handleCheckHostname} className="flex gap-2">
              <input
                type="text"
                placeholder="es. web01.example.com"
                value={hostname}
                onChange={(e) => {
                  setHostname(e.target.value);
                  setDuplicateResult(null);
                }}
                required
                className="flex-1 border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
              />
              <button
                type="submit"
                disabled={loading}
                className="bg-gray-700 text-white px-4 py-2 rounded text-sm hover:bg-gray-800 disabled:opacity-50"
              >
                {loading ? 'Controllo...' : 'Verifica'}
              </button>
            </form>

            {duplicateResult && duplicateResult.available && (
              <p className="text-green-700 bg-green-50 border border-green-200 rounded px-3 py-2 text-sm">
                Hostname disponibile.
              </p>
            )}
            {duplicateResult && !duplicateResult.available && (
              <p className="text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2 text-sm">
                Hostname già presente (id: {duplicateResult.existing?.id}).
              </p>
            )}

            <div className="flex justify-between">
              <button
                onClick={() => setStep(1)}
                className="text-sm text-gray-500 underline"
              >
                Indietro
              </button>
              <button
                onClick={handleStep2Next}
                disabled={!duplicateResult?.available}
                className="bg-blue-600 text-white px-5 py-2 rounded hover:bg-blue-700 text-sm disabled:opacity-40"
              >
                Avanti
              </button>
            </div>
          </div>
        )}

        {/* ── STEP 3 ─────────────────────────────────────────────────────── */}
        {step === 3 && (
          <form onSubmit={handleStep3Next} className="space-y-4">
            <h2 className="text-lg font-semibold">Dettagli Server</h2>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium mb-1">IP *</label>
                <input
                  type="text"
                  required
                  value={ip}
                  onChange={(e) => setIp(e.target.value)}
                  placeholder="192.168.1.10"
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">FQDN</label>
                <input
                  type="text"
                  value={fqdn}
                  onChange={(e) => setFqdn(e.target.value)}
                  placeholder="web01.example.com"
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Cliente</label>
                <input
                  type="text"
                  value={nomeCliente}
                  onChange={(e) => setNomeCliente(e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Codice Cliente</label>
                <input
                  type="text"
                  value={codiceCliente}
                  onChange={(e) => setCodiceCliente(e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Ambiente</label>
                <select
                  value={ambiente}
                  onChange={(e) => setAmbiente(e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                >
                  <option value="">—</option>
                  {AMBIENTI.map((a) => <option key={a}>{a}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Tipo Asset</label>
                <select
                  value={tipoAsset}
                  onChange={(e) => setTipoAsset(e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                >
                  <option value="">—</option>
                  {TIPI_ASSET.map((t) => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Sistema Operativo</label>
                <select
                  value={sistemaOs}
                  onChange={(e) => setSistemaOs(e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                >
                  <option value="">—</option>
                  {SISTEMI_OS.map((s) => <option key={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Distribuzione OS</label>
                <input
                  type="text"
                  value={distribuzioneOs}
                  onChange={(e) => setDistribuzioneOs(e.target.value)}
                  placeholder="Ubuntu, Debian, …"
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Versione OS</label>
                <input
                  type="text"
                  value={versioneOs}
                  onChange={(e) => setVersioneOs(e.target.value)}
                  placeholder="22.04"
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Hypervisor</label>
                <select
                  value={hypervisor}
                  onChange={(e) => setHypervisor(e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                >
                  <option value="">—</option>
                  {HYPERVISORS.map((h) => <option key={h}>{h}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Cluster Hypervisor</label>
                <input
                  type="text"
                  value={clusterHypervisor}
                  onChange={(e) => setClusterHypervisor(e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div className="flex justify-between">
              <button
                type="button"
                onClick={() => setStep(2)}
                className="text-sm text-gray-500 underline"
              >
                Indietro
              </button>
              <button
                type="submit"
                className="bg-blue-600 text-white px-5 py-2 rounded hover:bg-blue-700 text-sm"
              >
                Avanti
              </button>
            </div>
          </form>
        )}

        {/* ── STEP 4 ─────────────────────────────────────────────────────── */}
        {step === 4 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Riepilogo</h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              {[
                ['Hostname', hostname],
                ['IP', ip],
                ['FQDN', fqdn || '—'],
                ['Cliente', nomeCliente || '—'],
                ['Codice Cliente', codiceCliente || '—'],
                ['Ambiente', ambiente || '—'],
                ['Tipo Asset', tipoAsset || '—'],
                ['Sistema OS', sistemaOs || '—'],
                ['Distribuzione OS', distribuzioneOs || '—'],
                ['Versione OS', versioneOs || '—'],
                ['Hypervisor', hypervisor || '—'],
                ['Cluster', clusterHypervisor || '—'],
                [
                  'Inventario AWX',
                  awxInventoryId
                    ? inventories.find((i) => i.id === awxInventoryId)?.name ?? String(awxInventoryId)
                    : '—',
                ],
              ].map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="font-medium text-gray-600">{k}</dt>
                  <dd className="font-mono">{v}</dd>
                </div>
              ))}
            </dl>

            <div className="flex justify-between">
              <button
                type="button"
                onClick={() => setStep(3)}
                className="text-sm text-gray-500 underline"
              >
                Indietro
              </button>
              <button
                onClick={handleSubmit}
                disabled={loading}
                className="bg-green-600 text-white px-5 py-2 rounded hover:bg-green-700 text-sm disabled:opacity-50"
              >
                {loading ? 'Salvataggio...' : 'Salva Server'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Run build to check TypeScript**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "feat: add 4-step server creation wizard"
```

---

## Task 5: Admin — User Management page

**Files:**
- Create: `frontend/app/admin/page.tsx`

> Note: All API functions (`listUsers`, `createUser`, `updateUser`, `setupTotp`, `deleteTotp`) are already in `lib/api.ts` from Task 2.

---

- [ ] **Step 1: Create `frontend/app/admin/page.tsx`**

The page redirects to /dashboard if role is not admin, shows a user table, create form, role/active toggles, and TOTP management. Airtable section added here (import button + conflicts list); see also Task 6.

```tsx
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/AuthProvider';
import {
  listUsers,
  createUser,
  updateUser,
  setupTotp,
  deleteTotp,
  importAirtable,
  getConflicts,
  resolveConflict,
} from '@/lib/api';
import type { User, Conflict, TotpSetupResponse, AirtableImportResponse } from '@/lib/types';

export default function AdminPage() {
  const { token, user } = useAuth();
  const router = useRouter();

  // Role guard
  useEffect(() => {
    if (user && user.role !== 'admin') {
      router.push('/dashboard');
    }
  }, [user, router]);

  // Users
  const [users, setUsers] = useState<User[]>([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [usersError, setUsersError] = useState<string | null>(null);

  // Create user form
  const [newUsername, setNewUsername] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState('viewer');
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // TOTP setup result
  const [totpSetupResult, setTotpSetupResult] = useState<(TotpSetupResponse & { userId: number }) | null>(null);

  // Airtable
  const [importResult, setImportResult] = useState<AirtableImportResponse | null>(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [conflictsLoading, setConflictsLoading] = useState(false);

  useEffect(() => {
    if (!token) return;
    setUsersLoading(true);
    listUsers(token)
      .then(setUsers)
      .catch((err: unknown) =>
        setUsersError(err instanceof Error ? err.message : 'Errore caricamento utenti.')
      )
      .finally(() => setUsersLoading(false));

    setConflictsLoading(true);
    getConflicts(token)
      .then(setConflicts)
      .catch(() => setConflicts([]))
      .finally(() => setConflictsLoading(false));
  }, [token]);

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setCreateError(null);
    setCreateLoading(true);
    try {
      const created = await createUser(token, {
        username: newUsername,
        email: newEmail,
        password: newPassword,
        role: newRole,
      });
      setUsers((prev) => [...prev, created]);
      setNewUsername('');
      setNewEmail('');
      setNewPassword('');
      setNewRole('viewer');
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : 'Errore nella creazione utente.');
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleRoleChange(u: User, role: string) {
    if (!token) return;
    try {
      const updated = await updateUser(token, u.id, { role });
      setUsers((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Errore aggiornamento ruolo.');
    }
  }

  async function handleToggleActive(u: User) {
    if (!token) return;
    try {
      const updated = await updateUser(token, u.id, { is_active: !u.is_active });
      setUsers((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Errore aggiornamento stato.');
    }
  }

  async function handleSetupTotp(u: User) {
    if (!token) return;
    try {
      const result = await setupTotp(token, u.id);
      setTotpSetupResult({ ...result, userId: u.id });
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Errore setup TOTP.');
    }
  }

  async function handleDeleteTotp(u: User) {
    if (!token || !confirm(`Disabilitare TOTP per ${u.username}?`)) return;
    try {
      await deleteTotp(token, u.id);
      setUsers((prev) =>
        prev.map((x) => (x.id === u.id ? { ...x, totp_enabled: false } : x))
      );
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Errore rimozione TOTP.');
    }
  }

  async function handleImportAirtable() {
    if (!token) return;
    setImportError(null);
    setImportLoading(true);
    try {
      const result = await importAirtable(token);
      setImportResult(result);
      // Refresh conflicts
      const newConflicts = await getConflicts(token);
      setConflicts(newConflicts);
    } catch (err: unknown) {
      setImportError(err instanceof Error ? err.message : 'Errore importazione Airtable.');
    } finally {
      setImportLoading(false);
    }
  }

  async function handleResolve(conflict: Conflict, source: 'db' | 'airtable') {
    if (!token) return;
    try {
      await resolveConflict(token, conflict.server_id, source);
      setConflicts((prev) => prev.filter((c) => c.server_id !== conflict.server_id));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Errore risoluzione conflitto.');
    }
  }

  if (user?.role !== 'admin') return null;

  return (
    <div className="space-y-10">
      <h1 className="text-2xl font-bold">Gestione Utenti</h1>

      {/* Create user */}
      <section className="bg-white border border-gray-200 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Crea Utente</h2>
        <form onSubmit={handleCreateUser} className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium mb-1">Username</label>
            <input
              required
              value={newUsername}
              onChange={(e) => setNewUsername(e.target.value)}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1">Email</label>
            <input
              type="email"
              required
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1">Password</label>
            <input
              type="password"
              required
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1">Ruolo</label>
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value)}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
            >
              <option value="viewer">viewer</option>
              <option value="editor">editor</option>
              <option value="admin">admin</option>
            </select>
          </div>
          <div className="col-span-2 flex justify-end gap-3">
            {createError && <p className="text-red-600 text-sm self-center">{createError}</p>}
            <button
              type="submit"
              disabled={createLoading}
              className="bg-blue-600 text-white px-5 py-2 rounded hover:bg-blue-700 text-sm disabled:opacity-50"
            >
              {createLoading ? 'Caricamento...' : 'Crea Utente'}
            </button>
          </div>
        </form>
      </section>

      {/* Users table */}
      <section className="bg-white border border-gray-200 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Utenti</h2>
        {usersLoading && <p className="text-gray-500 text-sm">Caricamento...</p>}
        {usersError && <p className="text-red-600 text-sm">{usersError}</p>}
        {!usersLoading && !usersError && (
          <table className="min-w-full text-sm">
            <thead className="bg-gray-100">
              <tr>
                {['ID', 'Username', 'Email', 'Ruolo', 'Attivo', 'TOTP', 'Azioni'].map((h) => (
                  <th key={h} className="px-3 py-2 text-left font-semibold text-gray-600">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-3 py-2">{u.id}</td>
                  <td className="px-3 py-2 font-mono">{u.username}</td>
                  <td className="px-3 py-2">{u.email}</td>
                  <td className="px-3 py-2">
                    <select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u, e.target.value)}
                      className="border border-gray-300 rounded px-2 py-1 text-xs"
                    >
                      <option value="viewer">viewer</option>
                      <option value="editor">editor</option>
                      <option value="admin">admin</option>
                    </select>
                  </td>
                  <td className="px-3 py-2">
                    <button
                      onClick={() => handleToggleActive(u)}
                      className={`text-xs px-2 py-1 rounded ${
                        u.is_active !== false
                          ? 'bg-green-100 text-green-700 hover:bg-green-200'
                          : 'bg-red-100 text-red-700 hover:bg-red-200'
                      }`}
                    >
                      {u.is_active !== false ? 'Attivo' : 'Disabilitato'}
                    </button>
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`text-xs px-2 py-1 rounded ${
                        u.totp_enabled
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-gray-100 text-gray-500'
                      }`}
                    >
                      {u.totp_enabled ? 'Abilitato' : 'Disabilitato'}
                    </span>
                  </td>
                  <td className="px-3 py-2 space-x-2 whitespace-nowrap">
                    {!u.totp_enabled && (
                      <button
                        onClick={() => handleSetupTotp(u)}
                        className="text-blue-600 hover:underline text-xs"
                      >
                        Setup TOTP
                      </button>
                    )}
                    {u.totp_enabled && (
                      <button
                        onClick={() => handleDeleteTotp(u)}
                        className="text-red-600 hover:underline text-xs"
                      >
                        Rimuovi TOTP
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* TOTP setup result modal-ish */}
      {totpSetupResult && (
        <section className="bg-yellow-50 border border-yellow-300 rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-2">TOTP Configurato</h2>
          <p className="text-sm mb-2">
            <strong>Secret:</strong>{' '}
            <code className="bg-gray-100 px-2 py-0.5 rounded">{totpSetupResult.secret}</code>
          </p>
          <p className="text-sm mb-2">
            <strong>QR URL:</strong>{' '}
            <a href={totpSetupResult.qr_url} target="_blank" rel="noreferrer" className="text-blue-600 underline break-all">
              {totpSetupResult.qr_url}
            </a>
          </p>
          <p className="text-sm font-medium mb-1">Codici di backup:</p>
          <ul className="list-disc list-inside text-sm font-mono">
            {totpSetupResult.backup_codes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
          <button
            onClick={() => setTotpSetupResult(null)}
            className="mt-4 text-sm text-gray-500 underline"
          >
            Chiudi
          </button>
        </section>
      )}

      {/* Airtable section */}
      <section className="bg-white border border-gray-200 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Sincronizzazione Airtable</h2>
        <div className="flex items-center gap-4 mb-4">
          <button
            onClick={handleImportAirtable}
            disabled={importLoading}
            className="bg-purple-600 text-white px-5 py-2 rounded hover:bg-purple-700 text-sm disabled:opacity-50"
          >
            {importLoading ? 'Importazione...' : 'Importa da Airtable'}
          </button>
          {importResult && (
            <p className="text-sm text-gray-700">
              Creati: <strong>{importResult.created}</strong> | Aggiornati:{' '}
              <strong>{importResult.updated}</strong> | Conflitti:{' '}
              <strong>{importResult.conflicts}</strong>
            </p>
          )}
          {importError && <p className="text-red-600 text-sm">{importError}</p>}
        </div>

        {conflictsLoading && <p className="text-gray-500 text-sm">Caricamento conflitti...</p>}
        {!conflictsLoading && conflicts.length === 0 && (
          <p className="text-green-700 text-sm">Nessun conflitto da risolvere.</p>
        )}
        {conflicts.length > 0 && (
          <div className="space-y-4">
            <h3 className="font-medium text-sm">Conflitti da risolvere ({conflicts.length})</h3>
            {conflicts.map((c) => (
              <div
                key={c.server_id}
                className="border border-orange-200 bg-orange-50 rounded p-4 text-sm"
              >
                <p className="font-semibold mb-2">{c.hostname}</p>
                <table className="min-w-full mb-3 text-xs">
                  <thead>
                    <tr>
                      <th className="text-left font-medium text-gray-600 pr-4">Campo</th>
                      <th className="text-left font-medium text-gray-600 pr-4">DB</th>
                      <th className="text-left font-medium text-gray-600">Airtable</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(c.diffs).map(([field, { db, airtable }]) => (
                      <tr key={field} className="border-t border-orange-200">
                        <td className="pr-4 py-1 font-mono">{field}</td>
                        <td className="pr-4 py-1 font-mono">{String(db)}</td>
                        <td className="py-1 font-mono">{String(airtable)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleResolve(c, 'db')}
                    className="bg-blue-600 text-white px-3 py-1 rounded text-xs hover:bg-blue-700"
                  >
                    Mantieni DB
                  </button>
                  <button
                    onClick={() => handleResolve(c, 'airtable')}
                    className="bg-orange-600 text-white px-3 py-1 rounded text-xs hover:bg-orange-700"
                  >
                    Usa Airtable
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Run build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/
git commit -m "feat: add admin user management page with TOTP controls and Airtable sync"
```

---

## Task 6: Admin — Audit Log page

**Files:**
- Create: `frontend/app/admin/audit/page.tsx`

> Note: `getAuditLog` is already defined in `lib/api.ts` from Task 2.

---

- [ ] **Step 1: Create `frontend/app/admin/audit/page.tsx`**

```tsx
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/components/AuthProvider';
import { getAuditLog } from '@/lib/api';
import type { AuditLog } from '@/lib/types';

const PAGE_SIZE = 50;

export default function AuditPage() {
  const { token, user } = useAuth();
  const router = useRouter();

  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  // Role guard
  useEffect(() => {
    if (user && user.role !== 'admin') {
      router.push('/dashboard');
    }
  }, [user, router]);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    setError(null);
    getAuditLog(token, PAGE_SIZE, offset)
      .then((data) => {
        if (offset === 0) {
          setLogs(data);
        } else {
          setLogs((prev) => [...prev, ...data]);
        }
        setHasMore(data.length === PAGE_SIZE);
      })
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : 'Errore caricamento audit log.')
      )
      .finally(() => setLoading(false));
  }, [token, offset]);

  function handleLoadMore() {
    setOffset((prev) => prev + PAGE_SIZE);
  }

  if (user?.role !== 'admin') return null;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Audit Log</h1>

      {error && <p className="text-red-600 text-sm mb-4">{error}</p>}

      <div className="bg-white border border-gray-200 rounded-lg overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-100">
            <tr>
              {['ID', 'Data/Ora', 'User ID', 'Azione', 'Hostname', 'Dettaglio'].map((h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left font-semibold text-gray-600 whitespace-nowrap"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id} className="border-t border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-2 text-gray-400">{log.id}</td>
                <td className="px-4 py-2 whitespace-nowrap">
                  {new Date(log.created_at).toLocaleString('it-IT')}
                </td>
                <td className="px-4 py-2">{log.user_id}</td>
                <td className="px-4 py-2 font-mono">{log.action}</td>
                <td className="px-4 py-2 font-mono">{log.server_hostname ?? '—'}</td>
                <td className="px-4 py-2 text-gray-600 max-w-xs truncate">{log.detail ?? '—'}</td>
              </tr>
            ))}
            {logs.length === 0 && !loading && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-gray-500">
                  Nessun evento trovato.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {loading && <p className="mt-4 text-gray-500 text-sm">Caricamento...</p>}

      {!loading && hasMore && (
        <div className="mt-4 flex justify-center">
          <button
            onClick={handleLoadMore}
            className="bg-gray-200 px-6 py-2 rounded text-sm hover:bg-gray-300"
          >
            Carica altri
          </button>
        </div>
      )}

      {!loading && !hasMore && logs.length > 0 && (
        <p className="mt-4 text-center text-gray-400 text-xs">Fine del log ({logs.length} eventi totali)</p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Run full test suite and build**

```bash
cd frontend && npm test && npm run build
```

Expected: All tests pass, build succeeds.

- [ ] **Step 3: Final smoke test with Docker Compose**

From the project root (`ansible-inventory-ui/`):

```bash
docker compose build frontend
docker compose up frontend -d
curl http://localhost:3000
```

Expected: HTTP 200 response with HTML content.

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "feat: add audit log page with pagination"
```

---

## Self-Review

### Spec coverage check

| Requirement | Covered in |
|---|---|
| POST /api/auth/login step1 | Task 2 — `loginStep1` in api.ts, login page |
| POST /api/auth/verify-totp step2 | Task 2 — `loginStep2`, login page step 2 |
| GET /api/auth/me | Task 2 — `getMe`, AuthProvider rehydration |
| GET /api/servers/ with filters | Task 3 — `listServers`, dashboard page |
| POST /api/servers/ | Task 4 — `createServer`, ServerWizard step 4 |
| GET /api/servers/check-duplicate | Task 4 — `checkDuplicate`, ServerWizard step 2 |
| PATCH /api/servers/{id} | Task 2 — `updateServer` in api.ts |
| DELETE /api/servers/{id} admin only | Task 3 — `deleteServer`, ServerTable |
| GET /api/awx/inventories | Task 4 — `listInventories`, ServerWizard step 1 |
| 503 handling for AWX | Task 4 — `awxUnavailable` flag + "Salta" button |
| POST /api/airtable/import | Task 5 — `importAirtable`, admin page |
| GET /api/airtable/conflicts | Task 5 — `getConflicts`, admin page conflicts list |
| POST /api/airtable/conflicts/resolve | Task 5 — `resolveConflict`, resolve buttons |
| GET /api/admin/audit | Task 6 — `getAuditLog`, audit page |
| GET /api/users/ | Task 5 — `listUsers`, admin page |
| POST /api/users/ | Task 5 — `createUser`, admin page form |
| PATCH /api/users/{id} role/active | Task 5 — `updateUser`, role select + toggle button |
| POST /api/users/{id}/totp/setup | Task 5 — `setupTotp`, admin page |
| DELETE /api/users/{id}/totp | Task 5 — `deleteTotp`, admin page |
| viewer role — read only | Task 3 — "Aggiungi Server" hidden for viewer |
| editor role — create/update | Tasks 3, 4 — nav link and wizard visible |
| admin role — full access | Tasks 3, 5, 6 — delete, user management, audit |
| Admin-only redirect guard | Tasks 5, 6 — useEffect redirects non-admin |
| Auth guard on dashboard | Task 3 — dashboard layout useEffect |
| JWT in localStorage | Task 2 — AuthProvider login/logout/rehydration |
| Bearer header on all calls | Task 2 — `buildHeaders` in api.ts |
| NEXT_PUBLIC_API_URL env var | Task 1 — `BASE` in api.ts + .env.example |
| Docker Node 22 Alpine | Task 1 — Dockerfile |
| output: standalone | Task 1 — next.config.mjs |
| docker-compose frontend service | Task 1 — docker-compose.yml |
| Port 3000 | Task 1 — Dockerfile EXPOSE + docker-compose ports |
| Tailwind CSS 4 | Task 1 — package.json + globals.css |
| No UI component library | All tasks — plain HTML + Tailwind only |
| Jest + React Testing Library | Tasks 1, 2 — jest.config.ts + tests |
| Loading states + disabled buttons | All tasks — `loading` state pattern throughout |
| Inline error messages | All tasks — `error` state + red text |
| 4-step wizard | Task 4 — ServerWizard with step 1–4 |
| ServerCreate body all fields | Task 4 — ServerWizard step 3 + summary |

### Placeholder scan

No TBD, TODO, or incomplete steps found. All code blocks contain working TypeScript/TSX.

### Type consistency check

- `User`, `Server`, `ServerCreate`, `AwxInventory`, `AuditLog`, `Conflict`, `TotpSetupResponse`, `AirtableImportResponse`, `LoginStep1Response`, `DuplicateCheckResponse` — all defined in `lib/types.ts` Task 2 and used consistently.
- `buildHeaders(token: string | null)` — defined Task 1, tested Task 1, used in `apiFetch` Task 2.
- `apiFetch<T>` — defined Task 1 (expanded Task 2), called by all named API functions.
- `listServers`, `deleteServer`, `checkDuplicate`, `createServer`, `updateServer` — defined Task 2 api.ts, consumed in Tasks 3–4.
- `listUsers`, `createUser`, `updateUser`, `setupTotp`, `deleteTotp`, `importAirtable`, `getConflicts`, `resolveConflict`, `getAuditLog` — defined Task 2 api.ts, consumed in Tasks 5–6.
- `useAuth()` returns `{ token, user, login, logout }` — defined Task 2 AuthProvider, consumed consistently across Tasks 3–6.
- `onDeleted(id: number)` prop in `ServerTable` — defined and consumed in Task 3.
