import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { LogOut, User as UserIcon, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useAuthStore } from "@/stores/authStore";
import api from "@/lib/api";

const ROLE_LABELS: Record<string, string> = {
  superadmin: "Super Admin",
  admin: "Admin",
  operator: "Operatore",
  viewer: "Visualizzatore",
};

export default function Header() {
  const { user } = useAuth();
  const clearUser = useAuthStore((s) => s.clearUser);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const logout = useMutation({
    mutationFn: () => api.post("/auth/logout"),
    onSuccess: () => {
      clearUser();
      queryClient.clear();
      navigate("/login");
    },
    onError: () => {
      // Force logout even if API fails
      clearUser();
      queryClient.clear();
      navigate("/login");
    },
  });

  return (
    <header className="h-14 border-b bg-background flex items-center justify-between px-6 shrink-0">
      {/* Left — breadcrumb placeholder */}
      <div />

      {/* Right — user info + logout */}
      <div className="flex items-center gap-3">
        {user && (
          <div className="flex items-center gap-2 text-sm">
            <div className="flex items-center gap-1.5 bg-muted rounded-full px-3 py-1">
              <UserIcon className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-foreground font-medium max-w-[160px] truncate">
                {user.email}
              </span>
              <ChevronDown className="h-3 w-3 text-muted-foreground" />
            </div>
            <span className="bg-primary/10 text-primary text-xs font-medium px-2 py-0.5 rounded-full">
              {ROLE_LABELS[user.role] ?? user.role}
            </span>
          </div>
        )}

        <Button
          variant="ghost"
          size="icon"
          onClick={() => logout.mutate()}
          disabled={logout.isPending}
          title="Logout"
          className="text-muted-foreground hover:text-destructive"
        >
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
