"""Institution presets and setup-wizard persistence."""

PRESET_ORDER = ["lgu", "payment", "hospital", "bank", "church", "school", "generic"]

PRIORITY_DEFAULT = [
    {"name_en": "Senior Citizen", "name_fil": "Senior Citizen"},
    {"name_en": "PWD", "name_fil": "PWD"},
    {"name_en": "Pregnant", "name_fil": "Buntis"},
]


def _svc(name, prefix, **kw):
    base = {
        "name": name,
        "prefix": prefix,
        "is_express": False,
        "open_from": "",
        "open_to": "",
        "cut_off_time": "",
        "ask_account_number": False,
        "queue_alert_threshold": 0,
    }
    base.update(kw)
    return base


def _counter(name, prefixes):
    return {"name": name, "services": prefixes}


PRESETS = {
    "lgu": {
        "label_en": "Government / LGU",
        "label_fil": "Pamahalaan / LGU",
        "services": [
            _svc("Treasurer", "T", queue_alert_threshold=25),
            _svc("Assessor", "A"),
            _svc("Civil Registrar", "C"),
            _svc("GSO", "G"),
            _svc("Mayor's Office", "M"),
        ],
        "counters": [
            _counter("Window 1", ["T"]),
            _counter("Window 2", ["A", "C"]),
            _counter("Window 3", ["G", "M"]),
            _counter("Window 4", ["T"]),
        ],
        "priority_mode": "priority_first",
        "ask_account": False,
    },
    "payment": {
        "label_en": "Payment establishment",
        "label_fil": "Pagbabayaran / Water district, electric coop",
        "services": [
            _svc("Bill Payment", "B", ask_account_number=True, cut_off_time="17:00", queue_alert_threshold=40),
            _svc("New Connection / Application", "N", cut_off_time="16:30"),
            _svc("Reconnection", "R"),
            _svc("Inquiry / Complaint", "I"),
            _svc("Express Payment", "E", is_express=True, ask_account_number=True, queue_alert_threshold=15),
        ],
        "counters": [
            _counter("Cashier 1", ["B"]),
            _counter("Cashier 2", ["B"]),
            _counter("Cashier 3", ["B"]),
            _counter("Cashier 4", ["N", "R", "I"]),
            _counter("Express Window", ["E"]),
        ],
        "priority_mode": "interleave",
        "ask_account": True,
    },
    "hospital": {
        "label_en": "Hospital / clinic",
        "label_fil": "Ospital / klinika",
        "services": [
            _svc("Registration", "R"),
            _svc("Consultation", "C", queue_alert_threshold=30),
            _svc("Laboratory", "L"),
            _svc("Pharmacy", "P"),
            _svc("Cashier", "X"),
        ],
        "counters": [
            _counter("Window 1", ["R", "C"]),
            _counter("Window 2", ["C", "L"]),
            _counter("Window 3", ["P", "X"]),
        ],
        "priority_mode": "priority_first",
        "ask_account": False,
    },
    "bank": {
        "label_en": "Bank / cooperative",
        "label_fil": "Bangko / kooperatiba",
        "services": [
            _svc("Teller", "T", ask_account_number=True, queue_alert_threshold=35),
            _svc("New Account", "N"),
            _svc("Loans", "L"),
            _svc("Customer Service", "C"),
        ],
        "counters": [
            _counter("Window 1", ["T"]),
            _counter("Window 2", ["T"]),
            _counter("Window 3", ["N", "L", "C"]),
        ],
        "priority_mode": "priority_first",
        "ask_account": False,
    },
    "church": {
        "label_en": "Church / parish",
        "label_fil": "Simbahan / parokya",
        "services": [
            _svc("Certificates", "C"),
            _svc("Baptism / Wedding Inquiry", "B"),
            _svc("Mass Intentions", "M"),
        ],
        "counters": [
            _counter("Window 1", ["C", "B"]),
            _counter("Window 2", ["M"]),
        ],
        "priority_mode": "priority_first",
        "ask_account": False,
    },
    "school": {
        "label_en": "School / university",
        "label_fil": "Paaralan / unibersidad",
        "services": [
            _svc("Registrar", "R", queue_alert_threshold=25),
            _svc("Cashier", "C"),
            _svc("Clinic", "N"),
        ],
        "counters": [
            _counter("Window 1", ["R"]),
            _counter("Window 2", ["C"]),
            _counter("Window 3", ["N"]),
        ],
        "priority_mode": "priority_first",
        "ask_account": False,
    },
    "generic": {
        "label_en": "Generic / custom",
        "label_fil": "Pangkalahatan / custom",
        "services": [],
        "counters": [],
        "priority_mode": "priority_first",
        "ask_account": False,
    },
}


def preset_list() -> list[dict]:
    out = []
    for key in PRESET_ORDER:
        p = PRESETS[key]
        out.append({
            "key": key,
            "label_en": p["label_en"],
            "label_fil": p["label_fil"],
            "services": p["services"],
            "counters": p["counters"],
            "priority_mode": p["priority_mode"],
        })
    return out


def apply_setup(payload: dict) -> None:
    """Persist a completed wizard. Called once, on a database with no setup yet."""
    import json
    from . import db
    from .security import hash_secret

    inst = payload.get("institution", {})
    services = payload.get("services", [])
    counters = payload.get("counters", [])
    priorities = payload.get("priorities", {})
    intake = payload.get("intake", {})
    display = payload.get("display", {})
    admin = payload.get("admin", {})

    if not str(inst.get("name", "")).strip():
        raise ValueError("institution_name_required")
    if not services:
        raise ValueError("services_required")
    if not counters:
        raise ValueError("counters_required")
    if not str(admin.get("username", "")).strip() or len(str(admin.get("password", ""))) < 6:
        raise ValueError("admin_credentials_required")
    if not str(admin.get("password", "")).strip():
        raise ValueError("admin_credentials_required")

    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        # Fresh configuration.
        for table in ("tickets", "ticket_events", "daily_counters", "counter_services",
                      "staff", "counters", "services", "priority_types", "admin"):
            conn.execute(f"DELETE FROM {table}")

        priority_types = priorities.get("types") or PRIORITY_DEFAULT
        for i, pt in enumerate(priority_types):
            conn.execute(
                "INSERT INTO priority_types(name_en, name_fil, is_active, sort_order) VALUES(?,?,?,?)",
                (pt.get("name_en") or pt.get("name") or "Priority",
                 pt.get("name_fil") or pt.get("name_en") or pt.get("name") or "Priority",
                 0 if pt.get("is_active") is False else 1, i),
            )

        prefix_to_id = {}
        for i, svc in enumerate(services):
            name = str(svc.get("name", "")).strip()
            prefix = str(svc.get("prefix", "")).strip().upper()
            if not name or not prefix:
                raise ValueError("service_name_and_prefix_required")
            cur = conn.execute(
                """INSERT INTO services(name, prefix, is_express, open_from, open_to, cut_off_time,
                   ask_account_number, queue_alert_threshold, is_active, sort_order)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (name, prefix, 1 if svc.get("is_express") else 0,
                 svc.get("open_from") or None, svc.get("open_to") or None,
                 svc.get("cut_off_time") or None,
                 1 if svc.get("ask_account_number") else 0,
                 int(svc.get("queue_alert_threshold") or 0), 1, i),
            )
            prefix_to_id[prefix] = cur.lastrowid

        for i, ctr in enumerate(counters):
            name = str(ctr.get("name", "")).strip()
            if not name:
                raise ValueError("counter_name_required")
            cur = conn.execute(
                "INSERT INTO counters(name, is_active, status, sort_order) VALUES(?,?,?,?)",
                (name, 1, "closed", i),
            )
            for prefix in ctr.get("services", []):
                sid = prefix_to_id.get(str(prefix).upper())
                if sid:
                    conn.execute(
                        "INSERT OR IGNORE INTO counter_services(counter_id, service_id) VALUES(?,?)",
                        (cur.lastrowid, sid),
                    )

        conn.execute(
            "INSERT INTO admin(username, password_hash) VALUES(?,?)",
            (str(admin["username"]).strip(), hash_secret(str(admin["password"]))),
        )

        settings = {
            "setup_complete": True,
            "institution_name": str(inst.get("name", "")).strip(),
            "institution_type": inst.get("type") or "generic",
            "institution_address": inst.get("address", ""),
            "institution_contact": inst.get("contact", ""),
            "logo_file": inst.get("logo_file", ""),
            "timezone": inst.get("timezone") or "Asia/Manila",
            "language_default": display.get("language") if display.get("language") in ("en", "fil") else "en",
            "screen_language": display.get("language") or "en",
            "voice_enabled": bool(display.get("voice_enabled", True)),
            "voice_lang": display.get("voice_lang") or "both",
            "print_enabled": bool(intake.get("print_enabled", True)),
            "kiosk_enabled": bool(intake.get("kiosk_enabled", True)),
            "staff_issue_enabled": bool(intake.get("staff_issue_enabled", False)),
            "qr_phone_enabled": bool(intake.get("qr_phone_enabled", False)),
            "ticket_show_wait": bool(intake.get("show_estimate", True)),
            "ticket_show_qr": bool(intake.get("show_qr", True)),
            "ticket_paper_size": intake.get("paper_size") or "58",
            "duplicate_ticket_delay": int(intake.get("duplicate_ticket_delay") or 15),
            "priority_mode": priorities.get("mode") or "priority_first",
            "priority_interleave_n": int(priorities.get("interleave_n") or 3),
            "tracking_base_url": inst.get("tracking_base_url", ""),
            "banner_text_en": display.get("banner_en", ""),
            "banner_text_fil": display.get("banner_fil", ""),
        }
        for key, value in settings.items():
            conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value)),
            )
        conn.execute(
            "UPDATE media_settings SET layout=?, image_duration=?, banner_text_en=?, banner_text_fil=? WHERE id=1",
            (int(display.get("layout") or 60), int(display.get("image_duration") or 10),
             display.get("banner_en", ""), display.get("banner_fil", "")),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
