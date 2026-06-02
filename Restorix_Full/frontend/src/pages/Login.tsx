import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Eye, EyeOff } from "lucide-react";
import api from "@/lib/api";
import axios from "axios";

const loginSchema = z.object({
  email: z.string().email("Email non valida"),
  password: z.string().min(1, "Password obbligatoria"),
  totp_code: z
    .string()
    .optional()
    .refine((val) => !val || /^\d{6}$/.test(val), "Il codice deve essere di 6 cifre numeriche"),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function Login() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [requires2FA, setRequires2FA] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const mutation = useMutation({
    mutationFn: (data: LoginForm) => api.post("/auth/login", data),
    onSuccess: async (res) => {
      setErrorMsg(null);
      if (res.data?.require_2fa) {
        setRequires2FA(true);
        return;
      }
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      navigate("/");
    },
    onError: (err: unknown) => {
      if (axios.isAxiosError(err)) {
        const status = err.response?.status;
        const detail = err.response?.data?.detail as string | undefined;
        if (status === 401) {
          setErrorMsg(detail ?? "Credenziali non valide");
        } else if (status === 429) {
          setErrorMsg("Troppi tentativi. Riprova tra qualche minuto.");
        } else if (!err.response) {
          setErrorMsg("Impossibile connettersi al server.");
        } else {
          setErrorMsg(detail ?? "Errore durante il login.");
        }
      } else {
        setErrorMsg("Errore imprevisto. Riprova.");
      }
    },
  });

  const onSubmit = (data: LoginForm) => {
    setErrorMsg(null);
    mutation.mutate(data);
  };

  const inputClass =
    "w-full px-4 py-2.5 bg-rx-bg-surface border border-rx-border rounded-md text-rx-ink placeholder:text-rx-ink-faint focus:border-rx-accent focus:outline-none focus:ring-2 focus:ring-rx-accent/20 transition-colors";
  const labelClass =
    "block text-xs uppercase tracking-wider text-rx-ink-faint font-semibold mb-1.5";

  return (
    <div className="min-h-screen flex items-center justify-center bg-rx-bg px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex flex-col items-center gap-3 mb-8">
          <img src="/logo.svg" alt="Restorix" className="h-14 w-14" />
          <h1 className="text-3xl font-extrabold tracking-tight text-rx-ink">
            Restor<span className="text-rx-accent">ix</span>
          </h1>
          <p className="text-sm text-rx-ink-faint">Accedi al pannello di backup</p>
        </div>

        <div className="bg-rx-gradient-card border border-rx-border rounded-2xl shadow-rx-card p-8">
          <div className="mb-6">
            <h2 className="text-xl font-bold text-rx-ink">
              {requires2FA ? "Verifica identità" : "Accedi al pannello"}
            </h2>
            <p className="text-sm text-rx-ink-muted mt-1">
              {requires2FA
                ? "Inserisci il codice dal tuo autenticatore"
                : "Inserisci le tue credenziali per continuare"}
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {!requires2FA && (
              <>
                <div>
                  <label htmlFor="email" className={labelClass}>
                    Email
                  </label>
                  <input
                    id="email"
                    type="email"
                    placeholder="nome@azienda.com"
                    autoComplete="email"
                    className={inputClass}
                    {...register("email")}
                  />
                  {errors.email && (
                    <p className="text-red-400 text-xs mt-1">{errors.email.message}</p>
                  )}
                </div>

                <div>
                  <label htmlFor="password" className={labelClass}>
                    Password
                  </label>
                  <div className="relative">
                    <input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      placeholder="••••••••"
                      autoComplete="current-password"
                      className={`${inputClass} pr-10`}
                      {...register("password")}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-rx-ink-faint hover:text-rx-ink transition-colors"
                      aria-label={showPassword ? "Nascondi password" : "Mostra password"}
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                  {errors.password && (
                    <p className="text-red-400 text-xs mt-1">{errors.password.message}</p>
                  )}
                </div>
              </>
            )}

            {requires2FA && (
              <div>
                <label htmlFor="totp_code" className={labelClass}>
                  Codice Autenticatore (6 cifre)
                </label>
                <input
                  id="totp_code"
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="000000"
                  autoComplete="one-time-code"
                  className={`${inputClass} text-center text-2xl tracking-[0.5em] font-mono`}
                  autoFocus
                  {...register("totp_code")}
                />
                <p className="text-rx-ink-faint text-xs mt-1.5">
                  Apri la tua app di autenticazione e inserisci il codice a 6 cifre
                </p>
              </div>
            )}

            {errorMsg && (
              <div className="bg-red-500/10 border border-red-500/40 text-red-400 text-sm rounded-md px-3 py-2.5 flex items-center gap-2">
                <span className="shrink-0">⚠</span>
                <span>{errorMsg}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={mutation.isPending}
              className="w-full py-2.5 bg-rx-gradient-accent text-rx-bg font-bold rounded-md shadow-rx-glow hover:-translate-y-px transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
            >
              {mutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {requires2FA ? "Verifica in corso..." : "Accesso in corso..."}
                </>
              ) : requires2FA ? (
                "Verifica codice"
              ) : (
                "Accedi"
              )}
            </button>

            {requires2FA && (
              <button
                type="button"
                onClick={() => {
                  setRequires2FA(false);
                  setErrorMsg(null);
                  reset();
                }}
                className="w-full text-center text-sm text-rx-ink-muted hover:text-rx-ink transition-colors mt-1"
              >
                ← Torna al login
              </button>
            )}
          </form>
        </div>

        <p className="text-center text-xs text-rx-ink-faint mt-6">
          © 2026 Restorix v1.2.0
        </p>
      </div>
    </div>
  );
}
