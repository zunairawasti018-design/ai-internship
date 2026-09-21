import api from "./api";

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  name: string;
  email: string;
  password: string;
}

export async function loginUser(data: LoginRequest) {
  const formData = new URLSearchParams();

  formData.append("username", data.email);
  formData.append("password", data.password);

  const response = await api.post(
    "/auth/login",
    formData,
    {
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
    }
  );

  return response.data;
}

export async function registerUser(data: RegisterRequest) {
  const response = await api.post("/auth/register", {
    name: data.name,
    email: data.email,
    password: data.password,
  });

  return response.data;
}

export interface UserProfile {
  id: number;
  name: string;
  email: string;
}

export async function fetchCurrentUser(): Promise<UserProfile> {
  const response = await api.get<UserProfile>("/auth/me");
  return response.data;
}