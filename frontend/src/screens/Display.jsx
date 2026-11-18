import { useT } from "../i18n.jsx";

export default function Display() {
  const { t } = useT();
  return (
    <div className="centered-screen">
      <div className="card narrow">
        <h1>{t("home.display")}</h1>
        <p className="muted">{t("common.loading")}</p>
      </div>
    </div>
  );
}
