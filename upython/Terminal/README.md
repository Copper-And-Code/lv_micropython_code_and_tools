# MicroPython Terminal System for STM32H743

A complete terminal environment for STM32H743 with 32MB SDRAM and 1024x600 LCD.
Built on MicroPython + LVGL 9.3. Tested on real hardware.

## Files

```
config.py        -- Configuration (font, display, UART, SDRAM)
ansi_term.py     -- ANSI/VT100 parser + character cell buffer
term_widget.py   -- LVGL renderer (label+recolor, auto-detected API)
shell.py         -- Shell with 30+ commands, pipe, redirect
editor.py        -- Vi-like editor with smart redraw, syntax highlight
main.py          -- Entry point (import display_driver + terminal)
boot.py          -- Optional: mount SD/QSPI before main
test_offline.py  -- 111 tests (runs on PC without hardware)
```

Total: ~4700 lines.

## Quick Start

1. Copy all .py files to /flash (or SD card)
2. Connect via raw serial terminal (picocom, minicom, PuTTY -- NOT Thonny)
3. Reset board, or from REPL: `import main`

```bash
# Linux
picocom -b 115200 /dev/ttyACM0

# Permission fix if needed:
sudo usermod -a -G dialout $USER
```

IMPORTANT: Do NOT use Thonny for the shell. Thonny buffers input
line-by-line. The shell needs character-by-character input.
Thonny is fine for uploading files, but use picocom/minicom to interact.

## Configuration

Edit config.py:

```python
# Font (16x16 recommended for 7" display)
FONT_NAME   = 'font_unscii_16'   # or 'font_unscii_8'
FONT_WIDTH  = 16
FONT_HEIGHT = 16

# Input source
INPUT_SOURCE = 'repl'    # Uses sys.stdin (shared UART)

# Working directory (must be writable for editor!)
DEFAULT_CWD = '/sd'      # SD card (writable)
# DEFAULT_CWD = '/flash' # May be read-only on H7
```

## Shell Commands

### Navigation
```
ls [path]         List directory (color-coded)
ll [path]         Detailed list with sizes
cd <path>         Change directory
pwd               Print working directory
mount             List mount points
```

### Files
```
cat <file>        Display file
cp <src> <dst>    Copy
mv <src> <dst>    Move/rename
rm <file>         Remove
mkdir <dir>       Create directory
touch <file>      Create empty file
hexdump <f> [N]   Hex dump first N bytes
grep [-in] <p> <f>  Search pattern in file
head [-n N] <f>   First N lines
tail [-n N] <f>   Last N lines
wc <file>         Count lines/words/bytes
```

### Execution
```
run <file.py>     Execute MicroPython script
exec <file.bin>   Load+run PIC binary from SDRAM
repl              Enter MicroPython REPL
```

### System
```
cls / clear       Clear screen
free              Memory usage
df                Disk usage
uname             System info
top               Live memory monitor (q=quit)
date              Current time
uptime            System uptime
reset             Soft reset
```

### Pipe and Redirect
```
ls /sd | grep .py         Filter output
cat log.txt | grep ERROR  Search in file
echo hello > /sd/test.txt Redirect to file
cat file.py | head -20    First 20 lines
```

## Vi Editor

Open: `vi file.py` (also: vim, edit, nano)

### Modes

  i/a/o/O/I/A    Enter Insert mode
  ESC             Back to Normal mode
  :               Command mode
  /               Search forward
  v               Visual select

### Normal Mode Motions

  h j k l         Left, down, up, right
  w / b / e       Word forward / back / end
  0 / $           Start / end of line
  gg / G          First / last line
  Ctrl+D/U        Half page down / up
  Ctrl+F/B        Full page down / up
  { / }           Paragraph up / down
  %               Match bracket

### Normal Mode Editing

  x               Delete char
  dd              Delete line
  yy              Yank (copy) line
  p / P           Paste after / before
  u               Undo
  J               Join lines
  r + char        Replace one char
  dw / cw / yw    Delete/change/yank word

### Insert Mode

  Type normally. Enter = new line (auto-indent after ':').
  Backspace = delete. Tab = 4 spaces. ESC = back to Normal.

### Command Mode (:)

  :w              Save
  :q              Quit
  :q!             Force quit
  :wq             Save + quit
  :e <file>       Open file
  :42             Go to line 42
  :%s/old/new/g   Search and replace
  :set nu/nonu    Line numbers on/off

### Known Limitations

- /flash may be READ-ONLY on STM32H7. Use :w /sd/filename to save to SD.
- No background colors per-cell (label renderer supports foreground only).
- Font must be ASCII-only (unscii_8 or unscii_16).

## Architecture

```
  UART char --> Shell.feed(ch) --> line edit / dispatch
                    |                    |
                    |              Editor.feed(ch)
                    |              (when vi active)
                    v
              Shell.write(ANSI text)
                    |
                    v
              AnsiTerminal.write()
              parse ESC seqs --> cell buffer
              dirty line tracking
                    |
                    v
              TermWidget.refresh()
              rebuild only dirty labels
              recolor markup for colors
                    |
                    v
              LVGL display (1024x600)
```

## Adding Input Sources

```python
from main import InputProvider

class MyKeyboard(InputProvider):
    def init(self):
        pass  # setup hardware
    def poll(self):
        if has_input():
            return read_chars()
        return None

app = TerminalApp(input_provider=MyKeyboard())
app.run()
```

## Binary Execution

The exec command loads a PIC .bin into SDRAM and jumps to it:

```
exec myapp.bin
```

Requirements:
- Position-independent Thumb code (Cortex-M7)
- Entry point at offset 0
- Max size: 1MB (configurable in config.py)
- Loaded at SDRAM_EXEC_BASE (default 0xC0100000)

## Troubleshooting

Text too small?
  Change FONT_NAME to 'font_unscii_16' in config.py (16x16 pixels)

No input visible?
  Use picocom/minicom, NOT Thonny. Thonny buffers input.

Write error ENODEV?
  /flash is read-only. Save to /sd/ instead.

Cursor not blinking?
  Check that lv.OPA._50 exists in your build.

Board resets during init?
  Watchdog timeout. term_widget.py creates rows in batches
  with lv.task_handler() calls. If still resetting, reduce
  terminal rows in config.py.
