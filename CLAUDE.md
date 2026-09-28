# Regole operative – Influencer outreach @tommibernaa

Questo repository è il sistema di outreach di Tommy (TikTok @tommibernaa, ~26K follower) verso brand di moda.
Le regole sotto valgono per ogni sessione di Claude Code che lavora qui. Sono vincolanti.

## Profilo (usare solo questi dati)

- Creator: Tommy / Tommaso · TikTok **@tommibernaa** · **circa 26K follower**
- Contenuti: intrattenimento, lifestyle, nightlife, social/IRL · pubblico giovane · mercato Italia
- Proposta base: prodotti/abbigliamento in cambio di contenuti TikTok, aperti ad altre modalità
- Firma email, sempre identica:
  ```
  Tommy
  TikTok: @tommibernaa
  ```
- Non citare l'account Instagram nelle email finché Tommy non conferma che è di nuovo attivo
  (ad agosto 2026 risultava disattivato, vedi cartella Inviati di Gmail).

## Mai inventare

Email, nomi di persone, statistiche (views, engagement, reach), collaborazioni passate, informazioni sui brand.
Ogni personalizzazione di un'email deve basarsi su un fatto trovato durante la ricerca e annotato in `data/brands.csv`
(`source`, `compatibility`, `notes`). Se un'email non si trova: scrivere `email non trovata` e tenere sito/pagina contatti.

## Invio: solo dopo approvazione esplicita

1. Nessuna email parte senza un'approvazione esplicita di Tommy **nella conversazione corrente**, riferita a brand precisi
   (es. "approva B001, B004" o "approva tutte le ALTA"). Un'approvazione passata non vale per nuovi invii.
2. Registrare l'approvazione: `python3 outreach.py approve ID ...`
3. Prima di ogni invio:
   - `python3 outreach.py preflight ID` deve dare `OK` (destinatario valido, brand corretto, firma, nessun duplicato,
     stato `DA CONTATTARE`, non in `do_not_contact.csv` né in `previous_contacts.csv`);
   - cercare in Gmail `in:sent to:<email>` e `in:sent <dominio>`: se esiste già un invio, fermarsi e chiedere.
4. Inviare **una email alla volta** con lo strumento Gmail `send_message`, usando esattamente `to`, `subject` e `body`
   della bozza in `emails/drafts.json` (testo semplice, niente Markdown).
5. Subito dopo ogni invio: `python3 outreach.py mark-sent ID --message-id <id> --thread-id <threadId>`
   (imposta `CONTATTATO`, `date_contacted` = oggi, `follow_up_date` = +7 giorni, salva gli ID Gmail).
6. Mai invii in massa non approvati. Preferire sempre contatti business/PR a indirizzi personali o nominativi.

## Follow-up

- `python3 outreach.py followups` elenca i brand senza risposta da almeno 7 giorni e prepara una bozza breve.
- Mostrare la lista a Tommy (Brand | Data primo contatto | Giorni trascorsi | Follow-up consigliato) e **attendere
  approvazione** (`approve-followup ID`). Inviare nello stesso thread (`replyThreadId` = `gmail_thread_id`),
  poi `mark-followup-sent ID --message-id <id>`. Massimo un follow-up per brand.
- Prima di proporre follow-up, controllare in Gmail se il brand ha risposto (`from:<dominio>`); se sì,
  aggiornare con `set-response ID RISPOSTO --text "..."`.

## Opt-out

Se un destinatario chiede di non essere contattato: `python3 outreach.py set-response ID "NON CONTATTARE" --text "..."`.
Il brand finisce in `data/do_not_contact.csv` e il preflight blocca ogni invio futuro.

## Note ambiente

Nei container cloud la rete può bloccare i siti dei brand (WebFetch/curl): la ricerca si fa con WebSearch,
verificando gli indirizzi con una ricerca esatta (`"indirizzo@dominio"`) e annotando la fonte.
