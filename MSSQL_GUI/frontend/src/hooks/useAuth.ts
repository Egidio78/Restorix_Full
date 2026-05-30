import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/authStore";
import api from "@/lib/api";
import { useEffect } from "react";

export function useAuth() {
  const { user, setUser, clearUser } = useAuthStore();

  const { data, isLoading, error } = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const res = await api.get("/auth/me");
      return res.data;
    },
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (data) setUser(data);
    if (error) clearUser();
  }, [data, error, setUser, clearUser]);

  // Use data (server truth) if available, fall back to store (cached)
  const resolvedUser = data ?? user;

  return {
    user: resolvedUser,
    isLoading,
    isAuthenticated: !!resolvedUser,
  };
}
