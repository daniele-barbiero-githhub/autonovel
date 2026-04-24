# Mappa del flusso applicativo (orientata al **cosa**)

Questo documento descrive il funzionamento di `autonovel` come **sistema a stati e cicli**, concentrandosi su:

- cosa succede in sequenza;
- dove sono i loop decisionali;
- quando vengono scritti/aggiornati i file;
- quali artefatti rappresentano lo stato reale dell'applicazione.

> Focus: comportamento operativo dell'app, non dettagli interni di implementazione.

---

## 1) Vista d'insieme: che tipo di applicazione è

`autonovel` è una pipeline orchestrata che trasforma un'idea (`seed.txt`) in un pacchetto completo di romanzo:

1. **Fondazione narrativa** (mondo, personaggi, outline, voce, canone)
2. **Stesura capitoli**
3. **Revisioni iterative** (automatiche + review profonda)
4. **Export finale** (manoscritto, materiali tipografici, ecc.)

Il centro del controllo è `run_pipeline.py`, che legge e aggiorna `state.json` per sapere:

- in quale fase si trova;
- quanto è avanzato;
- quali soglie qualitative sono già state raggiunte.

---

## 2) Macchina a stati: il "filo rosso" dell'esecuzione

Lo stato persistente è in `state.json`.

Valori principali usati come bussole operative:

- `phase`: `foundation` → `drafting` → `revision` → `export` → `complete`
- `iteration`: numero di iterazione della fase foundation
- `foundation_score`, `lore_score`: qualità della pianificazione
- `chapters_drafted`, `chapters_total`: avanzamento drafting
- `novel_score`, `revision_cycle`: avanzamento revisione

In pratica, ogni run della pipeline è **resume-friendly**: riparte dalla fase indicata in `state.json` e prosegue.

---

## 3) Flusso step-by-step (end-to-end)

## Step A — Bootstrap / Ripresa

### Input
- `seed.txt` (obbligatorio se si avvia da zero)
- `state.json` (se si riprende una run)

### Cosa accade
1. Se `--from-scratch`: resetta stato a valori iniziali.
2. Crea directory operative se mancanti (`chapters/`, `briefs/`, `edit_logs/`, `eval_logs/`).
3. Decide quali fasi eseguire:
   - una singola fase (`--phase ...`) oppure
   - tutte le fasi da quella corrente in avanti.

### Scritture
- `state.json` viene scritto subito in caso di reset.

---

## Step B — Fase Foundation (loop di pianificazione)

Obiettivo: produrre una base narrativa robusta e coerente.

### Sequenza funzionale per iterazione
Per ogni iterazione:
1. genera/rigenera world bible;
2. genera/rigenera personaggi;
3. genera/rigenera outline (parte 1);
4. completa foreshadowing ledger (parte 2 outline);
5. genera/rigenera canone dei fatti;
6. aggiorna fingerprint della voce;
7. valuta la qualità foundation.

### Loop decisionale (keep/discard)
Dopo la valutazione:
- se il punteggio migliora rispetto al migliore precedente:
  - **keep**: commit e avanzamento stato;
- altrimenti:
  - **discard**: reset hard delle modifiche dell'iterazione.

### Condizione di uscita
- esce quando `foundation_score >= 7.5` (o quando raggiunge il limite massimo di iterazioni).

### Scritture principali
- `world.md`
- `characters.md`
- `outline.md`
- `canon.md`
- `voice.md` (parte variabile)
- `results.tsv` (log tabellare di keep/discard)
- `state.json` (aggiornamento metriche e passaggio a `drafting`)

---

## Step C — Fase Drafting (loop per capitolo + loop tentativi)

Obiettivo: completare tutti i capitoli pianificati.

### Sequenza funzionale per capitolo
Per ogni capitolo da `chapters_drafted + 1` a `chapters_total`:
1. genera bozza capitolo (`draft_chapter.py`);
2. verifica che il file capitolo esista e non sia vuoto;
3. valuta il capitolo (`evaluate.py --chapter=N`);
4. decide keep/discard.

### Loop annidati
1. **Loop esterno**: capitoli in ordine sequenziale.
2. **Loop interno**: fino a 5 tentativi per capitolo (`MAX_CHAPTER_ATTEMPTS`).

### Regola decisionale
- se `score >= 6.0`: keep + commit + avanzamento;
- se `score < 6.0`: discard dell'output del tentativo e retry;
- se finisce i tentativi: keep "best effort" dell'ultimo disponibile.

### Contesto usato in scrittura capitolo
La generazione capitolo usa:
- `voice.md`, `world.md`, `characters.md`, `outline.md`, `canon.md`;
- coda del capitolo precedente;
- breve preview del capitolo successivo (continuità).

### Scritture principali
- `chapters/ch_XX.md`
- `results.tsv`
- `state.json` (contatore capitoli, poi passaggio a `revision`)

---

## Step D — Fase Revision (cicli qualitativi con plateau detection)

Obiettivo: migliorare il romanzo intero, non solo singoli capitoli.

### Sequenza funzionale per ciclo
Per ogni ciclo di revisione:
1. passaggio adversarial su tutti i capitoli (trova tagli/cicatrici);
2. tagli meccanici (se disponibile `apply_cuts.py`);
3. valutazione panel lettori (`reader_panel.py`);
4. estrazione dei punti di consenso;
5. revisioni mirate su capitoli prioritari;
6. valutazione complessiva del romanzo;
7. commit di ciclo e aggiornamento stato.

### Loop decisionali interni
- per ogni item di consenso:
  - misura score pre;
  - genera/recupera brief;
  - rigenera il capitolo;
  - misura score post;
  - **keep** se migliora/non peggiora, **revert** se peggiora.

### Plateau detection (uscita anticipata)
Dopo almeno 3 cicli:
- se miglioramento `novel_score` < `0.3`, la revisione si ferma.

### Scritture principali
- `edit_logs/*.json` (panel, adversarial, review parse)
- `briefs/*.md` (brief di revisione)
- `chapters/ch_XX.md` (solo capitoli toccati)
- `results.tsv`
- `state.json` (`revision_cycle`, `novel_score`, avanzamento fase)

---

## Step E — Fase 3b Opus Review Loop (rifinitura profonda)

Sub-loop opzionale se `review.py` esiste.

### Sequenza per round
1. invia manoscritto completo a Opus e salva review;
2. parse della review in item azionabili;
3. controlla condizioni di stop qualitative;
4. genera brief automatico e applica una revisione prioritaria;
5. applica cleanup meccanico.

### Condizioni di stop
Il loop si interrompe in anticipo se la review indica maturità (es. stelle alte + assenza problemi maggiori non qualificati).

### Scritture principali
- `reviews.md` (se richiesto come output)
- `edit_logs/*_review.json`
- `briefs/*_auto.md`
- eventuali `chapters/ch_XX.md` rivisti

---

## Step F — Fase Export (assemblaggio artefatti finali)

Obiettivo: produrre i deliverable finali dal corpus dei capitoli.

### Sequenza funzionale
1. rigenera `outline.md` dai capitoli (se tool presente);
2. rigenera `arc_summary.md` (se tool presente);
3. concatena tutti i capitoli in `manuscript.md`;
4. genera contenuti LaTeX (`typeset/build_tex.py`);
5. se `tectonic` è disponibile, prova build PDF;
6. commit finale export.

### Scritture principali
- `outline.md` (rigenerato)
- `arc_summary.md`
- `manuscript.md`
- output tipografici sotto `typeset/` (se tool disponibili)
- `results.tsv`
- `state.json` → `phase: complete`

---

## 4) Dove sono i loop (mappa rapida)

1. **Loop Foundation**
   - unità: iterazione di pianificazione
   - stop: soglia score o max iterazioni

2. **Loop Drafting (esterno)**
   - unità: capitolo
   - stop: capitoli completati

3. **Loop Drafting (interno)**
   - unità: tentativo capitolo
   - stop: score soglia o max tentativi

4. **Loop Revision**
   - unità: ciclo revisione globale
   - stop: plateau o max cicli

5. **Loop per item consenso (dentro Revision)**
   - unità: issue capitolo-specifica
   - stop: fine item selezionati del ciclo

6. **Loop Opus Review**
   - unità: round review profonda
   - stop: criterio qualitativo o limite round

---

## 5) Dove e quando si scrive cosa (tracciabilità)

## File di controllo
- `state.json`: scritto a ogni avanzamento significativo.
- `results.tsv`: append a ogni decisione keep/discard/cycle/export.

## File contenuto narrativo
- Pianificazione: `world.md`, `characters.md`, `outline.md`, `canon.md`, `voice.md`.
- Prosa: `chapters/ch_XX.md`.
- Assemblato: `manuscript.md`, `arc_summary.md`.

## File di diagnostica/revisione
- `eval_logs/*.json`: output valutazioni.
- `edit_logs/*.json`: panel, adversarial, review parse.
- `briefs/*.md`: istruzioni puntuali per riscrittura capitoli.

---

## 6) Criteri di decisione (in termini di prodotto)

- **Foundation**: qualità sistemica della base narrativa (`>=7.5`).
- **Drafting**: qualità minima per capitolo (`>=6.0`).
- **Revision**: miglioramento del punteggio complessivo + assenza plateau.
- **Review profonda**: riduzione dei problemi maggiori fino a condizioni di stop.

Interpretazione pratica:
- il sistema privilegia progresso controllato;
- evita regressioni tramite revert;
- conserva una storia completa delle decisioni in `results.tsv` + git commit.

---

## 7) Mappa operativa minima (se devi spiegare il progetto in 30 secondi)

1. Legge stato corrente (`state.json`).
2. Esegue la fase corrente in pipeline.
3. Dopo ogni output importante: valuta.
4. Se migliora: tiene e committa; se peggiora: scarta/reverte.
5. Aggiorna stato e passa alla fase successiva.
6. Termina in `complete` con artefatti finali pronti.

---

## 8) Nota su "cosa fa" vs "come lo fa"

Il progetto non è un semplice generatore di testo: è un **sistema di produzione narrativa con controllo qualità iterativo**.

Il suo comportamento principale non è "scrivere un capitolo", ma:

- orchestrare sottotool specializzati;
- misurare continuamente output;
- prendere decisioni automatiche keep/discard;
- convergere verso un risultato completo e pubblicabile.
