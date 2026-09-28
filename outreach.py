#!/usr/bin/env python3
"""Influencer outreach helper for @tommibernaa.

This script never sends email. It manages the brand database, the approval
state of each draft, the pre-send checks and the post-send bookkeeping.
Sending happens through the Gmail integration, only after explicit approval.

Usage:
  python3 outreach.py review [--priority ALTA] [--all]
  python3 outreach.py show ID [ID ...]
  python3 outreach.py approve (ID ... | --priority P | --all)
  python3 outreach.py unapprove ID [ID ...]
  python3 outreach.py preflight [ID ...]
  python3 outreach.py mark-sent ID --message-id M [--thread-id T] [--date YYYY-MM-DD]
  python3 outreach.py followups [--days 7] [--today YYYY-MM-DD]
  python3 outreach.py approve-followup ID [ID ...]
  python3 outreach.py mark-followup-sent ID --message-id M [--date YYYY-MM-DD]
  python3 outreach.py mark-bounced ID [--note "..."]
  python3 outreach.py set-response ID STATUS [--text "..."]
  python3 outreach.py do-not-contact ID [--reason "..."]
  python3 outreach.py export-review
  python3 outreach.py stats
"""
import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
BRANDS_CSV = ROOT / "data" / "brands.csv"
DNC_CSV = ROOT / "data" / "do_not_contact.csv"
PREVIOUS_CSV = ROOT / "data" / "previous_contacts.csv"
DRAFTS_JSON = ROOT / "emails" / "drafts.json"
REVIEW_MD = ROOT / "emails" / "REVIEW.md"

NO_EMAIL = "email non trovata"
PRIORITIES = ("ALTA", "MEDIA", "BASSA")
FOLLOW_UP_DAYS = 7
SIGNATURE = "Tommy\nTikTok: @tommibernaa"
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
# Freemail domains are allowed but flagged: a business/PR address is preferred.
FREEMAIL = {"gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "libero.it", "icloud.com"}


# ---------------------------------------------------------------- storage --

def load_brands():
    with BRANDS_CSV.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def save_brands(fields, rows):
    with BRANDS_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def load_drafts():
    return json.loads(DRAFTS_JSON.read_text(encoding="utf-8"))


def save_drafts(drafts):
    DRAFTS_JSON.write_text(json.dumps(drafts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_simple_csv(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def today(arg=None):
    return dt.date.fromisoformat(arg) if arg else dt.date.today()


def by_id(items):
    return {x["id"]: x for x in items}


def domain_of(value):
    value = (value or "").strip().lower()
    if "@" in value:
        return value.rsplit("@", 1)[1]
    host = urlparse(value if "://" in value else f"https://{value}").hostname or ""
    return host[4:] if host.startswith("www.") else host


def die(msg):
    print(f"ERRORE: {msg}", file=sys.stderr)
    sys.exit(1)


def resolve_ids(ids, items):
    known = by_id(items)
    out = []
    for i in ids:
        i = i.upper()
        if i not in known:
            die(f"id sconosciuto: {i}")
        out.append(i)
    return out


def table(headers, rows):
    widths = [len(h) for h in headers]
    for r in rows:
        widths = [max(w, len(str(c))) for w, c in zip(widths, r)]
    line = lambda cells: "| " + " | ".join(str(c).ljust(w) for c, w in zip(cells, widths)) + " |"
    print(line(headers))
    print("|" + "|".join("-" * (w + 2) for w in widths) + "|")
    for r in rows:
        print(line(r))


# --------------------------------------------------------------- commands --

def cmd_review(args):
    _, brands = load_brands()
    brands = by_id(brands)
    drafts = load_drafts()
    order = {p: n for n, p in enumerate(PRIORITIES)}
    rows = []
    for d in drafts:
        b = brands[d["id"]]
        if not args.all and (d["sent_at"] or b["status"] != "DA CONTATTARE"):
            continue
        if args.priority and b["priority"] != args.priority:
            continue
        rows.append((order[b["priority"]], d["id"], b["brand"], d["to"], b["category"],
                     b["priority"], d["subject"], d["approval"]))
    rows.sort()
    table(["ID", "Brand", "Email", "Categoria", "Priorità", "Oggetto", "Approvazione"],
          [r[1:] for r in rows])
    print(f"\n{len(rows)} bozze. Nessuna email viene inviata da questo comando.")


def cmd_show(args):
    drafts = load_drafts()
    for i in resolve_ids(args.ids, drafts):
        d = by_id(drafts)[i]
        print(f"=== {d['id']} · {d['brand']} · {d['approval']} ===")
        print(f"A: {d['to']}\nOggetto: {d['subject']}\n")
        print(d["body"])
        print()


def cmd_approve(args):
    _, brands = load_brands()
    brands = by_id(brands)
    drafts = load_drafts()
    if args.all:
        targets = [d["id"] for d in drafts]
    elif args.priority:
        targets = [d["id"] for d in drafts if brands[d["id"]]["priority"] == args.priority]
    else:
        targets = resolve_ids(args.ids, drafts)
    if not targets:
        die("nessuna bozza selezionata")
    now = dt.datetime.now().isoformat(timespec="seconds")
    idx = by_id(drafts)
    changed = []
    for i in targets:
        d = idx[i]
        if d["sent_at"] or brands[i]["status"] != "DA CONTATTARE":
            continue
        d["approval"], d["approved_at"] = "APPROVED", now
        changed.append(i)
    save_drafts(drafts)
    print(f"Approvate {len(changed)} bozze: {', '.join(changed) or '-'}")


def cmd_unapprove(args):
    drafts = load_drafts()
    idx = by_id(drafts)
    for i in resolve_ids(args.ids, drafts):
        idx[i]["approval"], idx[i]["approved_at"] = "PENDING", ""
    save_drafts(drafts)
    print("Fatto.")


def preflight_checks(draft, brand, drafts, dnc, previous):
    """Return (errors, warnings) for one draft."""
    errors, warnings = [], []
    to = draft["to"].strip().lower()
    dom = domain_of(to)

    if draft["approval"] != "APPROVED":
        errors.append("bozza non approvata")
    if draft["sent_at"]:
        errors.append(f"già inviata il {draft['sent_at']}")
    if brand["status"] != "DA CONTATTARE":
        errors.append(f"stato brand = {brand['status']}")
    if not EMAIL_RE.match(to):
        errors.append(f"indirizzo non valido: {to!r}")
    if to != brand["email"].strip().lower():
        errors.append("destinatario diverso dall'email nel database")

    for other in drafts:
        if other["id"] != draft["id"] and other["to"].strip().lower() == to and \
                (other["sent_at"] or other["approval"] == "APPROVED"):
            errors.append(f"destinatario duplicato con {other['id']} ({other['brand']})")

    for row in dnc:
        v = (row.get("value") or "").strip().lower()
        if v and v in (to, dom, brand["brand"].lower()):
            errors.append(f"in do_not_contact: {row.get('reason', '')}")
    for row in previous:
        v = (row.get("email_or_domain") or "").strip().lower()
        if v and v in (to, dom):
            errors.append(f"contattato in passato: {row.get('date', '')} {row.get('note', '')}")

    body = draft["body"]
    if brand["brand"] not in body:
        errors.append("il corpo non cita il nome del brand")
    if not body.rstrip().endswith(SIGNATURE):
        errors.append("firma mancante o diversa")
    if "26K" not in body:
        errors.append("manca il riferimento ai ~26K follower")
    if re.search(r"[{}]|TODO|XXX", body + draft["subject"]):
        errors.append("segnaposto non compilato")
    if not draft["subject"].strip():
        errors.append("oggetto vuoto")

    site = domain_of(brand["website"])
    if site and dom != site and not dom.endswith("." + site) and not site.endswith("." + dom):
        warnings.append(f"dominio email ({dom}) diverso dal sito ({site})")
    if dom in FREEMAIL:
        warnings.append("indirizzo freemail: preferire un contatto business se esiste")
    if "customer" in brand["contact_type"] or "ordini" in brand["contact_type"]:
        warnings.append(f"contatto di tipo '{brand['contact_type']}' (non marketing/PR)")
    return errors, warnings


def cmd_preflight(args):
    _, brands = load_brands()
    brands = by_id(brands)
    drafts = load_drafts()
    dnc = load_simple_csv(DNC_CSV)
    previous = load_simple_csv(PREVIOUS_CSV)
    ids = resolve_ids(args.ids, drafts) if args.ids else \
        [d["id"] for d in drafts if d["approval"] == "APPROVED" and not d["sent_at"]]
    if not ids:
        print("Nessuna bozza approvata in attesa di invio.")
        return
    idx = by_id(drafts)
    ok = 0
    for i in ids:
        errors, warnings = preflight_checks(idx[i], brands[i], drafts, dnc, previous)
        status = "OK" if not errors else "BLOCCATA"
        ok += not errors
        print(f"[{status}] {i} {idx[i]['brand']} -> {idx[i]['to']}")
        for e in errors:
            print(f"    ✗ {e}")
        for w in warnings:
            print(f"    ! {w}")
    print(f"\n{ok}/{len(ids)} pronte. Ricorda: prima dell'invio cerca in Gmail 'in:sent to:<email>'.")
    if ok != len(ids):
        sys.exit(2)


def cmd_mark_sent(args):
    fields, rows = load_brands()
    brands = by_id(rows)
    drafts = load_drafts()
    [i] = resolve_ids([args.id], drafts)
    d = by_id(drafts)[i]
    if d["sent_at"]:
        die(f"{i} risulta già inviata il {d['sent_at']}")
    sent = today(args.date)
    b = brands[i]
    b["status"] = "CONTATTATO"
    b["date_contacted"] = sent.isoformat()
    b["follow_up_date"] = (sent + dt.timedelta(days=FOLLOW_UP_DAYS)).isoformat()
    b["gmail_message_id"] = args.message_id
    b["gmail_thread_id"] = args.thread_id or ""
    d["sent_at"] = sent.isoformat()
    save_brands(fields, rows)
    save_drafts(drafts)
    print(f"{i} {b['brand']}: CONTATTATO il {b['date_contacted']}, follow-up dal {b['follow_up_date']}")


def cmd_mark_bounced(args):
    fields, rows = load_brands()
    brands = by_id(rows)
    [i] = resolve_ids([args.id], rows)
    b = brands[i]
    if b["status"] != "CONTATTATO":
        die(f"{i} ha stato {b['status']}: si registra un rimbalzo solo dopo un invio")
    b["status"] = "EMAIL RIMBALZATA"
    b["follow_up_date"] = ""
    note = f"rimbalzata {dt.date.today().isoformat()}" + (f": {args.note}" if args.note else "")
    b["notes"] = (b["notes"] + " | " + note).strip(" |")
    save_brands(fields, rows)
    print(f"{i} {b['brand']}: EMAIL RIMBALZATA (nessun follow-up). Cercare un contatto alternativo.")


FOLLOWUP_IT = (
    "Ciao team {brand},\n\n"
    "vi riscrivo solo per riportare in cima la mia mail di qualche giorno fa: mi farebbe davvero piacere "
    "creare dei contenuti TikTok con {brand}, partendo anche solo dall'invio di qualche prodotto. "
    "Se non è il momento giusto nessun problema, fatemelo sapere e non vi disturbo più.\n\n"
    "Grazie!\n\n" + SIGNATURE
)
FOLLOWUP_EN = (
    "Hi {brand} team,\n\n"
    "just bumping my email from last week: I'd really love to create some TikTok content with {brand}, "
    "even starting with just a few products. If it's not the right time, no worries at all, just let me "
    "know and I won't follow up again.\n\n"
    "Thanks!\n\n" + SIGNATURE
)


def cmd_followups(args):
    _, rows = load_brands()
    drafts = load_drafts()
    idx = by_id(drafts)
    now = today(args.today)
    due = []
    for b in rows:
        if b["status"] != "CONTATTATO" or b["response"].strip() or not b["date_contacted"]:
            continue
        first = dt.date.fromisoformat(b["date_contacted"])
        days = (now - first).days
        if days < args.days:
            continue
        d = idx[b["id"]]
        if d.get("followup") and d["followup"].get("sent_at"):
            continue
        if not d.get("followup"):
            tmpl = FOLLOWUP_IT if d["language"] == "it" else FOLLOWUP_EN
            d["followup"] = {
                "subject": "Re: " + d["subject"],
                "body": tmpl.format(brand=b["brand"]),
                "approval": "PENDING", "approved_at": "", "sent_at": "",
                "gmail_message_id": "",
            }
        due.append((b["id"], b["brand"], b["date_contacted"], days, "sì, bozza pronta"))
    save_drafts(drafts)
    if not due:
        print("Nessun follow-up da fare.")
        return
    table(["ID", "Brand", "Data primo contatto", "Giorni trascorsi", "Follow-up consigliato"], due)
    print("\nBozze di follow-up salvate in emails/drafts.json (campo 'followup'). "
          "Mostrale con: python3 outreach.py show-followup ID. Nessun invio automatico.")


def cmd_show_followup(args):
    drafts = load_drafts()
    for i in resolve_ids(args.ids, drafts):
        d = by_id(drafts)[i]
        f = d.get("followup")
        if not f:
            print(f"{i}: nessun follow-up generato (esegui prima 'followups').")
            continue
        print(f"=== FOLLOW-UP {i} · {d['brand']} · {f['approval']} ===")
        print(f"A: {d['to']} (stesso thread)\nOggetto: {f['subject']}\n")
        print(f["body"])
        print()


def cmd_approve_followup(args):
    drafts = load_drafts()
    idx = by_id(drafts)
    now = dt.datetime.now().isoformat(timespec="seconds")
    for i in resolve_ids(args.ids, drafts):
        f = idx[i].get("followup")
        if not f:
            die(f"{i}: nessun follow-up generato")
        f["approval"], f["approved_at"] = "APPROVED", now
    save_drafts(drafts)
    print("Follow-up approvati.")


def cmd_mark_followup_sent(args):
    fields, rows = load_brands()
    brands = by_id(rows)
    drafts = load_drafts()
    [i] = resolve_ids([args.id], drafts)
    f = by_id(drafts)[i].get("followup")
    if not f or f["approval"] != "APPROVED":
        die(f"{i}: follow-up non approvato")
    f["sent_at"] = today(args.date).isoformat()
    f["gmail_message_id"] = args.message_id
    b = brands[i]
    b["status"] = "FOLLOW-UP INVIATO"
    b["notes"] = (b["notes"] + f" | follow-up {f['sent_at']} ({args.message_id})").strip(" |")
    save_brands(fields, rows)
    save_drafts(drafts)
    print(f"{i} {b['brand']}: FOLLOW-UP INVIATO il {f['sent_at']}")


RESPONSE_STATUSES = ("RISPOSTO", "INTERESSATO", "NON INTERESSATO", "COLLABORAZIONE ATTIVA", "NON CONTATTARE")


def cmd_set_response(args):
    fields, rows = load_brands()
    brands = by_id(rows)
    [i] = resolve_ids([args.id], rows)
    status = args.status.upper()
    if status not in RESPONSE_STATUSES:
        die(f"stato non valido, usa uno di: {', '.join(RESPONSE_STATUSES)}")
    b = brands[i]
    b["status"] = status
    if args.text:
        b["response"] = args.text
    save_brands(fields, rows)
    if status == "NON CONTATTARE":
        add_dnc(b, args.text or "richiesta del destinatario")
    print(f"{i} {b['brand']}: {status}")


def add_dnc(brand, reason):
    drafts = load_drafts()
    for d in drafts:
        if d["id"] == brand["id"] and not d["sent_at"]:
            d["approval"], d["approved_at"] = "BLOCKED", ""
    save_drafts(drafts)
    exists = DNC_CSV.exists()
    with DNC_CSV.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["value", "brand", "date", "reason"])
        if not exists:
            w.writeheader()
        value = brand["email"] if brand["email"] != NO_EMAIL else domain_of(brand["website"])
        w.writerow({"value": value, "brand": brand["brand"],
                    "date": dt.date.today().isoformat(), "reason": reason})


def cmd_do_not_contact(args):
    fields, rows = load_brands()
    brands = by_id(rows)
    [i] = resolve_ids([args.id], rows)
    brands[i]["status"] = "NON CONTATTARE"
    save_brands(fields, rows)
    add_dnc(brands[i], args.reason or "richiesta del destinatario")
    print(f"{i} {brands[i]['brand']} aggiunto a do_not_contact.")


def cmd_export_review(args):
    _, brands = load_brands()
    brands = by_id(brands)
    drafts = load_drafts()
    order = {p: n for n, p in enumerate(PRIORITIES)}
    drafts = sorted(drafts, key=lambda d: (order[brands[d["id"]]["priority"]], d["id"]))
    sent = sum(bool(d["sent_at"]) for d in drafts)
    out = ["# REVIEW – bozze email", "",
           f"Generato il {dt.date.today().isoformat()} · {len(drafts)} bozze · {sent} inviate. "
           "Per approvare: `python3 outreach.py approve ID ...` (o chiedilo a Claude in chat).", "",
           "| ID | Brand | Email | Categoria | Priorità | Oggetto | Approvazione | Stato |",
           "|---|---|---|---|---|---|---|---|"]
    for d in drafts:
        b = brands[d["id"]]
        out.append(f"| {d['id']} | {b['brand']} | {d['to']} | {b['category']} | {b['priority']} "
                   f"| {d['subject']} | {d['approval']} | {b['status']} |")
    out += ["", "---", ""]
    for d in drafts:
        b = brands[d["id"]]
        out += [f"## {d['id']} · {b['brand']} ({b['priority']})", "",
                f"- **Destinatario:** {d['to']} ({b['contact_type']})",
                f"- **Oggetto:** {d['subject']}",
                f"- **Fonte contatto:** {b['source']}"]
        if b["notes"]:
            out.append(f"- **Note:** {b['notes']}")
        out += ["", "```text", d["body"], "```", ""]
    REVIEW_MD.write_text("\n".join(out), encoding="utf-8")
    print(f"Scritto {REVIEW_MD.relative_to(ROOT)} ({len(drafts)} bozze)")


def cmd_stats(args):
    _, rows = load_brands()
    drafts = load_drafts()
    count = lambda key: {v: sum(1 for r in rows if r[key] == v) for v in sorted({r[key] for r in rows})}
    print(f"Brand totali: {len(rows)}")
    print(f"Con email: {sum(1 for r in rows if r['email'] != NO_EMAIL)}")
    print(f"Priorità: {count('priority')}")
    print(f"Stato: {count('status')}")
    print(f"Bozze: {len(drafts)} (approvate: {sum(d['approval'] == 'APPROVED' for d in drafts)}, "
          f"inviate: {sum(bool(d['sent_at']) for d in drafts)})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("review"); p.add_argument("--priority", choices=PRIORITIES); p.add_argument("--all", action="store_true"); p.set_defaults(fn=cmd_review)
    p = sub.add_parser("show"); p.add_argument("ids", nargs="+"); p.set_defaults(fn=cmd_show)
    p = sub.add_parser("approve"); p.add_argument("ids", nargs="*"); p.add_argument("--priority", choices=PRIORITIES); p.add_argument("--all", action="store_true"); p.set_defaults(fn=cmd_approve)
    p = sub.add_parser("unapprove"); p.add_argument("ids", nargs="+"); p.set_defaults(fn=cmd_unapprove)
    p = sub.add_parser("preflight"); p.add_argument("ids", nargs="*"); p.set_defaults(fn=cmd_preflight)
    p = sub.add_parser("mark-sent"); p.add_argument("id"); p.add_argument("--message-id", required=True); p.add_argument("--thread-id"); p.add_argument("--date"); p.set_defaults(fn=cmd_mark_sent)
    p = sub.add_parser("followups"); p.add_argument("--days", type=int, default=FOLLOW_UP_DAYS); p.add_argument("--today"); p.set_defaults(fn=cmd_followups)
    p = sub.add_parser("show-followup"); p.add_argument("ids", nargs="+"); p.set_defaults(fn=cmd_show_followup)
    p = sub.add_parser("approve-followup"); p.add_argument("ids", nargs="+"); p.set_defaults(fn=cmd_approve_followup)
    p = sub.add_parser("mark-followup-sent"); p.add_argument("id"); p.add_argument("--message-id", required=True); p.add_argument("--date"); p.set_defaults(fn=cmd_mark_followup_sent)
    p = sub.add_parser("mark-bounced"); p.add_argument("id"); p.add_argument("--note"); p.set_defaults(fn=cmd_mark_bounced)
    p = sub.add_parser("set-response"); p.add_argument("id"); p.add_argument("status"); p.add_argument("--text"); p.set_defaults(fn=cmd_set_response)
    p = sub.add_parser("do-not-contact"); p.add_argument("id"); p.add_argument("--reason"); p.set_defaults(fn=cmd_do_not_contact)
    p = sub.add_parser("export-review"); p.set_defaults(fn=cmd_export_review)
    p = sub.add_parser("stats"); p.set_defaults(fn=cmd_stats)

    args = ap.parse_args()
    if args.cmd == "approve" and not (args.ids or args.priority or args.all):
        ap.error("approve: indica degli ID, --priority o --all")
    args.fn(args)


if __name__ == "__main__":
    main()
