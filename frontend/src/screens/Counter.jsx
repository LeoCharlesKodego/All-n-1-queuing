import { useCallback, useEffect, useMemo, useState } from "react";
import { api, formatDuration, post } from "../api.js";
import { LanguageSwitch, useT } from "../i18n.jsx";
import { useLive } from "../live.js";

function priorityLabel(ticket, lang) {
  if (!ticket) return null;
  return lang === "fil" ? ticket.priority_fil : ticket.priority_en;
}

function Modal({ title, children, onClose, t }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="row between">
          <h2>{title}</h2>
          <button className="btn ghost small" onClick={onClose}>
            {t("common.close")}
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default function Counter() {
  const { t, lang } = useT();
  const [session, setSession] = useState(null);
  const [state, setState] = useState(null);
  const [options, setOptions] = useState(null);
  const [pin, setPin] = useState("");
  const [counterId, setCounterId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState(null);
  const [offset, setOffset] = useState(0);
  const [now, setNow] = useState(Date.now());
  const [transferTo, setTransferTo] = useState("");
  const [keepPlace, setKeepPlace] = useState(false);
  const [issueForm, setIssueForm] = useState({ service_id: "", priority_type_id: "", account_number: "" });

  const errorText = (err) => {
    const key = `error.${err?.message}`;
    const text = t(key);
    return text === key ? t("common.error") : text;
  };

  const load = useCallback(async () => {
    try {
      const data = await api("/api/counter/state");
      setState(data);
      setOffset(Date.parse(data.server_now) - Date.now());
      setError("");
      return data;
    } catch (err) {
      if (err.status === 401) {
        setSession(null);
        setState(null);
      } else {
        setError(errorText(err));
      }
      return null;
    }
  }, [lang]);

  useEffect(() => {
    api("/api/staff/options").then(setOptions).catch(() => {});
    api("/api/counter/me")
      .then((me) => {
        setSession(me);
        load();
      })
      .catch(() => {});
  }, [load]);

  useLive(() => {
    if (session) load();
  });

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 3000);
    return () => clearTimeout(timer);
  }, [notice]);

  const login = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const me = await post("/api/staff/login", {
        pin,
        counter_id: counterId ? Number(counterId) : null,
      });
      setSession({ staff: me.staff, counter_id: me.counter.id });
      setPin("");
      await load();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const logout = async () => {
    await post("/api/staff/logout", {});
    setSession(null);
    setState(null);
  };

  const act = async (path, body = {}, successKey) => {
    setBusy(true);
    try {
      await post(path, body);
      await load();
      if (successKey) setNotice(t(successKey));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const setStatus = (status) => act("/api/counter/status", { status });

  const current = state?.current;
  const isAway = state?.counter?.status === "away";
  const working = current && ["called", "serving"].includes(current.status);

  useEffect(() => {
    if (!session || modal) return;
    const onKey = (event) => {
      const tag = event.target.tagName;
      if (["INPUT", "SELECT", "TEXTAREA"].includes(tag)) return;
      if (!working) {
        if (event.code === "Space") {
          event.preventDefault();
          act("/api/counter/call-next", {});
        }
        return;
      }
      if (event.code === "Space" && current.status === "called") {
        event.preventDefault();
        act("/api/counter/start", { ticket_id: current.id });
      } else if (event.key.toLowerCase() === "r") {
        act("/api/counter/recall", { ticket_id: current.id });
      } else if (event.key.toLowerCase() === "d" || event.key === "Enter") {
        act("/api/counter/done", { ticket_id: current.id });
      } else if (event.key.toLowerCase() === "k") {
        act("/api/counter/skip", { ticket_id: current.id });
      } else if (event.key.toLowerCase() === "h") {
        act("/api/counter/hold", { ticket_id: current.id });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [session, modal, working, current]);

  if (!session) {
    return (
      <div className="staff-login">
        <form className="card narrow login-card" onSubmit={login}>
          <div className="row between">
            <div className="brand">
              <div className="brand-mark">Q</div>
              <div>
                <h1>{t("counter.login_title")}</h1>
                <p className="muted small">{options?.institution_name || t("app.name")}</p>
              </div>
            </div>
            <LanguageSwitch compact />
          </div>
          <label className="field pin-input">
            <span className="field-label">{t("counter.pin")}</span>
            <input
              value={pin}
              onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 8))}
              inputMode="numeric"
              autoComplete="off"
              autoFocus
            />
          </label>
          <label className="field">
            <span className="field-label">{t("counter.choose_counter")}</span>
            <select value={counterId} onChange={(e) => setCounterId(e.target.value)}>
              <option value="">{t("counter.assigned_counter")}</option>
              {(options?.counters || []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          {error && <p className="error-box">{error}</p>}
          <button className="btn primary big" disabled={busy || !pin}>
            {t("counter.sign_in")}
          </button>
          <a href="/" className="subtle-link" style={{ textAlign: "center" }}>
            {t("common.back")}
          </a>
        </form>
      </div>
    );
  }

  if (!state) {
    return (
      <div className="centered-screen">
        <div className="spinner" />
      </div>
    );
  }

  const elapsed = working
    ? Math.max(0, Math.floor((now + offset - Date.parse(current.serving_at || current.called_at)) / 1000))
    : 0;
  const assignedIds = new Set(state.estimates.map((e) => e.service_id));
  const assignedServices = state.services.filter((s) => assignedIds.has(s.id));
  const currentServiceName = current?.service_name;

  return (
    <div className="counter">
      <header className="counter-top">
        <div className="row gap wrap">
          <div>
            <h1>
              {state.counter.name} · {state.staff.name}
            </h1>
            <p className="muted small">
              {state.settings.institution_name} · {t("counter.staff_console")}
            </p>
          </div>
          {isAway && <span className="pill amber">{t("counter.away")}</span>}
        </div>
        <div className="row gap wrap">
          <LanguageSwitch compact />
          <button className="btn small" onClick={() => setStatus(isAway ? "open" : "away")}>
            {isAway ? t("counter.back_open") : t("counter.break")}
          </button>
          <button className="btn small" onClick={logout}>
            {t("counter.close")}
          </button>
        </div>
      </header>

      <div className="counter-body">
        <section className="current-panel">
          {error && <p className="error-box">{error}</p>}
          {notice && <p className="notice-box">{notice}</p>}
          <div className="current-top">
            <div>
              <p className="eyebrow">{t("counter.current")}</p>
              {current ? (
                <>
                  <p className="current-number">{current.number}</p>
                  <p className="current-meta">
                    <span>{current.service_name}</span>
                    {priorityLabel(current, lang) && (
                      <span className="pill amber">{priorityLabel(current, lang)}</span>
                    )}
                    {current.account_number && (
                      <span>
                        {t("counter.account")}: <strong>{current.account_number}</strong>
                      </span>
                    )}
                  </p>
                </>
              ) : (
                <p className="current-meta muted">{t("counter.no_current")}</p>
              )}
            </div>
            <div style={{ textAlign: "right" }}>
              {current && (
                <p className="eyebrow">{current.status === "serving" ? t("counter.serving") : t("counter.called")}</p>
              )}
              {current && <p className="timer">{working ? formatDuration(elapsed) : "—"}</p>}
              {current && current.recall_count > 0 && (
                <p className="small muted">
                  {t("counter.recalls")}: {current.recall_count}
                </p>
              )}
            </div>
          </div>

          <div className="action-grid">
            {!working ? (
              <button className="btn primary big" onClick={() => act("/api/counter/call-next", {})} disabled={busy}>
                {t("counter.call_next")} <kbd>Space</kbd>
              </button>
            ) : (
              <>
                {current.status === "called" && (
                  <button className="btn primary big" onClick={() => act("/api/counter/start", { ticket_id: current.id })}>
                    {t("counter.start")} <kbd>Space</kbd>
                  </button>
                )}
                <button className="btn" onClick={() => act("/api/counter/recall", { ticket_id: current.id })}>
                  {t("counter.recall")} <kbd>R</kbd>
                </button>
                <button className="btn" onClick={() => act("/api/counter/done", { ticket_id: current.id })}>
                  {t("counter.done")} <kbd>D</kbd>
                </button>
                <button className="btn" onClick={() => act("/api/counter/skip", { ticket_id: current.id })}>
                  {t("counter.skip")} <kbd>K</kbd>
                </button>
                <button className="btn" onClick={() => act("/api/counter/hold", { ticket_id: current.id })}>
                  {t("counter.hold")} <kbd>H</kbd>
                </button>
                <button
                  className="btn"
                  onClick={() => {
                    setTransferTo("");
                    setModal("transfer");
                  }}
                >
                  {t("counter.transfer")}
                </button>
              </>
            )}
            {state.settings.staff_issue_enabled && (
              <button
                className="btn"
                onClick={() => {
                  setIssueForm({
                    service_id: assignedServices[0]?.id || "",
                    priority_type_id: "",
                    account_number: "",
                  });
                  setModal("issue");
                }}
              >
                {t("counter.issue_ticket")}
              </button>
            )}
          </div>
          <p className="hint-bar">
            {t("counter.shortcuts")}: Space · R · D · K · H
          </p>
        </section>

        <aside className="waiting-panel">
          <div className="counts-row">
            <div className="count-pill">
              <div className="value">{state.waiting_count}</div>
              <div className="label">{t("counter.waiting")}</div>
            </div>
            <div className="count-pill">
              <div className="value">{state.served_today}</div>
              <div className="label">{t("counter.served_today")}</div>
            </div>
          </div>

          <div className="card waiting-card">
            <div className="row between">
              <h2>{t("counter.waiting_list")}</h2>
              <button className="btn ghost small" onClick={load}>
                {t("common.refresh")}
              </button>
            </div>
            <div className="waiting-list">
              {state.waiting.map((w) => (
                <div className={`waiting-item ${w.priority_type_id ? "prio" : ""}`} key={w.id}>
                  <span className="num">{w.number}</span>
                  <span className="muted small">{w.service_name}</span>
                  {priorityLabel(w, lang) && <span className="pill amber">{priorityLabel(w, lang)}</span>}
                  <span className="small muted">{formatDuration(w.wait_seconds)}</span>
                </div>
              ))}
              {!state.waiting.length && <p className="muted small">{t("counter.no_waiting")}</p>}
            </div>
          </div>

          {state.parked.length > 0 && (
            <div className="card waiting-card">
              <h2>{t("counter.parked")}</h2>
              <div className="waiting-list">
                {state.parked.map((p) => (
                  <div className="parked-item" key={p.id}>
                    <span>
                      <strong>{p.number}</strong>{" "}
                      <span className="muted small">{p.service_name}</span>{" "}
                      <span className={`pill ${p.status === "no_show" ? "red" : "blue"}`}>
                        {p.status === "no_show" ? t("counter.no_show") : t("counter.on_hold")}
                      </span>
                    </span>
                    {p.status === "on_hold" ? (
                      <button
                        className="btn small"
                        disabled={!p.can_recall}
                        onClick={() => act("/api/counter/resume", { ticket_id: p.id })}
                      >
                        {p.can_recall ? t("counter.recall") : `${p.recall_in}s`}
                      </button>
                    ) : (
                      <button className="btn small" onClick={() => act("/api/counter/reenter", { ticket_id: p.id })}>
                        {t("counter.reenter")}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>

      {modal === "transfer" && (
        <Modal title={t("counter.transfer")} onClose={() => setModal(null)} t={t}>
          <p className="muted small">{t("counter.transfer_hint")}</p>
          <label className="field">
            <span className="field-label">{t("counter.to_service")}</span>
            <select value={transferTo} onChange={(e) => setTransferTo(e.target.value)}>
              <option value="">—</option>
              {state.services
                .filter((s) => s.name !== currentServiceName)
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
            </select>
          </label>
          <label className="toggle-row">
            <input type="checkbox" checked={keepPlace} onChange={(e) => setKeepPlace(e.target.checked)} />
            <span>
              <strong>{t("counter.keep_place")}</strong>
              <small>{t("counter.keep_place_hint")}</small>
            </span>
          </label>
          <div className="row gap" style={{ justifyContent: "flex-end" }}>
            <button className="btn" onClick={() => setModal(null)}>
              {t("common.cancel")}
            </button>
            <button
              className="btn primary"
              disabled={!transferTo}
              onClick={async () => {
                await act("/api/counter/transfer", {
                  ticket_id: current.id,
                  to_service_id: Number(transferTo),
                  keep_place: keepPlace,
                });
                setModal(null);
              }}
            >
              {t("counter.transfer")}
            </button>
          </div>
        </Modal>
      )}

      {modal === "issue" && (
        <Modal title={t("counter.issue_ticket")} onClose={() => setModal(null)} t={t}>
          <label className="field">
            <span className="field-label">{t("setup.services.name")}</span>
            <select
              value={issueForm.service_id}
              onChange={(e) => setIssueForm({ ...issueForm, service_id: e.target.value })}
            >
              {assignedServices.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.prefix})
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">{t("counter.priority")}</span>
            <select
              value={issueForm.priority_type_id}
              onChange={(e) => setIssueForm({ ...issueForm, priority_type_id: e.target.value })}
            >
              <option value="">{t("common.none")}</option>
              {state.priorities.map((p) => (
                <option key={p.id} value={p.id}>
                  {lang === "fil" ? p.name_fil : p.name_en}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">{t("counter.account")}</span>
            <input
              value={issueForm.account_number}
              onChange={(e) => setIssueForm({ ...issueForm, account_number: e.target.value })}
            />
          </label>
          <div className="row gap" style={{ justifyContent: "flex-end" }}>
            <button className="btn" onClick={() => setModal(null)}>
              {t("common.cancel")}
            </button>
            <button
              className="btn primary"
              disabled={!issueForm.service_id}
              onClick={async () => {
                await act("/api/counter/issue", {
                  service_id: Number(issueForm.service_id),
                  priority_type_id: issueForm.priority_type_id
                    ? Number(issueForm.priority_type_id)
                    : null,
                  account_number: issueForm.account_number,
                });
                setModal(null);
              }}
            >
              {t("counter.issue_ticket")}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
