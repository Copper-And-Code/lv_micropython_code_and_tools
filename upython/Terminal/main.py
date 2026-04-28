# main.py -- Entry Point for MicroPython Terminal on STM32H743
# Wires: Input → Shell → AnsiTerminal → TermWidget (LVGL)
#
# Input is pluggable. Default: REPL (sys.stdin via select.poll).
# Also supports: dedicated UART, USB keyboard (extensible).

import lvgl as lv
import display_driver     # Initializes LTDC + registers LVGL display
import time
import sys
import gc

from ansi_term import AnsiTerminal
from term_widget import TermWidget
from shell import Shell

try:
    from config import (
        TERM_COLS, TERM_ROWS, FONT_WIDTH, FONT_HEIGHT,
        INPUT_SOURCE, UART_ID, UART_BAUD, UART_TX_PIN, UART_RX_PIN,
        REFRESH_MS, DEFAULT_CWD
    )
except ImportError:
    # Defaults for 1024x600 with font_unscii_16 (16x16)
    TERM_COLS = 64
    TERM_ROWS = 37
    FONT_WIDTH = 16
    FONT_HEIGHT = 16
    INPUT_SOURCE = 'uart'
    UART_ID = 1
    UART_BAUD = 115200
    UART_TX_PIN = 'A9'
    UART_RX_PIN = 'A10'
    REFRESH_MS = 33
    DEFAULT_CWD = '/'


# ── Input Provider Interface ──────────────────────────────────────

class InputProvider:
    """Abstract input source. Subclass for new input types."""
    def init(self):
        pass
    def poll(self):
        """Return characters as str, or None if nothing available."""
        return None
    def deinit(self):
        pass


class REPLInput(InputProvider):
    """
    Read from sys.stdin (the REPL serial port).
    Uses select.poll() for non-blocking reads.
    This is the default -- works when UART is shared with REPL.
    """
    def init(self):
        import select
        self._poll_obj = select.poll()
        self._poll_obj.register(sys.stdin, select.POLLIN)

    def poll(self):
        events = self._poll_obj.poll(0)  # Non-blocking
        if events:
            try:
                ch = sys.stdin.read(1)
                return ch
            except:
                pass
        return None

    def deinit(self):
        pass


class UARTInput(InputProvider):
    """
    Read from a dedicated UART (different from REPL).
    Use when you have a separate UART for terminal input.
    """
    def __init__(self, uart_id=1, baudrate=115200, tx_pin=None, rx_pin=None):
        self._uart_id = uart_id
        self._baudrate = baudrate
        self._tx_pin = tx_pin
        self._rx_pin = rx_pin
        self._uart = None

    def init(self):
        import machine
        kwargs = {'baudrate': self._baudrate}
        if self._tx_pin and self._rx_pin:
            kwargs['tx'] = machine.Pin(self._tx_pin)
            kwargs['rx'] = machine.Pin(self._rx_pin)
        #self._uart = machine.UART(self._uart_id, **kwargs)
        self._uart = machine.UART(self._uart_id, UART_BAUD)

    def poll_old(self):
        if self._uart and self._uart.any():
            data = self._uart.read(self._uart.any())
            if data:
                try:
                    return data.decode('utf-8', 'ignore')
                except:
                    return data.decode('ascii', 'ignore')
        return None

    def poll(self):
        if self._uart and self._uart.any():
            data = self._uart.read(self._uart.any())
            if data:
                # Filtra i dati mantenendo solo i byte ASCII validi (da 0 a 127)
                clean_data = bytes(b for b in data if b < 128)
                
                if clean_data:
                    # Ora la decodifica non andrà mai in crash
                    return clean_data.decode('utf-8')
        return None
        
    def deinit(self):
        if self._uart:
            self._uart.deinit()
            self._uart = None


class USBKeyboardInput(InputProvider):
    """Placeholder for USB HID keyboard. Implement when USB Host available."""
    def poll(self):
        return None


# ── Terminal Application ──────────────────────────────────────────

class TerminalApp:
    """
    Main application: ties input, shell, terminal, and LVGL widget together.

    Usage:
        app = TerminalApp()
        app.run()      # Blocking main loop
      or:
        app = TerminalApp()
        app.start()    # Non-blocking (LVGL timer drives refresh)
    """

    def __init__(self, input_provider=None, cols=TERM_COLS, rows=TERM_ROWS):
        # ── Terminal emulator ──
        self.terminal = AnsiTerminal(cols=cols, rows=rows)

        # ── LVGL widget ──
        self.screen = lv.screen_active()
        if self.screen is None:
            raise RuntimeError("No LVGL display! Is display_driver imported?")

        self.screen.set_style_bg_color(lv.color_hex(0x000000), 0)
        lv.task_handler()   # Feed WDT

        # Widget creation is progressive (batched with task_handler inside)
        self.widget = TermWidget(self.screen, self.terminal)
        lv.task_handler()   # Feed WDT

        # ── Shell (writes banner -> marks terminal lines dirty) ──
        self.shell = Shell(self.terminal)
        # Give shell access to widget container for runlv (hide/show)
        self.shell._term_widget_cont = self.widget.cont
        lv.task_handler()   # Feed WDT

        # ── First refresh: render the banner that Shell just wrote ──
        self.widget.refresh()
        lv.task_handler()   # Push banner pixels to display

        # ── Input ──
        if input_provider is None:
            if INPUT_SOURCE == 'uart':
                input_provider = UARTInput(
                    uart_id=UART_ID, baudrate=UART_BAUD,
                    tx_pin=UART_TX_PIN, rx_pin=UART_RX_PIN
                )
            else:
                input_provider = REPLInput()

        self.input = input_provider
        self.input.init()

        # Give shell access to input provider for runlv
        self.shell._input_poll = self.input.poll

        # ── State ──
        self._running = False
        self._timer = None

    def start(self):
        """Non-blocking: use LVGL timer for polling. Returns immediately."""
        self._running = True
        self._timer = lv.timer_create(self._tick_cb, REFRESH_MS, None)

    def stop(self):
        """Stop the terminal."""
        self._running = False
        if self._timer:
            self._timer.delete()
            self._timer = None
        self.input.deinit()
        self.widget.destroy()

    def run(self):
        """
        Blocking main loop. Terminal takes over.
        Exit only on machine.soft_reset() or Ctrl+C from REPL.
        """
        self._running = True
        try:
            while self._running:
                self._poll_input()
                self.widget.refresh()
                lv.task_handler()
                time.sleep_ms(5)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    # ── Internals ──

    def _tick_cb(self, timer):
        if not self._running:
            return
        self._poll_input()
        self.widget.refresh()

    def _poll_input(self):
        data = self.input.poll()
        if data:
            for ch in data:
                if getattr(self.shell, '_repl_requested', False):
                    self.shell._repl_requested = False
                    return
                self.shell.feed(ch)


# ── Entry Point ───────────────────────────────────────────────────

def main():
    """
    Launch terminal. Call from REPL:
        import main
        main.main()
    Or auto-start by placing call at bottom of this file.
    """
    gc.collect()
    print('[term] Free RAM: {} KB'.format(gc.mem_free() // 1024))
    print('[term] Display: {}x{}'.format(TERM_COLS * FONT_WIDTH, TERM_ROWS * FONT_HEIGHT))
    print('[term] Terminal: {} cols x {} rows'.format(TERM_COLS, TERM_ROWS))
    print('[term] Input: {}'.format(INPUT_SOURCE))
    print('[term] Starting...')

    app = TerminalApp()

    # Set working directory
    import os
    try:
        os.stat(DEFAULT_CWD)
        app.shell._cwd = DEFAULT_CWD
    except OSError:
        app.shell._cwd = '/'

    # Blocking run -- terminal takes over
    app.run()


# ── Auto-start when executed ──────────────────────────────────────

main()
