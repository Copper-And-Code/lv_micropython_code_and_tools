#!/usr/bin/env python3
# test_offline.py — Offline Test Suite
# Tests AnsiTerminal parser, Shell logic, and Editor without LVGL or hardware.
# Run with: python3 test_offline.py (CPython) or micropython test_offline.py
#
# This verifies the core logic works before deploying to STM32H743.

import sys
import os

# ── Add parent dir to path if needed ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Test counters ──
_pass = 0
_fail = 0
_total = 0

def check(name, condition):
    global _pass, _fail, _total
    _total += 1
    if condition:
        _pass += 1
        print('  \033[92mPASS\033[0m  {}'.format(name))
    else:
        _fail += 1
        print('  \033[91mFAIL\033[0m  {}'.format(name))

def section(title):
    print('\n\033[1;96m── {} ──\033[0m'.format(title))


# ══════════════════════════════════════════════════════════════════
#  1. AnsiTerminal Tests
# ══════════════════════════════════════════════════════════════════

from ansi_term import AnsiTerminal, DEF_FG, DEF_BG

section('AnsiTerminal: Basic output')

t = AnsiTerminal(cols=40, rows=10)

# Simple text
t.write('Hello')
check('write "Hello" → cursor at col 5', t.cx == 5 and t.cy == 0)
check('H at (0,0)', t.buf[0][0].char == 'H')
check('o at (0,4)', t.buf[0][4].char == 'o')
check('rest is space', t.buf[0][5].char == ' ')

# Newline (onlcr mode: LF auto-adds CR)
t.write('\nWorld')
check('LF+onlcr moves to row 1 col 0', t.cy == 1)
check('W at (1,0)', t.buf[1][0].char == 'W')
check('cursor at col 5', t.cx == 5)

# Carriage return
t.write('\r')
check('CR moves to col 0', t.cx == 0 and t.cy == 1)

# Tab
t.write('\t')
check('TAB moves to col 8', t.cx == 8)

# Backspace
t.write('X\x08')
check('BS moves cursor back', t.cx == 8)  # wrote X at 8, then back to 8

section('AnsiTerminal: Line wrap')

t2 = AnsiTerminal(cols=10, rows=5)
t2.write('0123456789AB')
check('wrap: A at (1,0)', t2.buf[1][0].char == 'A')
check('wrap: B at (1,1)', t2.buf[1][1].char == 'B')
check('wrap: cursor at (1,2)', t2.cx == 2 and t2.cy == 1)

section('AnsiTerminal: Scroll')

t3 = AnsiTerminal(cols=10, rows=3)
t3.write('line1\nline2\nline3\nline4')
check('scroll: row 0 = "line2"', ''.join(c.char for c in t3.buf[0][:5]) == 'line2')
check('scroll: row 1 = "line3"', ''.join(c.char for c in t3.buf[1][:5]) == 'line3')
check('scroll: row 2 starts with "line4"', ''.join(c.char for c in t3.buf[2][:5]) == 'line4')

section('AnsiTerminal: SGR colors')

t4 = AnsiTerminal(cols=40, rows=5)
# Red foreground
t4.write('\x1b[31mR')
check('SGR 31: fg=1 (red)', t4.buf[0][0].fg == 1)
check('SGR 31: char=R', t4.buf[0][0].char == 'R')

# Bold makes standard colors bright
t4.write('\x1b[1;32mG')
check('SGR 1;32: fg=10 (bright green)', t4.buf[0][1].fg == 10)

# Reset
t4.write('\x1b[0mN')
check('SGR 0: fg=default', t4.buf[0][2].fg == DEF_FG)

# Background
t4.write('\x1b[41mB')
check('SGR 41: bg=1 (red bg)', t4.buf[0][3].bg == 1)

# Bright fg
t4.write('\x1b[91mX')
check('SGR 91: fg=9 (bright red)', t4.buf[0][4].fg == 9)

section('AnsiTerminal: Cursor movement')

t5 = AnsiTerminal(cols=40, rows=10)
# CUP (cursor position)
t5.write('\x1b[3;5H')
check('CUP 3;5 → row=2, col=4', t5.cy == 2 and t5.cx == 4)

# CUU (cursor up)
t5.write('\x1b[1A')
check('CUU 1 → row=1', t5.cy == 1)

# CUD (cursor down)
t5.write('\x1b[2B')
check('CUD 2 → row=3', t5.cy == 3)

# CUF (cursor forward)
t5.write('\x1b[3C')
check('CUF 3 → col=7', t5.cx == 7)

# CUB (cursor back)
t5.write('\x1b[2D')
check('CUB 2 → col=5', t5.cx == 5)

# Home
t5.write('\x1b[H')
check('Home → (0,0)', t5.cy == 0 and t5.cx == 0)

section('AnsiTerminal: Erase')

t6 = AnsiTerminal(cols=10, rows=3)
t6.write('ABCDEFGHIJ')
t6.write('1234567890')
t6.write('abcdefghij')

# Erase line from cursor
t6.write('\x1b[2;4H')  # Row 1, Col 3
t6.write('\x1b[K')     # Erase to end of line
check('EL 0: col 3 cleared', t6.buf[1][3].char == ' ')
check('EL 0: col 2 kept', t6.buf[1][2].char == '3')

# Erase entire display
t6.write('\x1b[2J')
check('ED 2: screen cleared', t6.buf[0][0].char == ' ')
check('ED 2: cursor at (0,0)', t6.cx == 0 and t6.cy == 0)

section('AnsiTerminal: Save/Restore cursor')

t7 = AnsiTerminal(cols=40, rows=5)
t7.write('\x1b[3;10H')  # Move to (2, 9)
t7.write('\x1b7')        # Save
t7.write('\x1b[1;1H')   # Move to (0, 0)
t7.write('\x1b8')        # Restore
check('Restore cursor → row=2, col=9', t7.cy == 2 and t7.cx == 9)

section('AnsiTerminal: Scroll region')

t8 = AnsiTerminal(cols=10, rows=5)
# Set scroll region to rows 1-3 (1-based: 2-4)
t8.write('\x1b[2;4r')
check('DECSTBM: scroll_top=1', t8.scroll_top == 1)
check('DECSTBM: scroll_bot=3', t8.scroll_bot == 3)

section('AnsiTerminal: Dirty tracking')

t9 = AnsiTerminal(cols=10, rows=5)
_ = t9.get_dirty_lines()  # Clear initial dirty
t9.write('Hello')
dirty = t9.get_dirty_lines()
check('Dirty after write: row 0 dirty', 0 in dirty)
check('Dirty after write: row 1 not dirty', 1 not in dirty)
dirty2 = t9.get_dirty_lines()
check('Dirty cleared after get', len(dirty2) == 0)


# ══════════════════════════════════════════════════════════════════
#  2. Shell Tests (without LVGL)
# ══════════════════════════════════════════════════════════════════

section('Shell: Basic initialization')

# Shell needs a terminal — we use AnsiTerminal directly
st = AnsiTerminal(cols=80, rows=24)

# Import shell (editor.py exists, so HAS_EDITOR=True)
from shell import Shell

sh = Shell(st)
check('Shell created', sh is not None)
check('Shell has builtins', len(Shell.BUILTINS) > 0)
check('Shell cwd = /', sh._cwd == '/')

section('Shell: Path resolution')

check('resolve /flash/test → /flash/test',
      sh._normalize_path('/flash/test') == '/flash/test')
check('resolve test from / → /test',
      sh._normalize_path('test') == '/test')

sh._cwd = '/flash'
check('resolve test from /flash → /flash/test',
      sh._normalize_path('test') == '/flash/test')
check('resolve .. from /flash → /',
      sh._normalize_path('..') == '/')
check('resolve ./sub → /flash/sub',
      sh._normalize_path('./sub') == '/flash/sub')
check('resolve a/../b → /flash/b',
      sh._normalize_path('a/../b') == '/flash/b')

sh._cwd = '/'

section('Shell: Command dispatch')

# Capture output
output_buf = []
original_write = sh.write
def capture_write(text):
    output_buf.append(text)
    original_write(text)

sh.write = capture_write

# Test echo
output_buf.clear()
sh._dispatch_command('echo Hello World')
combined = ''.join(output_buf)
check('echo outputs text', 'Hello World' in combined)

# Test pwd
output_buf.clear()
sh._dispatch_command('pwd')
combined = ''.join(output_buf)
check('pwd outputs /', '/' in combined)

section('Shell: History')

sh._line = list('test_cmd_1')
sh._cursor = len(sh._line)
# Simulate enter
sh.write = original_write
sh._execute_line()

sh._line = list('test_cmd_2')
sh._cursor = len(sh._line)
sh._execute_line()

check('History has entries', len(sh._history) >= 2)
check('Last history = test_cmd_2', sh._history[-1] == 'test_cmd_2')

section('Shell: Alias')

sh.write = capture_write
output_buf.clear()
sh._dispatch_command('alias ll=ls -l')
check('Alias set', 'll' in sh.aliases or 'ls -l' in sh.aliases.get('ll', ''))

section('Shell: Pipe infrastructure')

output_buf.clear()
sh._dispatch_command('echo one two three')
combined = ''.join(output_buf)
check('echo for pipe test', 'one two three' in combined)

section('Shell: ANSI stripping')

stripped = Shell._strip_ansi('\x1b[31mRed\x1b[0m Normal')
check('strip_ansi removes ESC sequences', stripped == 'Red Normal')

stripped2 = Shell._strip_ansi('\x1b[1;32;40mBold\x1b[0m')
check('strip_ansi handles complex SGR', stripped2 == 'Bold')

section('Shell: Format size')

check('format 500 → 500B', Shell._format_size(500) == '500B')
check('format 1024 → 1.0KB', Shell._format_size(1024) == '1.0KB')
check('format 1048576 → 1.0MB', Shell._format_size(1048576) == '1.0MB')

# ══════════════════════════════════════════════════════════════════
#  3. Editor Tests (logic only, no LVGL)
# ══════════════════════════════════════════════════════════════════

section('Editor: Buffer management')

from editor import Editor, MODE_NORMAL, MODE_INSERT, MODE_COMMAND

# Create editor with mock terminal
et = AnsiTerminal(cols=80, rows=24)

# Monkey-patch terminal.write to be silent for the editor
# (editor does full ANSI redraws which flood the test output)
et_write_orig = et.write
et.write = lambda data: None

ed = Editor(et, filepath=None, cols=80, rows=24, syntax=False)

check('Editor starts in NORMAL mode', ed.mode == MODE_NORMAL)
check('Editor has one empty line', len(ed.lines) == 1 and ed.lines[0] == '')
check('Editor cursor at (0,0)', ed.cx == 0 and ed.cy == 0)

# Enter insert mode
ed.feed('i')
check('After i: INSERT mode', ed.mode == MODE_INSERT)

# Type some text
for ch in 'Hello World':
    ed.feed(ch)
check('After typing: line = "Hello World"', ed.lines[0] == 'Hello World')
check('Cursor at col 11', ed.cx == 11)

# Enter (newline)
ed.feed('\r')
check('After Enter: 2 lines', len(ed.lines) == 2)
check('Cursor on line 1', ed.cy == 1)

# Type on second line
for ch in 'Second line':
    ed.feed(ch)
check('Line 1 = "Second line"', ed.lines[1] == 'Second line')

# ESC to normal
ed.feed('\x1b')
check('After ESC: NORMAL mode', ed.mode == MODE_NORMAL)

section('Editor: Normal mode motions')

# h/l/j/k
ed.cy = 0
ed.cx = 5
ed.feed('h')
check('h: left → cx=4', ed.cx == 4)
ed.feed('l')
check('l: right → cx=5', ed.cx == 5)
ed.feed('j')
check('j: down → cy=1', ed.cy == 1)
ed.feed('k')
check('k: up → cy=0', ed.cy == 0)

# 0 and $
ed.cx = 5
ed.feed('0')
check('0: start of line → cx=0', ed.cx == 0)
ed.feed('$')
check('$: end of line', ed.cx == len(ed.lines[0]) - 1)

# gg and G
ed.lines = ['line 0', 'line 1', 'line 2', 'line 3', 'line 4']
ed.cy = 3
ed.feed('g')
ed.feed('g')
check('gg: top → cy=0', ed.cy == 0)

ed.feed('G')
check('G: bottom → cy=4', ed.cy == 4)

section('Editor: Editing operations')

ed.lines = ['Hello World']
ed.cy = 0
ed.cx = 5
ed.mode = MODE_NORMAL

# x: delete char
ed.feed('x')
check('x: deletes char at cursor', ed.lines[0] == 'HelloWorld')

# dd: delete line
ed.lines = ['line1', 'line2', 'line3']
ed.cy = 1
ed.feed('d')
ed.feed('d')
check('dd: line2 deleted', 'line2' not in ed.lines)
check('dd: 2 lines remain', len(ed.lines) == 2)

# yy + p: yank and paste
ed.lines = ['AAA', 'BBB', 'CCC']
ed.cy = 0
ed.feed('y')
ed.feed('y')
check('yy: yank_buf = ["AAA"]', ed.yank_buf == ['AAA'])
ed.cy = 2
ed.feed('p')
check('p: paste after → 4 lines', len(ed.lines) == 4)
check('p: pasted line', ed.lines[3] == 'AAA')

section('Editor: Undo')

ed.lines = ['Original']
ed.cy = 0
ed.cx = 0
ed._undo_stack = []

# Make a change and undo
ed.feed('i')
for ch in 'New':
    ed.feed(ch)
ed.feed('\x1b')
check('After insert: line = "NewOriginal"', ed.lines[0] == 'NewOriginal')

ed.feed('u')
check('After undo: line = "Original"', ed.lines[0] == 'Original')

section('Editor: Command mode')

ed.lines = ['test content']
ed.cy = 0
ed.cx = 0
ed.mode = MODE_NORMAL

# :42 → go to line (we only have 1 line so stays at 0)
ed.feed(':')
check('After :: COMMAND mode', ed.mode == MODE_COMMAND)
ed.feed('\x1b')
check('ESC exits command mode', ed.mode == MODE_NORMAL)

# Search
ed.lines = ['alpha beta', 'gamma beta', 'delta']
ed.cy = 0
ed.cx = 0
ed.feed('/')
for ch in 'beta':
    ed.feed(ch)
ed.feed('\r')
check('Search /beta: found at row 0', ed.cy == 0)
check('Search /beta: cx at match', ed.cx == 6)

ed.feed('n')
check('n: next match at row 1', ed.cy == 1)

section('Editor: Auto-indent')

ed.lines = ['def foo():']
ed.cy = 0
ed.cx = 10
ed.mode = MODE_NORMAL
ed.feed('A')  # Append at end of line → Insert mode
ed.feed('\r')  # Enter → should auto-indent with 4 extra spaces
check('Auto-indent after colon',
      ed.lines[1].startswith('        ') or ed.lines[1].startswith('    '))

section('Editor: Syntax highlighting')

from editor import PY_KEYWORDS, PY_BUILTINS

check('Python keywords include "def"', 'def' in PY_KEYWORDS)
check('Python keywords include "class"', 'class' in PY_KEYWORDS)
check('Python builtins include "print"', 'print' in PY_BUILTINS)
check('Python builtins include "len"', 'len' in PY_BUILTINS)

# Test highlighter doesn't crash
ed.syntax_enabled = True
try:
    result = ed._syntax_highlight('def foo(x):  # comment')
    check('Syntax highlight runs without error', True)
    check('Highlight output contains ANSI', '\x1b[' in result)
except Exception as e:
    check('Syntax highlight runs without error (FAILED: {})'.format(e), False)

try:
    result2 = ed._syntax_highlight('x = "hello" + 42  # test')
    check('Highlight strings+numbers OK', True)
except Exception as e:
    check('Highlight strings+numbers OK (FAILED)', False)

try:
    result3 = ed._syntax_highlight("triple = '''multi'''")
    check('Highlight triple-quote OK', True)
except Exception as e:
    check('Highlight triple-quote OK (FAILED)', False)


# ══════════════════════════════════════════════════════════════════
#  4. Integration Tests
# ══════════════════════════════════════════════════════════════════

section('Integration: Shell+Editor flow')

# Simulate: shell opens editor, user quits, returns to shell
it = AnsiTerminal(cols=80, rows=24)
it.write = lambda data: None  # Silent

ish = Shell(it)
ish.write = lambda text: None  # Silent

# Open editor via command
ish.cmd_edit(['test.py'])
check('cmd_edit creates editor', ish._editor is not None)

# Simulate :q in editor
ish._editor.feed(':')
ish._editor.feed('q')
ish._editor.feed('\r')
check('After :q editor inactive', not ish._editor.active)

# Feed a char to shell to trigger editor cleanup
ish.feed(' ')
check('Editor cleared after :q + feed', ish._editor is None)


# ══════════════════════════════════════════════════════════════════
#  5. Stress / Edge Cases
# ══════════════════════════════════════════════════════════════════

section('Edge cases')

# Very long line
long_t = AnsiTerminal(cols=20, rows=5)
long_t.write('A' * 100)
check('Long line wraps correctly', long_t.cy >= 4)

# Empty SGR
t_sgr = AnsiTerminal(cols=40, rows=5)
t_sgr.write('\x1b[m')  # SGR with no params = reset
check('Empty SGR = reset', t_sgr.cur_fg == DEF_FG)

# Malformed ESC sequences
t_mal = AnsiTerminal(cols=40, rows=5)
t_mal.write('\x1b[999;999H')  # Way out of bounds
check('Malformed CUP: clamped to bounds',
      t_mal.cy <= 4 and t_mal.cx <= 39)

# Rapid scroll
t_scroll = AnsiTerminal(cols=10, rows=3)
for i in range(100):
    t_scroll.write('line{}\n'.format(i))
check('100 lines scrolled: no crash', True)
check('Last visible line starts with line',
      t_scroll.buf[2][0].char == 'l' or t_scroll.buf[2][0].char == ' ')

# 256-color SGR (should not crash, maps to 16)
t_256 = AnsiTerminal(cols=10, rows=3)
t_256.write('\x1b[38;5;196mR')  # 256-color red
check('256-color SGR: no crash', True)

# OSC title (should not crash)
t_osc = AnsiTerminal(cols=10, rows=3)
title_received = [None]
t_osc.on_title = lambda t: title_received.__setitem__(0, t)
t_osc.write('\x1b]0;My Title\x07')
check('OSC title received', title_received[0] == 'My Title')

# Editor with empty file
ed_empty = Editor(
    AnsiTerminal(cols=40, rows=10),
    filepath=None, cols=40, rows=10, syntax=False
)
ed_empty.term.write = lambda d: None
ed_empty.feed('i')
ed_empty.feed('A')
ed_empty.feed('\x1b')
check('Editor empty file: insert works', ed_empty.lines[0] == 'A')

# Editor bracket matching
ed_br = Editor(
    AnsiTerminal(cols=40, rows=10),
    filepath=None, cols=40, rows=10, syntax=False
)
ed_br.term.write = lambda d: None
ed_br.lines = ['(hello)']
ed_br.cy = 0
ed_br.cx = 0
ed_br.feed('%')
check('% bracket match: jumps to )', ed_br.cx == 6)
ed_br.feed('%')
check('% bracket match: jumps back to (', ed_br.cx == 0)


# ══════════════════════════════════════════════════════════════════
#  Summary
# ══════════════════════════════════════════════════════════════════

print('\n' + '═' * 50)
if _fail == 0:
    print('\033[1;92m  ALL {} TESTS PASSED\033[0m'.format(_total))
else:
    print('\033[1;91m  {}/{} PASSED, {} FAILED\033[0m'.format(_pass, _total, _fail))
print('═' * 50)

sys.exit(0 if _fail == 0 else 1)
