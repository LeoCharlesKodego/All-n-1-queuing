import { useT } from "../i18n.jsx";

export default function Track({ publicId }) {
  const { t } = useT();
  return (
    <div className="centered-screen">
      <div className="card narrow">
        <h1>{t("track.title")}</h1>
        <p className="muted">{publicId}</p>
      </div>
    </div>
  );
}
