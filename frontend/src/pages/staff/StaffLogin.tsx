import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "@/services/api";
import { useAppStore } from "@/store/appStore";

const DEMO_ACCOUNTS = [
  { username: "admin", password: "admin123", label: "Admin" },
  { username: "roads", password: "roads123", label: "Roads Officer" },
  { username: "sanitation", password: "sanitation123", label: "Sanitation Officer" },
  { username: "electrical", password: "electrical123", label: "Electrical Officer" },
  { username: "drainage", password: "drainage123", label: "Drainage Officer" },
];

export default function StaffLogin() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const setStaffAuth = useAppStore((s) => s.setStaffAuth);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await api.login(username, password);
      setStaffAuth(result.access_token, {
        username: result.username,
        full_name: result.full_name,
        role: result.role,
        department: result.department,
      });
      navigate("/staff/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not log in. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-6 text-center">
          <span className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-brand-600 text-lg font-bold text-white">CF</span>
          <h1 className="text-xl font-bold text-slate-800">Municipal Staff Login</h1>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <input className="input-field" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
          <input className="input-field" placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button className="btn-primary" disabled={loading}>
            {loading ? "Logging in…" : "Log In"}
          </button>
        </form>

        <div className="mt-6 rounded-xl bg-slate-50 p-3 text-xs text-slate-500">
          <p className="mb-1 font-semibold text-slate-600">Demo credentials</p>
          {DEMO_ACCOUNTS.map((acc) => (
            <button
              key={acc.username}
              type="button"
              className="mt-1 flex w-full items-center justify-between rounded-lg px-2 py-1 text-left hover:bg-slate-100"
              onClick={() => {
                setUsername(acc.username);
                setPassword(acc.password);
              }}
            >
              <span>{acc.label}</span>
              <span className="font-mono">{acc.username} / {acc.password}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
