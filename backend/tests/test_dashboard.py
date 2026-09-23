"""Dashboard bucketing + enriched list fields."""

from __future__ import annotations

from datetime import date, datetime, timedelta


def _program(client, uni):
    return client.post("/api/programs", json={"university": uni}).json()


def _deadline(client, pid, day: date):
    client.post(f"/api/programs/{pid}/deadlines", json={"date": day.isoformat()})


def _backdate_activity(pid, when: datetime):
    """Force a program's activity timestamp into the past (simulate idleness)."""
    from app.db import SessionLocal
    from app.models import Program

    with SessionLocal() as s:
        p = s.get(Program, pid)
        p.updated_at = when
        s.commit()


def test_list_returns_enriched_fields(client):
    p = _program(client, "Enrich U")
    _deadline(client, p["id"], date.today() + timedelta(days=5))
    row = next(r for r in client.get("/api/programs").json() if r["id"] == p["id"])
    assert row["urgency"] == "due_soon"
    assert row["days_until_deadline"] == 5
    assert row["last_activity"] is not None
    assert row["is_stale"] is False  # freshly created


def test_dashboard_buckets(client):
    today = date.today()
    due = _program(client, "Due Soon U")
    _deadline(client, due["id"], today + timedelta(days=3))

    over = _program(client, "Overdue U")
    _deadline(client, over["id"], today - timedelta(days=2))

    stale = _program(client, "Stale U")
    _deadline(client, stale["id"], today + timedelta(days=30))
    _backdate_activity(stale["id"], datetime.now() - timedelta(days=40))

    dash = client.get("/api/dashboard").json()
    assert due["id"] in [s["id"] for s in dash["due_soon"]]
    assert over["id"] in [s["id"] for s in dash["overdue"]]
    assert stale["id"] in [s["id"] for s in dash["stale"]]
    # The stale program has a looming (30d) deadline, so it is NOT overdue/due_soon.
    assert stale["id"] not in [s["id"] for s in dash["overdue"]]


# ── Dashboard overview ──────────────────────────────────────────────────────


def _requirement_id(client, pid, kind):
    detail = client.get(f"/api/programs/{pid}").json()
    return next(r["id"] for r in detail["requirements"] if r["kind"] == kind)


def _set_requirement(client, pid, kind, value, confirmed=False):
    # A user edit auto-confirms, so a researched value has to say so explicitly.
    body = {"value": value, "source": "researched", "needs_human_verification": True}
    if confirmed:
        body |= {"source": "confirmed_by_program", "needs_human_verification": False}
    client.patch(f"/api/programs/{pid}/requirements/{_requirement_id(client, pid, kind)}", json=body)


def _tick(client, pid, key):
    steps = client.get(f"/api/programs/{pid}").json()["steps"]
    step = next(s for s in steps if s["key"] == key)
    client.patch(f"/api/programs/{pid}/steps/{step['id']}", json={"completed": True})


def test_parse_fee():
    from app.routers.dashboard import parse_fee

    assert parse_fee("$75") == 75
    assert parse_fee("USD 90") == 90
    assert parse_fee("$1,000") == 1000
    assert parse_fee("$90 domestic, $110 international") == 90
    assert parse_fee("125") == 125
    assert parse_fee("£80") is None
    assert parse_fee("Waived for some applicants") is None
    assert parse_fee(None) is None


def test_overview_agenda_is_date_ordered_and_mixes_reminders(client):
    today = date.today()
    a = _program(client, "Alpha U")
    b = _program(client, "Beta U")
    _deadline(client, a["id"], today + timedelta(days=20))
    _deadline(client, b["id"], today + timedelta(days=5))
    client.post(
        f"/api/programs/{a['id']}/my-notes",
        data={"text": "Ask about funding", "due_date": (today + timedelta(days=1)).isoformat()},
    )

    agenda = client.get("/api/dashboard/overview").json()["agenda"]
    assert [(i["university"], i["kind"]) for i in agenda] == [
        ("Alpha U", "reminder"),
        ("Beta U", "deadline"),
        ("Alpha U", "deadline"),
    ]
    assert agenda[0]["label"] == "Ask about funding"
    assert agenda[0]["source"] is None


def test_overview_drops_application_deadline_once_submitted(client):
    p = _program(client, "Done U")
    _deadline(client, p["id"], date.today() + timedelta(days=10))
    _tick(client, p["id"], "submitted")

    dash = client.get("/api/dashboard/overview").json()
    assert dash["agenda"] == []
    assert dash["submitted_count"] == 1
    # Nothing left to chase on a submitted program.
    assert [i for i in dash["attention"] if i["program_id"] == p["id"]] == []


def test_overview_attention_reasons(client):
    p = _program(client, "Gap U")  # seeded: blank deadline, blank requirements
    kinds = {
        i["kind"] for i in client.get("/api/dashboard/overview").json()["attention"]
        if i["program_id"] == p["id"]
    }
    assert kinds == {"no_deadline_date", "missing_requirements"}

    _set_requirement(client, p["id"], "gre", "Not required")
    _set_requirement(client, p["id"], "toefl", "100", confirmed=True)
    _set_requirement(client, p["id"], "app_fee", "$85", confirmed=True)
    dash = client.get("/api/dashboard/overview").json()
    items = [i for i in dash["attention"] if i["program_id"] == p["id"]]
    assert {i["kind"] for i in items} == {"no_deadline_date", "unverified"}
    assert next(i for i in items if i["kind"] == "unverified")["detail"] == (
        "1 researched fact not confirmed"
    )
    assert dash["unverified_count"] == 1


def test_overview_checklist_and_fees(client):
    a = _program(client, "Fee A")
    b = _program(client, "Fee B")
    c = _program(client, "Fee C")
    _set_requirement(client, a["id"], "app_fee", "$75")
    _set_requirement(client, b["id"], "app_fee", "USD 100")
    _set_requirement(client, c["id"], "app_fee", "Waived")
    _tick(client, a["id"], "cv")

    dash = client.get("/api/dashboard/overview").json()
    assert dash["fee_total"] == 175
    assert (dash["fee_counted"], dash["fee_unknown"]) == (2, 1)

    assert [c["key"] for c in dash["step_columns"]][-1] == "submitted"
    row = next(r for r in dash["checklist"] if r["program_id"] == a["id"])
    assert row["steps"]["cv"] is True
    assert row["steps"]["sop"] is False
    assert row["custom_total"] == 0


def test_summarize_test_requirements():
    from app.routers.dashboard import summarize_test

    # Real shapes from research passes.
    assert summarize_test(
        "Required for international applicants: TOEFL min 90 iBT (or 4.5 on new "
        "scale), IELTS min 6.5, PTE, or Duolingo min 120", "toefl"
    ) == "Required · min 90"
    assert summarize_test(
        "Required for international applicants unless exempt. Accepted tests: "
        "TOEFL iBT (min 100), IELTS (min 7), Duolingo (min 135).", "toefl"
    ) == "Required · min 100"
    assert summarize_test(
        "Required unless waived: TOEFL 79 overall (4.0 on the iBT 2026 scale), "
        "IELTS 6.5", "toefl"
    ) == "Required · min 79"
    assert summarize_test(
        "Required for PhD applicants (not required for Master's applicants)", "gre"
    ) == "Required"
    assert summarize_test(
        "Optional / not required — scores give no advantage", "gre"
    ) == "Optional"
    assert summarize_test("Test-optional — does not require GRE scores", "gre") == "Optional"
    assert summarize_test("Not required", "gre") == "Not required"
    assert summarize_test("GRE scores will not be considered", "gre") == "Not accepted"
    assert summarize_test("Required; minimum GRE 310 total", "gre") == "Required · min 310"
    # A section score isn't a total, so it isn't passed off as a minimum.
    assert summarize_test("Required; Quantitative 160 recommended", "gre") == "Required"
    assert summarize_test("Scores sent via ETS code 6001", "gre") == "See details"
    assert summarize_test("  ", "gre") is None
    assert summarize_test(None, "toefl") is None


def test_summarize_fee():
    from app.routers.dashboard import summarize_fee

    assert summarize_fee("$125, credit/debit cards only") == "$125"
    assert summarize_fee("$100 USD, paid online") == "$100"
    assert summarize_fee("USD 72.50") == "$72.50"
    assert summarize_fee("£80") == "See details"
    assert summarize_fee(None) is None


def test_overview_compare_rows(client):
    p = _program(client, "Compare U")
    _set_requirement(client, p["id"], "toefl", "Required: TOEFL min 90")
    _set_requirement(client, p["id"], "app_fee", "$85 online", confirmed=True)

    row = next(
        r for r in client.get("/api/dashboard/overview").json()["compare"]
        if r["program_id"] == p["id"]
    )
    assert row["toefl"]["text"] == "Required · min 90"
    assert row["toefl"]["detail"] == "Required: TOEFL min 90"
    assert row["toefl"]["source"] == "researched"
    assert row["app_fee"] == {
        "text": "$85",
        "detail": "$85 online",
        "source": "confirmed_by_program",
        "needs_human_verification": False,
    }
    assert row["gre"]["text"] is None  # seeded blank
