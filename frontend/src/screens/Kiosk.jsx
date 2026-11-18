import { useCallback, useEffect, useRef, useState } from "react";
import { api, formatDuration, formatTime, post } from "../api.js";
import { LanguageSwitch, useT } from "../i18n.jsx";
import { useLive } from "../live.js";

const IDLE_RESET_MS = 12000;

function priorityName(item, lang) {
  return lang === "fil" ? item.name_fil : item.name_en;
}

export default function Kiosk() {
  const { t, lang } = useT();
  const [data, setData] = useState(null);
  const [step, setStep] = useState("welcome");
  const [priority, setPriority] = useState(null);
  const [service, setService] = useState(null);
  const [account, setAccount] = useState("");
  const [ticket, setTicket] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [printerProblem, setPrinterProblem] = useState(false);
  const [clock, setClock] = useState(new Date());
  const resetTimer = useRef(null);
  const fullscreenAsked = useRef(false);

  const errorText = (err) => {
    const detail = err?.detail;
    if (detail && typeof detail === "object" && detail.code === "duplicate_delay") {
      return t("error.duplicate_delay", { seconds: detail.seconds });
    }
    const key = `error.${err?.message}`;
    const text = t(key);
    return text === key ? t("common.error") : text;
  };

  const load = useCallback(async () => {
    try {
      const next = await api("/api/kiosk");
      setData(next);
      setError("");
    } catch (err) {
      setError(errorText(err));
    }
  }, [lang]);

  useEffect(() => {
    load();
  }, [load]);

  useLive(() => load());

  useEffect(() => {
    const id = setInterval(() => setClock(new Date()), 15000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => () => clearTimeout(resetTimer.current), []);

  const reset = () => {
    clearTimeout(resetTimer.current);
    setStep("welcome");
    setPriority(null);
    setService(null);
    setAccount("");
    setTicket(null);
    setError("");
    setPrinterProblem(false);
    load();
  };

  const enterFullscreen = () => {
    if (fullscreenAsked.current) return;
    fullscreenAsked.current = true;
    if (document.documentElement.requestFullscreen && !document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    }
  };

  const start = () => {
    enterFullscreen();
    setError("");
    if (data?.priorities?.length) {
      setStep("priority");
    } else {
      setStep("service");
    }
  };

  const choosePriority = (item) => {
    setPriority(item);
    setStep("service");
  };

  const chooseService = (svc) => {
    if (!svc.can_issue) return;
    setError("");
    setService(svc);
    setAccount("");
    if (svc.ask_account_number) {
      setStep("account");
    } else {
      issue(svc, null);
    }
  };

  const issue = async (svc, accountNumber) => {
    setBusy(true);
    setError("");
    try {
      const res = await post("/api/kiosk/ticket", {
        service_id: svc.id,
        priority_type_id: priority?.id || null,
        account_number: accountNumber || null,
      });
      setTicket(res);
      setStep("ticket");
      if (data?.settings?.print_enabled) {
        setTimeout(() => window.print(), 400);
      }
      resetTimer.current = setTimeout(reset, IDLE_RESET_MS);
    } catch (err) {
      setError(errorText(err));
      setStep("service");
    } finally {
      setBusy(false);
    }
  };

  const reportPrinter = async () => {
    setPrinterProblem(true);
    try {
      await post("/api/kiosk/printer", { status: "error", note: "Reported from kiosk" });
    } catch {
      /* the on-screen message already tells the customer to ask staff */
    }
  };

  const paperClass = `paper-${data?.settings?.ticket_paper_size === "80" ? "80" : "58"}`;

  if (!data) {
    return (
      <div className="centered-screen">
        {error ? <p className="error-box">{error}</p> : <div className="spinner" />}
      </div>
    );
  }

  const settings = data.settings;
  const institution = settings.institution_name;
  const logo = data.logo;
  return (
    <div className="kiosk">
      <style>{`@media print { @page { size: ${settings.ticket_paper_size === "80" ? "80mm" : "58mm"} auto; margin: 2mm; } }`}</style>
      <header className="kiosk-head no-print">
        <div className="row gap">
          {logo && settings.ticket_show_logo && <img src={logo} alt="" className="kiosk-logo" />}
          <div>
            <p className="eyebrow">{institution}</p>
            <p className="muted small">
              {clock.toLocaleDateString(lang === "fil" ? "fil-PH" : "en-PH", {
                weekday: "short",
                month: "short",
                day: "numeric",
              })}{" "}
              · {formatTime(clock.toISOString(), lang === "fil" ? "fil-PH" : "en-PH", settings.timezone)}
            </p>
          </div>
        </div>
        <LanguageSwitch compact />
      </header>

      <main className="kiosk-body no-print" onPointerDown={enterFullscreen}>
        {error && step !== "ticket" && <p className="error-box">{error}</p>}

        {step === "welcome" && (
          <section className="kiosk-welcome">
            <h1>{institution}</h1>
            <p className="kiosk-lead">{t("kiosk.welcome")}</p>
            <button className="btn primary kiosk-big" onClick={start}>
              {t("kiosk.take_number")}
            </button>
            <p className="muted">{t("kiosk.tap_hint")}</p>
          </section>
        )}

        {step === "priority" && (
          <section className="kiosk-step">
            <p className="eyebrow">{t("kiosk.step_priority")}</p>
            <h1>{t("kiosk.priority_question")}</h1>
            <div className="kiosk-grid">
              {data.priorities.map((item) => (
                <button key={item.id} className="btn kiosk-choice" onClick={() => choosePriority(item)}>
                  {priorityName(item, lang)}
                </button>
              ))}
              <button className="btn kiosk-choice ghost" onClick={() => choosePriority(null)}>
                {t("kiosk.no_priority")}
              </button>
            </div>
            <button className="btn ghost" onClick={reset}>
              {t("common.back")}
            </button>
          </section>
        )}

        {step === "service" && (
          <section className="kiosk-step">
            <p className="eyebrow">{t("kiosk.step_service")}</p>
            <h1>{t("kiosk.choose_service")}</h1>
            {priority && <p className="pill amber">{priorityName(priority, lang)}</p>}
            <div className="kiosk-grid">
              {data.services.map((svc) => (
                <button
                  key={svc.id}
                  className={`btn kiosk-choice ${svc.can_issue ? "" : "disabled"}`}
                  disabled={!svc.can_issue}
                  onClick={() => chooseService(svc)}
                >
                  <span className="kiosk-choice-name">{svc.name}</span>
                  <span className="kiosk-choice-meta">
                    {svc.can_issue
                      ? t("kiosk.people_waiting", { count: svc.people_ahead })
                      : t(`kiosk.reason.${svc.reason || "closed"}`)}
                  </span>
                </button>
              ))}
            </div>
            <button className="btn ghost" onClick={() => (data.priorities.length ? setStep("priority") : reset())}>
              {t("common.back")}
            </button>
          </section>
        )}

        {step === "account" && service && (
          <section className="kiosk-step">
            <p className="eyebrow">{service.name}</p>
            <h1>{t("kiosk.account_prompt")}</h1>
            <p className="muted">{t("kiosk.account_hint")}</p>
            <div className="kiosk-account">{account || <span className="muted">—</span>}</div>
            <div className="keypad">
              {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((d) => (
                <button key={d} className="btn keypad-key" onClick={() => setAccount((a) => (a.length < 20 ? a + d : a))}>
                  {d}
                </button>
              ))}
              <button className="btn keypad-key" onClick={() => setAccount("")}>
                {t("kiosk.clear")}
              </button>
              <button className="btn keypad-key" onClick={() => setAccount((a) => a.slice(0, -1))}>
                ⌫
              </button>
              <button className="btn keypad-key" onClick={() => setAccount((a) => (a.length < 20 ? `${a}0` : a))}>
                0
              </button>
            </div>
            <div className="row gap">
              <button className="btn primary big" disabled={busy} onClick={() => issue(service, account.trim() || null)}>
                {t("kiosk.get_ticket")}
              </button>
              <button className="btn big" disabled={busy} onClick={() => issue(service, null)}>
                {t("kiosk.skip")}
              </button>
            </div>
            <button className="btn ghost" onClick={() => setStep("service")}>
              {t("common.back")}
            </button>
          </section>
        )}

        {step === "ticket" && ticket && (
          <section className="kiosk-step kiosk-issued">
            <p className="eyebrow">{t("kiosk.your_number")}</p>
            <p className="kiosk-number">{ticket.ticket.number}</p>
            <p className="kiosk-service">
              {ticket.ticket.service_name}
              {ticket.ticket.priority_en && (
                <span className="pill amber">
                  {lang === "fil" ? ticket.ticket.priority_fil : ticket.ticket.priority_en}
                </span>
              )}
            </p>
            {settings.ticket_show_wait && (
              <p className="muted">
                {t("kiosk.ahead", { count: ticket.people_ahead })}
                {ticket.estimated_seconds != null && ` · ${t("kiosk.estimate", { time: formatDuration(ticket.estimated_seconds) })}`}
              </p>
            )}
            {ticket.tracking_enabled && (ticket.show_qr || !settings.print_enabled) && (
              <div className="kiosk-qr">
                <img
                  src={`/api/qr?size=200&data=${encodeURIComponent(ticket.tracking_url)}`}
                  alt={t("kiosk.qr_alt")}
                />
                <p className="small muted">{t("kiosk.qr_hint")}</p>
              </div>
            )}
            {!settings.print_enabled && <p className="notice-box">{t("kiosk.no_print")}</p>}
            {printerProblem ? (
              <p className="error-box">{t("kiosk.printer_error")}</p>
            ) : (
              settings.print_enabled && (
                <button className="btn ghost small" onClick={reportPrinter}>
                  {t("kiosk.printer_help")}
                </button>
              )
            )}
            <button className="btn primary big" onClick={reset}>
              {t("kiosk.done")}
            </button>
          </section>
        )}
      </main>

      <footer className="kiosk-foot no-print">
        <span>{settings.institution_contact}</span>
        <span>{t("kiosk.footer_hint")}</span>
      </footer>

      {ticket && (
        <div className={`ticket-print ${paperClass}`} aria-hidden="true">
          {logo && settings.ticket_show_logo && <img src={logo} alt="" style={{ maxHeight: 60 }} />}
          <p className="t-inst">{institution}</p>
          {settings.institution_address && <p className="t-small">{settings.institution_address}</p>}
          <hr />
          <p className="t-number">{ticket.ticket.number}</p>
          <p className="t-svc">{ticket.ticket.service_name}</p>
          {ticket.ticket.priority_en && (
            <p className="t-priority">{lang === "fil" ? ticket.ticket.priority_fil : ticket.ticket.priority_en}</p>
          )}
          <hr />
          <div className="t-meta">
            <span>{new Date(ticket.ticket.issued_at).toLocaleDateString(lang === "fil" ? "fil-PH" : "en-PH")}</span>
            <span>{formatTime(ticket.ticket.issued_at, lang === "fil" ? "fil-PH" : "en-PH", settings.timezone)}</span>
          </div>
          {settings.ticket_show_wait && <p className="t-small">{t("kiosk.ahead", { count: ticket.people_ahead })}</p>}
          {ticket.show_qr && ticket.tracking_enabled && (
            <img className="t-qr" src={`/api/qr?size=200&data=${encodeURIComponent(ticket.tracking_url)}`} alt="" />
          )}
          <p className="t-small">{t("kiosk.ticket_footer")}</p>
        </div>
      )}
    </div>
  );
}
