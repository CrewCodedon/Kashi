import ctypes
myappid = 'danielkashi.prozessagent.diktierassistent.1' 
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

import tkinter as tk
from tkinter import ttk
import sounddevice as sd
import soundfile as sf
import numpy as np
import json
import os
import threading
import time
from datetime import datetime
import tempfile
import psutil
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.oauth2 import service_account
import traceback
import queue # Import für Thread-sichere Kommunikation
import pystray
from PIL import Image, ImageDraw
import keyboard
from tkinter import Canvas, PhotoImage
import requests
from PIL import Image, ImageTk
from io import BytesIO
import math

class DiktierAssistent:
    def __init__(self, root):
        self.root = root
        self.root.title("TranskriptionsAgent")
        self.root.geometry("500x500")
        self.root.attributes('-topmost', True)

        # Diese Zeile ist weiterhin wichtig und muss bleiben!
        try:
            self.root.iconbitmap('PNG.ico')
        except tk.TclError:
            print("Warnung: PNG.ico nicht gefunden oder beschädigt.")
        # --- ENDE DER LÖSUNG ---

        # Thread-sichere Queue für Ergebnisse
        self.result_queue = queue.Queue()
        
        # Google AI Setup
        self.model = None
        self.setup_google_ai()
        
        # Audio-Variablen
        self.is_recording = False
        self.audio_data = []
        self.all_recordings = []
        self.sample_rate = 16000
        self.recording_count = 0

        # Animation Variablen
        self.animation_running = False
        self.wave_radius = 0
        self.wave_alpha = 255

        # Icons laden
        self.load_icons()

        self.progress = None
        self.finished_label = None
        self.transcript_options_frame = None
        
        # Transkript-Variablen
        self.existing_transcript = ""
        self.has_transcript = False
        self.append_mode = False
        
        # UI erstellen
        self.create_ui()
        
        self.root.focus_force()
        
        self.setup_tray_icon()
        
        # Window close handler
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        # Global hotkey
        self.setup_global_hotkey()

    def create_rounded_rectangle(self, canvas, x1, y1, x2, y2, radius=25, **kwargs):
        """Zeichnet ein abgerundetes Rechteck auf einem Canvas."""
        points = [x1 + radius, y1,
                  x1 + radius, y1,
                  x2 - radius, y1,
                  x2 - radius, y1,
                  x2, y1,
                  x2, y1 + radius,
                  x2, y1 + radius,
                  x2, y2 - radius,
                  x2, y2 - radius,
                  x2, y2,
                  x2 - radius, y2,
                  x2 - radius, y2,
                  x1 + radius, y2,
                  x1 + radius, y2,
                  x1, y2,
                  x1, y2 - radius,
                  x1, y2 - radius,
                  x1, y1 + radius,
                  x1, y1 + radius,
                  x1, y1]
        return canvas.create_polygon(points, **kwargs, smooth=True)

    def load_icons(self):
        """Lädt Icons aus lokalen Dateien (gemischte Formate)"""
        icon_files = {
            'logo': 'ProzessagentLogo.png',
            'mic': 'MikrofonIcon.png', 
            'trash': 'MplltonnenIcon.png',
            'cross': 'Kreuz.png',
            'check': 'Haken.png'
        }
        
        self.icons = {}
        for name, filename in icon_files.items():
            try:
                if filename.endswith('.svg'):
                    # Für SVG-Dateien: cairosvg verwenden (falls installiert)
                    try:
                        import cairosvg
                        png_data = cairosvg.svg2png(url=filename)
                        img = Image.open(BytesIO(png_data))
                    except ImportError:
                        print(f"cairosvg nicht installiert. Überspringe {filename}")
                        self.create_fallback_icon(name)
                        continue
                else:
                    # Für JPG und PNG direkt laden
                    img = Image.open(filename).convert("RGBA") # Immer nach RGBA konvertieren

                    # --- NEU: LÖSUNG FÜR TRANSPARENZ-PROBLEM ---
                    # Nur bei der Verarbeitung des Mikrofon-Icons anwenden
                    if name == 'mic':
                        # Erstelle einen neuen, soliden Hintergrund in der App-Farbe
                        bg_color = '#f0f0f0'
                        background = Image.new('RGBA', img.size, bg_color)
                        
                        # Füge das transparente Icon auf den soliden Hintergrund
                        background.paste(img, (0, 0), img)
                        img = background
                
                # Icons skalieren
                if name == 'logo':
                    # Seitenverhältnis von 1080:700 ist ca. 1.54.
                    img = img.resize((120, 78), Image.Resampling.LANCZOS)
                elif name == 'mic':
                    img = img.resize((150, 150), Image.Resampling.LANCZOS) # Größer gemacht
                else:
                    img = img.resize((50, 50), Image.Resampling.LANCZOS)
                
                self.icons[name] = ImageTk.PhotoImage(img)
                print(f"✓ Icon geladen: {name} ({filename})")
                
            except Exception as e:
                print(f"Fehler beim Laden von {filename}: {e}")
                self.create_fallback_icon(name)

    def create_fallback_icon(self, name):
        """Erstellt moderne Fallback-Icons"""
        # Größen definieren
        sizes = {
            'logo': (100, 30),
            'mic': (80, 80),
            'trash': (50, 50),
            'cross': (50, 50),
            'check': (50, 50)
        }
        
        width, height = sizes[name]
        
        # Erstelle Icons mit PIL
        img = Image.new('RGBA', (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        
        if name == 'logo':
            # Modernes Logo
            draw.rectangle([0, 0, width-1, height-1], fill='#6B8EF5')
            draw.text((15, 7), "ProzessAgent", fill='white')
        
        elif name == 'mic':
            # Mikrofon Icon
            draw.rectangle([30, 15, 50, 45], fill='#6B8EF5')
            # Mikrofon Ständer
            draw.arc([20, 35, 60, 55], 0, 180, fill='#4A6ED4', width=3)
            draw.line([40, 55, 40, 65], fill='#4A6ED4', width=3)
            draw.line([30, 65, 50, 65], fill='#4A6ED4', width=2)
            
        elif name == 'trash':
            # Mülleimer Icon
            # Deckel
            draw.rectangle([10, 10, 40, 15], fill='#666')
            draw.rectangle([20, 5, 30, 10], fill='#666')
            # Körper
            draw.polygon([(13, 15), (15, 45), (35, 45), (37, 15)], fill='#888')
            # Linien
            for x in [20, 25, 30]:
                draw.line([x, 20, x, 40], fill='#666', width=1)
            
        elif name == 'cross':
            # X Icon in schwarzem Kreis
            draw.ellipse([5, 5, 45, 45], fill='black')
            draw.line([15, 15, 35, 35], fill='white', width=4)
            draw.line([35, 15, 15, 35], fill='white', width=4)
            
        elif name == 'check':
            # Häkchen in grünem Kreis
            draw.ellipse([5, 5, 45, 45], fill='#4CAF50')
            # Häkchen zeichnen
            draw.line([(15, 26), (22, 33)], fill='white', width=4)
            draw.line([(22, 33), (35, 18)], fill='white', width=4)
        
        self.icons[name] = ImageTk.PhotoImage(img)
        print(f"✓ Fallback-Icon erstellt: {name}")
        
    def setup_google_ai(self):
        try:
            # Suchen Sie nach dem Service-Account-Schlüssel im gleichen Verzeichnis
            credentials_path = 'Official_Key.json' 
            if not os.path.exists(credentials_path):
                self.log_to_ui(f"FEHLER: '{credentials_path}' nicht gefunden!")
                return

            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            
            with open(credentials_path, 'r') as f:
                service_account_info = json.load(f)
                project_id = service_account_info.get('project_id')
            
            print(f"✓ Service Account geladen für Projekt: {project_id}")
            self.log_to_ui(f"Service Account geladen: {project_id}")
            
            vertexai.init(
                project=project_id,
                location='europe-west4', # Stabile Region für Vertex AI
                credentials=credentials
            )
            
            # KONSISTENZ-FIX: Modellname und Log-Nachricht angeglichen
            model_name = 'gemini-2.5-flash'
            self.model = GenerativeModel(model_name)
            print(f"✓ Vertex AI Model initialisiert: {model_name}")
            self.log_to_ui(f"Vertex AI bereit ({model_name})")
            
        except Exception as e:
            error_msg = f"Fehler bei Google AI Setup: {str(e)}"
            print(f"✗ {error_msg}")
            traceback.print_exc()
            self.log_to_ui(error_msg)
            
    def log_to_ui(self, message):
        if hasattr(self, 'log_label'):
            self.log_label.config(text=message)
            self.root.update_idletasks()

    def create_ui(self):
        # Hintergrundfarbe
        self.root.configure(bg='#f0f0f0')
                
        # Top Frame für Logo und Counter (horizontal nebeneinander)
        top_frame = tk.Frame(self.root, bg='#f0f0f0')
        top_frame.pack(pady=(20, 10))

        # Container für Logo und Counter (zentriert)
        logo_counter_container = tk.Frame(top_frame, bg='#f0f0f0')
        logo_counter_container.pack(expand=True)

        # Logo zentriert
        logo_label = tk.Label(logo_counter_container, image=self.icons['logo'], bg='#f0f0f0')
        logo_label.pack(side='left', padx=(100, 10)) # <-- Wert von 65 auf 80 erhöht

        # Counter direkt neben dem Logo
        self.counter_canvas = tk.Canvas(logo_counter_container, width=60, height=40, bg='#f0f0f0', highlightthickness=0)
        # HIER IST DIE GEÄNDERTE ZEILE:
        self.counter_canvas.pack(side='left', padx=(20, 0)) # <-- Geändert: 20px Leerraum links vom Zähler hinzugefügt
        self.create_rounded_rectangle(self.counter_canvas, 2, 2, 58, 38, radius=15, fill='#6B8EF5', outline="")
        self.counter_text = self.counter_canvas.create_text(30, 21, text="0", font=("Arial", 16, "bold"), fill="white")
        
        # Canvas für Mikrofon und Animation
        self.canvas = Canvas(self.root, width=300, height=250, bg='#f0f0f0', highlightthickness=0)
        self.canvas.pack(pady=(10, 5))  # Unten weniger Abstand
        
        # Mikrofon-Button (zentriert)
        self.mic_button = self.canvas.create_image(150, 125, image=self.icons['mic'])
        self.canvas.tag_bind(self.mic_button, '<Button-1>', lambda e: self.toggle_recording())
        
        # Button-Frame unten
        button_frame = tk.Frame(self.root, bg='#f0f0f0')
        button_frame.pack(pady=(0, 20))  # Oben kein Abstand mehr, die Buttons rücken näher
        
        # Mülltonne Button
        self.trash_button = tk.Button(button_frame, image=self.icons['trash'], 
                                    command=self.show_delete_dialog, borderwidth=0, 
                                    bg='#f0f0f0', activebackground='#f0f0f0')
        self.trash_button.pack(side=tk.LEFT, padx=15)
        
        # X Button
        self.cross_button = tk.Button(button_frame, image=self.icons['cross'], 
                                    command=self.delete_last_recording, borderwidth=0,
                                    bg='#f0f0f0', activebackground='#f0f0f0')
        self.cross_button.pack(side=tk.LEFT, padx=15)
        
        # Haken Button
        self.check_button = tk.Button(button_frame, image=self.icons['check'], 
                                    command=self.finish_recordings, borderwidth=0,
                                    bg='#f0f0f0', activebackground='#f0f0f0',
                                    state='disabled')
        self.check_button.pack(side=tk.LEFT, padx=15)
        
        # Status Label (versteckt für minimales Design)
        self.status_label = tk.Label(self.root, text="", bg='#f0f0f0', font=("Arial", 10))
        self.log_label = tk.Label(self.root, text="", bg='#f0f0f0', font=("Arial", 9))
        
        # Tastaturkürzel
        self.root.bind('<F9>', lambda e: self.toggle_recording())
        self.root.bind('<F10>', lambda e: self.finish_recordings())
        self.root.bind('<Escape>', lambda e: self.hide_window())

    def animate_waves(self):
        """Animiert die Wellen beim Aufnehmen mit einem flüssigen Ausblenden."""
        if not self.animation_running:
            return

        # Canvas leeren, um die Szene für den nächsten Frame neu zu zeichnen
        self.canvas.delete("wave")

        # --- Animationsparameter ---
        # Der Radius, bei dem eine Welle komplett unsichtbar ist
        max_radius = 140
        # Der Abstand zwischen den einzelnen Wellen
        wave_spacing = 35
        # Anzahl der gleichzeitig sichtbaren Wellen
        num_waves = 58
        # Die Gesamtlänge des Zyklus, nach der sich das Muster wiederholt
        cycle_length = wave_spacing * num_waves

        # Zeichne alle Wellen basierend auf der aktuellen "Zeit" (self.wave_radius)
        for i in range(num_waves):
            # Der Modulo hier sorgt für den Endlos-Effekt: Eine Welle, die den
            # Zyklus verlässt, wird wieder als kleinste Welle "geboren".
            radius = (self.wave_radius + (i * wave_spacing)) % cycle_length

            # Berechne die Transparenz basierend auf dem Radius.
            # Je näher am Rand (max_radius), desto transparenter.
            if radius < max_radius:
                # Eine nichtlineare Abnahme (hier: quadratisch) sieht natürlicher aus.
                # Sie lässt die Welle im Zentrum heller und blendet sie am Rand schneller aus.
                alpha_ratio = 1.0 - (radius / max_radius)

                # Simuliere Transparenz durch Mischen der Wellenfarbe mit der Hintergrundfarbe.
                # Hintergrund: #f0f0f0 -> (240, 240, 240)
                # Wellenfarbe: #6B8EF5 -> (107, 142, 245)
                bg_r, bg_g, bg_b = 240, 240, 240
                wave_r, wave_g, wave_b = 107, 142, 245

                r = int(wave_r * alpha_ratio + bg_r * (1 - alpha_ratio))
                g = int(wave_g * alpha_ratio + bg_g * (1 - alpha_ratio))
                b = int(wave_b * alpha_ratio + bg_b * (1 - alpha_ratio))
                color = f'#{r:02x}{g:02x}{b:02x}'

                self.canvas.create_oval(
                    150 - radius, 125 - radius,
                    150 + radius, 125 + radius,
                    outline=color, width=3, tags="wave"
                )

        # Mikrofon wieder in den Vordergrund bringen
        self.canvas.tag_raise(self.mic_button)

        # Die "Zeit" der Animation voranschreiten lassen.
        # WICHTIG: Der kleine Modulo-Wert (`% 20`) wurde hier entfernt,
        # damit die Wellen kontinuierlich nach außen laufen können.
        self.wave_radius += 2

        # Nächsten Animationsschritt planen
        if self.animation_running:
            self.root.after(40, self.animate_waves) # 40ms für eine flüssige Animation

    def delete_last_recording(self):
        """Löscht die letzte Aufnahme"""
        if self.all_recordings:
            self.all_recordings.pop()
            self.recording_count = max(0, self.recording_count - 1)
            self.counter_canvas.itemconfig(self.counter_text, text=str(self.recording_count))
            if self.recording_count == 0:
                self.check_button.config(state='disabled')
            self.log_to_ui(f"Letzte Aufnahme gelöscht")

    def show_delete_dialog(self):
        """Zeigt ein Popup-Fenster, um ausgewählte Aufnahmen zu löschen."""
        if not self.all_recordings:
            self.log_to_ui("Keine Aufnahmen zum Löschen vorhanden.")
            return

        # Erstelle das Popup-Fenster (Toplevel)
        self.delete_dialog = tk.Toplevel(self.root)
        self.delete_dialog.title("Aufnahmen löschen")
        self.delete_dialog.geometry("300x400")
        self.delete_dialog.resizable(False, False)
        self.delete_dialog.transient(self.root) # Dialog bleibt über dem Hauptfenster
        self.delete_dialog.grab_set() # Macht den Dialog modal

        tk.Label(self.delete_dialog, text="Wähle die zu löschenden Aufnahmen:", 
                font=("Arial", 11)).pack(pady=(10, 5))

        # Frame für die Checkboxen mit Scrollbar
        list_frame = tk.Frame(self.delete_dialog)
        list_frame.pack(pady=5, padx=10, fill="both", expand=True)
        
        list_canvas = tk.Canvas(list_frame)
        list_canvas.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=list_canvas.yview)
        scrollbar.pack(side="right", fill="y")

        scrollable_frame = ttk.Frame(list_canvas)
        list_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        scrollable_frame.bind("<Configure>", lambda e: list_canvas.configure(scrollregion=list_canvas.bbox("all")))
        list_canvas.configure(yscrollcommand=scrollbar.set)

        # Erstelle eine Checkbox für jede Aufnahme
        self.checkbox_vars = []
        for i in range(self.recording_count):
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(scrollable_frame, text=f"Aufnahme {i + 1}", variable=var)
            cb.pack(anchor="w", padx=10, pady=3)
            self.checkbox_vars.append(var)

        # Frame für die Buttons
        button_frame = tk.Frame(self.delete_dialog)
        button_frame.pack(pady=10)

        # Buttons zum Bestätigen oder Abbrechen
        confirm_btn = ttk.Button(button_frame, text="Auswahl löschen", 
                                command=self.confirm_deletion)
        confirm_btn.pack(side="left", padx=10)

        cancel_btn = ttk.Button(button_frame, text="Abbrechen", 
                                command=self.delete_dialog.destroy)
        cancel_btn.pack(side="left", padx=10)


    def confirm_deletion(self):
        """Löscht die ausgewählten Aufnahmen und aktualisiert die UI."""
        # Erstellt eine neue Liste, die nur die Aufnahmen enthält, die NICHT gelöscht werden sollen.
        # Dies ist sicherer als das Löschen von Elementen während der Iteration.
        recordings_to_keep = []
        deleted_count = 0

        for i, var in enumerate(self.checkbox_vars):
            if not var.get(): # Wenn die Checkbox NICHT angehakt ist...
                recordings_to_keep.append(self.all_recordings[i])
            else:
                deleted_count += 1
        
        # Aktualisiere die Listen und Zähler
        self.all_recordings = recordings_to_keep
        self.recording_count = len(self.all_recordings)

        # Aktualisiere die UI
        self.counter_canvas.itemconfig(self.counter_text, text=str(self.recording_count))
        if self.recording_count == 0:
            self.check_button.config(state='disabled')
        
        self.log_to_ui(f"{deleted_count} Aufnahme(n) erfolgreich gelöscht.")
        
        # Schließe das Popup-Fenster
        self.delete_dialog.destroy()
    

    def set_append_mode(self):
        # Modus zum Ergänzen eines bestehenden Transkripts aktivieren
        self.append_mode = True
        self.transcript_options_frame.pack_forget()
        self.status_label.config(text="Modus: Transkript ergänzen - Neue Aufnahme startet...")
        self.root.after(1000, self.reset_for_new_recording)
        
    def set_new_mode(self):
        # Modus für ein komplett neues Transkript aktivieren
        self.append_mode = False
        self.existing_transcript = ""
        self.has_transcript = False
        self.transcript_options_frame.pack_forget()
        self.status_label.config(text="Modus: Neues Transkript - Neue Aufnahme startet...")
        self.root.after(1000, self.reset_for_new_recording)
        
    def reset_for_new_recording(self):
        # UI und Variablen für eine neue Aufnahmeserie zurücksetzen
        self.all_recordings = []
        self.recording_count = 0
        self.counter_canvas.itemconfig(self.counter_text, text="0")
        self.status_label.config(text="Bereit - Klicken Sie auf das Mikrofon")
        self.check_button.config(state="disabled")
        
        if self.finished_label:
            self.finished_label.pack_forget()
        
    def toggle_recording(self):
        # Aufnahme starten oder stoppen
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        # Eine neue Audio-Aufnahme starten
        self.is_recording = True
        self.animation_running = True
        self.animate_waves()
        self.audio_data = []
        self.status_label.config(text="🔴 Aufnahme läuft...")
        self.log_to_ui("Aufnahme gestartet")
        if self.finished_label:
            self.finished_label.pack_forget()
        self.record_thread = threading.Thread(target=self.record_audio)
        self.record_thread.start()
        
    def record_audio(self):
        # Audio-Stream mit sounddevice aufnehmen
        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=1, 
                               callback=self.audio_callback):
                while self.is_recording:
                    time.sleep(0.1)
        except Exception as e:
            print(f"Audio-Fehler: {e}")
            self.log_to_ui(f"Audio-Fehler: {str(e)}")
                
    def audio_callback(self, indata, frames, time, status):
        # Callback-Funktion, die Audiodaten sammelt
        if self.is_recording:
            self.audio_data.append(indata.copy())
            

    def stop_recording(self):
        # Aktuelle Aufnahme beenden und speichern
        self.is_recording = False
        self.animation_running = False
        self.canvas.delete("wave")
        self.status_label.config(text="Speichere Aufnahme...")
        
        if self.audio_data:
            audio_array = np.concatenate(self.audio_data, axis=0)
            self.all_recordings.append(audio_array)
            self.recording_count += 1
            
            self.counter_canvas.itemconfig(self.counter_text, text=str(self.recording_count))
            self.status_label.config(text=f"✅ Aufnahme {self.recording_count} gespeichert")
            
            if self.recording_count > 0:
                self.check_button.config(state='normal')

    def finish_recordings(self):
        # Verarbeitung aller Aufnahmen anstoßen
        if not self.all_recordings:
            self.status_label.config(text="Keine Aufnahmen vorhanden!")
            return
            
        self.check_button.config(state="disabled")
        self.status_label.config(text="Verarbeite alle Aufnahmen...")
        
        # Progress bar erstellen wenn noch nicht vorhanden
        if not self.progress:
            self.progress = ttk.Progressbar(self.root, mode='indeterminate')
        
        self.progress.pack(pady=10, padx=20, fill=tk.X)
        self.progress.start()
        
        # Verarbeitung in einem separaten Thread starten
        process_thread = threading.Thread(target=self.process_all_recordings, daemon=True)
        process_thread.start()

        # Den Queue-Checker starten
        self.check_result_queue()
        
    def check_result_queue(self):
        """Prüft die Queue auf Ergebnisse aus dem Worker-Thread."""
        try:
            result = self.result_queue.get_nowait()
            # Ergebnis erhalten, Verarbeitung im UI-Thread
            if isinstance(result, Exception):
                self.reset_ui_on_error(str(result))
            else:
                self.show_completion(result)
        except queue.Empty:
            # Noch kein Ergebnis, in 100ms erneut prüfen
            self.root.after(100, self.check_result_queue)

    def process_all_recordings(self):
        """Führt die langwierige Verarbeitung (Audio, Transkription, KI) im Hintergrund durch."""
        try:
            # Alle Audio-Teile mit einer kurzen Pause dazwischen zusammenfügen
            pause_samples = int(0.5 * self.sample_rate)
            pause = np.zeros((pause_samples, 1))
            combined_audio = []
            for i, recording in enumerate(self.all_recordings):
                combined_audio.append(recording)
                if i < len(self.all_recordings) - 1:
                    combined_audio.append(pause)
            audio_array = np.concatenate(combined_audio, axis=0)
            
            # Temporäre WAV-Datei erstellen
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                sf.write(tmp_file.name, audio_array, self.sample_rate)
                temp_path = tmp_file.name
            
            with open(temp_path, 'rb') as f:
                audio_bytes = f.read()
            
            # Audio an Google AI zur Transkription senden
            if self.model is None:
                raise Exception("Google AI Model nicht initialisiert! Prüfen Sie Official_Key.json")
                
            audio_part = Part.from_data(data=audio_bytes, mime_type="audio/wav")
            response_transcribe = self.model.generate_content(
                ["Bitte transkribiere das folgende deutsche Audio exakt wie gesprochen:", audio_part],
                generation_config={"temperature": 0.1, "max_output_tokens": 8192}
            )
            transcript = response_transcribe.text
            
            # --- START DER IMPLEMENTIERUNG FÜR DAS ERGÄNZEN ---
            # Je nach Modus (neu vs. ergänzen) wird ein anderer Prompt für die KI gewählt.
            if self.append_mode and self.existing_transcript:
                # Dieser Prompt wird verwendet, wenn ein bestehender Text ergänzt werden soll.
                prompt_summarize = f"""
Du bist eine hochqualifizierte zahnmedizinische Fachassistenz, die eine bestehende Patientendokumentation aktualisieren soll.

**AUFGABE:**
Integriere die Informationen aus einer neuen Audio-Transkription nahtlos und logisch in eine bereits existierende Dokumentation. Das Ergebnis soll ein einziger, kohärenter und professioneller Text sein, der für die DAMPSOFT-Software formatiert ist.

**BESTEHENDE DOKUMENTATION:**
```
{self.existing_transcript}
```

**NEUE INFORMATIONEN (aus der aktuellen Audio-Transkription):**
```
{transcript}
```

**ANWEISUNGEN:**
1.  **Analysiere** die bestehende Dokumentation und die neuen Informationen.
2.  **Fasse** die relevanten Punkte aus der neuen Transkription zusammen.
3.  **Füge** diese neuen Punkte an den passenden Stellen in die bestehende Dokumentation ein (z.B. neue Befunde zu "BEFUND", neue Maßnahmen zu "THERAPIE").
4.  **Korrigiere oder ergänze** bestehende Punkte, falls die neuen Informationen dies erfordern.
5.  **Stelle sicher, dass der finale Text keine Wiederholungen enthält** und sich liest wie aus einem Guss.
6.  **Behalte exakt die folgende Formatierung bei** und fülle die Sektionen entsprechend:
    BEFUND:
    [Alle relevanten Befunde, kombiniert aus alt und neu]
    DIAGNOSE:
    [Alle Diagnosen, kombiniert aus alt und neu]
    THERAPIE:
    [Alle Therapieschritte, kombiniert aus alt und neu]
    BEMERKUNGEN:
    [Alle Bemerkungen, kombiniert aus alt und neu]

Erstelle jetzt die finale, zusammengeführte Dokumentation.
"""
            else:
                # Dies ist der Standard-Prompt für eine komplett neue Dokumentation.
                prompt_summarize = f"""
                Du bist eine zahnmedizinische Fachassistenz. Erstelle aus der folgenden Transkription eine strukturierte Dokumentation für DAMPSOFT.
                Formatiere die Ausgabe wie folgt:
                BEFUND:
                [Hier die relevanten Befunde]
                DIAGNOSE:
                [Diagnosen mit ICD-10 wenn möglich (einschließlich der erweiterten oder Folgediagnose
                Beispiel: Zahnarzt entscheidet sich die Diagnose mit Röntkenbild zu erweitern. Da das ein diagnostischer Schritt ist, würde dieser Punkt unter Diagnose und NICHT unter
                Therapie fallen)]
                THERAPIE:
                [Durchgeführte/geplante Behandlungen]
                BEMERKUNGEN:
                [Weitere relevante Informationen]
                
                Transkription:
                {transcript}
                """
            # --- ENDE DER IMPLEMENTIERUNG ---
            
            # Den gewählten Prompt an die KI zur Zusammenfassung/Bearbeitung senden
            response_summarize = self.model.generate_content(
                prompt_summarize,
                generation_config={"temperature": 0.3, "max_output_tokens": 8192}
            )
            summary = response_summarize.text
            
            # Ergebnis in eine Textdatei auf dem Desktop speichern
            desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
            output_dir = os.path.join(desktop_path, 'DiktierAssistent')
            output_path = os.path.join(output_dir, 'output.txt')
            os.makedirs(output_dir, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(summary)
            os.unlink(temp_path) # Temporäre WAV-Datei löschen
            
            # Erfolgreiches Ergebnis in die Queue legen
            self.result_queue.put(summary)
            
        except Exception as e:
            print("\n\n!!! FEHLER IN 'process_all_recordings' !!!")
            traceback.print_exc()
            # Fehler in die Queue legen, um ihn in der UI anzuzeigen
            self.result_queue.put(e)
            
    def show_completion(self, summary):
        """UI-Updates nach erfolgreicher Verarbeitung."""
        if self.progress:
            self.progress.stop()
            self.progress.pack_forget()
        
        # Den neuen Text als "bestehendes Transkript" speichern
        self.existing_transcript = summary
        self.has_transcript = True
        
        self.status_label.config(text="Transkript wurde erfolgreich gespeichert!")
        self.log_to_ui(f"Gespeichert: ~/Desktop/DiktierAssistent/output.txt")
        
        # Finished Label erstellen wenn noch nicht vorhanden
        if not self.finished_label:
            self.finished_label = ttk.Label(self.root, text="✅ FERTIG - Transkript wurde gespeichert!", 
                                        font=("Arial", 14, "bold"), foreground="green")
        self.finished_label.pack(pady=20)
        
        self.check_button.config(state="disabled")
        
        # Nach einer kurzen Pause die Optionen anzeigen
        self.root.after(2000, self.show_transcript_options)
        
    def show_transcript_options(self):
        # Buttons für "Ergänzen" oder "Neu aufnehmen" anzeigen
        if self.finished_label:
            self.finished_label.pack_forget()
        
        self.status_label.config(text="Was möchten Sie als nächstes tun?")
        
        # Frame erstellen wenn noch nicht vorhanden
        if not self.transcript_options_frame:
            self.transcript_options_frame = ttk.Frame(self.root)
            self.append_button = ttk.Button(self.transcript_options_frame, 
                                        text="📝 Transkript ergänzen", 
                                        command=self.set_append_mode)
            self.append_button.pack(side=tk.LEFT, padx=5)
            self.new_button = ttk.Button(self.transcript_options_frame, 
                                        text="🔄 Transkript neu aufnehmen", 
                                        command=self.set_new_mode)
            self.new_button.pack(side=tk.LEFT, padx=5)
        
        self.transcript_options_frame.pack(pady=10)
        
    def reset_ui_on_error(self, error_msg):
        """UI-Updates im Fehlerfall."""
        if self.progress:
            self.progress.stop()
            self.progress.pack_forget()
        
        self.status_label.config(text=f"❌ Fehler: {error_msg}", wraplength=480)
        self.log_to_ui(error_msg)
        self.check_button.config(state="disabled")
        self.all_recordings = []
        self.recording_count = 0
        self.counter_canvas.itemconfig(self.counter_text, text="0")
    
    def setup_tray_icon(self):
        """Erstellt das Tray-Icon"""
        # Icon erstellen (einfacher roter Kreis)
        image = Image.new('RGB', (64, 64), color='white')
        draw = ImageDraw.Draw(image)
        draw.ellipse([8, 8, 56, 56], fill='red', outline='darkred')
        
        # Menü für Tray-Icon
        menu = pystray.Menu(
            pystray.MenuItem("Öffnen", self.show_window),
            pystray.MenuItem("Beenden", self.quit_app)
        )
        
        self.tray_icon = pystray.Icon(
            "DiktierAssistent",
            image,
            "Dictate Pro - Prozessagent",
            menu
        )
        
        # Tray-Icon in separatem Thread starten
        icon_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        icon_thread.start()
        
    def setup_global_hotkey(self):
        """Registriert globalen Hotkey Ctrl+Alt+F9"""
        def hotkey_handler():
            self.root.after(0, self.show_window)
            
        keyboard.add_hotkey('ctrl+8', hotkey_handler)
        self.log_to_ui("Hotkey Ctrl+8 aktiviert")
        
    def hide_window(self):
        """Versteckt das Fenster statt es zu schließen"""
        self.root.withdraw()
        
    def show_window(self):
        """Zeigt das Fenster wieder an"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        
    def quit_app(self):
        """Beendet die Anwendung komplett"""
        try:
            self.tray_icon.stop()
        except:
            pass
        self.root.quit()

if __name__ == "__main__":
    root = tk.Tk()
    app = DiktierAssistent(root)
    
    # Fenster beim Start verstecken (optional)
    root.withdraw()
    
    root.mainloop()