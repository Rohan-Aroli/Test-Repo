import os
import json
import queue
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import cv2
from PIL import Image, ImageTk


class Dashboard:
    def __init__(self, root, driver_id):
        self.root = root
        self.driver_id = driver_id
        self.events = queue.Queue()
        self.latest_image = None
        self.running = True

        root.title("Driver Monitoring")
        root.geometry("1080x680")
        root.minsize(850, 560)
        root.configure(bg="#eef2f3")
        root.protocol("WM_DELETE_WINDOW", self.close)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", background="#eef2f3", foreground="#173042")
        style.configure("Metric.TLabel", font=("Segoe UI", 18, "bold"), foreground="#173042")
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"), background="#173042", foreground="white")

        header = tk.Label(root, text="DRIVER MONITORING", anchor="w", padx=24,
                          bg="#173042", fg="white", font=("Segoe UI", 18, "bold"))
        header.pack(fill="x", ipady=12)
        self.stop_button = ttk.Button(root, text="Stop monitoring", command=self.close)
        self.stop_button.place(relx=1.0, x=-20, y=18, anchor="ne")

        body = tk.Frame(root, bg="#eef2f3")
        body.pack(fill="both", expand=True, padx=20, pady=20)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(1, weight=1)

        self.video = tk.Label(body, text="Starting camera...", bg="#10232d", fg="white")
        self.video.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 18))

        self.state = ttk.Label(body, text="State: starting", style="Metric.TLabel")
        self.state.grid(row=0, column=1, sticky="w", pady=(0, 12))

        metrics_frame = tk.Frame(body, bg="#eef2f3")
        metrics_frame.grid(row=1, column=1, sticky="new")
        self.metric_labels = {}
        for row, (key, label) in enumerate((
            ("ear", "EAR"), ("perclos", "PERCLOS"), ("blink_rate", "Blink rate"),
            ("mar", "MAR"), ("continuous_eye_closure", "Eye closure"),
            ("drowsiness_score", "Fatigue score"), ("pitch", "Head pitch"),
        )):
            ttk.Label(metrics_frame, text=label).grid(row=row, column=0, sticky="w", pady=5)
            value = ttk.Label(metrics_frame, text="--", style="Metric.TLabel")
            value.grid(row=row, column=1, sticky="e", padx=18, pady=5)
            self.metric_labels[key] = value

        log_frame = tk.Frame(root, bg="#173042")
        log_frame.pack(fill="x", padx=20, pady=(0, 20))
        tk.Label(log_frame, text="DATABASE LOG", bg="#173042", fg="#a8d8d8",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        self.log = tk.Text(log_frame, height=5, bg="#10232d", fg="#d9eeee",
                           relief="flat", state="disabled", font=("Consolas", 9))
        self.log.pack(fill="x", padx=12, pady=8)

        self.root.after(80, self.process_events)
        threading.Thread(target=self.run_engine, daemon=True).start()

    def run_engine(self):
        os.environ["DASHBOARD_MODE"] = "1"
        try:
            import main
            from backend import push_metrics
            self.engine = main
            main.set_dashboard_callback(self.on_frame)
            push_metrics.set_status_callback(self.on_database_status)
            threading.Thread(target=main.start_api, daemon=True).start()
            main.run_face_detection()
        except Exception as error:
            self.events.put(("log", f"Engine failed: {error}", False))

    def on_frame(self, frame, metrics, state):
        self.events.put(("frame", frame, metrics, state))

    def on_database_status(self, message, success):
        self.events.put(("log", message, success))

    def process_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "frame":
                    _, frame, metrics, state = event
                    self.update_frame(frame)
                    self.state.configure(text=f"State: {state}")
                    for key, label in self.metric_labels.items():
                        value = metrics.get(key, 0)
                        label.configure(text=f"{value:.2f}" if isinstance(value, float) else str(value))
                else:
                    _, message, success = event
                    self.write_log(message, success)
        except queue.Empty:
            pass
        if self.running:
            self.root.after(80, self.process_events)

    def update_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        image.thumbnail((700, 500))
        self.latest_image = ImageTk.PhotoImage(image)
        self.video.configure(image=self.latest_image, text="")

    def write_log(self, message, success):
        self.log.configure(state="normal")
        self.log.insert("end", ("[OK] " if success else "[ERROR] ") + message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def close(self):
        self.running = False
        engine = getattr(self, "engine", None)
        if engine is not None:
            engine.request_stop()
        self.root.destroy()


def start():
    root = tk.Tk()
    root.withdraw()
    driver_id = os.getenv("DRIVER_ID") or tk.simpledialog.askstring(
        "Driver",
        "Employee ID or driver UUID:",
    )
    if not driver_id:
        messagebox.showwarning("Driver required", "Enter a driver ID to start monitoring.")
        root.destroy()
        return
    profile_json = os.getenv("DRIVER_PROFILE_JSON")
    profile = json.loads(profile_json) if profile_json else {}
    driver_name = profile.get("name")
    if not driver_name and not profile_json:
        driver_name = tk.simpledialog.askstring(
            "Driver registration",
            "If this is a new driver, enter their name.\nLeave blank for an existing driver.",
            parent=root,
        )
    if driver_name:
        os.environ["DRIVER_PROFILE_JSON"] = json.dumps({"name": driver_name.strip()})
    os.environ["DRIVER_ID"] = driver_id.strip().lower()
    root.deiconify()
    Dashboard(root, driver_id.strip().lower())
    root.mainloop()


if __name__ == "__main__":
    start()