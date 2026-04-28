"""
===============================================================================
SDRAM Memory Test for STM32H743 - MicroPython (Heap-Safe)
===============================================================================

Alloca la memoria tramite MicroPython (bytearray) per non sovrascrivere
il heap. Testa il piu' possibile della SDRAM allocando chunk multipli.

Uso:
    import sdram_test
    sdram_test.run()            # test completo
    sdram_test.quick()          # test veloce
    sdram_test.run_bus()        # solo bus dati/indirizzi/byte
    sdram_test.run_bandwidth()  # solo bandwidth
===============================================================================
"""

import gc
import time
import micropython
import uctypes
import struct
import sys

# ==============================================================================
# Configurazione
# ==============================================================================

SDRAM_BASE = 0xC0000000
CHUNK_SIZE = 128 * 1024  # 128 KB per chunk


# ==============================================================================
# Utilita' per accesso a basso livello dentro un bytearray
# ==============================================================================

def buf_addr(buf):
    """Ottieni l'indirizzo fisico di un bytearray (unsigned)."""
    return uctypes.addressof(buf) & 0xFFFFFFFF


def write32_buf(buf, offset, value):
    struct.pack_into("<I", buf, offset, value)


def read32_buf(buf, offset):
    return struct.unpack_from("<I", buf, offset)[0]


def write16_buf(buf, offset, value):
    struct.pack_into("<H", buf, offset, value)


def read16_buf(buf, offset):
    return struct.unpack_from("<H", buf, offset)[0]


# ==============================================================================
# Allocatore: prende piu' memoria possibile in chunk
# ==============================================================================

def allocate_chunks(chunk_size=CHUNK_SIZE):
    gc.collect()
    free_before = gc.mem_free()
    print("  Memoria libera prima: {} KB".format(free_before // 1024))

    chunks = []
    total = 0
    fails = 0

    while fails < 3:
        try:
            gc.collect()
            buf = bytearray(chunk_size)
            addr = buf_addr(buf)
            if addr >= SDRAM_BASE and addr < (SDRAM_BASE + 64 * 1024 * 1024):
                chunks.append(buf)
                total += chunk_size
            else:
                del buf
                fails += 1
        except MemoryError:
            fails += 1
            if chunk_size > 16 * 1024:
                chunk_size //= 2
                fails = 0
            else:
                break

    gc.collect()
    free_after = gc.mem_free()

    print("  Allocati {} chunk = {:.1f} MB ({} KB)".format(
        len(chunks), total / (1024*1024), total // 1024))
    print("  Memoria libera dopo: {} KB".format(free_after // 1024))

    if chunks:
        first_addr = buf_addr(chunks[0])
        last_addr = buf_addr(chunks[-1])
        print("  Range: 0x{:08X} - 0x{:08X}".format(
            first_addr, last_addr + len(chunks[-1])))

    return chunks, total


def free_chunks(chunks):
    for i in range(len(chunks)):
        chunks[i] = None
    chunks.clear()
    gc.collect()


# ==============================================================================
# TEST 1: Data Bus (Walking 1s / Walking 0s)
# ==============================================================================

def test_data_bus(buf, verbose=False):
    print("\n[TEST 1] Data Bus - Walking 1s / Walking 0s")
    addr = buf_addr(buf)
    print("  Indirizzo fisico: 0x{:08X}".format(addr))
    errors = 0

    print("  Walking 1s...", end="")
    for bit in range(32):
        pattern = 1 << bit
        write32_buf(buf, 0, pattern)
        readback = read32_buf(buf, 0)
        if readback != pattern:
            errors += 1
            print("\n  !! ERRORE bit {}: scritto 0x{:08X}, letto 0x{:08X} (XOR: 0x{:08X})".format(
                bit, pattern, readback, pattern ^ readback))
            if verbose:
                xor = pattern ^ readback
                for b in range(32):
                    if xor & (1 << b):
                        print("     -> Bit D{} errato".format(b))
    if errors == 0:
        print(" OK")

    print("  Walking 0s...", end="")
    w0_errors = 0
    for bit in range(32):
        pattern = ~(1 << bit) & 0xFFFFFFFF
        write32_buf(buf, 0, pattern)
        readback = read32_buf(buf, 0)
        if readback != pattern:
            w0_errors += 1
            print("\n  !! ERRORE bit {}: scritto 0x{:08X}, letto 0x{:08X}".format(
                bit, pattern, readback))
    errors += w0_errors
    if w0_errors == 0:
        print(" OK")

    print("  Test half-word alto/basso...", end="")
    hw_errors = 0
    for pattern, name in [
        (0x0000FFFF, "low word"),
        (0xFFFF0000, "high word"),
        (0x00FF00FF, "byte alternati"),
        (0xFF00FF00, "byte alternati inv"),
    ]:
        write32_buf(buf, 0, pattern)
        readback = read32_buf(buf, 0)
        if readback != pattern:
            hw_errors += 1
            print("\n  !! ERRORE {}: scritto 0x{:08X}, letto 0x{:08X}".format(
                name, pattern, readback))
    errors += hw_errors
    if hw_errors == 0:
        print(" OK")

    return errors


# ==============================================================================
# TEST 2: Address Bus
# ==============================================================================

def test_address_bus(buf, verbose=False):
    size = len(buf)
    print("\n[TEST 2] Address Bus ({} KB)".format(size // 1024))
    errors = 0

    addr_bits = 0
    temp = size // 4
    while temp > 1:
        temp >>= 1
        addr_bits += 1
    print("  Bit di indirizzo testabili: {}".format(addr_bits))

    PA = 0xAAAAAAAA
    PB = 0x55555555

    write32_buf(buf, 0, PA)

    print("  Fase 1: scrittura power-of-2...", end="")
    for i in range(addr_bits):
        offset = 1 << (i + 2)
        if offset < size:
            write32_buf(buf, offset, PB)

    if read32_buf(buf, 0) != PA:
        errors += 1
        print("\n  !! ERRORE: offset 0 sovrascritto!")
    else:
        print(" OK")

    print("  Fase 2: verifica...", end="")
    write32_buf(buf, 0, PB)
    for i in range(addr_bits):
        offset = 1 << (i + 2)
        if offset < size:
            write32_buf(buf, offset, PA)
            for j in range(addr_bits):
                if j != i:
                    co = 1 << (j + 2)
                    if co < size:
                        if read32_buf(buf, co) != PB:
                            errors += 1
                            if verbose:
                                print("\n  !! A{} e A{} possibile corto".format(i, j))
            write32_buf(buf, offset, PB)

    if errors == 0:
        print(" OK")
    return errors


# ==============================================================================
# TEST FAST: Pattern veloce con operazioni byte (per quick mode)
# ==============================================================================

def test_pattern_fast(buf, byte_val, name=""):
    """
    Test veloce: riempi il buffer un byte alla volta (molto piu' veloce
    di struct.pack_into in MicroPython) e verifica.
    """
    size = len(buf)
    print("\n[TEST FAST] Pattern byte {} - {} KB".format(name, size // 1024), end="")

    errors = 0
    t_start = time.ticks_ms()

    # Scrittura - il modo piu' veloce in MicroPython
    for i in range(size):
        buf[i] = byte_val

    t_write = time.ticks_diff(time.ticks_ms(), t_start)
    print("  W:{:.1f}s".format(t_write / 1000), end="")

    # Verifica
    t_start = time.ticks_ms()
    first_errors = []
    for i in range(size):
        if buf[i] != byte_val:
            errors += 1
            if len(first_errors) < 5:
                first_errors.append((buf_addr(buf) + i, buf[i]))

    t_read = time.ticks_diff(time.ticks_ms(), t_start)
    print("  R:{:.1f}s".format(t_read / 1000), end="")

    if errors > 0:
        print("  !! {} ERRORI!".format(errors))
        for addr, val in first_errors:
            print("     0x{:08X}: letto 0x{:02X} atteso 0x{:02X}".format(
                addr, val, byte_val))
    else:
        print("  OK")

    return errors


# ==============================================================================
# TEST 3: Pattern su tutti i chunk
# ==============================================================================

def test_pattern_chunks(chunks, pattern, step=4):
    total_bytes = sum(len(c) for c in chunks)
    print("\n[TEST 3] Pattern 0x{:08X} - {:.1f} MB, step={}".format(
        pattern, total_bytes / (1024*1024), step))

    errors = 0
    t_start = time.ticks_ms()

    print("  Scrittura...", end="")
    cc = 0
    for buf in chunks:
        offset = 0
        size = len(buf)
        while offset <= size - 4:
            write32_buf(buf, offset, pattern)
            offset += step
        cc += 1
        if cc % max(1, len(chunks) // 5) == 0:
            print(".", end="")
    t_write = time.ticks_diff(time.ticks_ms(), t_start)
    print(" {:.1f}s".format(t_write / 1000))

    print("  Verifica...", end="")
    t_start = time.ticks_ms()
    first_errors = []
    cc = 0
    for buf in chunks:
        base = buf_addr(buf)
        size = len(buf)
        offset = 0
        while offset <= size - 4:
            readback = read32_buf(buf, offset)
            if readback != pattern:
                errors += 1
                if len(first_errors) < 10:
                    first_errors.append((base + offset, readback))
            offset += step
        cc += 1
        if cc % max(1, len(chunks) // 5) == 0:
            print(".", end="")
    t_read = time.ticks_diff(time.ticks_ms(), t_start)
    print(" {:.1f}s".format(t_read / 1000))

    if errors > 0:
        print("  !! {} ERRORI!".format(errors))
        for addr, val in first_errors:
            print("     0x{:08X}: letto 0x{:08X} (XOR 0x{:08X})".format(
                addr, val, pattern ^ val))
        if errors > 10:
            print("     ... e altri {}".format(errors - 10))
    else:
        print("  OK")
    return errors


# ==============================================================================
# TEST 4: Multi-pattern
# ==============================================================================

def test_multi_pattern(chunks, step=4):
    patterns = [
        0x00000000, 0xFFFFFFFF,
        0xAA55AA55, 0x55AA55AA,
        0xFF00FF00, 0x00FF00FF,
        0xFFFF0000, 0x0000FFFF,
    ]
    print("\n" + "="*60)
    print("[TEST 4] Multi-Pattern ({} pattern)".format(len(patterns)))
    print("="*60)

    total = 0
    for p in patterns:
        total += test_pattern_chunks(chunks, p, step)
    return total


# ==============================================================================
# TEST 5: Incrementing Address
# ==============================================================================

def test_increment(chunks, step=4):
    total_bytes = sum(len(c) for c in chunks)
    print("\n[TEST 5] Incrementing Address - {:.1f} MB".format(total_bytes / (1024*1024)))
    errors = 0
    t_start = time.ticks_ms()

    print("  Scrittura...", end="")
    cc = 0
    for buf in chunks:
        base = buf_addr(buf)
        size = len(buf)
        offset = 0
        while offset <= size - 4:
            write32_buf(buf, offset, (base + offset) & 0xFFFFFFFF)
            offset += step
        cc += 1
        if cc % max(1, len(chunks) // 5) == 0:
            print(".", end="")
    t_write = time.ticks_diff(time.ticks_ms(), t_start)
    print(" {:.1f}s".format(t_write / 1000))

    print("  Verifica...", end="")
    t_start = time.ticks_ms()
    first_errors = []
    cc = 0
    for buf in chunks:
        base = buf_addr(buf)
        size = len(buf)
        offset = 0
        while offset <= size - 4:
            expected = (base + offset) & 0xFFFFFFFF
            readback = read32_buf(buf, offset)
            if readback != expected:
                errors += 1
                if len(first_errors) < 10:
                    first_errors.append((base + offset, readback, expected))
            offset += step
        cc += 1
        if cc % max(1, len(chunks) // 5) == 0:
            print(".", end="")
    t_read = time.ticks_diff(time.ticks_ms(), t_start)
    print(" {:.1f}s".format(t_read / 1000))

    if errors > 0:
        print("  !! {} ERRORI!".format(errors))
        for addr, val, exp in first_errors:
            print("     0x{:08X}: letto 0x{:08X} atteso 0x{:08X}".format(addr, val, exp))
    else:
        print("  OK")
    return errors


# ==============================================================================
# TEST 6: Data Retention
# ==============================================================================

def test_retention(chunks, delay_ms=3000, step=4):
    total_bytes = sum(len(c) for c in chunks)
    print("\n[TEST 6] Data Retention (delay {}ms) - {:.1f} MB".format(
        delay_ms, total_bytes / (1024*1024)))

    pattern = 0xA5A5A5A5
    errors = 0

    print("  Scrittura 0x{:08X}...".format(pattern), end="")
    for buf in chunks:
        offset = 0
        size = len(buf)
        while offset <= size - 4:
            write32_buf(buf, offset, pattern)
            offset += step
    print(" fatto")

    print("  Attesa {}ms...".format(delay_ms))
    time.sleep_ms(delay_ms)

    print("  Verifica...", end="")
    first_errors = []
    cc = 0
    for buf in chunks:
        base = buf_addr(buf)
        size = len(buf)
        offset = 0
        while offset <= size - 4:
            readback = read32_buf(buf, offset)
            if readback != pattern:
                errors += 1
                if len(first_errors) < 10:
                    first_errors.append((base + offset, readback))
            offset += step
        cc += 1
        if cc % max(1, len(chunks) // 5) == 0:
            print(".", end="")
    print()

    if errors > 0:
        print("  !! {} ERRORI! Possibile problema di refresh".format(errors))
        for addr, val in first_errors:
            print("     0x{:08X}: letto 0x{:08X}".format(addr, val))
    else:
        print("  OK - dati integri dopo {}ms".format(delay_ms))
    return errors


# ==============================================================================
# TEST 7: Byte / Half-word Access (cruciale per RGB888!)
# ==============================================================================

def test_byte_access(buf, num_locations=4096):
    size = len(buf)
    num_locations = min(num_locations, size // 4)
    print("\n[TEST 7] Byte / Half-word Access ({} locazioni)".format(num_locations))
    errors = 0

    # 8-bit
    print("  Test 8-bit...", end="")
    for i in range(num_locations):
        off = i * 4
        buf[off + 0] = 0x11
        buf[off + 1] = 0x22
        buf[off + 2] = 0x33
        buf[off + 3] = 0x44

        readback = read32_buf(buf, off)
        if readback != 0x44332211:
            errors += 1
            if errors <= 5:
                print("\n  !! ERRORE off {}: letto 0x{:08X} atteso 0x44332211".format(
                    off, readback))

        if buf[off] != 0x11 or buf[off+1] != 0x22 or buf[off+2] != 0x33 or buf[off+3] != 0x44:
            errors += 1
            if errors <= 5:
                print("\n  !! ERRORE byte read off {}: {:02X} {:02X} {:02X} {:02X}".format(
                    off, buf[off], buf[off+1], buf[off+2], buf[off+3]))
    if errors == 0:
        print(" OK")

    # 16-bit
    print("  Test 16-bit...", end="")
    hw_errors = 0
    for i in range(num_locations):
        off = i * 4
        write16_buf(buf, off, 0xBEEF)
        write16_buf(buf, off + 2, 0xDEAD)
        if read32_buf(buf, off) != 0xDEADBEEF:
            hw_errors += 1
            if hw_errors <= 5:
                print("\n  !! ERRORE off {}: letto 0x{:08X}".format(
                    off, read32_buf(buf, off)))
    errors += hw_errors
    if hw_errors == 0:
        print(" OK")

    # RGB888 packed
    print("  Test RGB888 packed (3 byte)...", end="")
    rgb_errors = 0
    max_rgb = min(num_locations, size // 3)
    for i in range(max_rgb):
        off = i * 3
        buf[off + 0] = 0xAA
        buf[off + 1] = 0xBB
        buf[off + 2] = 0xCC
        if buf[off] != 0xAA or buf[off+1] != 0xBB or buf[off+2] != 0xCC:
            rgb_errors += 1
            if rgb_errors <= 5:
                print("\n  !! ERRORE RGB off {}: {:02X} {:02X} {:02X}".format(
                    off, buf[off], buf[off+1], buf[off+2]))
    errors += rgb_errors
    if rgb_errors == 0:
        print(" OK")

    return errors


# ==============================================================================
# TEST 8: Bandwidth
# ==============================================================================

def test_bandwidth(buf):
    size = min(len(buf), 1 * 1024 * 1024)
    print("\n[TEST 8] Bandwidth ({} KB)".format(size // 1024))

    t_start = time.ticks_us()
    offset = 0
    while offset <= size - 4:
        write32_buf(buf, offset, 0xDEADBEEF)
        offset += 4
    t_write = time.ticks_diff(time.ticks_us(), t_start)

    t_start = time.ticks_us()
    offset = 0
    while offset <= size - 4:
        _ = read32_buf(buf, offset)
        offset += 4
    t_read = time.ticks_diff(time.ticks_us(), t_start)

    if t_write > 0:
        print("  Write: {:.2f} MB/s ({:.1f} ms)".format(
            (size / (1024*1024)) / (t_write / 1000000), t_write / 1000))
    if t_read > 0:
        print("  Read:  {:.2f} MB/s ({:.1f} ms)".format(
            (size / (1024*1024)) / (t_read / 1000000), t_read / 1000))
    print("  (Overhead MicroPython incluso, utile per confronto relativo)")
    return 0


# ==============================================================================
# Entry points
# ==============================================================================

def run(full=True, step=4):
    print("="*60)
    print("  SDRAM MEMORY TEST - STM32H743 (Heap-Safe)")
    print("="*60)

    chunks, total = allocate_chunks()
    if not chunks:
        print("\n  !! Nessun chunk allocato in SDRAM!")
        return -1

    total_errors = 0
    try:
        # Test 1: Data bus
        total_errors += test_data_bus(chunks[0], verbose=True)

        # Test 2: Address bus (sul chunk piu' grande)
        biggest = max(chunks, key=len)
        total_errors += test_address_bus(biggest, verbose=True)

        # Test 3: Pattern veloci byte-level su TUTTI i chunk
        byte_patterns = [0x00, 0xFF, 0xAA, 0x55]
        if full:
            byte_patterns += [0x0F, 0xF0, 0xA5, 0x5A]
        for bp in byte_patterns:
            for ci, buf in enumerate(chunks):
                total_errors += test_pattern_fast(buf, bp, "0x{:02X} chunk {}/{}".format(
                    bp, ci + 1, len(chunks)))

        # Test 4: Word-level test solo su primo chunk (32-bit bus verification)
        print("\n[TEST WORD] Pattern 32-bit sul primo chunk ({} KB)".format(
            len(chunks[0]) // 1024))
        for pattern in [0xFFFF0000, 0x0000FFFF, 0xAA55AA55, 0x55AA55AA]:
            total_errors += test_pattern_chunks([chunks[0]], pattern, step)

        # Test 5: Incrementing (solo primo chunk)
        total_errors += test_increment([chunks[0]], step)

        # Test 6: Retention su tutti i chunk
        total_errors += test_retention(chunks, delay_ms=3000, step=max(step, 16))

        # Test 7: Byte/half-word access
        total_errors += test_byte_access(chunks[0], num_locations=4096)

        # Test 8: Bandwidth
        test_bandwidth(chunks[0])
    finally:
        free_chunks(chunks)

    print("\n" + "="*60)
    if total_errors == 0:
        print("  RISULTATO: PASSED - SDRAM OK")
    else:
        print("  RISULTATO: FAILED - {} ERRORI TOTALI".format(total_errors))
    print("="*60)
    return total_errors


def quick():
    """Test veloce: alloca solo 2 MB, pattern ridotti."""
    print("="*60)
    print("  SDRAM QUICK TEST - STM32H743")
    print("="*60)

    gc.collect()
    # Alloca solo 2 MB per il test veloce
    try:
        buf = bytearray(2 * 1024 * 1024)
    except MemoryError:
        try:
            buf = bytearray(512 * 1024)
        except MemoryError:
            buf = bytearray(128 * 1024)

    addr = buf_addr(buf)
    size = len(buf)
    print("  Buffer: {} KB @ 0x{:08X}".format(size // 1024, addr))

    errors = 0
    errors += test_data_bus(buf, verbose=True)
    errors += test_address_bus(buf, verbose=True)
    errors += test_pattern_fast(buf, 0xAA, "0xAA")
    errors += test_pattern_fast(buf, 0x55, "0x55")
    errors += test_pattern_fast(buf, 0xFF, "0xFF")
    errors += test_pattern_fast(buf, 0x00, "0x00")
    errors += test_byte_access(buf, num_locations=4096)
    test_bandwidth(buf)

    del buf
    gc.collect()

    print("\n" + "="*60)
    if errors == 0:
        print("  RISULTATO: PASSED")
    else:
        print("  RISULTATO: FAILED - {} ERRORI".format(errors))
    print("="*60)
    return errors


def run_bus():
    print("="*60)
    print("  SDRAM BUS TEST")
    print("="*60)
    gc.collect()
    try:
        buf = bytearray(256 * 1024)
    except MemoryError:
        buf = bytearray(64 * 1024)
    print("  Buffer: {} KB @ 0x{:08X}".format(len(buf) // 1024, buf_addr(buf)))

    errors = 0
    errors += test_data_bus(buf, verbose=True)
    errors += test_address_bus(buf, verbose=True)
    errors += test_byte_access(buf, num_locations=4096)
    del buf
    gc.collect()

    print("\n" + "="*60)
    if errors == 0:
        print("  RISULTATO: PASSED")
    else:
        print("  RISULTATO: FAILED - {} ERRORI".format(errors))
    print("="*60)
    return errors


def run_bandwidth():
    gc.collect()
    try:
        buf = bytearray(1 * 1024 * 1024)
    except MemoryError:
        buf = bytearray(256 * 1024)
    test_bandwidth(buf)
    del buf
    gc.collect()


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    mode = "full"
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()

    print("\nSDRAM Test - STM32H743 (Heap-Safe)")
    print("Modalita': {}".format(mode))
    print()

    if mode == "quick":
        errors = quick()
    elif mode == "bus":
        errors = run_bus()
    elif mode == "bandwidth":
        run_bandwidth()
        errors = 0
    else:
        errors = run(full=True, step=4)

    if errors:
        print("\n!! TEST FALLITO !!")
    else:
        print("\nTutto OK.")
