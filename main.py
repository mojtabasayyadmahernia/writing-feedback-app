import tkinter as tk
import random
import time
from datetime import datetime
import spacy
import wordfreq

class WritingFeedbackApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Writing Feedback App")
        self.root.geometry("900x700")
        self.root.configure(bg="#2c3e50")
        self.root.minsize(600, 400)

        # Load spaCy model once at startup
        self.nlp = spacy.load("en_core_web_sm")

        # Configuration
        self.pause_duration = 10000
        self.log_file = "history.log"

        # Track pause timing
        self.pause_start_time = None

        # Track writing stats
        self.session_start_time = time.time()
        self.total_pause_time = 0.0
        self.pause_count = 0

        # Frequency threshold for word recognition (4+ char words)
        self.WORD_FREQ_THRESHOLD = 1e-5

        # Curated whitelist of common short words (1-3 chars)
        self.COMMON_SHORT_WORDS = {
            'a', 'i', 'an', 'as', 'at', 'be', 'by', 'do', 'go', 'he',
            'if', 'in', 'is', 'it', 'me', 'my', 'no', 'of', 'on', 'or',
            'so', 'to', 'up', 'us', 'we', 'am', 'are', 'was', 'the', 'and',
            'but', 'for', 'not', 'you', 'all', 'can', 'her', 'his', 'how',
            'its', 'may', 'now', 'our', 'out', 'own', 'say', 'she', 'too',
            'two', 'use', 'way', 'who', 'did', 'get', 'has', 'had', 'him',
            'let', 'man', 'new', 'old', 'see', 'try', 'yet', 'one', 'any',
            'few', 'far', 'off', 'set', 'put', 'run', 'ask', 'add', 'big',
            'end', 'why', 'age', 'ago', 'air', 'act', 'arm', 'art', 'bay',
            'bed', 'bit', 'box', 'boy', 'bus', 'buy', 'car', 'cut', 'day',
            'dog', 'ear', 'eat', 'eye', 'fit', 'fly', 'fun', 'god', 'got',
            'gun', 'guy', 'hit', 'hot', 'job', 'key', 'kid', 'law', 'lay',
            'led', 'leg', 'lie', 'low', 'map', 'mix', 'mom', 'net', 'nor',
            'pay', 'per', 'pop', 'pot', 'raw', 'red', 'rid', 'row', 'sat',
            'sea', 'sit', 'six', 'sky', 'son', 'sun', 'tax', 'ten', 'tie',
            'tip', 'top', 'toy', 'via', 'war', 'win', 'won', 'yes', 'yet',
        }

        # Feedback messages
        self.messages = [
            "Keep writing!",
            "What happens next?",
            "Don't think, just type.",
            "Keep the flow going!",
            "Just one more sentence...",
        ]

        # ===== HEADER =====
        header_frame = tk.Frame(self.root, bg="#1a252f", pady=12)
        header_frame.pack(side="top", fill="x")

        tk.Label(
            header_frame,
            text="Writing Feedback App",
            font=("Arial", 18, "bold"),
            fg="white",
            bg="#1a252f"
        ).pack(side="left", padx=20)

        tk.Label(
            header_frame,
            text="Prototype v0.4",
            font=("Arial", 9),
            fg="#7f8c8d",
            bg="#1a252f"
        ).pack(side="right", padx=20)

        # ===== SETTINGS BAR =====
        settings_frame = tk.Frame(self.root, bg="#34495e", pady=8)
        settings_frame.pack(side="top", fill="x")

        tk.Label(
            settings_frame,
            text="Settings:",
            font=("Arial", 10, "bold"),
            fg="#ecf0f1",
            bg="#34495e"
        ).pack(side="left", padx=(20, 10))

        tk.Label(
            settings_frame,
            text="Pause threshold:",
            font=("Arial", 10),
            fg="#bdc3c7",
            bg="#34495e"
        ).pack(side="left")

        self.threshold_var = tk.StringVar(value="10")
        self.threshold_entry = tk.Entry(
            settings_frame,
            textvariable=self.threshold_var,
            width=4,
            font=("Arial", 10),
            justify="center"
        )
        self.threshold_entry.pack(side="left", padx=5)

        tk.Label(
            settings_frame,
            text="sec",
            font=("Arial", 10),
            fg="#bdc3c7",
            bg="#34495e"
        ).pack(side="left")

        apply_btn = tk.Button(
            settings_frame,
            text="Apply",
            font=("Arial", 9, "bold"),
            bg="#27ae60",
            fg="white",
            relief="flat",
            padx=10,
            command=self.apply_settings
        )
        apply_btn.pack(side="left", padx=(15, 5))

        self.settings_status = tk.Label(
            settings_frame,
            text="",
            font=("Arial", 9),
            fg="#2ecc71",
            bg="#34495e"
        )
        self.settings_status.pack(side="left", padx=5)

        # ===== FEEDBACK LABEL =====
        self.feedback_label = tk.Label(
            self.root,
            text="",
            font=("Arial", 13, "bold"),
            fg="white",
            bg="#2c3e50",
            pady=0
        )
        self.feedback_label.pack(side="top", fill="x")

        # ===== BOUNDARY INFO LABEL =====
        self.boundary_label = tk.Label(
            self.root,
            text="",
            font=("Arial", 11),
            fg="white",
            bg="#2c3e50",
            pady=0
        )
        self.boundary_label.pack(side="top", fill="x")

        # ===== TEXT AREA =====
        text_frame = tk.Frame(self.root, bg="#2c3e50")
        text_frame.pack(expand=True, fill="both", padx=20, pady=(10, 10))

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        self.text_area = tk.Text(
            text_frame,
            wrap="word",
            font=("Georgia", 13),
            bg="#ecf0f1",
            fg="#2c3e50",
            insertbackground="#2c3e50",
            selectbackground="#3498db",
            padx=15,
            pady=15,
            relief="flat",
            yscrollcommand=scrollbar.set
        )
        self.text_area.pack(expand=True, fill="both")
        scrollbar.config(command=self.text_area.yview)

        # ===== STATS BAR =====
        stats_frame = tk.Frame(self.root, bg="#1a252f", pady=6)
        stats_frame.pack(side="bottom", fill="x")

        self.words_label = tk.Label(
            stats_frame,
            text="Words: 0",
            font=("Arial", 10),
            fg="#3498db",
            bg="#1a252f"
        )
        self.words_label.pack(side="left", padx=(20, 15))

        self.wpm_label = tk.Label(
            stats_frame,
            text="WPM: 0",
            font=("Arial", 10),
            fg="#2ecc71",
            bg="#1a252f"
        )
        self.wpm_label.pack(side="left", padx=15)

        self.pauses_label = tk.Label(
            stats_frame,
            text="Pauses: 0",
            font=("Arial", 10),
            fg="#e67e22",
            bg="#1a252f"
        )
        self.pauses_label.pack(side="left", padx=15)

        self.status_label = tk.Label(
            stats_frame,
            text="Start typing...",
            font=("Arial", 10),
            fg="#bdc3c7",
            bg="#1a252f"
        )
        self.status_label.pack(side="right", padx=20)

        # Timer and bindings
        self.timer_id = None
        self.text_area.bind("<Key>", self.on_key_press)
        self.text_area.focus_set()

        # Log session start
        self.write_log("--- Session started ---")

    def write_log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, "a") as f:
            f.write(f"{timestamp} - {message}\n")

    def get_word_count(self):
        content = self.text_area.get("1.0", "end-1c")
        words = content.split()
        return len(words)

    def get_wpm(self):
        elapsed = time.time() - self.session_start_time
        active_time = elapsed - self.total_pause_time
        if active_time < 1:
            return 0
        word_count = self.get_word_count()
        wpm = round((word_count / active_time) * 60)
        return wpm

    def update_stats(self, state):
        words = self.get_word_count()
        wpm = self.get_wpm()
        self.words_label.config(text=f"Words: {words}")
        self.wpm_label.config(text=f"WPM: {wpm}")
        self.pauses_label.config(text=f"Pauses: {self.pause_count}")
        self.status_label.config(text=state)

    def is_real_word(self, word):
        """Return True if the word is a recognized English word."""
        if not word or not word.isalpha():
            return False
        lower = word.lower()
        # 1-2 char words: only accept from the curated whitelist
        if len(lower) <= 2:
            return lower in self.COMMON_SHORT_WORDS
        # 3-char words: accept if in whitelist OR frequency is high enough
        if len(lower) == 3:
            return lower in self.COMMON_SHORT_WORDS or wordfreq.word_frequency(lower, 'en') >= self.WORD_FREQ_THRESHOLD
        # 4+ char words: use frequency threshold
        return wordfreq.word_frequency(lower, 'en') >= self.WORD_FREQ_THRESHOLD

    # Mapping from spaCy coarse POS tags to human-readable labels
    POS_LABELS = {
        'NOUN':  'Noun',
        'VERB':  'Verb',
        'ADJ':   'Adjective',
        'ADV':   'Adverb',
        'PRON':  'Pronoun',
        'DET':   'Determiner',
        'ADP':   'Preposition',
        'CONJ':  'Conjunction',
        'CCONJ': 'Conjunction',
        'SCONJ': 'Conjunction',
        'NUM':   'Number',
        'INTJ':  'Interjection',
        'PROPN': 'Proper Noun',
        'AUX':   'Auxiliary Verb',
        'PART':  'Particle',
    }

    def analyze_linguistic_context(self, text):
        """
        Analyze the text up to the cursor position and determine
        what kind of linguistic boundary the pause occurs at.

        Returns a tuple: (boundary_type, pos_label)
        - boundary_type: one of "sentence_boundary", "phrase_boundary",
                         "word_boundary", "mid_word"
        - pos_label: human-readable POS of the last word (only set for
                     "word_boundary"; None for all other types)
        """
        if not text or text.isspace():
            return "sentence_boundary", None

        # Strip trailing whitespace for analysis
        stripped = text.rstrip()

        if not stripped:
            return "sentence_boundary", None

        last_char = stripped[-1]

        # Sentence boundary: ends with sentence-ending punctuation
        if last_char in '.!?':
            return "sentence_boundary", None

        # Phrase boundary: ends with phrase-separating punctuation
        if last_char in ',;:':
            return "phrase_boundary", None

        # Parse the stripped text with spaCy
        doc = self.nlp(stripped)

        if len(doc) == 0:
            return "word_boundary", None

        last_token = doc[-1]

        # Check if the last token is a complete, recognized word.
        # This handles both "my test[pause]" and "my test [pause]" correctly.
        if not self.is_real_word(last_token.text):
            return "mid_word", None

        # The last token IS a real word. Now determine if it's a phrase
        # boundary or just a word boundary using dependency parsing.

        # Check if the last token is the final token in a noun chunk
        for chunk in doc.noun_chunks:
            if last_token == chunk[-1]:
                if last_token.dep_ in ('pobj', 'dobj', 'attr', 'iobj', 'oprd'):
                    return "phrase_boundary", None
                if last_token.dep_ in ('nsubj', 'nsubjpass'):
                    has_verb = any(t.pos_ == 'VERB' for t in doc if t != last_token)
                    if has_verb:
                        return "phrase_boundary", None

        # Check dependency relations indicating phrase completion
        if last_token.dep_ in ('pobj', 'dobj', 'attr', 'acomp', 'oprd', 'iobj'):
            return "phrase_boundary", None

        # Check for adverbial phrases
        if last_token.dep_ == 'advmod' and last_token.head.pos_ == 'VERB':
            return "phrase_boundary", None

        # It's a word boundary — get the POS label for the last token
        pos_label = self.POS_LABELS.get(last_token.pos_, last_token.pos_)
        return "word_boundary", pos_label

    def get_boundary_display_text(self, boundary_type, pos_label=None):
        """Return a human-readable message for the boundary type."""
        if boundary_type == "word_boundary" and pos_label:
            return f"Pause is at a word boundary  —  last word is a {pos_label}"
        messages = {
            "sentence_boundary": "Pause is at a sentence boundary",
            "phrase_boundary":   "Pause is at a phrase boundary",
            "word_boundary":     "Pause is at a word boundary",
            "mid_word":          "Pause is at a mid-word position",
        }
        return messages.get(boundary_type, "Unknown boundary")

    def get_boundary_color(self, boundary_type):
        """Return a color for the boundary type label."""
        colors = {
            "sentence_boundary": "#27ae60",
            "phrase_boundary":   "#f39c12",
            "word_boundary":     "#3498db",
            "mid_word":          "#e74c3c",
        }
        return colors.get(boundary_type, "#bdc3c7")

    def apply_settings(self):
        try:
            value = int(self.threshold_var.get())
            if value < 1 or value > 120:
                self.settings_status.config(text="Use 1-120 seconds", fg="#e74c3c")
                return
            self.pause_duration = value * 1000
            self.settings_status.config(text=f"Set to {value}s", fg="#2ecc71")
            self.update_stats("Ready")
            self.write_log(f"Threshold changed to {value}s")
        except ValueError:
            self.settings_status.config(text="Enter a number!", fg="#e74c3c")

    def on_key_press(self, event):
        if self.pause_start_time is not None:
            pause_length = time.time() - self.pause_start_time
            self.total_pause_time += pause_length
            self.write_log(f"Writing resumed (paused for {round(pause_length, 1)}s)")
            self.pause_start_time = None

        # Hide feedback and boundary labels
        self.feedback_label.config(text="", bg="#2c3e50", pady=0)
        self.boundary_label.config(text="", bg="#2c3e50", pady=0)

        self.update_stats("Writing...")

        if self.timer_id is not None:
            self.root.after_cancel(self.timer_id)

        self.timer_id = self.root.after(self.pause_duration, self.on_pause_detected)

    def on_pause_detected(self):
        self.pause_start_time = time.time()
        self.pause_count += 1

        # Get text up to cursor position
        cursor_pos = self.text_area.index("insert")
        text_before_cursor = self.text_area.get("1.0", cursor_pos)

        # Analyze linguistic context
        boundary_type, pos_label = self.analyze_linguistic_context(text_before_cursor)
        boundary_text = self.get_boundary_display_text(boundary_type, pos_label)
        boundary_color = self.get_boundary_color(boundary_type)

        # Show encouragement message
        encouragement = random.choice(self.messages)
        self.feedback_label.config(
            text=encouragement,
            bg="#e74c3c",
            pady=8
        )

        # Show boundary classification
        self.boundary_label.config(
            text=boundary_text,
            bg=boundary_color,
            pady=6
        )

        self.update_stats("Paused...")
        log_entry = f"Pause detected at {boundary_type}"
        if pos_label:
            log_entry += f" ({pos_label})"
        log_entry += f" (threshold: {self.pause_duration // 1000}s)"
        self.write_log(log_entry)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = WritingFeedbackApp()
    app.run()
