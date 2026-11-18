import { useEffect, useState } from "react";
import { api } from "./api.js";
import { LanguageProvider, translate, useLanguageState } from "./i18n.jsx";
import Home from "./screens/Home.jsx";
import Setup from "./screens/Setup.jsx";
import Admin from "./screens/Admin.jsx";
import Kiosk from "./screens/Kiosk.jsx";
import Counter from "./screens/Counter.jsx";
import Display from "./screens/Display.jsx";
import Track from "./screens/Track.jsx";

function Router({ boot, refreshBoot }) {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  if (path.startsWith("/track/")) {
    return <Track publicId={path.split("/")[2]} />;
  }
  if (path === "/setup") {
    return <Setup initial={boot} onDone={refreshBoot} />;
  }
  if (!boot.setup_complete) {
    return <Setup initial={boot} onDone={refreshBoot} />;
  }
  if (path === "/kiosk") return <Kiosk boot={boot} />;
  if (path === "/counter") return <Counter />;
  if (path === "/display") return <Display />;
  if (path === "/admin") return <Admin boot={boot} onSetupChange={refreshBoot} />;
  return <Home boot={boot} />;
}

function Shell({ boot, refreshBoot }) {
  const language = useLanguageState(boot?.language_default || "en");
  return (
    <LanguageProvider value={language}>
      <Router boot={boot} refreshBoot={refreshBoot} />
    </LanguageProvider>
  );
}

export default function App() {
  const [boot, setBoot] = useState(null);
  const [error, setError] = useState(null);
  const t = (key) => translate("en", key);

  const load = () => {
    api("/api/bootstrap")
      .then((data) => {
        setBoot(data);
        setError(null);
      })
      .catch((err) => setError(err));
  };

  useEffect(() => {
    load();
  }, []);

  if (error) {
    return (
      <div className="centered-screen">
        <div className="card narrow">
          <h2>{t("error.network")}</h2>
          <p className="muted">{String(error.message || error)}</p>
          <button className="btn primary" onClick={load}>
            {t("common.retry")}
          </button>
        </div>
      </div>
    );
  }
  if (!boot) {
    return (
      <div className="centered-screen">
        <div className="spinner" />
      </div>
    );
  }
  return <Shell boot={boot} refreshBoot={load} />;
}
