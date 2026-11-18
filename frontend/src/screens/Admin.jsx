import { useCallback, useEffect, useState } from "react";
import { api, post, put, formatDuration, formatTime } from "../api.js";
import { LanguageSwitch, useT } from "../i18n.jsx";
import { useLive } from "../live.js";

function Modal({ title, children, onClose }) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label={title}>
      <div className="modal">
        <div className="row between">
          <h2>{title}</h2>
          <button type="button" className="btn ghost small" onClick={onClose}>
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

function Toggle({ label, checked, onChange }) {
  return (
    <label className="row gap" style={{ alignItems: "center" }}>
      <input type="checkbox" checked={!!checked} onChange={(e) => onChange(e.target.checked)} style={{ width: 18, height: 18 }} />
      <span>{label}</span>
    </label>
  );
}

function useSettings() {
  const [settings, setSettings] = useState(null);
  const [media, setMedia] = useState([]);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    const data = await api("/api/admin/settings");
    setSettings(data.settings);
    setMedia(data.media || []);
  }, []);
  useEffect(() => {
    load().catch(() => setError("error.network"));
  }, [load]);
  const save = async (patch) => {
    setError("");
    try {
      const result = await put("/api/admin/settings", patch);
      setSettings(result.settings);
      return true;
    } catch (err) {
      setError(`admin.save_failed|${typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail)}`);
      return false;
    }
  };
  return { settings, setSettings, media, load, save, error, setError };
}

function SettingsMessage({ error, saved, t }) {
  if (error) {
    const [key, detail] = error.split("|");
    return <p className="error-box">{t(key)}{detail ? ` (${detail})` : ""}</p>;
  }
  if (saved) return <p className="notice-box">{t("admin.saved")}</p>;
  return null;
}

// --- dashboard ------------------------------------------------------------

function Dashboard({ t }) {
  const [data, setData] = useState(null);
  const load = useCallback(() => {
    api("/api/admin/dashboard").then(setData).catch(() => {});
  }, []);
  useLive(useCallback(() => load(), [load]));
  useEffect(() => {
    load();
    const id = setInterval(load, 8000);
    return () => clearInterval(id);
  }, [load]);

  if (!data) return <p className="muted">{t("common.loading")}</p>;
  const stats = [
    ["dashboard.issued", data.issued, ""],
    ["dashboard.waiting", data.waiting, data.waiting > 0 ? "alert" : ""],
    ["dashboard.serving", data.serving, ""],
    ["dashboard.completed", data.completed, ""],
    ["dashboard.no_show", data.no_show, ""],
    ["dashboard.avg_wait", formatDuration(data.avg_wait_seconds), ""],
    ["dashboard.avg_service", formatDuration(data.avg_service_seconds), ""],
    ["dashboard.media", data.media_files, ""],
  ];
  return (
    <div className="panel">
      <div className="panel-head">
        <h2>{t("admin.tabs.dashboard")}</h2>
        <div className="row gap">
          <span className="muted small">{t("dashboard.date", { date: data.business_date })}</span>
          <button className="btn small" onClick={load}>{t("admin.refresh")}</button>
        </div>
      </div>
      {data.alerts.length > 0 && (
        <div className="notice-box" style={{ background: "#fef8ec", color: "#8a5a12", borderColor: "#eec27b" }}>
          {t("dashboard.alerts")}:{" "}
          {data.alerts.map((a) => t("dashboard.alert_item", { name: a.name, waiting: a.waiting, threshold: a.threshold })).join(" · ")}
        </div>
      )}
      <div className="stat-grid">
        {stats.map(([label, value, cls]) => (
          <div className={`stat-card ${cls}`} key={label}>
            <span className="label">{t(label)}</span>
            <span className="value">{value}</span>
          </div>
        ))}
      </div>
      <div className="card">
        <h2>{t("dashboard.counters")}</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t("counters.name")}</th>
                <th>{t("counters.status")}</th>
                <th>{t("dashboard.now_calling")}</th>
                <th>{t("staff.title")}</th>
                <th>{t("dashboard.logged_in")}</th>
              </tr>
            </thead>
            <tbody>
              {data.counters.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>
                    <span className={`pill ${c.is_active ? (c.status === "open" ? "green" : c.status === "away" ? "amber" : "") : "red"}`}>
                      {t(`counters.state.${c.is_active ? c.status : "closed"}`)}
                    </span>
                  </td>
                  <td>{c.ticket_number || "—"}</td>
                  <td>{c.staff_names || "—"}</td>
                  <td>{c.logged_in ? `✔ ${c.logged_in}` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="card">
        <div className="row between">
          <h2>{t("dashboard.printer")}</h2>
          <span className={`pill ${data.printer_status === "works" ? "green" : "amber"}`}>
            {t(`kiosk.printer.${data.printer_status || "unknown"}`)}
          </span>
        </div>
        {data.printer_note && <p className="muted small">{data.printer_note}</p>}
      </div>
    </div>
  );
}

// --- services -------------------------------------------------------------

const emptyService = {
  name: "", prefix: "", open_from: "", open_to: "", cut_off_time: "",
  ask_account_number: 0, queue_alert_threshold: 0, is_active: 1, is_express: 0, sort_order: 0,
};

function ServicesTab({ t }) {
  const [rows, setRows] = useState(null);
  const [edit, setEdit] = useState(null);
  const [error, setError] = useState("");
  const load = useCallback(() => api("/api/admin/services").then((d) => setRows(d.services)), []);
  useEffect(() => { load().catch(() => setError("error.network")); }, [load]);

  const save = async (event) => {
    event.preventDefault();
    setError("");
    try {
      if (edit.id) await put(`/api/admin/services/${edit.id}`, edit);
      else await post("/api/admin/services", edit);
      setEdit(null);
      await load();
    } catch (err) {
      setError(typeof err.detail === "string" ? `error.${err.detail}` : "admin.save_failed");
    }
  };

  if (!rows) return <p className="muted">{t("common.loading")}</p>;
  return (
    <div className="panel">
      <div className="panel-head">
        <h2>{t("admin.tabs.services")}</h2>
        <button className="btn primary" onClick={() => { setEdit({ ...emptyService }); setError(""); }}>
          + {t("services.add")}
        </button>
      </div>
      {error && <p className="error-box">{t(error)}</p>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{t("services.name")}</th>
              <th>{t("services.prefix")}</th>
              <th>{t("services.hours")}</th>
              <th>{t("services.waiting")}</th>
              <th>{t("services.alert_threshold")}</th>
              <th>{t("common.status")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id}>
                <td>{s.name}{s.is_express ? <span className="pill blue" style={{ marginLeft: 6 }}>{t("services.express")}</span> : null}</td>
                <td>{s.prefix}-###</td>
                <td className="muted">
                  {s.open_from ? `${s.open_from}–${s.open_to || ""}` : t("services.all_day")}
                  {s.cut_off_time ? ` · ${t("services.cutoff")} ${s.cut_off_time}` : ""}
                </td>
                <td>{s.waiting}</td>
                <td>{s.queue_alert_threshold || "—"}</td>
                <td><span className={`pill ${s.is_active ? "green" : "red"}`}>{t(s.is_active ? "common.active" : "common.inactive")}</span></td>
                <td className="table-actions">
                  <button className="btn small" onClick={() => { setEdit({ ...s }); setError(""); }}>{t("common.edit")}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="field-hint">{t("services.renumber_note")}</p>
      {edit && (
        <Modal title={t(edit.id ? "services.edit" : "services.add")} onClose={() => setEdit(null)}>
          <form className="stack" onSubmit={save}>
            <Field label={t("services.name")}>
              <input value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} autoFocus />
            </Field>
            <div className="form-grid">
              <Field label={t("services.prefix")} hint={t("services.prefix_hint")}>
                <input value={edit.prefix} maxLength={4} onChange={(e) => setEdit({ ...edit, prefix: e.target.value.toUpperCase() })} />
              </Field>
              <Field label={t("services.sort")}>
                <input type="number" value={edit.sort_order} onChange={(e) => setEdit({ ...edit, sort_order: Number(e.target.value) })} />
              </Field>
            </div>
            <div className="form-grid">
              <Field label={t("services.open_from")}><input type="time" value={edit.open_from || ""} onChange={(e) => setEdit({ ...edit, open_from: e.target.value })} /></Field>
              <Field label={t("services.open_to")}><input type="time" value={edit.open_to || ""} onChange={(e) => setEdit({ ...edit, open_to: e.target.value })} /></Field>
              <Field label={t("services.cutoff")}><input type="time" value={edit.cut_off_time || ""} onChange={(e) => setEdit({ ...edit, cut_off_time: e.target.value })} /></Field>
              <Field label={t("services.alert_threshold")} hint={t("services.alert_hint")}>
                <input type="number" min="0" value={edit.queue_alert_threshold} onChange={(e) => setEdit({ ...edit, queue_alert_threshold: Number(e.target.value) })} />
              </Field>
            </div>
            <Toggle label={t("services.ask_account")} checked={edit.ask_account_number} onChange={(v) => setEdit({ ...edit, ask_account_number: v ? 1 : 0 })} />
            <Toggle label={t("services.express")} checked={edit.is_express} onChange={(v) => setEdit({ ...edit, is_express: v ? 1 : 0 })} />
            <Toggle label={t("common.active")} checked={edit.is_active} onChange={(v) => setEdit({ ...edit, is_active: v ? 1 : 0 })} />
            {error && <p className="error-box">{t(error)}</p>}
            <div className="row gap">
              <button className="btn primary">{t("common.save")}</button>
              <button type="button" className="btn ghost" onClick={() => setEdit(null)}>{t("common.cancel")}</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}

// --- counters -------------------------------------------------------------

function CountersTab({ t }) {
  const [rows, setRows] = useState(null);
  const [services, setServices] = useState([]);
  const [edit, setEdit] = useState(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    const [c, l] = await Promise.all([api("/api/admin/counters"), api("/api/admin/lookups")]);
    setRows(c.counters);
    setServices(l.services);
  }, []);
  useEffect(() => { load().catch(() => setError("error.network")); }, [load]);

  const save = async (event) => {
    event.preventDefault();
    setError("");
    try {
      if (edit.id) await put(`/api/admin/counters/${edit.id}`, edit);
      else await post("/api/admin/counters", edit);
      setEdit(null);
      await load();
    } catch {
      setError("admin.save_failed");
    }
  };
  const toggleService = (id) => {
    const has = (edit.service_ids || []).includes(id);
    setEdit({ ...edit, service_ids: has ? edit.service_ids.filter((x) => x !== id) : [...(edit.service_ids || []), id] });
  };

  if (!rows) return <p className="muted">{t("common.loading")}</p>;
  return (
    <div className="panel">
      <div className="panel-head">
        <h2>{t("admin.tabs.counters")}</h2>
        <button className="btn primary" onClick={() => { setEdit({ name: "", is_active: 1, sort_order: rows.length + 1, service_ids: [] }); setError(""); }}>
          + {t("counters.add")}
        </button>
      </div>
      {error && <p className="error-box">{t(error)}</p>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{t("counters.name")}</th>
              <th>{t("counters.services")}</th>
              <th>{t("counters.staff")}</th>
              <th>{t("counters.status")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td className="muted">
                  {c.service_ids.map((id) => services.find((s) => s.id === id)?.name || id).join(", ") || "—"}
                </td>
                <td className="muted">{c.staff?.map((s) => s.name).join(", ") || "—"}</td>
                <td>
                  <span className={`pill ${c.is_active ? (c.status === "open" ? "green" : c.status === "away" ? "amber" : "") : "red"}`}>
                    {t(`counters.state.${c.is_active ? c.status : "closed"}`)}
                  </span>
                </td>
                <td className="table-actions">
                  <button className="btn small" onClick={() => { setEdit({ ...c }); setError(""); }}>{t("common.edit")}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {edit && (
        <Modal title={t(edit.id ? "counters.edit" : "counters.add")} onClose={() => setEdit(null)}>
          <form className="stack" onSubmit={save}>
            <Field label={t("counters.name")}>
              <input value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} autoFocus />
            </Field>
            <Field label={t("counters.sort")}>
              <input type="number" value={edit.sort_order} onChange={(e) => setEdit({ ...edit, sort_order: Number(e.target.value) })} />
            </Field>
            <div className="stack">
              <span className="field-label">{t("counters.services")}</span>
              {services.map((s) => (
                <Toggle key={s.id} label={s.name} checked={(edit.service_ids || []).includes(s.id)} onChange={() => toggleService(s.id)} />
              ))}
            </div>
            <Toggle label={t("common.active")} checked={edit.is_active} onChange={(v) => setEdit({ ...edit, is_active: v ? 1 : 0 })} />
            <p className="field-hint">{t("counters.disable_note")}</p>
            {error && <p className="error-box">{t(error)}</p>}
            <div className="row gap">
              <button className="btn primary">{t("common.save")}</button>
              <button type="button" className="btn ghost" onClick={() => setEdit(null)}>{t("common.cancel")}</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}

// --- staff ----------------------------------------------------------------

function StaffTab({ t }) {
  const [rows, setRows] = useState(null);
  const [counters, setCounters] = useState([]);
  const [edit, setEdit] = useState(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    const [s, l] = await Promise.all([api("/api/admin/staff"), api("/api/admin/lookups")]);
    setRows(s.staff);
    setCounters(l.counters);
  }, []);
  useEffect(() => { load().catch(() => setError("error.network")); }, [load]);

  const save = async (event) => {
    event.preventDefault();
    setError("");
    try {
      if (!edit.id && (!edit.pin || edit.pin.length < 4)) {
        setError("error.invalid_pin");
        return;
      }
      if (edit.id) await put(`/api/admin/staff/${edit.id}`, edit);
      else await post("/api/admin/staff", edit);
      setEdit(null);
      await load();
    } catch (err) {
      setError(typeof err.detail === "string" ? `error.${err.detail}` : "admin.save_failed");
    }
  };

  if (!rows) return <p className="muted">{t("common.loading")}</p>;
  return (
    <div className="panel">
      <div className="panel-head">
        <h2>{t("admin.tabs.staff")}</h2>
        <button className="btn primary" onClick={() => { setEdit({ name: "", username: "", pin: "", counter_id: "", is_active: 1 }); setError(""); }}>
          + {t("staff.add")}
        </button>
      </div>
      {error && <p className="error-box">{t(error)}</p>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{t("staff.name")}</th>
              <th>{t("staff.username")}</th>
              <th>{t("staff.counter")}</th>
              <th>{t("common.status")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td>{s.username}</td>
                <td>{s.counter_name || "—"}</td>
                <td><span className={`pill ${s.is_active ? "green" : "red"}`}>{t(s.is_active ? "common.active" : "common.inactive")}</span></td>
                <td className="table-actions">
                  <button className="btn small" onClick={() => { setEdit({ ...s, pin: "" }); setError(""); }}>{t("common.edit")}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {edit && (
        <Modal title={t(edit.id ? "staff.edit" : "staff.add")} onClose={() => setEdit(null)}>
          <form className="stack" onSubmit={save}>
            <Field label={t("staff.name")}>
              <input value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} autoFocus />
            </Field>
            <Field label={t("staff.username")}>
              <input value={edit.username} onChange={(e) => setEdit({ ...edit, username: e.target.value })} autoComplete="off" />
            </Field>
            <Field label={t(edit.id ? "staff.new_pin" : "staff.pin")} hint={t("staff.pin_hint")}>
              <input
                type="password"
                inputMode="numeric"
                value={edit.pin}
                onChange={(e) => setEdit({ ...edit, pin: e.target.value.replace(/\D/g, "") })}
                maxLength={8}
                autoComplete="new-password"
              />
            </Field>
            <Field label={t("staff.counter")}>
              <select value={edit.counter_id || ""} onChange={(e) => setEdit({ ...edit, counter_id: e.target.value ? Number(e.target.value) : "" })}>
                <option value="">{t("staff.no_counter")}</option>
                {counters.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </Field>
            <Toggle label={t("common.active")} checked={edit.is_active} onChange={(v) => setEdit({ ...edit, is_active: v ? 1 : 0 })} />
            {error && <p className="error-box">{t(error)}</p>}
            <div className="row gap">
              <button className="btn primary">{t("common.save")}</button>
              <button type="button" className="btn ghost" onClick={() => setEdit(null)}>{t("common.cancel")}</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}

// --- priority rules -------------------------------------------------------

function PriorityTab({ t }) {
  const { settings, save, error } = useSettings();
  const [rows, setRows] = useState(null);
  const [edit, setEdit] = useState(null);
  const [saved, setSaved] = useState(false);
  const load = useCallback(() => api("/api/admin/priorities").then((d) => setRows(d.priorities)), []);
  useEffect(() => { load().catch(() => {}); }, [load]);

  const saveRule = async (event) => {
    event.preventDefault();
    if (edit.id) await put(`/api/admin/priorities/${edit.id}`, edit);
    else await post("/api/admin/priorities", edit);
    setEdit(null);
    await load();
  };

  if (!rows || !settings) return <p className="muted">{t("common.loading")}</p>;
  const saveMode = async (patch) => {
    const ok = await save(patch);
    setSaved(ok);
  };
  return (
    <div className="panel">
      <div className="panel-head">
        <h2>{t("admin.tabs.priority")}</h2>
        <button className="btn primary" onClick={() => setEdit({ name_en: "", name_fil: "", is_active: 1, sort_order: rows.length + 1 })}>
          + {t("priority.add")}
        </button>
      </div>
      <div className="card stack">
        <span className="field-label">{t("priority.mode")}</span>
        {["priority_first", "interleave"].map((mode) => (
          <label className="radio-row" key={mode}>
            <input
              type="radio"
              name="priority-mode"
              checked={settings.priority_mode === mode}
              onChange={() => saveMode({ priority_mode: mode })}
            />
            <span>{t(`priority.mode.${mode}`)}</span>
          </label>
        ))}
        {settings.priority_mode === "interleave" && (
          <Field label={t("priority.interleave_n")}>
            <input
              type="number"
              min="2"
              max="10"
              value={settings.priority_interleave_n}
              onChange={(e) => saveMode({ priority_interleave_n: Number(e.target.value) })}
            />
          </Field>
        )}
        <SettingsMessage error={error} saved={saved} t={t} />
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{t("priority.name_en")}</th>
              <th>{t("priority.name_fil")}</th>
              <th>{t("priority.sort")}</th>
              <th>{t("common.status")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.id}>
                <td>{p.name_en}</td>
                <td>{p.name_fil}</td>
                <td>{p.sort_order}</td>
                <td><span className={`pill ${p.is_active ? "green" : "red"}`}>{t(p.is_active ? "common.active" : "common.inactive")}</span></td>
                <td className="table-actions">
                  <button className="btn small" onClick={() => setEdit({ ...p })}>{t("common.edit")}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="field-hint">{t("priority.disable_note")}</p>
      {edit && (
        <Modal title={t(edit.id ? "priority.edit" : "priority.add")} onClose={() => setEdit(null)}>
          <form className="stack" onSubmit={saveRule}>
            <Field label={t("priority.name_en")}>
              <input value={edit.name_en} onChange={(e) => setEdit({ ...edit, name_en: e.target.value })} autoFocus />
            </Field>
            <Field label={t("priority.name_fil")}>
              <input value={edit.name_fil} onChange={(e) => setEdit({ ...edit, name_fil: e.target.value })} />
            </Field>
            <Field label={t("priority.sort")}>
              <input type="number" value={edit.sort_order} onChange={(e) => setEdit({ ...edit, sort_order: Number(e.target.value) })} />
            </Field>
            <Toggle label={t("common.active")} checked={edit.is_active} onChange={(v) => setEdit({ ...edit, is_active: v ? 1 : 0 })} />
            <div className="row gap">
              <button className="btn primary">{t("common.save")}</button>
              <button type="button" className="btn ghost" onClick={() => setEdit(null)}>{t("common.cancel")}</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}

// --- display --------------------------------------------------------------

function DisplayTab({ t }) {
  const { settings, media, save, error } = useSettings();
  const [form, setForm] = useState(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => { if (settings && !form) setForm({ ...settings }); }, [settings, form]);
  if (!form) return <p className="muted">{t("common.loading")}</p>;
  const set = (key, value) => { setForm({ ...form, [key]: value }); setSaved(false); };
  const submit = async (event) => {
    event.preventDefault();
    const ok = await save({
      display_layout: Number(form.display_layout),
      screen_language: form.screen_language,
      voice_enabled: form.voice_enabled,
      voice_lang: form.voice_lang,
      media_volume: Number(form.media_volume),
      image_duration: Number(form.image_duration),
      banner_text_en: form.banner_text_en,
      banner_text_fil: form.banner_text_fil,
      display_show_next: form.display_show_next,
      display_show_estimate: form.display_show_estimate,
      media_schedule: form.media_schedule,
    });
    setSaved(ok);
  };
  const schedule = form.media_schedule || { enabled: false, from: "08:00", to: "17:00" };
  return (
    <form className="panel" onSubmit={submit}>
      <div className="panel-head">
        <h2>{t("admin.tabs.display")}</h2>
        <button className="btn primary">{t("common.save")}</button>
      </div>
      <SettingsMessage error={error} saved={saved} t={t} />
      <div className="card stack">
        <div className="form-grid">
          <Field label={t("display.language")} hint={t("display.language_hint")}>
            <select value={form.screen_language} onChange={(e) => set("screen_language", e.target.value)}>
              <option value="en">English</option>
              <option value="fil">Filipino</option>
              <option value="both">{t("display.both")}</option>
            </select>
          </Field>
          <Field label={t("display.layout")} hint={t("display.layout_hint")}>
            <input type="range" min="45" max="80" value={form.display_layout} onChange={(e) => set("display_layout", e.target.value)} />
            <span className="muted small">{form.display_layout}% {t("display.queue_width")}</span>
          </Field>
          <Field label={t("display.image_duration")}>
            <input type="number" min="2" max="120" value={form.image_duration} onChange={(e) => set("image_duration", e.target.value)} />
          </Field>
          <Field label={t("display.volume")}>
            <input type="range" min="0" max="1" step="0.05" value={form.media_volume} onChange={(e) => set("media_volume", e.target.value)} />
            <span className="muted small">{Math.round(Number(form.media_volume) * 100)}%</span>
          </Field>
        </div>
        <div className="form-grid">
          <Field label={t("display.banner_en")}>
            <input value={form.banner_text_en} onChange={(e) => set("banner_text_en", e.target.value)} />
          </Field>
          <Field label={t("display.banner_fil")}>
            <input value={form.banner_text_fil} onChange={(e) => set("banner_text_fil", e.target.value)} />
          </Field>
        </div>
        <div className="row gap" style={{ flexWrap: "wrap" }}>
          <Toggle label={t("display.show_next")} checked={form.display_show_next} onChange={(v) => set("display_show_next", v)} />
          <Toggle label={t("display.show_estimate")} checked={form.display_show_estimate} onChange={(v) => set("display_show_estimate", v)} />
        </div>
      </div>
      <div className="card stack">
        <h2>{t("display.voice")}</h2>
        <Toggle label={t("display.voice_enabled")} checked={form.voice_enabled} onChange={(v) => set("voice_enabled", v)} />
        <Field label={t("display.voice_lang")} hint={t("display.voice_hint")}>
          <select value={form.voice_lang} onChange={(e) => set("voice_lang", e.target.value)} disabled={!form.voice_enabled}>
            <option value="both">{t("display.both")}</option>
            <option value="en">English</option>
            <option value="fil">Filipino</option>
          </select>
        </Field>
      </div>
      <div className="card stack">
        <h2>{t("display.schedule")}</h2>
        <Toggle
          label={t("display.schedule_enabled")}
          checked={schedule.enabled}
          onChange={(v) => set("media_schedule", { ...schedule, enabled: v })}
        />
        <div className="form-grid">
          <Field label={t("display.from")}>
            <input type="time" value={schedule.from || ""} onChange={(e) => set("media_schedule", { ...schedule, from: e.target.value })} />
          </Field>
          <Field label={t("display.to")}>
            <input type="time" value={schedule.to || ""} onChange={(e) => set("media_schedule", { ...schedule, to: e.target.value })} />
          </Field>
        </div>
        <p className="field-hint">{t("display.schedule_hint")}</p>
      </div>
      <div className="card stack">
        <div className="row between">
          <h2>{t("display.media")}</h2>
          <span className="muted small">{media.length} {t("display.files")}</span>
        </div>
        <p className="field-hint">{t("display.media_hint")}</p>
        {media.length === 0 ? (
          <p className="muted small">{t("display.no_media")}</p>
        ) : (
          <div className="media-grid">
            {media.map((f) => (
              <div className="media-item" key={f.name}>
                {f.kind === "image" ? <img src={f.url} alt="" /> : <div className="video-chip">▶</div>}
                <span title={f.name}>{f.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="row gap">
        <button className="btn primary">{t("common.save")}</button>
      </div>
    </form>
  );
}

// --- kiosk ----------------------------------------------------------------

function KioskTab({ t }) {
  const { settings, save, error } = useSettings();
  const [form, setForm] = useState(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => { if (settings && !form) setForm({ ...settings }); }, [settings, form]);
  if (!form) return <p className="muted">{t("common.loading")}</p>;
  const set = (key, value) => { setForm({ ...form, [key]: value }); setSaved(false); };
  const submit = async (event) => {
    event.preventDefault();
    const ok = await save({
      ticket_paper_size: form.ticket_paper_size,
      print_enabled: form.print_enabled,
      kiosk_enabled: form.kiosk_enabled,
      staff_issue_enabled: form.staff_issue_enabled,
      qr_phone_enabled: form.qr_phone_enabled,
      ticket_show_qr: form.ticket_show_qr,
      ticket_show_wait: form.ticket_show_wait,
      ticket_show_logo: form.ticket_show_logo,
      duplicate_ticket_delay: Number(form.duplicate_ticket_delay),
      printer_note: form.printer_note,
    });
    setSaved(ok);
  };
  const printTest = () => {
    // The admin page is hidden in print styles, so the test ticket lives on its own.
    const style = document.createElement("style");
    style.textContent = `@page { size: ${form.ticket_paper_size}mm auto; margin: 4mm; }`;
    const sheet = document.createElement("div");
    sheet.className = `ticket-print${form.ticket_paper_size === "80" ? " paper-80" : ""}`;
    const inst = document.createElement("div");
    inst.className = "t-inst";
    inst.textContent = form.institution_name || "Queue system";
    const label = document.createElement("p");
    label.className = "t-small";
    label.textContent = t("kiosk.test_ticket");
    const number = document.createElement("div");
    number.className = "t-number";
    number.textContent = "A-001";
    const when = document.createElement("p");
    when.className = "t-small";
    when.textContent = new Date().toLocaleString();
    sheet.append(inst, label, number, when);
    document.head.appendChild(style);
    document.body.appendChild(sheet);
    window.print();
    setTimeout(() => { sheet.remove(); style.remove(); }, 1500);
  };
  return (
    <form className="panel" onSubmit={submit}>
      <div className="panel-head">
        <h2>{t("admin.tabs.kiosk")}</h2>
        <button className="btn primary">{t("common.save")}</button>
      </div>
      <SettingsMessage error={error} saved={saved} t={t} />
      <div className="card stack">
        <h2>{t("kiosk.intake")}</h2>
        <Toggle label={t("kiosk.kiosk_enabled")} checked={form.kiosk_enabled} onChange={(v) => set("kiosk_enabled", v)} />
        <Toggle label={t("kiosk.staff_issue")} checked={form.staff_issue_enabled} onChange={(v) => set("staff_issue_enabled", v)} />
        <Toggle label={t("kiosk.qr_phone")} checked={form.qr_phone_enabled} onChange={(v) => set("qr_phone_enabled", v)} />
        <Field label={t("kiosk.duplicate_delay")} hint={t("kiosk.duplicate_hint")}>
          <input type="number" min="0" max="600" value={form.duplicate_ticket_delay} onChange={(e) => set("duplicate_ticket_delay", e.target.value)} />
        </Field>
      </div>
      <div className="card stack">
        <h2>{t("kiosk.ticket")}</h2>
        <div className="form-grid">
          <Field label={t("kiosk.paper")} hint={t("kiosk.paper_hint")}>
            <select value={form.ticket_paper_size} onChange={(e) => set("ticket_paper_size", e.target.value)}>
              <option value="58">58 mm</option>
              <option value="80">80 mm</option>
            </select>
          </Field>
        </div>
        <Toggle label={t("kiosk.print_enabled")} checked={form.print_enabled} onChange={(v) => set("print_enabled", v)} />
        <Toggle label={t("kiosk.show_qr")} checked={form.ticket_show_qr} onChange={(v) => set("ticket_show_qr", v)} />
        <Toggle label={t("kiosk.show_wait")} checked={form.ticket_show_wait} onChange={(v) => set("ticket_show_wait", v)} />
        <Toggle label={t("kiosk.show_logo")} checked={form.ticket_show_logo} onChange={(v) => set("ticket_show_logo", v)} />
      </div>
      <div className="card stack">
        <h2>{t("dashboard.printer")}</h2>
        <div className="row between">
          <span className={`pill ${form.printer_status === "works" ? "green" : "amber"}`}>
            {t(`kiosk.printer.${form.printer_status || "unknown"}`)}
          </span>
          <button type="button" className="btn small" onClick={printTest}>{t("kiosk.test_print")}</button>
        </div>
        {form.printer_note && <p className="muted small">{t("kiosk.printer_note")}: {form.printer_note}</p>}
        <Field label={t("kiosk.printer_note_label")}>
          <input value={form.printer_note || ""} onChange={(e) => set("printer_note", e.target.value)} />
        </Field>
        <p className="field-hint">{t("kiosk.print_hint")}</p>
      </div>
      <div className="row gap"><button className="btn primary">{t("common.save")}</button></div>
    </form>
  );
}

// --- system ---------------------------------------------------------------

function SystemTab({ t, boot, onSetupChange }) {
  const { lang } = useT();
  const { settings, media, save, error } = useSettings();
  const [form, setForm] = useState(null);
  const [saved, setSaved] = useState(false);
  const [system, setSystem] = useState(null);
  const [backups, setBackups] = useState([]);
  const [confirmRestore, setConfirmRestore] = useState(null);
  const [check, setCheck] = useState(null);
  const [message, setMessage] = useState("");

  const loadSystem = useCallback(async () => {
    const [s, b] = await Promise.all([api("/api/admin/system"), api("/api/admin/backups")]);
    setSystem(s);
    setBackups(b.backups);
  }, []);
  const runCheck = useCallback(() => api("/api/admin/system/check").then(setCheck).catch(() => {}), []);
  useEffect(() => {
    loadSystem().catch(() => {});
    runCheck();
  }, [loadSystem, runCheck]);
  useEffect(() => { if (settings && !form) setForm({ ...settings }); }, [settings, form]);
  if (!form) return <p className="muted">{t("common.loading")}</p>;

  const set = (key, value) => { setForm({ ...form, [key]: value }); setSaved(false); };
  const submit = async (event) => {
    event.preventDefault();
    const ok = await save({
      institution_name: form.institution_name,
      institution_type: form.institution_type,
      institution_address: form.institution_address,
      institution_contact: form.institution_contact,
      logo_file: form.logo_file,
      language_default: form.language_default,
      timezone: form.timezone,
      reset_time: form.reset_time,
      tracking_enabled: form.tracking_enabled,
      tracking_base_url: form.tracking_base_url,
      backup_keep: Number(form.backup_keep),
    });
    setSaved(ok);
    if (ok && onSetupChange) onSetupChange();
  };
  const doBackup = async () => {
    await post("/api/admin/backups", {});
    await loadSystem();
    setMessage(t("system.backup_created"));
  };
  const doRestore = async () => {
    await post("/api/admin/backups/restore", { name: confirmRestore.name });
    setConfirmRestore(null);
    setMessage(t("system.restored"));
    await loadSystem();
    if (onSetupChange) onSetupChange();
  };
  const images = media.filter((f) => f.kind === "image");

  return (
    <div className="panel">
      <form className="card stack" onSubmit={submit}>
        <div className="panel-head">
          <h2>{t("system.institution")}</h2>
          <button className="btn primary">{t("common.save")}</button>
        </div>
        <SettingsMessage error={error} saved={saved} t={t} />
        <div className="form-grid">
          <Field label={t("system.name")}>
            <input value={form.institution_name} onChange={(e) => set("institution_name", e.target.value)} />
          </Field>
          <Field label={t("system.type")}>
            <select value={form.institution_type} onChange={(e) => set("institution_type", e.target.value)}>
              {(system?.types || []).map((type) => (
                <option key={type.key} value={type.key}>{lang === "fil" ? type.label_fil : type.label_en}</option>
              ))}
            </select>
          </Field>
          <Field label={t("system.address")}>
            <input value={form.institution_address} onChange={(e) => set("institution_address", e.target.value)} />
          </Field>
          <Field label={t("system.contact")}>
            <input value={form.institution_contact} onChange={(e) => set("institution_contact", e.target.value)} />
          </Field>
          <Field label={t("system.logo")} hint={t("system.logo_hint")}>
            <select value={form.logo_file || ""} onChange={(e) => set("logo_file", e.target.value)}>
              <option value="">{t("system.no_logo")}</option>
              {images.map((f) => <option key={f.name} value={f.name}>{f.name}</option>)}
            </select>
          </Field>
        </div>
        <div className="form-grid">
          <Field label={t("system.reset_time")} hint={t("system.reset_hint")}>
            <input type="time" value={form.reset_time} onChange={(e) => set("reset_time", e.target.value)} />
          </Field>
          <Field label={t("system.timezone")} hint={t("system.timezone_hint")}>
            <input value={form.timezone} onChange={(e) => set("timezone", e.target.value)} />
          </Field>
          <Field label={t("system.default_language")}>
            <select value={form.language_default} onChange={(e) => set("language_default", e.target.value)}>
              <option value="en">English</option>
              <option value="fil">Filipino</option>
            </select>
          </Field>
          <Field label={t("system.backup_keep")}>
            <input type="number" min="1" max="365" value={form.backup_keep} onChange={(e) => set("backup_keep", e.target.value)} />
          </Field>
        </div>
        <div className="divider" />
        <h3>{t("system.tracking")}</h3>
        <Toggle label={t("system.tracking_enabled")} checked={form.tracking_enabled} onChange={(v) => set("tracking_enabled", v)} />
        <Field label={t("system.tracking_base")} hint={t("system.tracking_hint")}>
          <input value={form.tracking_base_url || ""} onChange={(e) => set("tracking_base_url", e.target.value)} placeholder={system?.server_origin || ""} />
        </Field>
        <div className="row gap"><button className="btn primary">{t("common.save")}</button></div>
      </form>

      <div className="card stack">
        <h2>{t("system.network")}</h2>
        <div className="network-box">
          <div>
            <p className="server-url">{system?.server_origin || "—"}</p>
            <p className="field-hint">{t("system.network_hint")},{system?.hostname ? ` ${t("system.host")}: ${system.hostname}` : ""}</p>
          </div>
          {system?.server_origin && (
            <img className="qr" alt={t("system.network_qr")} src={`/api/qr?data=${encodeURIComponent(system.server_origin)}&size=160`} />
          )}
        </div>
      </div>

      <div className="card stack">
        <div className="panel-head">
          <h2>{t("system.check")}</h2>
          <button className="btn small" onClick={runCheck}>{t("system.run_check")}</button>
        </div>
        {check ? (
          <div className="table-wrap">
            <table>
              <tbody>
                {check.checks.map((c) => (
                  <tr key={c.key}>
                    <td><span className={`pill ${c.ok ? "green" : "red"}`}>{t(c.ok ? "system.ok" : "system.fail")}</span></td>
                    <td>{t(`system.check.${c.key}`)}</td>
                    <td className="muted small">{c.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="muted">{t("common.loading")}</p>}
      </div>

      <div className="card stack">
        <div className="panel-head">
          <h2>{t("system.backups")}</h2>
          <button className="btn small" onClick={doBackup}>{t("system.create_backup")}</button>
        </div>
        {message && <p className="notice-box">{message}</p>}
        <p className="field-hint">{t("system.backup_hint")}</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t("system.backup_file")}</th>
                <th>{t("system.backup_when")}</th>
                <th>{t("system.backup_size")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {backups.length === 0 && (
                <tr><td colSpan={4} className="muted">{t("system.no_backups")}</td></tr>
              )}
              {backups.map((b) => (
                <tr key={b.name}>
                  <td className="small">{b.name}</td>
                  <td>{formatTime(b.created_at)}</td>
                  <td>{(b.size / 1024).toFixed(0)} KB</td>
                  <td className="table-actions">
                    <button className="btn small danger" onClick={() => setConfirmRestore(b)}>{t("system.restore")}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {confirmRestore && (
        <Modal title={t("system.restore")} onClose={() => setConfirmRestore(null)}>
          <p className="warn-note">{t("system.restore_warn", { name: confirmRestore.name })}</p>
          <div className="row gap">
            <button className="btn danger" onClick={doRestore}>{t("system.restore_confirm")}</button>
            <button className="btn ghost" onClick={() => setConfirmRestore(null)}>{t("common.cancel")}</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// --- shell ----------------------------------------------------------------

export default function Admin({ boot, onSetupChange }) {
  const { t } = useT();
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("dashboard");
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/auth/me")
      .then((data) => setMe(data.role === "admin" ? data : null))
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

  const tabs = ["dashboard", "services", "counters", "staff", "priority", "display", "kiosk", "system"];
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
          <a className="btn small" href="/display" target="_blank" rel="noreferrer">{t("admin.open_display")}</a>
          <button className="btn small" onClick={logout}>
            {t("common.logout")}
          </button>
        </div>
      </header>
      <nav className="tabs" aria-label={t("admin.title")}>
        {tabs.map((name) => (
          <button key={name} type="button" className={`tab ${tab === name ? "active" : ""}`} onClick={() => setTab(name)}>
            {t(`admin.tabs.${name}`)}
          </button>
        ))}
      </nav>
      {tab === "dashboard" && <Dashboard t={t} />}
      {tab === "services" && <ServicesTab t={t} />}
      {tab === "counters" && <CountersTab t={t} />}
      {tab === "staff" && <StaffTab t={t} />}
      {tab === "priority" && <PriorityTab t={t} />}
      {tab === "display" && <DisplayTab t={t} />}
      {tab === "kiosk" && <KioskTab t={t} />}
      {tab === "system" && <SystemTab t={t} boot={boot} onSetupChange={onSetupChange} />}
    </div>
  );
}
