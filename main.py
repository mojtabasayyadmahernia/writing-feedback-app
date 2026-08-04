import os
import tkinter as tk
from tkinter import messagebox
import random
import time
from datetime import datetime
import spacy
import wordfreq

from burst_logger import BurstRecorder

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
        self.session_dir = "sessions"

        # Burst and pause recording (CSV + final text)
        self.bursts = BurstRecorder(output_dir=self.session_dir, participant="P01")
        self.session_ended = False

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
            text="Prototype v0.5",
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
            text="Participant:",
            font=("Arial", 10),
            fg="#bdc3c7",
            bg="#34495e"
        ).pack(side="left")

        self.participant_var = tk.StringVar(value="P01")
        tk.Entry(
            settings_frame,
            textvariable=self.participant_var,
            width=8,
            font=("Arial", 10),
            justify="center"
        ).pack(side="left", padx=(5, 15))

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
            width=6,
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

        end_btn = tk.Button(
            settings_frame,
            text="End session & save",
            font=("Arial", 9, "bold"),
            bg="#c0392b",
            fg="white",
            relief="flat",
            padx=10,
            command=self.end_session
        )
        end_btn.pack(side="right", padx=(5, 20))

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

        # ===== TIER 1: Structural boundary label =====
        self.boundary_label = tk.Label(
            self.root,
            text="",
            font=("Arial", 11, "bold"),
            fg="white",
            bg="#2c3e50",
            pady=0
        )
        self.boundary_label.pack(side="top", fill="x")

        # ===== TIER 2: Transitivity role label =====
        self.tier2_label = tk.Label(
            self.root,
            text="",
            font=("Arial", 10, "italic"),
            fg="#bdc3c7",
            bg="#2c3e50",
            pady=0
        )
        self.tier2_label.pack(side="top", fill="x")

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

        # Closing the window ends the session and writes the log files
        self.root.protocol("WM_DELETE_WINDOW", lambda: self.end_session(show_dialog=False))

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

    # ── SFG: Tier 2 — Transitivity role mapping ──────────────────────────
    DEP_TO_TRANSITIVITY = {
        'nsubj':    'Participant (Actor/Senser/Carrier)',
        'nsubjpass':'Participant (Goal — passive)',
        'dobj':     'Participant (Goal/Phenomenon)',
        'iobj':     'Participant (Recipient)',
        'attr':     'Participant (Attribute)',
        'pobj':     'Circumstance',
        'advmod':   'Circumstance',
        'acomp':    'Participant (Attribute)',
        'oprd':     'Participant (Attribute)',
        'ROOT':     'Process',
        'aux':      'Process (auxiliary)',
        'auxpass':  'Process (auxiliary — passive)',
        'amod':     'Epithet (Qualifier)',
        'nummod':   'Numerative',
        'det':      'Deictic',
        'poss':     'Possessive Deictic',
        'compound': 'Classifier',
        'prep':     'Circumstance (preposition)',
        'cc':       'Conjunction',
        'mark':     'Conjunction',
    }

    POS_FALLBACK = {
        'NOUN':  'Participant',
        'PROPN': 'Participant (Proper noun)',
        'PRON':  'Participant (Pronoun)',
        'ADJ':   'Epithet',
        'ADV':   'Circumstance',
        'NUM':   'Numerative',
        'DET':   'Deictic',
        'ADP':   'Circumstance (preposition)',
        'INTJ':  'Interjection',
    }

    # ── SFG: Tier 1 — Theme/Rheme structural position ────────────────────
    def get_sfg_tier1(self, doc):
        """
        Determine where in the clause structure the pause falls.
        Returns one of:
        - 'pre_theme'            : No Subject or Finite written yet
        - 'theme_rheme_boundary' : Subject written but no Finite yet
        - 'within_rheme'         : Subject + Finite both present
        """
        has_finite = any(t.pos_ in ('VERB', 'AUX') for t in doc)
        has_explicit_subject = any(t.dep_ in ('nsubj', 'nsubjpass', 'expl') for t in doc)
        # ROOT noun/pronoun = implicit subject in incomplete clauses
        # Guard against spaCy mislabelling determiners as PRON ROOT
        has_root_nominal = any(
            t.dep_ == 'ROOT' and
            t.pos_ in ('NOUN', 'PROPN', 'PRON') and
            t.tag_ not in ('DT', 'IN', 'CC')
            for t in doc
        )
        has_subject = has_explicit_subject or has_root_nominal

        if not has_subject and not has_finite:
            return 'pre_theme'
        if has_subject and not has_finite:
            return 'theme_rheme_boundary'
        return 'within_rheme'

    # ── SFG: Tier 2 — Transitivity role of the last token ────────────────
    def get_sfg_tier2(self, last_token):
        """Return the SFG Transitivity role of the last token."""
        if last_token.pos_ == 'VERB':
            return 'Process'
        if last_token.pos_ == 'AUX':
            return 'Process (auxiliary)'
        if last_token.dep_ == 'ROOT':
            if last_token.pos_ in ('NOUN', 'PROPN', 'PRON'):
               return 'Participant (Actor/Senser/Carrier — Process not yet written)'
            return self.POS_FALLBACK.get(last_token.pos_, f'Unknown ({last_token.pos_})')
        role = self.DEP_TO_TRANSITIVITY.get(last_token.dep_)
        if role:
            return role
        return self.POS_FALLBACK.get(last_token.pos_, f'Unknown ({last_token.pos_})')

    # ── Main analysis ─────────────────────────────────────────────────────
    def analyze_linguistic_context(self, text):
        """
        Analyze the text up to the cursor and determine the boundary type.

        Returns a tuple: (boundary_type, sfg_tier1, sfg_tier2)
        - boundary_type : 'sentence_boundary' | 'phrase_boundary' |
                          'word_boundary' | 'mid_word'
        - sfg_tier1     : Tier 1 label (only for 'word_boundary'; else None)
        - sfg_tier2     : Tier 2 label (only for 'word_boundary'; else None)
        """
        if not text or text.isspace():
            return 'sentence_boundary', None, None

        stripped = text.rstrip()
        if not stripped:
            return 'sentence_boundary', None, None

        last_char = stripped[-1]

        if last_char in '.!?':
            return 'sentence_boundary', None, None

        if last_char in ',;:':
            return 'phrase_boundary', None, None

        doc = self.nlp(stripped)
        if len(doc) == 0:
            return 'word_boundary', None, None

        last_token = doc[-1]

        if not self.is_real_word(last_token.text):
            return 'mid_word', None, None

        # Check for phrase boundary (syntactic)
        for chunk in doc.noun_chunks:
            if last_token == chunk[-1]:
                if last_token.dep_ in ('pobj', 'dobj', 'attr', 'iobj', 'oprd'):
                    return 'phrase_boundary', None, None
                if last_token.dep_ in ('nsubj', 'nsubjpass'):
                    has_verb = any(t.pos_ == 'VERB' for t in doc if t != last_token)
                    if has_verb:
                        return 'phrase_boundary', None, None

        if last_token.dep_ in ('pobj', 'dobj', 'attr', 'acomp', 'oprd', 'iobj'):
            return 'phrase_boundary', None, None

        if last_token.dep_ == 'advmod' and last_token.head.pos_ == 'VERB':
            return 'phrase_boundary', None, None

        # Word boundary — run two-tier SFG analysis
        tier1 = self.get_sfg_tier1(doc)
        tier2 = self.get_sfg_tier2(last_token)
        return 'word_boundary', tier1, tier2

    # ── Display helpers ───────────────────────────────────────────────────
    TIER1_DISPLAY = {
        'pre_theme':            'Pre-Theme pause — clause not yet begun',
        'theme_rheme_boundary': 'Theme\u2013Rheme boundary — Subject set, Process not yet written',
        'within_rheme':         'Within-Rheme pause — clause in progress',
    }

    def get_boundary_display_text(self, boundary_type, tier1=None, tier2=None):
        """Return the Tier 1 (structural) display string."""
        if boundary_type == 'word_boundary' and tier1:
            return self.TIER1_DISPLAY.get(tier1, tier1)
        messages = {
            'sentence_boundary': 'Clause boundary — clause appears complete',
            'phrase_boundary':   'Pause is at a phrase boundary',
            'word_boundary':     'Pause is at a word boundary',
            'mid_word':          'Pause is at a mid-word position',
        }
        return messages.get(boundary_type, 'Unknown boundary')

    def get_tier2_display_text(self, boundary_type, tier2=None):
        """Return the Tier 2 (transitivity) display string."""
        if boundary_type == 'word_boundary' and tier2:
            return f'Last element: {tier2}'
        return ''

    def get_boundary_color(self, boundary_type, tier1=None):
        """Return a color for the Tier 1 label."""
        if boundary_type == 'word_boundary':
            tier1_colors = {
                'pre_theme':            '#8e44ad',
                'theme_rheme_boundary': '#2980b9',
                'within_rheme':         '#16a085',
            }
            return tier1_colors.get(tier1, '#3498db')
        colors = {
            'sentence_boundary': '#27ae60',
            'phrase_boundary':   '#f39c12',
            'mid_word':          '#e74c3c',
        }
        return colors.get(boundary_type, '#bdc3c7')

    def apply_settings(self):
        try:
            value = float(self.threshold_var.get())
            if value < 0.5 or value > 120:
                self.settings_status.config(text="Use 0.5-120 seconds", fg="#e74c3c")
                return
            self.pause_duration = int(value * 1000)
            self.settings_status.config(text=f"Set to {value}s", fg="#2ecc71")
            self.update_stats("Ready")
            self.write_log(f"Threshold changed to {value}s")
        except ValueError:
            self.settings_status.config(text="Enter a number!", fg="#e74c3c")

    # ── Burst recording ───────────────────────────────────────────────────
    def end_session(self, show_dialog=True):
        """Write the burst CSV and the final text, then close."""
        if self.session_ended:
            return
        self.session_ended = True

        if self.timer_id is not None:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None

        self.bursts.participant = self.participant_var.get().strip() or "P01"
        final_text = self.text_area.get("1.0", "end-1c")
        csv_path, txt_path = self.bursts.save(final_text)

        self.write_log(f"--- Session ended | {csv_path} | {txt_path} ---")

        if show_dialog:
            messagebox.showinfo(
                "Session saved",
                f"Bursts and pauses:\n{os.path.abspath(csv_path)}\n\n"
                f"Final text:\n{os.path.abspath(txt_path)}"
            )

        self.root.destroy()

    def on_key_press(self, event):
        # Feed the burst recorder first. A keystroke arriving here also
        # closes any pause that is currently open.
        self.bursts.key_typed(event.keysym, event.char)

        if self.pause_start_time is not None:
            pause_length = time.time() - self.pause_start_time
            self.total_pause_time += pause_length
            self.write_log(f"Writing resumed (paused for {round(pause_length, 1)}s)")
            self.pause_start_time = None

        # Hide feedback and boundary labels
        self.feedback_label.config(text="", bg="#2c3e50", pady=0)
        self.boundary_label.config(text="", bg="#2c3e50", pady=0)
        self.tier2_label.config(text="", bg="#2c3e50", pady=0)

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
        boundary_type, tier1, tier2 = self.analyze_linguistic_context(text_before_cursor)
        tier1_text  = self.get_boundary_display_text(boundary_type, tier1, tier2)
        tier2_text  = self.get_tier2_display_text(boundary_type, tier2)
        tier1_color = self.get_boundary_color(boundary_type, tier1)

        # Close the burst that just ended. The pause itself is measured when
        # writing resumes.
        self.bursts.pause_detected(boundary_type, tier1, tier2)

        # Show encouragement message (red banner)
        encouragement = random.choice(self.messages)
        self.feedback_label.config(
            text=encouragement,
            bg="#e74c3c",
            pady=8
        )

        # Show Tier 1 structural label
        self.boundary_label.config(
            text=tier1_text,
            bg=tier1_color,
            pady=6
        )

        # Show Tier 2 transitivity label (only for word boundaries)
        if tier2_text:
            self.tier2_label.config(
                text=tier2_text,
                bg="#2c3e50",
                fg="#bdc3c7",
                pady=4
            )
        else:
            self.tier2_label.config(text="", bg="#2c3e50", pady=0)

        self.update_stats("Paused...")
        log_entry = f"Pause detected at {boundary_type}"
        if tier1:
            log_entry += f" | Tier1: {tier1}"
        if tier2:
            log_entry += f" | Tier2: {tier2}"
        log_entry += f" (threshold: {self.pause_duration // 1000}s)"
        self.write_log(log_entry)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = WritingFeedbackApp()
    app.run()