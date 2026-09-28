# Influencer outreach – @tommibernaa

Sistema per trovare brand di moda compatibili, preparare email personalizzate e gestire invii e follow-up via Gmail,
con approvazione manuale a ogni passo. Le regole operative per Claude sono in [`CLAUDE.md`](CLAUDE.md).

## Struttura

| File | Contenuto |
|---|---|
| `data/brands.csv` | Database dei brand (69 al 28/09/2026): contatti, fonte, compatibilità, priorità, stato, date, ID Gmail |
| `emails/drafts.json` | Bozze email (44), stato di approvazione, follow-up |
| `emails/REVIEW.md` | Documento di revisione: tabella + testo completo di ogni email |
| `data/previous_contacts.csv` | Contatti già avuti in passato (dalla cartella Inviati), bloccati dal preflight |
| `data/do_not_contact.csv` | Chi ha chiesto di non essere contattato |
| `outreach.py` | CLI per review, approvazione, controlli pre-invio, registrazione invii e follow-up (non invia email) |

## Campi del database

`id, brand, website, instagram, tiktok, email, contact_type, collab_page, category, country, source, compatibility,
priority, status, date_contacted, follow_up_date, response, gmail_message_id, gmail_thread_id, notes`

- `priority`: **ALTA** (molto compatibile e aperto a collaborazioni) · **MEDIA** (buona compatibilità, meno evidenze) ·
  **BASSA** (compatibilità debole o contatto poco adatto, es. solo customer care). Serve solo per ordinare la revisione.
- `status`: `DA CONTATTARE` → `CONTATTATO` → `FOLLOW-UP INVIATO` / `RISPOSTO` / `INTERESSATO` / `NON INTERESSATO` /
  `COLLABORAZIONE ATTIVA` / `NON CONTATTARE`.

## Flusso

```bash
python3 outreach.py review                 # tabella Brand | Email | Categoria | Priorità | Oggetto
python3 outreach.py show B001 B004         # testo completo
python3 outreach.py approve B001 B004      # oppure --priority ALTA, oppure --all
python3 outreach.py preflight              # controlli prima dell'invio
# invio via Gmail (Claude), una email alla volta, poi:
python3 outreach.py mark-sent B001 --message-id <id> --thread-id <thread>
python3 outreach.py followups              # brand senza risposta da ≥7 giorni + bozza follow-up
python3 outreach.py set-response B001 RISPOSTO --text "Interessati, chiedono indirizzo"
python3 outreach.py export-review          # rigenera emails/REVIEW.md
python3 outreach.py stats
```

In pratica basta chiedere a Claude in chat: "mostrami la review", "approva B001, B004 e B006", "invia le approvate",
"ci sono follow-up da fare?".
