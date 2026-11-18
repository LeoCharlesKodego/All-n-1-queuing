import { useCallback, useEffect, useRef, useState } from "react";
import { api, formatDuration, formatTime } from "../api.js";
import { useT } from "../i18n.jsx";
import { useLive } from "../live.js";

const STATUS_KEYS = {
  waiting: "track.status.waiting",
  called: "track.status.called",
  serving: "track.status.serving",
  done: "track.status.done",
  no_show: "track.status.no_show",
  transferred: "track.status.transferred",
  expired: "track.status.expired",
  cancelled: "track.status.expired",
};

export default function Track({ publicId }) {
  const { t, lang } = useT();
  const [data, setData] = useState(null);
  const [missing, setMissing] = useState(false);
  const [offline, setOffline] = useState(false);
  const [updated, setUpdated] = useState(null);
  const timer = useRef(null);
  const debounce = useRef(null);

  const load = useCallback(async () => {
    try {
      const next = await api(`/api/track/${encodeURIComponent(publicId)}`);
      setData(next);
      setMissing(false);
      setOffline(false);
      setUpdated(new Date());
    } catch (err) {
      if (err?.status === 404 || err?.message === "ticket_not_found") {
        setMissing(true);
        setOffline(false);
      } else {
        setOffline(true);
      }
    }
  }, [publicId]);

  useEffect(() => {
    load();
    timer.current = setInterval(load, 15000);
    return () => {
      clearInterval(timer.current);
      clearTimeout(debounce.current);
    };
  }, [load]);

  useLive(() => {
    clearTimeout(debounce.current);
    debounce.current = setTimeout(load, 300);
  });

  if (missing) {
    return (
      <div className="track">
        <div className="card narrow track-card">
          <p className="eyebrow">{t("track.title")}</p>
          <h1>{t("track.not_found")}</h1>
          <p className="muted">{t("track.not_found_hint")}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="track">
        <div className="card narrow track-card">
          {offline ? (
            <>
              <p className="eyebrow">{t("track.title")}</p>
              <h1>{t("track.offline")}</h1>
              <p className="muted">{t("track.offline_hint")}</p>
              <button className="btn primary" onClick={load}>{t("common.retry")}</button>
            </>
          ) : (
            <span className="spinner" aria-label={t("common.loading")} />
          )}
        </div>
      </div>
    );
  }

  const ticket = data.ticket;
  const settings = data.settings || {};
  const priority = lang === "fil" ? ticket.priority_fil : ticket.priority_en;
  const active = ticket.status === "waiting" || ticket.status === "called" || ticket.status === "serving";
  const statusKey = STATUS_KEYS[ticket.status] || "track.title";

  return (
    <div className="track">
      <header className="track-head">
        <h1>{settings.institution_name || t("track.title")}</h1>
        {offline && <span className="pill amber">{t("common.reconnecting")}</span>}
      </header>

      <main className="card track-card">
        <p className="eyebrow">{t("track.your_number")}</p>
        <p className="track-number">{ticket.number}</p>
        <p className="track-service">{ticket.service_name}</p>
        {priority && <span className="pill amber">{priority}</span>}
        <p className={`track-status ${ticket.status}`}>{t(statusKey)}</p>

        {ticket.status === "waiting" && (
          <div className="track-figures">
            <div>
              <span className="label">{t("track.ahead")}</span>
              <span className="value">{data.people_ahead}</span>
            </div>
            {settings.display_show_estimate && data.estimate?.estimated_seconds != null && (
              <div>
                <span className="label">{t("track.estimate")}</span>
                <span className="value">{formatDuration(data.estimate.estimated_seconds)}</span>
              </div>
            )}
          </div>
        )}

        {(ticket.status === "called" || ticket.status === "serving") && ticket.counter_name && (
          <div className="track-window">
            <p className="eyebrow">{t("track.window")}</p>
            <p className="track-counter">{ticket.counter_name}</p>
            {ticket.recall_count > 0 && <p className="muted small">{t("track.recalled", { count: ticket.recall_count })}</p>}
          </div>
        )}

        {!active && <p className="notice-box">{t("track.finished_hint")}</p>}

        <div className="track-now">
          <p className="eyebrow">{t("track.now_serving")}</p>
          {data.now_serving.length === 0 ? (
            <p className="muted">{t("track.no_serving")}</p>
          ) : (
            <ul>
              {data.now_serving.map((row) => (
                <li key={`${row.counter_name}-${row.number}`}>
                  <strong>{row.number}</strong>
                  <span>{row.counter_name}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <footer className="track-foot">
          <span>{t("track.updated", { when: updated ? formatTime(updated.toISOString(), lang === "fil" ? "fil-PH" : "en-PH", settings.timezone) : "—" })}</span>
          <span>{t("track.auto_refresh")}</span>
        </footer>
      </main>
    </div>
  );
}
