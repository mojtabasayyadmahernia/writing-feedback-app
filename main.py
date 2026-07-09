import tkinter as tk

class WritingFeedbackApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Writing Feedback App")
        self.root.geometry("900x650")
        self.root.configure(bg="#2c3e50")

        # Configuration
        self.pause_duration = 5000  # milliseconds
        self.feedback_message = "SFL-Based Feedback Based on Pause Location"

        # Header
        header = tk.Label(
            self.root,
            text="Writing Feedback App",
            font=("Arial", 16, "bold"),
            fg="white",
            bg="#2c3e50",
            pady=10
        )
        header.pack(side="top", fill="x")

        # Feedback label (always packed, starts invisible)
        self.feedback_label = tk.Label(
            self.root,
            text="",
            font=("Arial", 13, "bold"),
            fg="white",
            bg="#2c3e50",
            pady=0
        )
        self.feedback_label.pack(side="top", fill="x")

        # Frame for text area
        frame = tk.Frame(self.root, bg="#2c3e50")
        frame.pack(expand=True, fill="both", padx=20, pady=(0, 20))

        # Scrollbar
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")

        # Text area
        self.text_area = tk.Text(
            frame,
            wrap="word",
            font=("Georgia", 13),
            bg="#ecf0f1",
            fg="#2c3e50",
            insertbackground="#2c3e50",
            selectbackground="#3498db",
            padx=15,
            pady=15,
            yscrollcommand=scrollbar.set
        )
        self.text_area.pack(expand=True, fill="both")
        scrollbar.config(command=self.text_area.yview)

        # Status bar
        self.status_bar = tk.Label(
            self.root,
            text="Start typing...",
            font=("Arial", 10),
            fg="#bdc3c7",
            bg="#2c3e50",
            anchor="w",
            padx=20
        )
        self.status_bar.pack(side="bottom", fill="x")

        # Timer ID
        self.timer_id = None

        # Bind key press
        self.text_area.bind("<Key>", self.on_key_press)

        # Focus the text area on launch
        self.text_area.focus_set()

    def on_key_press(self, event):
        """Called every time a key is pressed."""
        # Hide feedback by clearing text and matching background
        self.feedback_label.config(text="", bg="#2c3e50", pady=0)

        # Update status bar
        self.status_bar.config(text="Writing...")

        # Cancel previous timer
        if self.timer_id is not None:
            self.root.after_cancel(self.timer_id)

        # Start new timer
        self.timer_id = self.root.after(self.pause_duration, self.on_pause_detected)

    def on_pause_detected(self):
        """Called when pause duration passes without a key press."""
        self.feedback_label.config(
            text=self.feedback_message,
            bg="#e74c3c",
            pady=8
        )
        self.status_bar.config(text="Paused...")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = WritingFeedbackApp()
    app.run()
