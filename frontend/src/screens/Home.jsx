import { LanguageSwitch, useT } from "../i18n.jsx";

const LINKS = [
  { path: "/kiosk", title: "home.kiosk", desc: "home.kiosk_desc", icon: "🎫" },
  { path: "/counter", title: "home.counter", desc: "home.counter_desc", icon: "🖥️" },
  { path: "/display", title: "home.display", desc: "home.display_desc", icon: "📺" },
  { path: "/admin", title: "home.admin", desc: "home.admin_desc", icon: "⚙️" },
];

export default function Home({ boot }) {
  const { t } = useT();
  return (
    <div className="home">
      <header className="home-head">
        <div className="brand">
          {boot.logo ? <img src={boot.logo} alt="" className="brand-logo" /> : <div className="brand-mark">Q</div>}
          <div>
            <h1>{boot.institution_name || t("home.title")}</h1>
            <p className="muted">{t("home.subtitle")}</p>
          </div>
        </div>
        <LanguageSwitch />
      </header>
      <div className="home-grid">
        {LINKS.map((link) => (
          <a className="home-card" href={link.path} key={link.path}>
            <span className="home-icon" aria-hidden="true">
              {link.icon}
            </span>
            <h2>{t(link.title)}</h2>
            <p>{t(link.desc)}</p>
          </a>
        ))}
      </div>
      <footer className="home-foot">
        <a href="/admin" className="subtle-link">
          {t("home.admin")}
        </a>
      </footer>
    </div>
  );
}
