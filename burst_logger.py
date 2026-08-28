"""
Burst and pause recording for the writing feedback app.

A burst is the run of text produced between two pauses. Each row of the CSV
is one pause together with the burst that preceded it:

    burst_id,burst,burst_chars,burst_ms,pause_ms,pause_location,
    sfl_tier1,sfl_tier2,process_type

A pause is only given a duration when writing actually resumes, so pause_ms
is the true interval between the last keystroke of the burst and the first
keystroke of the next one. A pause that is still open when the session ends
has no measurable duration and is written with pause_ms empty (NA in R),
rather than being silently truncated to the session end.

Standard library only.
"""

import csv
import os
import time
from datetime import datetime

FIELDNAMES = [
    "burst_id",
    "burst",
    "burst_chars",
    "burst_ms",
    "pause_ms",
    "pause_location",
    "sfl_tier1",
    "sfl_tier2",
    "process_type",
]


class BurstRecorder:
    """Accumulates typed characters into bursts and closes them at pauses."""

    def __init__(self, output_dir="sessions", participant="P01"):
        self.output_dir = output_dir
        self.participant = participant
        self.start_clock = datetime.now()

        self.rows = []
        self._buffer = []          # characters typed in the current burst
        self._burst_start = None   # time of the first keystroke of the burst
        self._last_key_time = None # time of the most recent keystroke
        self._open_pause = None    # row waiting for its pause to be measured

    # ── recording ────────────────────────────────────────────────────────
    def key_typed(self, keysym, char, now=None):
        """Call on every key press."""
        now = time.time() if now is None else now

        # A keystroke arriving while a pause is open closes that pause.
        if self._open_pause is not None:
            self._open_pause["pause_ms"] = round(
                (now - self._open_pause.pop("_last_key_time")) * 1000
            )
            self.rows.append(self._open_pause)
            self._open_pause = None
            self._buffer = []
            self._burst_start = None

        if self._burst_start is None:
            self._burst_start = now
        self._last_key_time = now

        if keysym == "BackSpace":
            # Only pops text produced within this burst. A backspace that
            # eats into an earlier burst leaves the buffer untouched.
            if self._buffer:
                self._buffer.pop()
        elif keysym in ("Return", "KP_Enter"):
            self._buffer.append("\n")
        elif keysym == "Tab":
            self._buffer.append("\t")
        elif char and char.isprintable():
            self._buffer.append(char)
        # Delete, arrows, Home/End and modifiers are ignored.

    def pause_detected(self, location, tier1=None, tier2=None, process=None):
        """Call when the pause threshold fires."""
        if self._last_key_time is None:
            return  # a pause before any typing has no burst

        self._open_pause = {
            "burst_id": len(self.rows) + 1,
            "burst": "".join(self._buffer),
            "burst_chars": len(self._buffer),
            "burst_ms": round((self._last_key_time - self._burst_start) * 1000),
            "pause_ms": None,
            "pause_location": location or "",
            "sfl_tier1": tier1 or "",
            "sfl_tier2": tier2 or "",
            "process_type": process or "",
            "_last_key_time": self._last_key_time,
        }

    # ── output ───────────────────────────────────────────────────────────
    def _finalise(self):
        """Close whatever the session ended in the middle of."""
        if self._open_pause is not None:
            # Pause never ended, so its length is unknown: leave pause_ms empty.
            self._open_pause.pop("_last_key_time", None)
            self.rows.append(self._open_pause)
            self._open_pause = None
        elif self._buffer:
            # Writing ran up to the end of the session with no pause after it.
            self.rows.append({
                "burst_id": len(self.rows) + 1,
                "burst": "".join(self._buffer),
                "burst_chars": len(self._buffer),
                "burst_ms": round((self._last_key_time - self._burst_start) * 1000),
                "pause_ms": None,
                "pause_location": "",
                "sfl_tier1": "",
                "sfl_tier2": "",
                "process_type": "",
            })
        self._buffer = []

    def save(self, final_text):
        """Write the burst CSV and the final text. Returns (csv_path, txt_path)."""
        self._finalise()
        os.makedirs(self.output_dir, exist_ok=True)

        stem = f"{self.participant}_{self.start_clock.strftime('%Y%m%d_%H%M%S')}"
        csv_path = os.path.join(self.output_dir, stem + "_bursts.csv")
        txt_path = os.path.join(self.output_dir, stem + ".txt")

        with open(csv_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            for row in self.rows:
                writer.writerow({key: row.get(key, "") for key in FIELDNAMES})

        with open(txt_path, "w", encoding="utf-8") as handle:
            handle.write(final_text)

        return csv_path, txt_path