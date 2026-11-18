import { useEffect, useMemo, useState } from "react";
import { api, post } from "../api.js";
import { LanguageSwitch, useT } from "../i18n.jsx";

const STEPS = ["institution", "services", "counters", "priority", "intake", "display", "admin", "review"];
const DEFAULT_PRIORITIES = [
  { name_en: "Senior Citizen", name_fil: "Senior Citizen", is_active: true },
  { name_en: "PWD", name_fil: "PWD", is_active: true },
  { name_en: "Pregnant", name_fil: "Buntis", is_active: true },
];

function emptyService() {
  return {
    name: "",
    prefix: "",
    is_express: false,
    open_from: "",
    open_to: "",
    cut_off_time: "",
    ask_account_number: false,
    queue_alert_threshold: 0,
  };
}

function Field({ label, hint, children, className = "" }) {
  return (
    <label className={`field ${className}`}>
      {label && <span className="field-label">{label}</span>}
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

function Toggle({ checked, onChange, label, hint }) {
  return (
    <label className="toggle-row">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>
        <strong>{label}</strong>
        {hint && <small>{hint}</small>}
      </span>
    </label>
  );
}

export default function Setup({ initial, onDone }) {
  const { t, lang } = useT();
  const [step, setStep] = useState(0);
  const [presets, setPresets] = useState([]);
  const [media, setMedia] = useState({ images: [], folder: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);
  const [data, setData] = useState({
    institution: {
      name: "",
      type: "generic",
      address: "",
      contact: "",
      logo_file: "",
      tracking_base_url: "",
      timezone: "Asia/Manila",
    },
    services: [],
    counters: [],
    priorities: { types: DEFAULT_PRIORITIES, mode: "priority_first", interleave_n: 3 },
    intake: {
      kiosk_enabled: true,
      staff_issue_enabled: false,
      qr_phone_enabled: false,
      print_enabled: true,
      paper_size: "58",
      show_estimate: true,
      show_qr: true,
      duplicate_ticket_delay: 15,
    },
    display: {
      language: "en",
      voice_enabled: true,
      voice_lang: "both",
      layout: 60,
      image_duration: 10,
      banner_en: "",
      banner_fil: "",
    },
    admin: { username: "admin", password: "", confirm: "" },
    demo_ticket: false,
  });

  useEffect(() => {
    api("/api/setup/state").then((state) => setPresets(state.presets)).catch(() => {});
    api("/api/setup/media").then(setMedia).catch(() => {});
  }, []);

  const presetLabel = (key) => {
    const p = presets.find((x) => x.key === key);
    if (!p) return key;
    return lang === "fil" ? p.label_fil : p.label_en;
  };

  const selectType = (key) => {
    const preset = presets.find((p) => p.key === key);
    setData((d) => ({
      ...d,
      institution: { ...d.institution, type: key },
      services: preset ? preset.services.map((s) => ({ ...s })) : [],
      counters: preset ? preset.counters.map((c) => ({ ...c, services: [...c.services] })) : [],
      priorities: { ...d.priorities, mode: preset?.priority_mode || d.priorities.mode },
    }));
  };

  const patch = (section, key, value) =>
    setData((d) => ({ ...d, [section]: { ...d[section], [key]: value } }));

  const patchService = (index, key, value) =>
    setData((d) => {
      const services = d.services.map((s, i) => (i === index ? { ...s, [key]: value } : s));
      return { ...d, services };
    });

  const patchCounter = (index, key, value) =>
    setData((d) => {
      const counters = d.counters.map((c, i) => (i === index ? { ...c, [key]: value } : c));
      return { ...d, counters };
    });

  const allPrefixes = useMemo(() => data.services.map((s) => s.prefix?.toUpperCase()).filter(Boolean), [data.services]);

  const validationError = () => {
    if (step === 0 && !data.institution.name.trim()) return t("error.institution_name_required");
    if (step === 1) {
      if (!data.services.length) return t("error.services_required");
      if (data.services.some((s) => !s.name.trim() || !s.prefix.trim()))
        return t("error.service_name_and_prefix_required");
    }
    if (step === 2) {
      if (!data.counters.length) return t("error.counters_required");
      if (data.counters.some((c) => !c.name.trim())) return t("error.counter_name_required");
      if (data.counters.some((c) => !c.services.length)) return t("setup.counters.no_services");
    }
    if (step === 6) {
      if (!data.admin.username.trim() || data.admin.password.length < 6)
        return t("error.admin_credentials_required");
      if (data.admin.password !== data.admin.confirm) return t("setup.admin.mismatch");
    }
    return "";
  };

  const next = () => {
    const err = validationError();
    if (err) {
      setError(err);
      return;
    }
    setError("");
    setStep((s) => Math.min(STEPS.length - 1, s + 1));
    window.scrollTo({ top: 0 });
  };

  const back = () => {
    setError("");
    setStep((s) => Math.max(0, s - 1));
    window.scrollTo({ top: 0 });
  };

  const finish = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await post("/api/setup/complete", data);
      setDone(result);
      if (onDone) onDone();
    } catch (err) {
      setError(t(`error.${err.message}`) === `error.${err.message}` ? t("setup.error") : t(`error.${err.message}`));
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <div className="centered-screen">
        <div className="card setup-done">
          <div className="done-badge">✓</div>
          <h1>{t("setup.done.title")}</h1>
          <p className="muted">{t("setup.done.hint")}</p>
          {done.demo_ticket && (
            <p className="demo-ticket">
              {t("setup.done.demo", { number: done.demo_ticket.number })}
            </p>
          )}
          <div className="link-grid">
            <a className="btn primary" href="/kiosk" target="_blank" rel="noreferrer">
              {t("setup.done.kiosk")}
            </a>
            <a className="btn" href="/counter" target="_blank" rel="noreferrer">
              {t("setup.done.counter")}
            </a>
            <a className="btn" href="/display" target="_blank" rel="noreferrer">
              {t("setup.done.display")}
            </a>
            <a className="btn" href="/admin">
              {t("setup.done.admin")}
            </a>
          </div>
        </div>
      </div>
    );
  }

  const current = STEPS[step];

  return (
    <div className="setup">
      <header className="setup-head">
        <div>
          <p className="eyebrow">{t("setup.title")}</p>
          <h1>{t(`setup.steps.${current}`)}</h1>
          <p className="muted">{t("setup.step_of", { current: step + 1, total: STEPS.length })}</p>
        </div>
        <LanguageSwitch />
      </header>

      <ol className="step-track" aria-hidden="true">
        {STEPS.map((name, i) => (
          <li key={name} className={i === step ? "current" : i < step ? "done" : ""}>
            <span>{i + 1}</span>
            <em>{t(`setup.steps.${name}`)}</em>
          </li>
        ))}
      </ol>

      <main className="card setup-card">
        {current === "institution" && (
          <div className="stack">
            <Field label={t("setup.institution.name")}>
              <input
                value={data.institution.name}
                onChange={(e) => patch("institution", "name", e.target.value)}
                placeholder={t("setup.institution.name")}
                autoFocus
              />
            </Field>
            <div>
              <span className="field-label">{t("setup.institution.type")}</span>
              <p className="field-hint">{t("setup.institution.type_hint")}</p>
              <div className="preset-grid">
                {presets.map((p) => (
                  <button
                    type="button"
                    key={p.key}
                    className={`preset-card ${data.institution.type === p.key ? "selected" : ""}`}
                    onClick={() => selectType(p.key)}
                  >
                    {lang === "fil" ? p.label_fil : p.label_en}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid two">
              <Field label={t("setup.institution.address")}>
                <input
                  value={data.institution.address}
                  onChange={(e) => patch("institution", "address", e.target.value)}
                />
              </Field>
              <Field label={t("setup.institution.contact")}>
                <input
                  value={data.institution.contact}
                  onChange={(e) => patch("institution", "contact", e.target.value)}
                />
              </Field>
              <Field label={t("setup.institution.logo")} hint={t("setup.institution.logo_hint")}>
                <input
                  value={data.institution.logo_file}
                  onChange={(e) => patch("institution", "logo_file", e.target.value)}
                  list="media-images"
                  placeholder="logo.png"
                />
                <datalist id="media-images">
                  {media.images.map((name) => (
                    <option key={name} value={name} />
                  ))}
                </datalist>
              </Field>
              <Field label={t("setup.institution.timezone")}>
                <select
                  value={data.institution.timezone}
                  onChange={(e) => patch("institution", "timezone", e.target.value)}
                >
                  <option value="Asia/Manila">Asia/Manila</option>
                  <option value="Asia/Singapore">Asia/Singapore</option>
                  <option value="UTC">UTC</option>
                </select>
              </Field>
            </div>
            <Field label={t("setup.institution.tracking")} hint={t("setup.institution.tracking_hint")}>
              <input
                value={data.institution.tracking_base_url}
                onChange={(e) => patch("institution", "tracking_base_url", e.target.value)}
                placeholder={window.location.origin}
              />
            </Field>
          </div>
        )}

        {current === "services" && (
          <div className="stack">
            <p className="muted">{t("setup.services.hint")}</p>
            <div className="service-list">
              {data.services.map((svc, i) => (
                <div className="service-row" key={i}>
                  <div className="grid three">
                    <Field label={t("setup.services.name")}>
                      <input value={svc.name} onChange={(e) => patchService(i, "name", e.target.value)} />
                    </Field>
                    <Field label={t("setup.services.prefix")}>
                      <input
                        value={svc.prefix}
                        maxLength={3}
                        onChange={(e) => patchService(i, "prefix", e.target.value.toUpperCase())}
                      />
                    </Field>
                    <Field label={t("setup.services.cutoff")} hint={t("setup.services.cutoff_hint")}>
                      <input
                        type="time"
                        value={svc.cut_off_time || ""}
                        onChange={(e) => patchService(i, "cut_off_time", e.target.value)}
                      />
                    </Field>
                    <Field label={t("setup.services.from")}>
                      <input
                        type="time"
                        value={svc.open_from || ""}
                        onChange={(e) => patchService(i, "open_from", e.target.value)}
                      />
                    </Field>
                    <Field label={t("setup.services.to")}>
                      <input
                        type="time"
                        value={svc.open_to || ""}
                        onChange={(e) => patchService(i, "open_to", e.target.value)}
                      />
                    </Field>
                    <Field label={t("setup.services.alert")} hint={t("setup.services.alert_hint")}>
                      <input
                        type="number"
                        min="0"
                        value={svc.queue_alert_threshold}
                        onChange={(e) => patchService(i, "queue_alert_threshold", Number(e.target.value))}
                      />
                    </Field>
                  </div>
                  <div className="row wrap between">
                    <div className="row wrap">
                      <Toggle
                        checked={!!svc.is_express}
                        onChange={(v) => patchService(i, "is_express", v)}
                        label={t("setup.services.express")}
                      />
                      <Toggle
                        checked={!!svc.ask_account_number}
                        onChange={(v) => patchService(i, "ask_account_number", v)}
                        label={t("setup.services.ask_account")}
                      />
                    </div>
                    <button
                      type="button"
                      className="btn ghost danger"
                      onClick={() =>
                        setData((d) => ({ ...d, services: d.services.filter((_, idx) => idx !== i) }))
                      }
                    >
                      {t("common.remove")}
                    </button>
                  </div>
                </div>
              ))}
            </div>
            {!data.services.length && <p className="empty-note">{t("setup.services.empty")}</p>}
            <button
              type="button"
              className="btn"
              onClick={() => setData((d) => ({ ...d, services: [...d.services, emptyService()] }))}
            >
              + {t("setup.services.add")}
            </button>
          </div>
        )}

        {current === "counters" && (
          <div className="stack">
            <p className="muted">{t("setup.counters.hint")}</p>
            {data.counters.map((ctr, i) => (
              <div className="service-row" key={i}>
                <div className="row wrap between">
                  <Field label={t("setup.counters.name")} className="grow">
                    <input value={ctr.name} onChange={(e) => patchCounter(i, "name", e.target.value)} />
                  </Field>
                  <button
                    type="button"
                    className="btn ghost danger"
                    onClick={() => setData((d) => ({ ...d, counters: d.counters.filter((_, idx) => idx !== i) }))}
                  >
                    {t("common.remove")}
                  </button>
                </div>
                <span className="field-label">{t("setup.counters.services")}</span>
                <div className="chip-row">
                  {data.services.map((svc) => {
                    const prefix = svc.prefix.toUpperCase();
                    const on = ctr.services.includes(prefix);
                    return (
                      <button
                        type="button"
                        key={prefix + svc.name}
                        className={`chip ${on ? "on" : ""}`}
                        onClick={() =>
                          patchCounter(
                            i,
                            "services",
                            on ? ctr.services.filter((p) => p !== prefix) : [...ctr.services, prefix]
                          )
                        }
                      >
                        {svc.name} ({prefix})
                      </button>
                    );
                  })}
                </div>
                {!ctr.services.length && <p className="warn-note">{t("setup.counters.no_services")}</p>}
              </div>
            ))}
            {!data.counters.length && <p className="empty-note">{t("setup.counters.empty")}</p>}
            <button
              type="button"
              className="btn"
              onClick={() =>
                setData((d) => ({
                  ...d,
                  counters: [...d.counters, { name: `Window ${d.counters.length + 1}`, services: [...allPrefixes] }],
                }))
              }
            >
              + {t("setup.counters.add")}
            </button>
          </div>
        )}

        {current === "priority" && (
          <div className="stack">
            <p className="muted">{t("setup.priority.hint")}</p>
            {data.priorities.types.map((pt, i) => (
              <div className="row wrap gap" key={i}>
                <Toggle
                  checked={pt.is_active !== false}
                  onChange={(v) =>
                    setData((d) => ({
                      ...d,
                      priorities: {
                        ...d.priorities,
                        types: d.priorities.types.map((x, idx) => (idx === i ? { ...x, is_active: v } : x)),
                      },
                    }))
                  }
                  label={pt.name_en}
                />
                <input
                  value={pt.name_en}
                  onChange={(e) =>
                    setData((d) => ({
                      ...d,
                      priorities: {
                        ...d.priorities,
                        types: d.priorities.types.map((x, idx) =>
                          idx === i ? { ...x, name_en: e.target.value } : x
                        ),
                      },
                    }))
                  }
                  placeholder={t("setup.priority.name_en")}
                />
                <input
                  value={pt.name_fil}
                  onChange={(e) =>
                    setData((d) => ({
                      ...d,
                      priorities: {
                        ...d.priorities,
                        types: d.priorities.types.map((x, idx) =>
                          idx === i ? { ...x, name_fil: e.target.value } : x
                        ),
                      },
                    }))
                  }
                  placeholder={t("setup.priority.name_fil")}
                />
                <button
                  type="button"
                  className="btn ghost danger"
                  onClick={() =>
                    setData((d) => ({
                      ...d,
                      priorities: {
                        ...d.priorities,
                        types: d.priorities.types.filter((_, idx) => idx !== i),
                      },
                    }))
                  }
                >
                  {t("common.remove")}
                </button>
              </div>
            ))}
            <button
              type="button"
              className="btn"
              onClick={() =>
                setData((d) => ({
                  ...d,
                  priorities: {
                    ...d.priorities,
                    types: [...d.priorities.types, { name_en: "", name_fil: "", is_active: true }],
                  },
                }))
              }
            >
              + {t("common.add")}
            </button>
            <div className="divider" />
            {data.priorities.types.some((pt) => pt.is_active !== false) ? (
              <div className="stack">
                <span className="field-label">{t("setup.priority.mode")}</span>
                <label className="radio-row">
                  <input
                    type="radio"
                    name="priority-mode"
                    checked={data.priorities.mode === "priority_first"}
                    onChange={() => patch("priorities", "mode", "priority_first")}
                  />
                  <span>{t("setup.priority.priority_first")}</span>
                </label>
                <label className="radio-row">
                  <input
                    type="radio"
                    name="priority-mode"
                    checked={data.priorities.mode === "interleave"}
                    onChange={() => patch("priorities", "mode", "interleave")}
                  />
                  <span>{t("setup.priority.interleave")}</span>
                </label>
                {data.priorities.mode === "interleave" && (
                  <Field label={t("setup.priority.n")}>
                    <input
                      type="number"
                      min="2"
                      max="10"
                      value={data.priorities.interleave_n}
                      onChange={(e) => patch("priorities", "interleave_n", Number(e.target.value))}
                    />
                  </Field>
                )}
              </div>
            ) : (
              <p className="muted">{t("setup.priority.off")}</p>
            )}
          </div>
        )}

        {current === "intake" && (
          <div className="stack">
            <p className="muted">{t("setup.intake.hint")}</p>
            <Toggle
              checked={data.intake.kiosk_enabled}
              onChange={(v) => patch("intake", "kiosk_enabled", v)}
              label={t("setup.intake.kiosk")}
            />
            <Toggle
              checked={data.intake.staff_issue_enabled}
              onChange={(v) => patch("intake", "staff_issue_enabled", v)}
              label={t("setup.intake.staff")}
            />
            <Toggle
              checked={data.intake.qr_phone_enabled}
              onChange={(v) => patch("intake", "qr_phone_enabled", v)}
              label={t("setup.intake.qr")}
            />
            <Toggle
              checked={data.intake.print_enabled}
              onChange={(v) => patch("intake", "print_enabled", v)}
              label={t("setup.intake.print")}
            />
            {data.intake.print_enabled && (
              <Field label={t("setup.intake.paper")}>
                <select
                  value={data.intake.paper_size}
                  onChange={(e) => patch("intake", "paper_size", e.target.value)}
                >
                  <option value="58">58 mm</option>
                  <option value="80">80 mm</option>
                </select>
              </Field>
            )}
            <Toggle
              checked={data.intake.show_estimate}
              onChange={(v) => patch("intake", "show_estimate", v)}
              label={t("setup.intake.show_estimate")}
            />
            <Toggle
              checked={data.intake.show_qr}
              onChange={(v) => patch("intake", "show_qr", v)}
              label={t("setup.intake.show_qr")}
            />
            <Field label={t("setup.intake.duplicate")} hint={t("setup.intake.duplicate_hint")}>
              <input
                type="number"
                min="0"
                value={data.intake.duplicate_ticket_delay}
                onChange={(e) => patch("intake", "duplicate_ticket_delay", Number(e.target.value))}
              />
            </Field>
          </div>
        )}

        {current === "display" && (
          <div className="stack">
            <Field label={t("setup.display.language")}>
              <select
                value={data.display.language}
                onChange={(e) => patch("display", "language", e.target.value)}
              >
                <option value="en">{t("setup.display.en")}</option>
                <option value="fil">{t("setup.display.fil")}</option>
                <option value="both">{t("setup.display.both")}</option>
              </select>
            </Field>
            <Toggle
              checked={data.display.voice_enabled}
              onChange={(v) => patch("display", "voice_enabled", v)}
              label={t("setup.display.voice")}
            />
            <Field label={t("setup.display.voice_lang")}>
              <select value={data.display.voice_lang} onChange={(e) => patch("display", "voice_lang", e.target.value)}>
                <option value="en">{t("setup.display.en")}</option>
                <option value="fil">{t("setup.display.fil")}</option>
                <option value="both">{t("setup.display.both")}</option>
              </select>
            </Field>
            <Field label={t("setup.display.layout")} hint={t("setup.display.layout_hint")}>
              <input
                type="range"
                min="40"
                max="85"
                value={data.display.layout}
                onChange={(e) => patch("display", "layout", Number(e.target.value))}
              />
              <span className="range-value">{data.display.layout}%</span>
            </Field>
            <Field label={t("setup.display.image_duration")}>
              <input
                type="number"
                min="3"
                value={data.display.image_duration}
                onChange={(e) => patch("display", "image_duration", Number(e.target.value))}
              />
            </Field>
            <div className="grid two">
              <Field label={t("setup.display.banner_en")}>
                <textarea
                  rows="2"
                  value={data.display.banner_en}
                  onChange={(e) => patch("display", "banner_en", e.target.value)}
                />
              </Field>
              <Field label={t("setup.display.banner_fil")}>
                <textarea
                  rows="2"
                  value={data.display.banner_fil}
                  onChange={(e) => patch("display", "banner_fil", e.target.value)}
                />
              </Field>
            </div>
          </div>
        )}

        {current === "admin" && (
          <div className="stack">
            <div className="grid two">
              <Field label={t("setup.admin.username")}>
                <input
                  value={data.admin.username}
                  onChange={(e) => patch("admin", "username", e.target.value)}
                  autoComplete="username"
                />
              </Field>
              <div />
              <Field label={t("setup.admin.password")}>
                <input
                  type="password"
                  value={data.admin.password}
                  onChange={(e) => patch("admin", "password", e.target.value)}
                  autoComplete="new-password"
                />
              </Field>
              <Field label={t("setup.admin.confirm")}>
                <input
                  type="password"
                  value={data.admin.confirm}
                  onChange={(e) => patch("admin", "confirm", e.target.value)}
                  autoComplete="new-password"
                />
              </Field>
            </div>
            {data.admin.password && data.admin.password.length < 6 && (
              <p className="warn-note">{t("setup.admin.short")}</p>
            )}
            <div className="network-box">
              <div>
                <span className="field-label">{t("setup.admin.network")}</span>
                <p className="server-url">{window.location.origin}</p>
                <p className="field-hint">{t("setup.admin.network_hint")}</p>
              </div>
              <img
                className="qr"
                alt={t("setup.admin.qr_hint")}
                src={`/api/qr?data=${encodeURIComponent(window.location.origin)}&size=180`}
              />
            </div>
          </div>
        )}

        {current === "review" && (
          <div className="stack review">
            <p className="muted">{t("setup.review.hint")}</p>
            <div className="review-row">
              <h3>{t("setup.review.institution")}</h3>
              <p>
                <strong>{data.institution.name}</strong>
                <span className="muted"> · {presetLabel(data.institution.type)}</span>
                {data.institution.address && <><br />{data.institution.address}</>}
                {data.institution.contact && <><br />{data.institution.contact}</>}
              </p>
            </div>
            <div className="review-row">
              <h3>{t("setup.review.services")}</h3>
              <p>
                {data.services.map((s) => `${s.prefix} · ${s.name}`).join(" · ") || "—"}
              </p>
            </div>
            <div className="review-row">
              <h3>{t("setup.review.counters")}</h3>
              <p>
                {data.counters
                  .map((c) => `${c.name} (${c.services.join(", ") || "—"})`)
                  .join(" · ") || "—"}
              </p>
            </div>
            <div className="review-row">
              <h3>{t("setup.review.priorities")}</h3>
              <p>
                {data.priorities.types.filter((x) => x.is_active !== false).map((x) => lang === "fil" ? x.name_fil : x.name_en).join(", ") || "—"}
                {" · "}
                {data.priorities.mode === "interleave"
                  ? t("setup.priority.interleave")
                  : t("setup.priority.priority_first")}
              </p>
            </div>
            <div className="review-row">
              <h3>{t("setup.review.intake")}</h3>
              <p>
                {[
                  data.intake.kiosk_enabled && t("setup.intake.kiosk"),
                  data.intake.staff_issue_enabled && t("setup.intake.staff"),
                  data.intake.qr_phone_enabled && t("setup.intake.qr"),
                  data.intake.print_enabled && `${t("setup.intake.print")} · ${data.intake.paper_size} mm`,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </div>
            <div className="review-row">
              <h3>{t("setup.review.display")}</h3>
              <p>
                {data.display.language === "both"
                  ? t("setup.display.both")
                  : data.display.language === "fil"
                  ? t("setup.display.fil")
                  : t("setup.display.en")}
                {" · "}
                {data.display.voice_enabled ? t("setup.display.voice") : t("common.off")}
              </p>
            </div>
            <div className="review-row">
              <h3>{t("setup.review.admin")}</h3>
              <p>{data.admin.username}</p>
            </div>
            <Toggle
              checked={data.demo_ticket}
              onChange={(v) => setData((d) => ({ ...d, demo_ticket: v }))}
              label={t("setup.review.demo")}
              hint={t("setup.review.demo_hint")}
            />
          </div>
        )}

        {error && <p className="error-box">{error}</p>}

        <div className="setup-actions">
          {step > 0 ? (
            <button type="button" className="btn" onClick={back}>
              {t("common.back")}
            </button>
          ) : (
            <span />
          )}
          {step < STEPS.length - 1 ? (
            <button type="button" className="btn primary" onClick={next}>
              {t("common.next")}
            </button>
          ) : (
            <button type="button" className="btn primary" onClick={finish} disabled={busy}>
              {busy ? t("common.loading") : t("common.finish")}
            </button>
          )}
        </div>
      </main>
    </div>
  );
}
