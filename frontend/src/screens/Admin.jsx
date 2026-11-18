import { useEffect, useState } from "react";
import { api, post } from "../api.js";
import { LanguageSwitch, useT } from "../i18n.jsx";

export default function Admin({ boot }) {
  const { t } = useT();
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/auth/me")
      .then(setMe)
      .catch(() => setMe(null))
      .finally(() => setLoading(false));
  }, []);

  const login = async (event) => {
    event.preventDefault();
    if (!form.username || !form.password) {
      setError(t("login.required"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await post("/api/auth/login", form);
      setMe(result);
    } catch (err) {
      setError(err.status === 429 ? t("login.too_many") : t("login.invalid"));
    } finally {
      setBusy(false);
    }
  };

  const logout = async () => {
    await post("/api/auth/logout", {});
    setMe(null);
  };

  if (loading) {
    return (
      <div className="centered-screen">
        <div className="spinner" />
      </div>
    );
  }

  if (!me) {
    return (
      <div className="centered-screen">
        <form className="card narrow login-card" onSubmit={login}>
          <div className="row between">
            <h1>{t("login.title")}</h1>
            <LanguageSwitch compact />
          </div>
          <p className="muted">{t("login.subtitle")}</p>
          <label className="field">
            <span className="field-label">{t("login.username")}</span>
            <input
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              autoComplete="username"
              autoFocus
            />
          </label>
          <label className="field">
            <span className="field-label">{t("login.password")}</span>
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              autoComplete="current-password"
            />
          </label>
          {error && <p className="error-box">{error}</p>}
          <button className="btn primary" disabled={busy}>
            {busy ? t("common.loading") : t("login.submit")}
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="admin">
      <header className="topbar">
        <div className="brand">
          {boot.logo ? <img src={boot.logo} alt="" className="brand-logo" /> : <div className="brand-mark">Q</div>}
          <div>
            <h1>{t("admin.title")}</h1>
            <p className="muted small">{boot.institution_name}</p>
          </div>
        </div>
        <div className="row gap">
          <LanguageSwitch compact />
          <button className="btn small" onClick={logout}>
            {t("common.logout")}
          </button>
        </div>
      </header>
      <div className="card">
        <h2>{t("admin.welcome", { name: me.username })}</h2>
        <p className="muted">{t("common.loading")}</p>
      </div>
    </div>
  );
}
