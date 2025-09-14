"""
Enhanced Test Application with PDF Upload and Audio Processing
Combines PDF reading, text extraction, TTS, and Whisper transcription
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import os
import sys
import yaml
from pathlib import Path
import time

# Import custom modules
try:
    from standalone_whisper import StandaloneWhisperApp
except ImportError:
    print("Warning: StandaloneWhisperApp not found. Transcription will be disabled.")
    StandaloneWhisperApp = None

try:
    from pdf_processor import PDFProcessor
    from tts_engine import AudioController
except ImportError as e:
    print(f"Warning: Required modules not found: {e}")
    PDFProcessor = None
    AudioController = None

class TestApplication:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Learning Assistant - PDF to Audio Test System")
        self.root.geometry("1000x800")
        
        # Initialize variables
        self.pdf_text = ""
        self.questions = []
        self.current_question_index = 0
        self.audio_queue = queue.Queue()
        self.is_playing = False
        self.is_paused = False
        self.current_audio_file = None
        self.is_transcribing = False
        
        # Load config
        self.config = self.load_config()
        
        # Initialize components
        self.pdf_processor = PDFProcessor() if PDFProcessor else None
        self.audio_controller = AudioController(self.audio_status_callback) if AudioController else None
        self.transcriber = None
        self.init_whisper()
        
        # Setup GUI
        self.create_widgets()
        self.setup_layout()

    def audio_status_callback(self, status, message):
        """Callback for audio status updates"""
        def update_ui():
            if status == 'playing':
                self.play_button.config(state="disabled")
                self.pause_button.config(state="normal")
                self.stop_button.config(state="normal")
                self.status_bar.config(text=message)
            elif status == 'paused':
                self.play_button.config(state="normal")
                self.pause_button.config(state="disabled")
                self.stop_button.config(state="normal")
                self.status_bar.config(text=message)
            elif status == 'stopped' or status == 'completed':
                self.play_button.config(state="normal")
                self.pause_button.config(state="disabled")
                self.stop_button.config(state="disabled")
                self.status_bar.config(text=message)
            elif status == 'error':
                self.play_button.config(state="normal")
                self.pause_button.config(state="disabled")
                self.stop_button.config(state="disabled")
                self.status_bar.config(text=f"Error: {message}")
        
        # Schedule UI update in main thread
        self.root.after(0, update_ui)

    def load_config(self):
        """Load configuration from config.yaml"""
        config_path = Path("config.yaml")
        if config_path.exists():
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        else:
            # Default config if file not found
            return {
                'audio': {
                    'sample_rate': 16000,
                    'chunk_duration': 4,
                    'channels': 1
                },
                'processing': {
                    'max_workers': 4,
                    'silence_threshold': 0.001,
                    'queue_timeout': 1.0
                },
                'model_paths': {
                    'encoder_path': 'models/WhisperEncoder.onnx',
                    'decoder_path': 'models/WhisperDecoder.onnx'
                }
            }

    def init_whisper(self):
        """Initialize Whisper transcriber if available"""
        try:
            if StandaloneWhisperApp:
                self.transcriber = StandaloneWhisperApp()
                print("Whisper transcriber initialized successfully")
            else:
                print("Whisper transcriber not available")
        except Exception as e:
            print(f"Error initializing Whisper: {e}")
            self.transcriber = None

    def create_widgets(self):
        """Create all GUI widgets"""
        
        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        
        # PDF Upload Tab
        self.pdf_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.pdf_frame, text="PDF Upload & Processing")
        
        # Audio Control Tab
        self.audio_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.audio_frame, text="Audio Controls")
        
        # Transcription Tab
        self.transcription_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.transcription_frame, text="Voice Response")
        
        self.create_pdf_widgets()
        self.create_audio_widgets()
        self.create_transcription_widgets()

    def create_pdf_widgets(self):
        """Create PDF upload and processing widgets"""
        
        # PDF Upload Section
        upload_frame = ttk.LabelFrame(self.pdf_frame, text="PDF Upload", padding=10)
        upload_frame.pack(fill="x", padx=10, pady=5)
        
        self.upload_button = ttk.Button(
            upload_frame, 
            text="Select PDF File", 
            command=self.upload_pdf
        )
        self.upload_button.pack(side="left", padx=5)
        
        self.pdf_label = ttk.Label(upload_frame, text="No file selected")
        self.pdf_label.pack(side="left", padx=10)
        
        # Processing Options
        options_frame = ttk.LabelFrame(self.pdf_frame, text="Processing Options", padding=10)
        options_frame.pack(fill="x", padx=10, pady=5)
        
        self.use_ocr = tk.BooleanVar(value=False)
        self.ocr_checkbox = ttk.Checkbutton(
            options_frame, 
            text="Use OCR for image-based PDFs", 
            variable=self.use_ocr
        )
        self.ocr_checkbox.pack(side="left")
        
        self.extract_questions = tk.BooleanVar(value=True)
        self.questions_checkbox = ttk.Checkbutton(
            options_frame, 
            text="Extract questions automatically", 
            variable=self.extract_questions
        )
        self.questions_checkbox.pack(side="left", padx=20)
        
        # Process Button
        self.process_button = ttk.Button(
            options_frame, 
            text="Process PDF", 
            command=self.process_pdf,
            state="disabled"
        )
        self.process_button.pack(side="right")
        
        # Text Display
        text_frame = ttk.LabelFrame(self.pdf_frame, text="Extracted Text", padding=10)
        text_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.text_display = scrolledtext.ScrolledText(
            text_frame, 
            height=20, 
            wrap=tk.WORD,
            state="disabled"
        )
        self.text_display.pack(fill="both", expand=True)

    def create_audio_widgets(self):
        """Create audio control widgets"""
        
        # Current Question Display
        question_frame = ttk.LabelFrame(self.audio_frame, text="Current Question", padding=10)
        question_frame.pack(fill="x", padx=10, pady=5)
        
        self.question_display = scrolledtext.ScrolledText(
            question_frame, 
            height=5, 
            wrap=tk.WORD,
            state="disabled"
        )
        self.question_display.pack(fill="both", expand=True)
        
        # Navigation Controls
        nav_frame = ttk.Frame(self.audio_frame)
        nav_frame.pack(fill="x", padx=10, pady=5)
        
        self.prev_button = ttk.Button(
            nav_frame, 
            text="◀ Previous", 
            command=self.previous_question,
            state="disabled"
        )
        self.prev_button.pack(side="left", padx=5)
        
        self.question_counter = ttk.Label(nav_frame, text="Question 0 of 0")
        self.question_counter.pack(side="left", padx=20)
        
        self.next_button = ttk.Button(
            nav_frame, 
            text="Next ▶", 
            command=self.next_question,
            state="disabled"
        )
        self.next_button.pack(side="left", padx=5)
        
        # Audio Controls
        audio_controls_frame = ttk.LabelFrame(self.audio_frame, text="Audio Controls", padding=10)
        audio_controls_frame.pack(fill="x", padx=10, pady=5)
        
        # Speed Control
        speed_frame = ttk.Frame(audio_controls_frame)
        speed_frame.pack(fill="x", pady=5)
        
        ttk.Label(speed_frame, text="Reading Speed:").pack(side="left")
        
        self.speed_var = tk.DoubleVar(value=1.0)
        self.speed_scale = ttk.Scale(
            speed_frame, 
            from_=0.5, 
            to=2.0, 
            variable=self.speed_var,
            orient="horizontal",
            length=200
        )
        self.speed_scale.pack(side="left", padx=10)
        
        self.speed_label = ttk.Label(speed_frame, text="1.0x")
        self.speed_label.pack(side="left", padx=5)
        
        # Update speed label
        self.speed_var.trace('w', self.update_speed_label)
        
        # Playback Controls
        playback_frame = ttk.Frame(audio_controls_frame)
        playback_frame.pack(fill="x", pady=10)
        
        self.play_button = ttk.Button(
            playback_frame, 
            text="▶ Play", 
            command=self.play_current_question,
            state="disabled"
        )
        self.play_button.pack(side="left", padx=5)
        
        self.pause_button = ttk.Button(
            playback_frame, 
            text="⏸ Pause", 
            command=self.pause_audio,
            state="disabled"
        )
        self.pause_button.pack(side="left", padx=5)
        
        self.stop_button = ttk.Button(
            playback_frame, 
            text="⏹ Stop", 
            command=self.stop_audio,
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=5)
        
        self.repeat_button = ttk.Button(
            playback_frame, 
            text="🔁 Repeat", 
            command=self.repeat_current,
            state="disabled"
        )
        self.repeat_button.pack(side="left", padx=5)

    def create_transcription_widgets(self):
        """Create voice transcription widgets"""
        
        # Transcription Controls
        controls_frame = ttk.LabelFrame(self.transcription_frame, text="Voice Response Controls", padding=10)
        controls_frame.pack(fill="x", padx=10, pady=5)
        
        self.transcribe_button = ttk.Button(
            controls_frame, 
            text="🎤 Start Listening", 
            command=self.toggle_transcription,
            state="disabled" if not self.transcriber else "normal"
        )
        self.transcribe_button.pack(side="left", padx=5)
        
        self.transcription_status = ttk.Label(controls_frame, text="Ready")
        self.transcription_status.pack(side="left", padx=20)
        
        # Transcription Display
        transcription_display_frame = ttk.LabelFrame(self.transcription_frame, text="Your Response", padding=10)
        transcription_display_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.transcription_display = scrolledtext.ScrolledText(
            transcription_display_frame, 
            height=10, 
            wrap=tk.WORD
        )
        self.transcription_display.pack(fill="both", expand=True)

    def setup_layout(self):
        """Setup the main layout"""
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Status bar
        self.status_bar = ttk.Label(
            self.root, 
            text="Ready - Please upload a PDF to begin",
            relief="sunken"
        )
        self.status_bar.pack(fill="x", side="bottom")

    def upload_pdf(self):
        """Handle PDF file upload"""
        file_path = filedialog.askopenfilename(
            title="Select PDF file",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        
        if file_path:
            self.pdf_file_path = file_path
            filename = os.path.basename(file_path)
            self.pdf_label.config(text=f"Selected: {filename}")
            self.process_button.config(state="normal")
            self.status_bar.config(text=f"PDF selected: {filename}")

    def process_pdf(self):
        """Process the uploaded PDF file"""
        if not hasattr(self, 'pdf_file_path'):
            messagebox.showerror("Error", "Please select a PDF file first")
            return
        
        self.status_bar.config(text="Processing PDF... This may take a moment")
        self.process_button.config(state="disabled")
        
        # Run processing in separate thread to avoid blocking UI
        threading.Thread(target=self._process_pdf_thread, daemon=True).start()

    def _process_pdf_thread(self):
        """PDF processing thread"""
        try:
            if not self.pdf_processor:
                raise Exception("PDF processor not available")
                
            self.root.after(0, lambda: self.status_bar.config(text="Extracting text from PDF..."))
            
            # Extract text from PDF
            use_ocr = self.use_ocr.get()
            self.pdf_text = self.pdf_processor.extract_text_from_pdf(
                self.pdf_file_path, 
                use_ocr=use_ocr
            )
            
            if not self.pdf_text.strip():
                raise Exception("No text could be extracted from the PDF")
            
            self.root.after(0, lambda: self.status_bar.config(text="Processing extracted text..."))
            
            # Extract questions if requested
            if self.extract_questions.get():
                self.questions = self.pdf_processor.extract_questions(self.pdf_text)
                if not self.questions:
                    # If no questions found, use the full text
                    self.questions = [self.pdf_text]
            else:
                # Split text into manageable chunks
                self.questions = self.pdf_processor.chunk_text_by_sentences(self.pdf_text)
            
            # Update UI in main thread
            self.root.after(0, self._update_ui_after_processing)
            
        except Exception as e:
            error_msg = f"Error processing PDF: {str(e)}"
            self.root.after(0, lambda: messagebox.showerror("Processing Error", error_msg))
            self.root.after(0, lambda: self.process_button.config(state="normal"))
            self.root.after(0, lambda: self.status_bar.config(text="Processing failed"))

    def _update_ui_after_processing(self):
        """Update UI after PDF processing is complete"""
        # Update text display
        self.text_display.config(state="normal")
        self.text_display.delete(1.0, tk.END)
        self.text_display.insert(1.0, self.pdf_text)
        self.text_display.config(state="disabled")
        
        # Enable audio controls if questions found
        if self.questions:
            self.current_question_index = 0
            self.update_question_display()
            self.enable_audio_controls()
            
        self.process_button.config(state="normal")
        self.status_bar.config(text=f"Processing complete - Found {len(self.questions)} question(s)")

    def update_question_display(self):
        """Update the current question display"""
        if self.questions and 0 <= self.current_question_index < len(self.questions):
            question = self.questions[self.current_question_index]
            
            self.question_display.config(state="normal")
            self.question_display.delete(1.0, tk.END)
            self.question_display.insert(1.0, question)
            self.question_display.config(state="disabled")
            
            # Update counter
            self.question_counter.config(
                text=f"Question {self.current_question_index + 1} of {len(self.questions)}"
            )
            
            # Update navigation buttons
            self.prev_button.config(
                state="normal" if self.current_question_index > 0 else "disabled"
            )
            self.next_button.config(
                state="normal" if self.current_question_index < len(self.questions) - 1 else "disabled"
            )

    def enable_audio_controls(self):
        """Enable audio control buttons"""
        self.play_button.config(state="normal")
        self.repeat_button.config(state="normal")

    def previous_question(self):
        """Navigate to previous question"""
        if self.current_question_index > 0:
            self.current_question_index -= 1
            self.update_question_display()

    def next_question(self):
        """Navigate to next question"""
        if self.current_question_index < len(self.questions) - 1:
            self.current_question_index += 1
            self.update_question_display()

    def update_speed_label(self, *args):
        """Update speed display label"""
        speed = self.speed_var.get()
        self.speed_label.config(text=f"{speed:.1f}x")

    def play_current_question(self):
        """Play the current question using TTS"""
        if not self.questions or not self.audio_controller:
            messagebox.showerror("Error", "No audio controller available or no questions loaded")
            return
        
        question = self.questions[self.current_question_index]
        speed = self.speed_var.get()
        
        # Play using the audio controller
        success = self.audio_controller.play_text(question, speed)
        
        if not success:
            messagebox.showerror("Error", "Failed to start audio playback")

    def pause_audio(self):
        """Pause audio playback"""
        if self.audio_controller:
            self.audio_controller.pause()

    def stop_audio(self):
        """Stop audio playback"""
        if self.audio_controller:
            self.audio_controller.stop()

    def repeat_current(self):
        """Repeat the current question"""
        if not self.questions or not self.audio_controller:
            messagebox.showerror("Error", "No audio controller available or no questions loaded")
            return
            
        # Get the current question and speed, then play it
        question = self.questions[self.current_question_index]
        speed = self.speed_var.get()
        
        # Stop current playback and play again
        self.audio_controller.stop()
        success = self.audio_controller.play_text(question, speed)
        
        if not success:
            messagebox.showerror("Error", "Failed to repeat audio playback")

    def audio_processor(self):
        """Audio processing thread"""
        # This is now handled by the AudioController
        pass

    def toggle_transcription(self):
        """Toggle voice transcription"""
        if not self.transcriber:
            messagebox.showerror("Error", "Whisper transcriber not available")
            return
        
        current_text = self.transcribe_button.cget("text")
        if "Start" in current_text:
            # Start transcription
            self.is_transcribing = True
            self.transcribe_button.config(text="🛑 Stop Listening")
            self.transcription_status.config(text="Listening...")
            
            # Start transcription in separate thread
            threading.Thread(target=self._transcription_thread, daemon=True).start()
        else:
            # Stop transcription
            self.is_transcribing = False
            self.transcribe_button.config(text="🎤 Start Listening")
            self.transcription_status.config(text="Ready")

    def _transcription_thread(self):
        """Handle voice transcription in separate thread"""
        try:
            while self.is_transcribing:
                # This would integrate with your existing Whisper transcription
                # For now, simulate transcription
                time.sleep(1)
                
                # In real implementation, this would capture audio and transcribe
                # Example integration with existing transcriber:
                # if self.transcriber:
                #     result = self.transcriber.transcribe_live()
                #     if result:
                #         self.root.after(0, lambda: self.update_transcription_display(result))
                
        except Exception as e:
            print(f"Transcription error: {e}")
            self.root.after(0, lambda: self.transcription_status.config(text=f"Error: {e}"))

    def update_transcription_display(self, text):
        """Update transcription display with new text"""
        self.transcription_display.insert(tk.END, text + "\n")
        self.transcription_display.see(tk.END)

def main():
    root = tk.Tk()
    app = TestApplication(root)
    root.mainloop()

if __name__ == "__main__":
    main()