# -*- coding: utf-8 -*-
# Motore di generazione del cruciverba
# Crossword puzzle generation engine

try:
    from urandom import getrandbits, choice as _choice
    def randint(a, b):
        return a + (getrandbits(16) % (b - a + 1))
    def shuffle(lst):
        for i in range(len(lst) - 1, 0, -1):
            j = randint(0, i)
            lst[i], lst[j] = lst[j], lst[i]
    def choice(lst):
        return lst[randint(0, len(lst) - 1)]
except ImportError:
    try:
        from random import randint, shuffle, choice
    except:
        def randint(a, b):
            import time
            return a + (int(time.ticks_ms()) % (b - a + 1))
        def shuffle(lst):
            for i in range(len(lst) - 1, 0, -1):
                j = randint(0, i)
                lst[i], lst[j] = lst[j], lst[i]
        def choice(lst):
            return lst[randint(0, len(lst) - 1)]


# Direzioni di posizionamento / Placement directions
ACROSS = 0  # Orizzontale
DOWN = 1     # Verticale


class CrosswordGrid:
    """Gestisce la griglia del cruciverba e la generazione."""

    def __init__(self, rows=13, cols=13):
        self.rows = rows
        self.cols = cols
        self.grid = [['.' for _ in range(cols)] for _ in range(rows)]
        self.placed_words = []  # [(word, clue, row, col, direction), ...]
        self.word_numbers = {}  # (row, col) -> number

    def reset(self):
        """Resetta la griglia."""
        self.grid = [['.' for _ in range(self.cols)] for _ in range(self.rows)]
        self.placed_words = []
        self.word_numbers = {}

    def can_place_word(self, word, row, col, direction):
        """Verifica se una parola puo essere posizionata nella posizione data."""
        wlen = len(word)

        if direction == ACROSS:
            if col + wlen > self.cols:
                return False
            # Controlla che non ci sia una lettera subito prima
            if col > 0 and self.grid[row][col - 1] != '.':
                return False
            # Controlla che non ci sia una lettera subito dopo
            if col + wlen < self.cols and self.grid[row][col + wlen] != '.':
                return False

            has_intersection = False
            for i in range(wlen):
                c = col + i
                cell = self.grid[row][c]

                if cell != '.':
                    # La cella e' occupata: deve avere la stessa lettera
                    if cell != word[i]:
                        return False
                    has_intersection = True
                else:
                    # Controlla che le celle sopra e sotto siano libere
                    # (per evitare parole adiacenti parallele)
                    if row > 0 and self.grid[row - 1][c] != '.':
                        return False
                    if row < self.rows - 1 and self.grid[row + 1][c] != '.':
                        return False

            return has_intersection or len(self.placed_words) == 0

        else:  # DOWN
            if row + wlen > self.rows:
                return False
            # Controlla che non ci sia una lettera subito prima
            if row > 0 and self.grid[row - 1][col] != '.':
                return False
            # Controlla che non ci sia una lettera subito dopo
            if row + wlen < self.rows and self.grid[row + wlen][col] != '.':
                return False

            has_intersection = False
            for i in range(wlen):
                r = row + i
                cell = self.grid[r][col]

                if cell != '.':
                    if cell != word[i]:
                        return False
                    has_intersection = True
                else:
                    if col > 0 and self.grid[r][col - 1] != '.':
                        return False
                    if col < self.cols - 1 and self.grid[r][col + 1] != '.':
                        return False

            return has_intersection or len(self.placed_words) == 0

    def place_word(self, word, clue, row, col, direction):
        """Posiziona una parola nella griglia."""
        if direction == ACROSS:
            for i in range(len(word)):
                self.grid[row][col + i] = word[i]
        else:
            for i in range(len(word)):
                self.grid[row + i][col] = word[i]

        self.placed_words.append((word, clue, row, col, direction))

    def find_intersections(self, word):
        """Trova tutte le posizioni valide dove una parola puo intersecare."""
        positions = []

        for pw, pc, pr, pc2, pd in self.placed_words:
            for i, ch1 in enumerate(word):
                for j, ch2 in enumerate(pw):
                    if ch1 == ch2:
                        if pd == ACROSS:
                            # La parola esistente e' orizzontale
                            # Prova a posizionare verticalmente
                            new_row = pr - i
                            new_col = pc2 + j
                            if new_row >= 0 and self.can_place_word(word, new_row, new_col, DOWN):
                                positions.append((new_row, new_col, DOWN))
                        else:
                            # La parola esistente e' verticale
                            # Prova a posizionare orizzontalmente
                            new_row = pr + j
                            new_col = pc2 - i
                            if new_col >= 0 and self.can_place_word(word, new_row, new_col, ACROSS):
                                positions.append((new_row, new_col, ACROSS))

        return positions

    def assign_numbers(self):
        """Assegna i numeri alle caselle di inizio parola."""
        self.word_numbers = {}
        # Raccogli tutte le posizioni di inizio
        starts = set()
        for word, clue, row, col, direction in self.placed_words:
            starts.add((row, col))

        # Ordina per riga e poi per colonna
        sorted_starts = sorted(starts, key=lambda x: (x[0], x[1]))

        num = 1
        for pos in sorted_starts:
            if pos not in self.word_numbers:
                self.word_numbers[pos] = num
                num += 1

    def get_clues(self):
        """Restituisce le definizioni organizzate per direzione."""
        across_clues = []
        down_clues = []

        for word, clue, row, col, direction in self.placed_words:
            num = self.word_numbers.get((row, col), 0)
            entry = (num, clue, word)
            if direction == ACROSS:
                across_clues.append(entry)
            else:
                down_clues.append(entry)

        across_clues.sort(key=lambda x: x[0])
        down_clues.sort(key=lambda x: x[0])

        return across_clues, down_clues

    def get_cell_info(self, row, col):
        """Restituisce info sulla cella: lettera, numero, se e' attiva."""
        letter = self.grid[row][col]
        number = self.word_numbers.get((row, col), 0)
        active = letter != '.'
        return letter, number, active


def generate_crossword(word_list, grid_rows=13, grid_cols=13, max_words=20):
    """
    Genera un cruciverba a partire dalla lista di parole.

    Args:
        word_list: lista di tuple (parola, definizione)
        grid_rows: numero di righe della griglia
        grid_cols: numero di colonne della griglia
        max_words: numero massimo di parole da piazzare

    Returns:
        CrosswordGrid con le parole posizionate
    """
    grid = CrosswordGrid(grid_rows, grid_cols)

    # Filtra parole troppo lunghe per la griglia
    max_len = max(grid_rows, grid_cols)
    valid_words = [(w.upper(), d) for w, d in word_list if 3 <= len(w) <= max_len - 2]

    if not valid_words:
        return grid

    # Ordina per lunghezza decrescente (le parole piu lunghe prima)
    valid_words.sort(key=lambda x: len(x[0]), reverse=True)

    # Mescola un po' per varieta mantenendo la priorita alla lunghezza
    # Dividi in gruppi per lunghezza e mescola dentro ogni gruppo
    groups = {}
    for w, d in valid_words:
        l = len(w)
        if l not in groups:
            groups[l] = []
        groups[l].append((w, d))

    for l in groups:
        shuffle(groups[l])

    shuffled_words = []
    for l in sorted(groups.keys(), reverse=True):
        shuffled_words.extend(groups[l])

    # Limita il numero di parole candidate
    candidates = shuffled_words[:min(len(shuffled_words), max_words * 4)]

    # Posiziona la prima parola al centro orizzontalmente
    first_word, first_clue = candidates[0]
    start_row = grid_rows // 2
    start_col = (grid_cols - len(first_word)) // 2
    if start_col < 0:
        start_col = 0

    grid.place_word(first_word, first_clue, start_row, start_col, ACROSS)

    # Prova a posizionare le altre parole
    placed_count = 1
    attempts_without_placement = 0
    max_attempts = 100

    for word, clue in candidates[1:]:
        if placed_count >= max_words:
            break
        if attempts_without_placement > max_attempts:
            break

        # Controlla che la parola non sia gia stata piazzata
        already_placed = False
        for pw, _, _, _, _ in grid.placed_words:
            if pw == word:
                already_placed = True
                break
        if already_placed:
            continue

        positions = grid.find_intersections(word)

        if positions:
            # Scegli una posizione casuale tra quelle valide
            pos = choice(positions)
            grid.place_word(word, clue, pos[0], pos[1], pos[2])
            placed_count += 1
            attempts_without_placement = 0
        else:
            attempts_without_placement += 1

    grid.assign_numbers()
    return grid
