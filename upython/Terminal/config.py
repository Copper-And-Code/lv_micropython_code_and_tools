# config.py — Centralized Configuration for MicroPython Terminal
# Edit this file to match your STM32H743 hardware setup.

# ── Display ───────────────────────────────────────────────────────
DISPLAY_WIDTH   = 1024
DISPLAY_HEIGHT  = 600

# ── Font ──────────────────────────────────────────────────────────
# font_unscii_16 = 16x16 monospace (64 cols x 37 rows) — readable on 7"
# font_unscii_8  = 8x8   monospace (128 cols x 75 rows) — tiny but more rows
FONT_NAME    = 'font_unscii_16'
FONT_WIDTH   = 16
FONT_HEIGHT  = 16

# ── Terminal Geometry (auto-calculated) ───────────────────────────
TERM_COLS = DISPLAY_WIDTH  // FONT_WIDTH    # 128
TERM_ROWS = DISPLAY_HEIGHT // FONT_HEIGHT   # 75

# ── Colors (ANSI 16-color palette — customize to your taste) ─────
# Standard VGA palette. You can tweak for better contrast on your LCD.
COLOR_PALETTE = [
    0x000000,  # 0  black
    0xAA0000,  # 1  red
    0x00AA00,  # 2  green
    0xAA5500,  # 3  yellow/brown
    0x0000AA,  # 4  blue
    0xAA00AA,  # 5  magenta
    0x00AAAA,  # 6  cyan
    0xAAAAAA,  # 7  white (light gray)
    0x555555,  # 8  bright black (dark gray)
    0xFF5555,  # 9  bright red
    0x55FF55,  # 10 bright green
    0xFFFF55,  # 11 bright yellow
    0x5555FF,  # 12 bright blue
    0xFF55FF,  # 13 bright magenta
    0x55FFFF,  # 14 bright cyan
    0xFFFFFF,  # 15 bright white
]
DEFAULT_FG = 7   # white
DEFAULT_BG = 0   # black

# ── UART ──────────────────────────────────────────────────────────
UART_ID      = 1           # UART peripheral (1=USART1, 3=USART3, etc.)
UART_BAUD    = 115200
UART_TX_PIN  = None        # None = use default pin for the UART
UART_RX_PIN  = None        # Set e.g. 'A9' / 'A10' if remapped
UART_BITS    = 8
UART_PARITY  = None
UART_STOP    = 1

# Input source: 'uart', 'repl', 'usb_keyboard'
INPUT_SOURCE = 'repl'

# ── SDRAM Execution (for binary PIC loader) ───────────────────────
# Adjust to match your FMC SDRAM mapping.
# STM32H743: Bank 1 = 0xC0000000, Bank 2 = 0xD0000000
SDRAM_BASE       = 0xC0000000
SDRAM_SIZE       = 32 * 1024 * 1024    # 32 MB
SDRAM_EXEC_BASE  = 0xC0100000          # 1MB offset (avoid framebuffer area)
SDRAM_EXEC_SIZE  = 0x00100000          # 1MB max binary

# ── Filesystem Mount Points ───────────────────────────────────────
# The shell will scan these for ls, cd, df, etc.
MOUNT_POINTS = ['/flash', '/sd', '/qspi']

# Default working directory at boot
DEFAULT_CWD = '/flash'

# ── Shell ─────────────────────────────────────────────────────────
HISTORY_MAX    = 50        # Max command history entries
SHELL_PROMPT   = 'upy'    # Prompt prefix

# ── Editor ────────────────────────────────────────────────────────
EDITOR_TAB_SIZE    = 4     # Tab → N spaces
EDITOR_UNDO_LEVELS = 30
EDITOR_SYNTAX_ON   = True  # Auto syntax-highlight .py files
EDITOR_LINE_NUMBERS = True

# ── LVGL Refresh ──────────────────────────────────────────────────
REFRESH_MS       = 33      # ~30 FPS display refresh
CURSOR_BLINK_MS  = 500     # Cursor blink interval

# ── Boot Behavior ─────────────────────────────────────────────────
SHOW_BANNER  = True        # Show welcome banner at startup
AUTO_RUN     = None        # Set to a .py path to auto-execute at boot
                           # e.g. '/flash/autorun.py'
