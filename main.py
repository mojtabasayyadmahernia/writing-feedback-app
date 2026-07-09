import tkinter as tk

def main():
    root = tk.Tk()
    root.title("Writing Feedback App")
    root.geometry("800x600")

    # Create a frame for the text area and scrollbar
    frame = tk.Frame(root)
    frame.pack(expand=True, fill="both", padx=10, pady=10)

    # Scrollbar
    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side="right", fill="y")

    # Text area
    text_area = tk.Text(frame, wrap="word", font=("Arial", 12),
                        yscrollcommand=scrollbar.set)
    text_area.pack(expand=True, fill="both")

    scrollbar.config(command=text_area.yview)

    root.mainloop()

if __name__ == "__main__":
    main()