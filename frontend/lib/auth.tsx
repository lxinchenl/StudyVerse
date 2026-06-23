"use client";

import { createContext, useContext, useEffect, useState } from "react";

import { fetchCurrentUser, loginUser, registerUser, type ApiUser } from "./api";

export type User = ApiUser;

const STORAGE_KEY = "edu_agent_current_user";

interface AuthContextValue {
  user: User | null;
  login: (email: string, password: string) => Promise<User>;
  register: (name: string, email: string, password: string, major?: string) => Promise<User>;
  logout: () => void;
  memoryPath: (category: string) => string;
  ready: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    async function init() {
      try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
          const me = await fetchCurrentUser(saved);
          setUser(me);
        }
      } catch {
        localStorage.removeItem(STORAGE_KEY);
        setUser(null);
      } finally {
        setReady(true);
      }
    }
    void init();
  }, []);

  async function login(email: string, password: string) {
    const loggedIn = await loginUser(email, password);
    localStorage.setItem(STORAGE_KEY, loggedIn.id);
    setUser(loggedIn);
    return loggedIn;
  }

  async function register(name: string, email: string, password: string, major = "") {
    const created = await registerUser(name, email, password, major);
    localStorage.setItem(STORAGE_KEY, created.id);
    setUser(created);
    return created;
  }

  function logout() {
    localStorage.removeItem(STORAGE_KEY);
    setUser(null);
  }

  function memoryPath(category: string) {
    if (!user) return "";
    return `data/users/${user.id}/${category}`;
  }

  if (!ready) return null;

  return (
    <AuthContext.Provider value={{ user, login, register, logout, memoryPath, ready }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
