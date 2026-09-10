import os
import csv
import tkinter as tk
from tkinter import messagebox
import time
from datetime import datetime
import spacy
import wordfreq

from burst_logger import BurstRecorder
from process_type import clause_process_type
import feedback_rules


class WritingFeedbackApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Writing Feedback App")
        self.root.geometry("900x700")
        self.root.configure(bg="#2c3e50")
        self.root.minsize(600, 400)

        # Load spaCy model once at startup
        self.nlp = spacy.load("en_core_web_sm")

        # ── Configuration ────────────────────────────────────────────────
        # Two thresholds:
        #   min_pause_ms - when a burst ends and the context is analysed (~1 s)
        #   prompt threshold - how long the writer must stay stopped before a
        #                      prompt appears. Per context, in feedback_rules.py
        self.min_pause_ms = 1000
        self.log_file = "history.log"
        self.session_dir = "sessions"

        # Burst and pause recording (CSV + final text)
        self.bursts = BurstRecorder(output_dir=self.session_dir, participant="P01")
        self.session_ended = False

        # Pause / prompt state
        self.pause_start_time = None
        self.timer_id = None            # stage 1: min pause
        self.norm_timer_id = None       # stage 2: context duration norm
        self.prompt_timer_id = None     # prompt auto-dismiss
        self.pending_ctx = None
        self.current_prompt = None

        self.prompts_shown = 0
        self.prompt_timeout_ms = 8000

        # One row per pause. Written at session end.
        self.decision_log = []

        # Writing stats
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
            text="Prototype v0.7",
            font=("Arial", 9),
            fg="#7f8c8d",
            bg="#1a252f"
        ).pack(side="right", padx=20)

        # ===== SETTINGS BAR =====
        settings_frame = tk.Frame(self.root, bg="#34495e", pady=8)
        settings_frame.pack(side="top", fill="x")

        tk.Label(
            settings_frame,
            text="Participant:",
            font=("Arial", 10),
            fg="#bdc3c7",
            bg="#34495e"
        ).pack(side="left", padx=(20, 5))

        self.participant_var = tk.StringVar(value="P01")
        tk.Entry(
            settings_frame,
            textvariable=self.participant_var,
            width=7,
            font=("Arial", 10),
            justify="center"
        ).pack(side="left", padx=(0, 15))

        tk.Label(
            settings_frame,
            text="Min pause:",
            font=("Arial", 10),
            fg="#bdc3c7",
            bg="#34495e"
        ).pack(side="left")

        self.threshold_var = tk.StringVar(value="1.0")
        self.threshold_entry = tk.Entry(
            settings_frame,
            textvariable=self.threshold_var,
            width=5,
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

        tk.Button(
            settings_frame,
            text="Apply",
            font=("Arial", 9, "bold"),
            bg="#27ae60",
            fg="white",
            relief="flat",
            padx=10,
            command=self.apply_settings
        ).pack(side="left", padx=(12, 5))

        self.prompting_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            settings_frame,
            text="Prompting",
            variable=self.prompting_var,
            font=("Arial", 9),
            fg="#bdc3c7",
            bg="#34495e",
            selectcolor="#2c3e50",
            activebackground="#34495e",
            activeforeground="#ecf0f1"
        ).pack(side="left", padx=(15, 5))

        self.settings_status = tk.Label(
            settings_frame,
            text="",
            font=("Arial", 9),
            fg="#2ecc71",
            bg="#34495e"
        )
        self.settings_status.pack(side="left", padx=8)

        tk.Button(
            settings_frame,
            text="End session & save",
            font=("Arial", 9, "bold"),
            bg="#c0392b",
            fg="white",
            relief="flat",
            padx=10,
            command=self.end_session
        ).pack(side="right", padx=(5, 20))

        # ===== PROMPT LABEL =====
        # This is the intervention. In the experiment it is the only thing
        # that differs between arms, so it is styled distinctly from the
        # analytic tier labels below it.
        self.feedback_label = tk.Label(
            self.root,
            text="",
            font=("Georgia", 14, "bold"),
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
            stats_frame, text="Words: 0", font=("Arial", 10),
            fg="#3498db", bg="#1a252f")
        self.words_label.pack(side="left", padx=(20, 15))

        self.wpm_label = tk.Label(
            stats_frame, text="WPM: 0", font=("Arial", 10),
            fg="#2ecc71", bg="#1a252f")
        self.wpm_label.pack(side="left", padx=15)

        self.pauses_label = tk.Label(
            stats_frame, text="Pauses: 0", font=("Arial", 10),
            fg="#e67e22", bg="#1a252f")
        self.pauses_label.pack(side="left", padx=15)

        self.prompts_label = tk.Label(
            stats_frame, text="Prompts: 0", font=("Arial", 10),
            fg="#9b59b6", bg="#1a252f")
        self.prompts_label.pack(side="left", padx=15)

        self.status_label = tk.Label(
            stats_frame, text="Start typing...", font=("Arial", 10),
            fg="#bdc3c7", bg="#1a252f")
        self.status_label.pack(side="right", padx=20)

        # Why the last pause did or did not produce a prompt. Invaluable
        # when calibrating; hide it before running participants.
        self.decision_label = tk.Label(
            stats_frame, text="", font=("Arial", 9, "italic"),
            fg="#7f8c8d", bg="#1a252f")
        self.decision_label.pack(side="right", padx=10)

        # Bindings
        self.text_area.bind("<Key>", self.on_key_press)
        self.text_area.focus_set()
        self.root.protocol("WM_DELETE_WINDOW", lambda: self.end_session(show_dialog=False))

        self.write_log("--- Session started ---")

    # ── Logging ───────────────────────────────────────────────────────────
    def write_log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, "a") as f:
            f.write(f"{timestamp} - {message}\n")

    # ── Stats ─────────────────────────────────────────────────────────────
    def get_word_count(self):
        content = self.text_area.get("1.0", "end-1c")
        return len(content.split())

    def get_wpm(self):
        elapsed = time.time() - self.session_start_time
        active_time = elapsed - self.total_pause_time
        if active_time < 1:
            return 0
        return round((self.get_word_count() / active_time) * 60)

    def update_stats(self, state):
        self.words_label.config(text=f"Words: {self.get_word_count()}")
        self.wpm_label.config(text=f"WPM: {self.get_wpm()}")
        self.pauses_label.config(text=f"Pauses: {self.pause_count}")
        self.prompts_label.config(text=f"Prompts: {self.prompts_shown}")
        self.status_label.config(text=state)

    # ── Word recognition ──────────────────────────────────────────────────
    def is_real_word(self, word):
        """Return True if the word is a recognized English word."""
        if not word or not word.isalpha():
            return False
        lower = word.lower()
        if len(lower) <= 2:
            return lower in self.COMMON_SHORT_WORDS
        if len(lower) == 3:
            return (lower in self.COMMON_SHORT_WORDS
                    or wordfreq.word_frequency(lower, 'en') >= self.WORD_FREQ_THRESHOLD)
        return wordfreq.word_frequency(lower, 'en') >= self.WORD_FREQ_THRESHOLD

    # ── SFG: Tier 2 — Transitivity role mapping ───────────────────────────
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

    # ── SFG: Tier 1 — Theme/Rheme structural position ─────────────────────
    def get_sfg_tier1(self, doc):
        """
        Determine where in the clause structure the pause falls.
        - 'pre_theme'            : No Subject or Finite written yet
        - 'theme_rheme_boundary' : Subject written but no Finite yet
        - 'within_rheme'         : Subject + Finite both present
        """
        has_finite = any(t.pos_ in ('VERB', 'AUX') for t in doc)
        has_explicit_subject = any(t.dep_ in ('nsubj', 'nsubjpass', 'expl') for t in doc)
        has_root_nominal = any(
            t.dep_ == 'ROOT'
            and t.pos_ in ('NOUN', 'PROPN', 'PRON')
            and t.tag_ not in ('DT', 'IN', 'CC')
            for t in doc
        )
        has_subject = has_explicit_subject or has_root_nominal

        if not has_subject and not has_finite:
            return 'pre_theme'
        if has_subject and not has_finite:
            return 'theme_rheme_boundary'
        return 'within_rheme'

    # ── SFG: Tier 2 — Transitivity role of the last token ─────────────────
    def get_sfg_tier2(self, last_token):
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
        """Returns (boundary_type, sfg_tier1, sfg_tier2)."""
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

        for chunk in doc.noun_chunks:
            if last_token == chunk[-1]:
                if last_token.dep_ in ('pobj', 'dobj', 'attr', 'iobj', 'oprd'):
                    return 'phrase_boundary', None, None
                if last_token.dep_ in ('nsubj', 'nsubjpass'):
                    if any(t.pos_ == 'VERB' for t in doc if t != last_token):
                        return 'phrase_boundary', None, None

        if last_token.dep_ in ('pobj', 'dobj', 'attr', 'acomp', 'oprd', 'iobj'):
            return 'phrase_boundary', None, None

        if last_token.dep_ == 'advmod' and last_token.head.pos_ == 'VERB':
            return 'phrase_boundary', None, None

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
        if boundary_type == 'word_boundary' and tier2:
            return f'Last element: {tier2}'
        return ''

    def get_boundary_color(self, boundary_type, tier1=None):
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

    # ── Settings ──────────────────────────────────────────────────────────
    def apply_settings(self):
        try:
            value = float(self.threshold_var.get())
            if value < 0.3 or value > 30:
                self.settings_status.config(text="Use 0.3-30 s", fg="#e74c3c")
                return
            self.min_pause_ms = int(value * 1000)
            self.settings_status.config(text=f"Min pause {value}s", fg="#2ecc71")
            self.update_stats("Ready")
            self.write_log(f"Min pause set to {value}s")
        except ValueError:
            self.settings_status.config(text="Enter a number", fg="#e74c3c")

    # ── Prompt display ────────────────────────────────────────────────────
    def show_prompt(self, prompt_text):
        self.current_prompt = prompt_text
        self.feedback_label.config(text=prompt_text, bg="#2980b9", pady=12)
        self.prompt_timer_id = self.root.after(
            self.prompt_timeout_ms, self.dismiss_prompt)

    def dismiss_prompt(self):
        if self.prompt_timer_id is not None:
            self.root.after_cancel(self.prompt_timer_id)
            self.prompt_timer_id = None
        self.current_prompt = None
        self.feedback_label.config(text="", bg="#2c3e50", pady=0)
        self.boundary_label.config(text="", bg="#2c3e50", pady=0)
        self.tier2_label.config(text="", bg="#2c3e50", pady=0)

    # ── Keystrokes ────────────────────────────────────────────────────────
    def _cancel_timers(self):
        for name in ("timer_id", "norm_timer_id", "prompt_timer_id"):
            tid = getattr(self, name, None)
            if tid is not None:
                self.root.after_cancel(tid)
                setattr(self, name, None)

    def on_key_press(self, event):
        # Feed the burst recorder first. A keystroke here also closes any
        # pause that is currently open.
        self.bursts.key_typed(event.keysym, event.char)

        if self.pause_start_time is not None:
            pause_length = time.time() - self.pause_start_time
            self.total_pause_time += pause_length
            self.write_log(f"Writing resumed (paused for {round(pause_length, 1)}s)")
            self.pause_start_time = None

        self.dismiss_prompt()
        self.update_stats("Writing...")

        self._cancel_timers()
        self.timer_id = self.root.after(self.min_pause_ms, self.on_min_pause)

    # ── Stage 1: a burst has ended ────────────────────────────────────────
    def on_min_pause(self):
        """Record the burst, analyse the context, schedule the prompt."""
        self.pause_start_time = time.time()
        self.pause_count += 1

        cursor_pos = self.text_area.index("insert")
        text_before_cursor = self.text_area.get("1.0", cursor_pos)

        boundary_type, tier1, tier2 = self.analyze_linguistic_context(text_before_cursor)
        process = clause_process_type(self.nlp, text_before_cursor)

        self.bursts.pause_detected(boundary_type, tier1, tier2, process)
        self.pending_ctx = (boundary_type, tier1, tier2, process)

        # Analytic tier labels
        tier1_text = self.get_boundary_display_text(boundary_type, tier1, tier2)
        tier2_text = self.get_tier2_display_text(boundary_type, tier2)
        if process:
            tier2_text = (tier2_text + "   \u00b7   " if tier2_text else "") + f"Process: {process}"

        self.boundary_label.config(
            text=tier1_text, bg=self.get_boundary_color(boundary_type, tier1), pady=6)
        if tier2_text:
            self.tier2_label.config(text=tier2_text, bg="#2c3e50", fg="#bdc3c7", pady=4)
        else:
            self.tier2_label.config(text="", bg="#2c3e50", pady=0)

        self.update_stats("Paused...")

        log = f"Pause at {boundary_type}"
        if tier1:
            log += f" | Tier1: {tier1}"
        if tier2:
            log += f" | Tier2: {tier2}"
        if process:
            log += f" | Process: {process}"
        self.write_log(log)

        # Schedule the prompt at this context's threshold.
        context = feedback_rules.get_context(boundary_type, tier1)
        threshold_ms = feedback_rules.get_threshold_ms(context)

        if threshold_ms is None:
            self.record_pause(context, threshold_ms, None)
            self.decision_label.config(text=f"{context}: no prompt here", fg="#7f8c8d")
            return

        remaining = max(0, threshold_ms - self.min_pause_ms)
        self.norm_timer_id = self.root.after(remaining, self.on_threshold_reached)

    # ── Stage 2: the threshold was reached ────────────────────────────────
    def on_threshold_reached(self):
        """The writer is still stopped. Show the prompt for this context."""
        if self.pending_ctx is None:
            return

        boundary_type, tier1, tier2, process = self.pending_ctx
        context = feedback_rules.get_context(boundary_type, tier1)
        threshold_ms = feedback_rules.get_threshold_ms(context)
        prompt = feedback_rules.get_prompt(context, tier2, process)

        if prompt and self.prompting_var.get():
            self.prompts_shown += 1
            self.show_prompt(prompt)
            self.decision_label.config(
                text=f"{context}: prompt shown", fg="#2ecc71")
        else:
            self.decision_label.config(
                text=f"{context}: prompting off" if prompt else f"{context}: no prompt",
                fg="#7f8c8d")

        self.record_pause(context, threshold_ms, prompt if self.prompting_var.get() else None)
        self.write_log(f"{context} | threshold {threshold_ms}ms | prompt: {prompt}")
        self.update_stats("Paused...")

    def record_pause(self, context, threshold_ms, prompt):
        boundary_type, tier1, tier2, process = self.pending_ctx
        self.decision_log.append({
            "pause_n":       self.pause_count,
            "boundary_type": boundary_type,
            "tier1":         tier1 or "",
            "tier2":         tier2 or "",
            "process":       process or "",
            "context":       context,
            "threshold_ms":  threshold_ms if threshold_ms else "",
            "prompt":        prompt or "",
        })

    # ── Session end ───────────────────────────────────────────────────────
    def save_decision_log(self):
        """
        Every pause evaluation, delivered or not.

        The withheld events are half the randomised sample in the RQ3
        experiment, and the exit reasons are what allow the trigger
        parameters to be recalibrated without recollecting data.
        """
        if not self.decision_log:
            return None
        participant = self.participant_var.get().strip() or "P01"
        os.makedirs(self.session_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.session_dir, f"{participant}_{stamp}_decisions.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(self.decision_log[0].keys()))
            writer.writeheader()
            writer.writerows(self.decision_log)
        return path

    def end_session(self, show_dialog=True):
        if self.session_ended:
            return
        self.session_ended = True

        self._cancel_timers()

        self.bursts.participant = self.participant_var.get().strip() or "P01"
        final_text = self.text_area.get("1.0", "end-1c")
        csv_path, txt_path = self.bursts.save(final_text)
        dec_path = self.save_decision_log()

        self.write_log(
            f"--- Session ended | {csv_path} | {txt_path} | {dec_path} "
            f"| prompts={self.prompts_shown} ---"
        )

        if show_dialog:
            msg = (f"Bursts and pauses:\n{os.path.abspath(csv_path)}\n\n"
                   f"Final text:\n{os.path.abspath(txt_path)}")
            if dec_path:
                msg += f"\n\nPrompt decisions:\n{os.path.abspath(dec_path)}"
            messagebox.showinfo("Session saved", msg)

        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = WritingFeedbackApp()
    app.run()