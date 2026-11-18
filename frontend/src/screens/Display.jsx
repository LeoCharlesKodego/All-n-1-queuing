import { useCallback, useEffect, useRef, useState } from "react";
import { api, formatTime } from "../api.js";
import { useLive } from "../live.js";
import { translate } from "../i18n.jsx";

function useClock(timezone) {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const time = now.toLocaleTimeString("en-PH", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: timezone,
  });
  const date = now.toLocaleDateString("en-PH", {
    weekday: "long",
    month: "long",
    day: "numeric",
    timeZone: timezone,
  });
  return { time, date };
}

function minutesOf(value) {
  if (!value || !/^\d{1,2}:\d{2}$/.test(value)) return null;
  const [hours, minutes] = value.split(":").map(Number);
  return hours * 60 + minutes;
}

function mediaAllowed(settings) {
  const schedule = settings?.media_schedule;
  if (!schedule || !schedule.enabled) return true;
  const from = minutesOf(schedule.from);
  const to = minutesOf(schedule.to);
  if (from === null || to === null) return true;
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: settings.timezone || "Asia/Manila",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(new Date());
  const part = (type) => Number(parts.find((p) => p.type === type)?.value || 0);
  const now = part("hour") * 60 + part("minute");
  return from <= to ? now >= from && now < to : now >= from || now < to;
}

export default function Display() {
  const [data, setData] = useState(null);
  const [unlocked, setUnlocked] = useState(false);
  const [flash, setFlash] = useState(null);
  const [mediaIndex, setMediaIndex] = useState(0);
  const [ducked, setDucked] = useState(false);
  const audioCtx = useRef(null);
  const videoRef = useRef(null);
  const flashTimer = useRef(null);

  const load = useCallback(async () => {
    try {
      const next = await api("/api/display");
      setData(next);
      return next;
    } catch {
      return null;
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  const settings = data?.settings;
  const screenLang = settings?.screen_language || "en";
  const L = (key, vars) => {
    if (screenLang === "fil") return translate("fil", key, vars);
    if (screenLang === "both") return `${translate("en", key, vars)} / ${translate("fil", key, vars)}`;
    return translate("en", key, vars);
  };

  const chime = () => {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      audioCtx.current = audioCtx.current || new Ctx();
      const ctx = audioCtx.current;
      if (ctx.state === "suspended") ctx.resume();
      [880, 1174].forEach((freq, i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.value = freq;
        const start = ctx.currentTime + i * 0.28;
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(0.35, start + 0.03);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.3);
        osc.connect(gain).connect(ctx.destination);
        osc.start(start);
        osc.stop(start + 0.32);
      });
    } catch {
      /* audio is optional */
    }
  };

  const speak = (text, langCode) =>
    new Promise((resolve) => {
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        clearTimeout(guard);
        resolve();
      };
      // Never let a browser without voices block the queue or keep media ducked.
      const guard = setTimeout(finish, 9000);
      try {
        if (!("speechSynthesis" in window)) return finish();
        const utter = new SpeechSynthesisUtterance(text);
        utter.lang = langCode;
        utter.rate = 0.92;
        utter.pitch = 1;
        utter.onend = finish;
        utter.onerror = finish;
        window.speechSynthesis.speak(utter);
      } catch {
        finish();
      }
    });

  const announce = async (state, event) => {
    if (!unlocked || !state) return;
    const voiceLang = state.settings.voice_lang || "both";
    const langs = voiceLang === "both" ? ["en-PH", "fil-PH"] : [voiceLang === "fil" ? "fil-PH" : "en-PH"];
    setDucked(true);
    chime();
    await new Promise((r) => setTimeout(r, 700));
    for (const code of langs) {
      const key = code === "fil-PH" ? "fil" : "en";
      const text = translate(key, "display.announce", {
        number: event.ticket.number,
        window: event.counter_name || "",
      });
      await speak(text, code);
      await new Promise((r) => setTimeout(r, 220));
    }
    setDucked(false);
  };

  const handleEvent = (event) => {
    if (event.type === "called" && event.ticket) {
      setFlash({ id: event.ticket.id, at: Date.now() });
      clearTimeout(flashTimer.current);
      flashTimer.current = setTimeout(() => setFlash(null), 4000);
      load().then((next) => {
        const counter = next?.windows?.find((w) => w.id === event.counter_id);
        announce(next, { ...event, counter_name: counter?.name });
      });
    } else if (event.type !== "hello") {
      load();
    }
  };

  const connected = useLive(handleEvent);
  const { time, date } = useClock(settings?.timezone || "Asia/Manila");

  const playlist = mediaAllowed(settings) ? (data?.media || []).filter((f) => !f.is_logo) : [];
  const current = playlist.length ? playlist[mediaIndex % playlist.length] : null;

  useEffect(() => {
    if (current?.kind === "image" && data) {
      const id = setTimeout(() => setMediaIndex((i) => i + 1), (data.settings.image_duration || 10) * 1000);
      return () => clearTimeout(id);
    }
  }, [current, data?.settings.image_duration, mediaIndex]);

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.volume = ducked ? 0.08 : data?.settings.media_volume ?? 0.4;
    }
  }, [ducked, current, data?.settings.media_volume]);

  useEffect(() => () => clearTimeout(flashTimer.current), []);

  if (!data) {
    return (
      <div className="display" style={{ display: "grid", placeItems: "center" }}>
        <div className="spinner" />
      </div>
    );
  }

  const { now_serving: nowServing, windows, next, waiting_total: waitingTotal } = data;
  const top = nowServing?.[0] || null;
  const bannerText =
    screenLang === "fil"
      ? settings.banner_text_fil
      : screenLang === "both"
        ? [settings.banner_text_en, settings.banner_text_fil].filter(Boolean).join("  •  ")
        : settings.banner_text_en;
  const isEmpty = waitingTotal === 0 && !nowServing?.length && playlist.length > 0;
  const queueWidth = Math.min(80, Math.max(45, Number(settings.display_layout) || 60));

  return (
    <div className="display">
      {!connected && <div className="reconnect">{L("display.reconnecting")}</div>}

      {!unlocked && (
        <div className="start-overlay">
          <div className="inner">
            <h1>{settings.institution_name}</h1>
            <p>{L("display.start_hint")}</p>
            <button
              className="btn primary big"
              onClick={() => {
                setUnlocked(true);
                chime();
                setTimeout(() => speak(L("display.sound_sample"), "en-PH"), 500);
              }}
            >
              {L("display.start")}
            </button>
            <p className="small">{L("display.start_note")}</p>
          </div>
        </div>
      )}

      <header className="display-header">
        <div className="brand row gap">
          {settings.logo_file && (
            <img className="brand-logo" src={`/media/${settings.logo_file}`} alt="" />
          )}
          <div>
            <p className="eyebrow" style={{ color: "#9fc0c7" }}>
              {L("display.subtitle")}
            </p>
            <h1>{settings.institution_name}</h1>
          </div>
        </div>
        <div className="row gap">
          {unlocked && (
            <button
              className="btn small"
              style={{ background: "rgba(255,255,255,0.08)", color: "#d7e8eb", borderColor: "rgba(255,255,255,0.18)" }}
              onClick={() => {
                chime();
                setTimeout(() => speak(L("display.sound_sample"), "en-PH"), 600);
              }}
            >
              {L("display.sound_test")}
            </button>
          )}
          <div className="display-clock">
            {time}
            <small>{date}</small>
          </div>
        </div>
      </header>

      {isEmpty ? (
        <div className="media-full">
          {current?.kind === "video" ? (
            <video
              key={current.url}
              ref={videoRef}
              src={current.url}
              autoPlay
              muted={!unlocked}
              playsInline
              onEnded={() => setMediaIndex((i) => i + 1)}
            />
          ) : current ? (
            <img key={current.url} src={current.url} alt="" />
          ) : null}
        </div>
      ) : (
        <main className="display-main">
          <section className="queue-pane" style={{ flexBasis: `${queueWidth}%` }}>
            <div className={`now-serving ${top ? "" : "empty"} ${flash ? "flash" : ""}`}>
              <div>
                <p className="label">{L("display.now_serving")}</p>
                <p className="number">{top ? top.number : "—"}</p>
                {top?.priority_en && (
                  <span className="pill amber">
                    {screenLang === "fil" ? top.priority_fil : top.priority_en}
                  </span>
                )}
              </div>
              <div className="window">{top ? top.counter_name : L("display.waiting_for_calls")}</div>
            </div>

            <div className="window-grid">
              {windows.map((w) => (
                <div key={w.id} className={`window-cell ${w.state}`}>
                  <span className="name">{w.name}</span>
                  <span className="tnum">
                    {w.number || (w.state === "closed" ? L("display.closed") : w.state === "away" ? L("display.away") : "—")}
                  </span>
                  <span className="state">
                    {w.state === "serving"
                      ? L("display.serving")
                      : w.state === "called"
                        ? L("display.called")
                        : w.state === "away"
                          ? L("display.away")
                          : w.state === "closed"
                            ? L("display.closed")
                            : L("display.open")}
                  </span>
                </div>
              ))}
            </div>

            {settings.display_show_next && next?.length > 0 && (
              <div className="next-list">
                <h3>
                  {L("display.next")} · {L("display.waiting_count", { count: waitingTotal })}
                </h3>
                <div className="row-items">
                  {next.slice(0, 8).map((t) => (
                    <span key={t.id} className="next-chip">
                      {t.number}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </section>

          {playlist.length > 0 && (
            <aside className="media-pane" style={{ flexBasis: `${100 - queueWidth}%` }}>
              {current?.kind === "video" ? (
                <video
                  key={current.url}
                  ref={videoRef}
                  src={current.url}
                  autoPlay
                  loop
                  muted={!unlocked}
                  playsInline
                />
              ) : (
                <img key={current.url} src={current.url} alt="" />
              )}
            </aside>
          )}
        </main>
      )}

      {bannerText && (
        <footer className="display-banner">
          <span className={bannerText.length < 70 ? "no-scroll" : ""}>{bannerText}</span>
        </footer>
      )}
    </div>
  );
}
