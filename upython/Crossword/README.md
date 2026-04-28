# CRUCIVERBA / CROSSWORD PUZZLE
### MicroPython + LVGL 9.3 — Display 1024×600

---

## Struttura del progetto / Project Structure

```
crossword/
├── main.py               ← UI principale LVGL + logica di gioco
├── crossword_engine.py   ← Motore di generazione della griglia
├── words_it.py           ← Database parole italiane (~500+ parole)
├── words_en.py           ← Database parole inglesi (~500+ parole)
└── README.md             ← Questo file
```

## Caratteristiche / Features

- **Selezione lingua all'avvio**: Italiano o Inglese
- **Griglia 13×13** con generazione automatica del cruciverba
- **Definizioni** organizzate per Orizzontali e Verticali
- **Tastiera virtuale** QWERTY integrata nel display
- **Evidenziazione** della parola corrente e cella selezionata
- **Controllo risposte** con feedback visivo (verde/rosso)
- **Rivela parola** con penalità punteggio
- **Punteggio** basato sulle parole corrette
- **Database separati** per lingua, facilmente estendibili
- **Layout ottimizzato** per display 1024×600

## Layout Display (1024×600)

```
┌──────────────────────────────────────────────────┐
│  CRUCIVERBA    Punteggio: 0    [Nuovo][Ctrl][◄]  │  ← Barra superiore (44px)
├────────────────────┬─────────────────────────────┤
│                    │  ORIZZONTALI                 │
│   ┌──┬──┬──┬──┐   │  1. Serve per cucire         │
│   │1 │A │G │O │   │  3. Frutto della vite        │
│   ├──┼──┼──┼──┤   │  ...                         │
│   │  │2 │  │  │   │                              │
│   ├──┼──┼──┼──┤   │  VERTICALI                   │
│   │  │U │  │  │   │  1. Animale domestico         │
│   ├──┼──┼──┼──┤   │  2. Colore del cielo          │
│   │  │V │  │  │   │  ...                         │
│   ├──┼──┼──┼──┤   │                              │
│   │  │A │  │  │   │                              │
│   └──┴──┴──┴──┘   │                              │
│ [1 ORI. - Serve..] │                              │
├────────────────────┤                              │
│ Q W E R T Y U I O P│                              │
│  A S D F G H J K L │                              │
│   Z X C V B N M [←]│                              │
└────────────────────┴─────────────────────────────┘
       Griglia + Tastiera              Definizioni
        (~510px)                       (~500px)
```

## Requisiti / Requirements

- **MicroPython** con binding LVGL 9.3
- **Display**: 1024×600 pixel (es. ILI9488, RA8875, SSD1963, ecc.)
- **Touch screen** o altro dispositivo di input
- **RAM**: minimo 512KB liberi (consigliati 1MB+)

### Board compatibili / Compatible Boards
- ESP32-S3 con PSRAM
- STM32F7/H7
- Raspberry Pi Pico 2 (con display esterno)
- Qualsiasi board MicroPython con LVGL 9.3

## Installazione / Installation

1. **Copiare i file** sulla board MicroPython:
   ```
   mpremote cp main.py :main.py
   mpremote cp crossword_engine.py :crossword_engine.py
   mpremote cp words_it.py :words_it.py
   mpremote cp words_en.py :words_en.py
   ```

2. **Inizializzare display e touch** nel `boot.py`:
   ```python
   import lvgl as lv
   lv.init()
   
   # === ADATTARE ALLA VOSTRA BOARD ===
   # Esempio per display SPI generico:
   # from your_display_driver import YourDriver
   # disp = YourDriver(width=1024, height=600, ...)
   
   # Esempio per touch I2C:
   # from your_touch_driver import YourTouch
   # touch = YourTouch(i2c_bus=0, ...)
   ```

3. **Avviare il gioco**:
   ```python
   import main
   ```

## Come giocare / How to Play

1. **Scegli la lingua** nella schermata iniziale
2. **Tocca una cella** bianca per selezionarla
3. **Tocca di nuovo** la stessa cella per cambiare direzione (orizzontale ↔ verticale)
4. **Usa la tastiera** virtuale per inserire le lettere
5. **Tocca una definizione** nel pannello destro per selezionare quella parola
6. **Premi "Controlla"** per verificare le risposte
7. **Premi "Rivela"** per mostrare la parola corrente (-5 punti)
8. **Premi "Nuovo Gioco"** per generare un nuovo cruciverba

## Estendere il database / Extending the Database

### Aggiungere parole italiane:
```python
# In words_it.py, aggiungi alla lista WORDS:
WORDS = [
    ...
    ("NUOVAPAROLA", "La definizione della nuova parola"),
    ...
]
```

### Aggiungere parole inglesi:
```python
# In words_en.py, aggiungi alla lista WORDS:
WORDS = [
    ...
    ("NEWWORD", "The clue for the new word"),
    ...
]
```

### Regole per le parole:
- Lunghezza minima: 3 lettere
- Lunghezza massima: 12 lettere (per griglia 13×13)
- Solo lettere maiuscole A-Z (niente accenti nel database)
- Definizioni brevi e chiare

## Personalizzazione / Customization

### Colori (in main.py):
```python
COLOR_BG         = lv.color_hex(0x1A1A2E)   # Sfondo
COLOR_CELL_BG    = lv.color_hex(0xFFFFFF)   # Celle bianche
COLOR_CELL_SEL   = lv.color_hex(0xFFE082)   # Cella selezionata
COLOR_CELL_WORD  = lv.color_hex(0xBBDEFB)   # Parola corrente
COLOR_CORRECT    = lv.color_hex(0xC8E6C9)   # Risposta OK
COLOR_WRONG      = lv.color_hex(0xFFCDD2)   # Risposta errata
```

### Dimensione griglia:
```python
GRID_ROWS = 13    # Righe della griglia
GRID_COLS = 13    # Colonne della griglia
CELL_SIZE = 38    # Pixel per cella
```

### Numero massimo parole:
```python
# In _start_new_game():
self.grid = generate_crossword(word_list, max_words=18)
```

## Note tecniche / Technical Notes

- Il generatore di cruciverba usa un algoritmo greedy: posiziona le parole
  più lunghe prima e cerca intersezioni con le parole già piazzate
- Le parole sono mescolate casualmente all'interno di ogni gruppo di lunghezza
  per garantire varietà tra partite diverse
- La griglia utente è separata dalla griglia soluzione per consentire
  il controllo delle risposte
- Il gioco gestisce automaticamente il focus della cella e il cambio
  di direzione con un singolo tocco
- I font utilizzati sono quelli built-in di LVGL (Montserrat 10-28)

## Licenza / License

Questo progetto è rilasciato come software libero.
This project is released as free software.
