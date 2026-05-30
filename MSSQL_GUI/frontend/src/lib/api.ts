import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  withCredentials: true,
});

// Interceptor: on 401, attempt token refresh once then redirect to login
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/login") &&
      !originalRequest.url?.includes("/auth/refresh")
    ) {
      originalRequest._retry = true;
      try {
        await axios.post("/api/v1/auth/refresh", {}, { withCredentials: true });
        return api(originalRequest);
      } catch {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default api;
