import axios from "axios";
import { getClientToken } from "../lib/auth";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000",
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const token = getClientToken();

  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

export default api;