import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, Loader2, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import api from "@/lib/api";

const loginSchema = z.object({
  email: z.string().email("Email non valida"),
  password: z.string().min(1, "Password obbligatoria"),
  totp_code: z.string().optional(),
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
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const mutation = useMutation({
    mutationFn: (data: LoginForm) => api.post("/auth/login", data),
    onSuccess: (res) => {
      setErrorMsg(null);
      if (res.data?.require_2fa) {
        setRequires2FA(true);
        return;
      }
      queryClient.invalidateQueries({ queryKey: ["me"] });
      navigate("/");
    },
    onError: (err: unknown) => {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setErrorMsg(axiosErr.response?.data?.detail ?? "Credenziali non valide");
    },
  });

  const onSubmit = (data: LoginForm) => {
    setErrorMsg(null);
    mutation.mutate(data);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="bg-primary rounded-xl p-2.5 shadow-lg shadow-primary/25">
            <ShieldCheck className="h-8 w-8 text-white" />
          </div>
          <div>
            <span className="text-3xl font-bold text-white tracking-tight">DBShield</span>
            <p className="text-slate-400 text-xs mt-0.5">MSSQL Backup Manager</p>
          </div>
        </div>

        <Card className="shadow-2xl border-slate-700/50 bg-white/5 backdrop-blur-sm text-white">
          <CardHeader className="pb-4">
            <CardTitle className="text-xl">
              {requires2FA ? "Verifica identità" : "Accedi al pannello"}
            </CardTitle>
            <CardDescription className="text-slate-400">
              {requires2FA
                ? "Inserisci il codice dal tuo autenticatore"
                : "Inserisci le tue credenziali per continuare"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              {!requires2FA && (
                <>
                  <div className="space-y-1.5">
                    <Label htmlFor="email" className="text-slate-200">
                      Email
                    </Label>
                    <Input
                      id="email"
                      type="email"
                      placeholder="nome@azienda.com"
                      autoComplete="email"
                      className="bg-slate-800/50 border-slate-600 text-white placeholder:text-slate-500 focus-visible:ring-primary"
                      {...register("email")}
                    />
                    {errors.email && (
                      <p className="text-destructive text-xs mt-1">{errors.email.message}</p>
                    )}
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="password" className="text-slate-200">
                      Password
                    </Label>
                    <div className="relative">
                      <Input
                        id="password"
                        type={showPassword ? "text" : "password"}
                        placeholder="••••••••"
                        autoComplete="current-password"
                        className="bg-slate-800/50 border-slate-600 text-white placeholder:text-slate-500 focus-visible:ring-primary pr-10"
                        {...register("password")}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((v) => !v)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 transition-colors"
                        tabIndex={-1}
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
                      <p className="text-destructive text-xs mt-1">{errors.password.message}</p>
                    )}
                  </div>
                </>
              )}

              {requires2FA && (
                <div className="space-y-1.5">
                  <Label htmlFor="totp_code" className="text-slate-200">
                    Codice Autenticatore (6 cifre)
                  </Label>
                  <Input
                    id="totp_code"
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="000000"
                    autoComplete="one-time-code"
                    className="bg-slate-800/50 border-slate-600 text-white placeholder:text-slate-500 focus-visible:ring-primary text-center text-2xl tracking-[0.5em] font-mono"
                    autoFocus
                    {...register("totp_code")}
                  />
                  <p className="text-slate-400 text-xs">
                    Apri la tua app di autenticazione e inserisci il codice a 6 cifre
                  </p>
                </div>
              )}

              {errorMsg && (
                <div className="bg-destructive/20 border border-destructive/50 text-red-300 text-sm rounded-md px-3 py-2.5 flex items-center gap-2">
                  <span className="shrink-0">⚠</span>
                  <span>{errorMsg}</span>
                </div>
              )}

              <Button
                type="submit"
                className="w-full mt-2"
                size="lg"
                disabled={mutation.isPending}
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
              </Button>

              {requires2FA && (
                <button
                  type="button"
                  onClick={() => setRequires2FA(false)}
                  className="w-full text-center text-sm text-slate-400 hover:text-slate-200 transition-colors mt-1"
                >
                  ← Torna al login
                </button>
              )}
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-slate-500 text-xs mt-6">
          © 2025 EDM Informatica — DBShield v1.0
        </p>
      </div>
    </div>
  );
}
