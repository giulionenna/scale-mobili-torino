# Censimento documentale della metropolitana M1

Ricerca completata il 16 ottobre 2026: **23 stazioni, 142 scale mobili e 73 ascensori** nella tratta Fermi–Bengasi. Ogni impianto ha un ID interno immutabile, la matricola così riportata dal documento, collegamento tra piani, costruttore, anno di messa in esercizio e riferimento alla pagina della fonte. Non sono stati effettuati sopralluoghi né importati stati di funzionamento.

## Fonti primarie e perimetro

- [GTT: linea in esercizio e mappa](https://www.gtt.to.it/cms/linee-e-orari/torino-e-cintura/urbana/240-metropolitana.html), consultata il 16 ottobre 2026: nomi, ordine e capolinea delle 23 stazioni.
- [GTT: fermata Italia 61–Regione Piemonte](https://www.gtt.to.it/cms/percorari/urbano?bacino=U&linea=METRO&palina=8232&realtime=true&view=palina): denominazione estesa della stazione.
- [GTT PA 58/2026](https://gtt-to.acquistitelematici.it/tender/7773), allegato 2B, pagine 2–5, pubblicato il 31 marzo 2026: 142 scale mobili con matricola, posizione, direzione prevista, dislivello e numero di gradini. Le caratteristiche tecniche sono indicative e il documento chiede la verifica sull’impianto.
- [GTT PA 82/2025](https://gtt-to.acquistitelematici.it/tender/5133), allegato 2, revisione 21 marzo 2025, pagine 5–7, pubblicato il 28 aprile 2025: 73 ascensori nelle stazioni. I 7 ascensori del comprensorio tecnico di Collegno, pagina 3, sono esclusi dal censimento passeggeri.
- [GTT: schemi e manutenzioni straordinarie](https://www.gtt.to.it/cms/en/19-linee-e-orari/urbana/12186-metropolitana-aggiornamento-ascensori-e-scale-mobili), schemi datati 16 ottobre 2026: confermano i totali 142 e 73. Non consentono di collegare senza ambiguità ogni casella colorata a una matricola.

I documenti originali sono conservati nell’archivio privato; nel dataset compaiono URL, nome del PDF interno allo ZIP, numero di pagina, SHA256 del PDF e dello ZIP, pubblicazione e acquisizione. Non vengono ripubblicati PDF, mappe o immagini GTT.

## Elenco delle stazioni

| Ordine da Fermi | Stazione | Scale mobili | Ascensori | Totale |
| --- | --- | ---: | ---: | ---: |
| 1 | Fermi | 4 | 3 | 7 |
| 2 | Paradiso | 6 | 3 | 9 |
| 3 | Marche | 6 | 3 | 9 |
| 4 | Massaua | 6 | 3 | 9 |
| 5 | Pozzo Strada | 5 | 3 | 8 |
| 6 | Monte Grappa | 5 | 3 | 8 |
| 7 | Rivoli | 6 | 3 | 9 |
| 8 | Racconigi | 6 | 3 | 9 |
| 9 | Bernini | 6 | 3 | 9 |
| 10 | Principi d’Acaja | 6 | 3 | 9 |
| 11 | XVIII Dicembre | 8 | 4 | 12 |
| 12 | Porta Susa | 8 | 2 | 10 |
| 13 | Vinzaglio | 6 | 3 | 9 |
| 14 | Re Umberto | 6 | 3 | 9 |
| 15 | Porta Nuova | 8 | 6 | 14 |
| 16 | Marconi | 4 | 3 | 7 |
| 17 | Nizza | 6 | 3 | 9 |
| 18 | Dante | 6 | 3 | 9 |
| 19 | Carducci-Molinette | 8 | 4 | 12 |
| 20 | Spezia | 6 | 3 | 9 |
| 21 | Lingotto | 7 | 3 | 10 |
| 22 | Italia ’61–Regione Piemonte | 7 | 3 | 10 |
| 23 | Bengasi | 6 | 3 | 9 |
| | **Totale** | **142** | **73** | **215** |

## Limiti dell’identificazione

Il censimento è documentale, non una certificazione dello stato attuale. I totali sono riscontrati nel report corrente; l’elenco puntuale degli ascensori resta quello della revisione 2025. Un futuro rimpiazzo o una modifica non ancora pubblicata potrebbe richiedere una rettifica.

La matricola **RL10924** di una scala esterna a Re Umberto compare così negli allegati GTT del 2025 e del 2026, benché la sequenza sia atipica: viene conservata senza correzione e segnalata per verifica sulla targhetta. I suffissi `-1`, `-2`, ecc. degli ascensori vengono conservati come riportati nella colonna Matricola, senza presumere che coincidano con tutte le targhette fisiche.

Le fonti non associano sempre univocamente la matricola all’uscita su strada o alla banchina verso Fermi/Bengasi. Queste informazioni e le fotografie per riconoscere gli impianti richiedono una verifica sul posto. La direzione salita/discesa è quella prevista nel capitolato, non un’osservazione odierna. Il costruttore non viene usato come gestore: `operator` rimane mancante.

A Porta Susa il report GTT riguarda le scale all’interno dei tornelli della metro; a Porta Nuova i collegamenti tra l’atrio ferroviario e i tornelli metro di competenza Grandi Stazioni non vengono aggiunti per supposizione. Non sono inclusi impianti di stazioni ferroviarie, depositi o prolungamenti non in esercizio.

Gli impianti partono **senza informazioni di stato**. Il silenzio del report manutenzioni non significa funzionante, e il verde dello schema non viene trasformato automaticamente in uno stato associato a una matricola.

## Dati e importazione

- Dataset versionato: [`data/torino-m1-2026-10-16.json`](../data/torino-m1-2026-10-16.json).
- CSV consultabile/esportabile dal sito: [`frontend/static/censimento-m1.csv`](../frontend/static/censimento-m1.csv).
- Ricostruzione dai PDF privati: `pdftotext -layout` sugli allegati e `uv run --project backend python scripts/build_m1_census.py <cartella-evidenze>`.
- Simulazione persistente senza scritture: `smt import-inventory data/torino-m1-2026-10-16.json` in modalità local/aws con credenziali/configurazione previste.
- Applicazione esplicita: stesso comando con `--apply`. Il ritmo iniziale è una transazione ogni 0,75 secondi per rispettare la capacità della prova. Nessun servizio o indice aggiuntivo.

L’import verifica collisioni, duplicati e provenienza prima delle scritture. Le scritture sono condizionate e additive, riprendibili dopo un’interruzione. La directory importata resta nascosta alla home finché tutti i dispositivi non sono visibili nell’indice delle stazioni; poi un puntatore attiva il dataset completo. Nessuna creazione di STATE, osservazioni o foto e nessuna cancellazione. Un dataset con stesso nome e contenuto differente viene respinto: le revisioni future richiedono un percorso esplicito che conservi gli ID pubblicati.

Con il censimento reale attivo, home, feed e statistiche usano i dati reali. I vecchi ID demo e il loro storico restano consultabili esplicitamente; i preferiti non vengono riscritti automaticamente. Se rimandano soltanto a stazioni demo, l’interfaccia propone di scegliere le nuove stazioni reali.

Per 215 impianti la panoramica legge i metadata originali e gli stati con BatchGet coerenti in gruppi fino a 100, senza centinaia di richieste individuali e senza Scan. Gli elementi non elaborati vengono ritentati con attesa limitata; un fallimento non si trasforma in dati assenti.
