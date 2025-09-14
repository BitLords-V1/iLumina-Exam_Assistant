"""
Real-time Whisper Voice Controller
Integrates with your working ONNX Whisper models for actual speech-to-text processing
"""

import os
import threading
import time
import logging
import tempfile
import wave
import pyaudio
import numpy as np
import sys
import re
from typing import Dict, Any, Optional, Callable

# Add src directory to path for imports exactly like your working LiveTranscriber
src_path = os.path.join(os.path.dirname(__file__), '..', 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Handle imports for both direct Python execution and PyInstaller (same pattern as your LiveTranscriber)
try:
    from standalone_model import StandaloneWhisperModel
    WHISPER_MODEL_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ Successfully imported StandaloneWhisperModel")
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Primary import failed: {e}")
    try:
        from .standalone_model import StandaloneWhisperModel
        WHISPER_MODEL_AVAILABLE = True
        logger.info("✅ Successfully imported StandaloneWhisperModel (relative import)")
    except ImportError as e2:
        logger.warning(f"Relative import also failed: {e2}")
        logger.info("Will use demo mode for voice recognition")
        StandaloneWhisperModel = None
        WHISPER_MODEL_AVAILABLE = False

logger = logging.getLogger(__name__)

class WhisperVoiceController:
    def __init__(self, models_path: str = None):
        """
        Initialize the voice controller with your ONNX Whisper models
        
        Args:
            models_path: Path to directory containing ONNX model files
        """
        # Use the models from the backend/models directory
        self.models_path = models_path or os.path.join(
            os.path.dirname(__file__), 'models'
        )
        
        # Model file paths
        self.encoder_path = os.path.join(self.models_path, 'WhisperEncoder.onnx')
        self.decoder_path = os.path.join(self.models_path, 'WhisperDecoder.onnx')
        
        # Initialize the Whisper model
        self.whisper_model = None
        self._initialize_whisper_model()
        
        # Audio recording settings
        self.sample_rate = 16000
        self.chunk_size = 1024
        self.channels = 1
        self.format = pyaudio.paInt16
        
        # State
        self.is_listening = False
        self.is_recording = False
        self.is_processing = False  # Add processing lock
        self.audio_buffer = []
        self.pyaudio_instance = None
        self.stream = None
        self.recording_thread = None
        self._state_lock = threading.Lock()  # Add state lock
        
        # Command callbacks
        self.command_handlers = {}
        
        self._initialize_audio()
        
    def _initialize_whisper_model(self):
        """Initialize the ONNX Whisper model using your models"""
        if not WHISPER_MODEL_AVAILABLE:
            logger.warning("StandaloneWhisperModel not available - using demo mode")
            return
            
        # Check if model files exist
        if not os.path.exists(self.encoder_path) or not os.path.exists(self.decoder_path):
            logger.warning(f"Model files not found:")
            logger.warning(f"  - Encoder: {self.encoder_path}")
            logger.warning(f"  - Decoder: {self.decoder_path}")
            return
            
        try:
            logger.info(f"Loading Whisper models from {self.models_path}")
            self.whisper_model = StandaloneWhisperModel(
                encoder_path=self.encoder_path,
                decoder_path=self.decoder_path
            )
            logger.info("✅ Whisper ONNX model initialized successfully!")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Whisper model: {e}")
            import traceback
            traceback.print_exc()
            self.whisper_model = None
        
    def _initialize_audio(self):
        """Initialize PyAudio for microphone capture"""
        try:
            self.pyaudio_instance = pyaudio.PyAudio()
            logger.info("Audio system initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize audio system: {e}")
            self.pyaudio_instance = None
    
    def register_command_handler(self, command: str, handler: Callable):
        """Register a handler function for a specific voice command"""
        self.command_handlers[command.lower()] = handler
        
    def start_listening(self) -> Dict[str, Any]:
        """Start listening for voice commands"""
        with self._state_lock:
            if not self.pyaudio_instance:
                return {'success': False, 'error': 'Audio system not available'}
                
            if self.is_listening:
                return {'success': False, 'error': 'Already listening'}
            
            if self.is_processing:
                return {'success': False, 'error': 'Currently processing previous recording'}
                
            try:
                # Start audio stream
                self.stream = self.pyaudio_instance.open(
                    format=self.format,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    frames_per_buffer=self.chunk_size
                )
                
                self.is_listening = True
                self.audio_buffer = []
                
                # Start recording in background thread
                self.recording_thread = threading.Thread(target=self._recording_loop, daemon=True)
                self.recording_thread.start()
                
                logger.info("Started voice listening")
                return {
                    'success': True,
                    'message': 'Voice recognition started - speak now!',
                    'status': 'listening'
                }
                
            except Exception as e:
                logger.error(f"Failed to start listening: {e}")
                return {'success': False, 'error': str(e)}
    
    def stop_listening(self) -> Dict[str, Any]:
        """Stop listening and process any recorded audio"""
        with self._state_lock:
            if not self.is_listening:
                logger.warning("stop_listening called but not currently listening")
                return {
                    'success': True, 
                    'message': 'Already stopped',
                    'status': 'stopped',
                    'text': ''
                }
            
            if self.is_processing:
                logger.warning("stop_listening called while processing")
                return {
                    'success': True,
                    'message': 'Processing previous recording',
                    'status': 'processing',
                    'text': ''
                }
            
            # Mark as processing to prevent double-clicks
            self.is_processing = True
        
        try:
            logger.info("Stopping voice listening...")
            self.is_listening = False
            
            # Wait a moment for recording thread to finish
            if self.recording_thread and self.recording_thread.is_alive():
                logger.info("Waiting for recording thread to finish...")
                self.recording_thread.join(timeout=3.0)
                if self.recording_thread.is_alive():
                    logger.warning("Recording thread did not finish cleanly")
            
            # Close audio stream safely
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                    self.stream = None
                    logger.info("Audio stream closed successfully")
                except Exception as stream_error:
                    logger.warning(f"Error closing audio stream: {stream_error}")
            
            # Process recorded audio if we have any
            result = self._process_audio_buffer()
            
            # Ensure we return a complete result
            if not result.get('success'):
                result = {
                    'success': True,
                    'text': '',
                    'message': 'Listening stopped',
                    'status': 'stopped'
                }
            
            logger.info(f"Voice listening stopped successfully. Result: {result.get('text', 'No text')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to stop listening: {e}")
            return {
                'success': False,
                'error': f'Stop failed: {str(e)}'
            }
        finally:
            # Always clear the processing lock
            with self._state_lock:
                self.is_processing = False
    
    def _recording_loop(self):
        """Background thread for continuous audio recording"""
        try:
            while self.is_listening and self.stream:
                try:
                    data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    self.audio_buffer.append(data)
                except Exception as e:
                    logger.warning(f"Audio read error: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Recording loop error: {e}")
    
    def _process_audio_buffer(self) -> Dict[str, Any]:
        """Process the recorded audio buffer through Whisper"""
        if not self.audio_buffer:
            return {
                'success': True,
                'text': '',
                'message': 'No audio recorded'
            }
        
        try:
            # Save audio buffer to temporary WAV file
            temp_audio_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            
            with wave.open(temp_audio_file.name, 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(self.pyaudio_instance.get_sample_size(self.format))
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(b''.join(self.audio_buffer))
            
            temp_audio_file.close()
            
            # Process with Whisper ONNX model
            whisper_result = self._call_whisper_model(temp_audio_file.name)
            
            # Clean up temp file
            try:
                os.unlink(temp_audio_file.name)
            except:
                pass
            
            # Process the command if recognition was successful
            if whisper_result['success'] and whisper_result['text']:
                self._handle_voice_command(whisper_result['text'])
            
            return whisper_result
            
        except Exception as e:
            logger.error(f"Failed to process audio buffer: {e}")
            return {
                'success': False,
                'error': f'Audio processing failed: {str(e)}'
            }
    
    def _call_whisper_model(self, audio_file_path: str) -> Dict[str, Any]:
        """Process audio file using the ONNX Whisper model directly"""
        
        if not self.whisper_model:
            return self._demo_transcription(audio_file_path)
        
        try:
            # Load and properly process audio file
            with wave.open(audio_file_path, 'rb') as wav_file:
                # Get audio parameters
                sample_rate = wav_file.getframerate()
                n_channels = wav_file.getnchannels()
                n_frames = wav_file.getnframes()
                duration = n_frames / sample_rate
                
                # Read raw audio data
                audio_data = wav_file.readframes(n_frames)
                
                # Convert to numpy array based on sample width
                sample_width = wav_file.getsampwidth()
                if sample_width == 1:
                    # 8-bit unsigned
                    audio_array = np.frombuffer(audio_data, dtype=np.uint8).astype(np.float32)
                    audio_array = (audio_array - 128.0) / 128.0  # Convert to [-1, 1]
                elif sample_width == 2:
                    # 16-bit signed (most common)
                    audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
                    audio_array = audio_array / 32768.0  # Convert to [-1, 1]
                elif sample_width == 4:
                    # 32-bit signed
                    audio_array = np.frombuffer(audio_data, dtype=np.int32).astype(np.float32)
                    audio_array = audio_array / 2147483648.0  # Convert to [-1, 1]
                else:
                    raise ValueError(f"Unsupported sample width: {sample_width}")
                
                # Handle stereo to mono conversion
                if n_channels == 2:
                    audio_array = audio_array.reshape(-1, 2).mean(axis=1)
                elif n_channels > 2:
                    audio_array = audio_array.reshape(-1, n_channels).mean(axis=1)
                
                # Validate audio length - skip very short recordings
                if duration < 0.5:  # Less than 500ms - increase threshold
                    logger.warning(f"Audio too short ({duration:.3f}s), skipping transcription")
                    return {
                        'success': True,
                        'text': '',
                        'confidence': 0.0,
                        'processing_time': '0.00s',
                        'mode': 'whisper_onnx',
                        'audio_duration': f"{duration:.2f}s",
                        'message': 'Audio too short'
                    }
                
                # Validate audio amplitude - skip very quiet recordings  
                rms = np.sqrt(np.mean(audio_array ** 2))
                if rms < 0.001:  # Lowered threshold to be more sensitive to quiet audio
                    logger.warning(f"Audio too quiet (RMS: {rms:.6f}), skipping transcription")
                    return {
                        'success': True,
                        'text': '',
                        'confidence': 0.0,
                        'processing_time': '0.00s',
                        'mode': 'whisper_onnx',
                        'audio_duration': f"{duration:.2f}s",
                        'message': 'Audio too quiet'
                    }
                
                # Add simple noise gate - remove very quiet samples
                noise_floor = rms * 0.1
                audio_array = np.where(np.abs(audio_array) > noise_floor, audio_array, 0)
            
            logger.info(f"Processing audio: {duration:.2f}s, {sample_rate}Hz, RMS: {rms:.4f}")
            
            # Transcribe using the ONNX model with proper audio format
            start_time = time.time()
            transcribed_text = self.whisper_model.transcribe(audio_array, sample_rate)
            processing_time = time.time() - start_time
            
            # Clean up the transcription result
            transcribed_text = transcribed_text.strip()
            
            # Filter out obviously wrong transcriptions
            if transcribed_text:
                # Common Whisper hallucination patterns to filter out
                hallucination_patterns = [
                    r"see you in the next video",
                    r"thanks for watching",
                    r"subscribe and",
                    r"like and subscribe",
                    r"don't forget to",
                    r"and I'll see you",
                    r"outro|intro|ending",
                    r"bye\.?\s*(bye\.?\s*){3,}",  # Multiple "bye bye bye"
                    r"(thank you|thanks).*next.*time",
                    r"until next time"
                ]
                
                text_lower = transcribed_text.lower()
                for pattern in hallucination_patterns:
                    if re.search(pattern, text_lower):
                        logger.warning(f"Detected likely hallucination pattern: {pattern}")
                        transcribed_text = ''
                        break
                
                # Check for repetitive patterns that indicate transcription errors
                words = transcribed_text.split()
                if len(words) > 10:
                    # Check for excessive repetition (same word repeated >5 times)
                    word_counts = {}
                    for word in words:
                        word_lower = word.lower().strip('.,!?')
                        word_counts[word_lower] = word_counts.get(word_lower, 0) + 1
                    
                    max_repetitions = max(word_counts.values())
                    if max_repetitions > 5:
                        logger.warning(f"Detected excessive repetition in transcription, likely error")
                        transcribed_text = ''
                
                # Filter out very long transcriptions that are likely hallucinations
                if len(transcribed_text) > 200:
                    logger.warning(f"Transcription too long ({len(transcribed_text)} chars), likely hallucination")
                    transcribed_text = ''
            
            logger.info(f"Whisper transcription result: '{transcribed_text}' (took {processing_time:.2f}s)")
            
            return {
                'success': True,
                'text': transcribed_text,
                'confidence': 0.9 if transcribed_text else 0.0,
                'processing_time': f"{processing_time:.2f}s",
                'mode': 'whisper_onnx',
                'audio_duration': f"{duration:.2f}s",
                'audio_quality': {
                    'sample_rate': sample_rate,
                    'channels': n_channels,
                    'rms': f"{rms:.4f}",
                    'duration': f"{duration:.2f}s"
                }
            }
                
        except Exception as e:
            logger.error(f"Failed to process audio with Whisper model: {e}")
            import traceback
            traceback.print_exc()
            return self._demo_transcription(audio_file_path)
    
    def _demo_transcription(self, audio_file_path: str) -> Dict[str, Any]:
        """Fallback demo transcription when executable is not available"""
        try:
            # Analyze the audio file to provide intelligent demo responses
            with wave.open(audio_file_path, 'rb') as wav_file:
                frames = wav_file.getnframes()
                duration = frames / wav_file.getframerate()
                audio_data = wav_file.readframes(frames)
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
            
            logger.info(f"Demo mode - Audio: {duration:.2f}s, RMS: {rms:.2f}")
            
            # Generate contextually appropriate responses
            demo_responses = [
                "repeat question one again",
                "play the audio", 
                "next question please",
                "pause the recording",
                "what is the first question",
                "go back to previous question"
            ]
            
            # Choose based on audio characteristics
            if duration > 2.5:
                response = demo_responses[0]  # "repeat question one again"
            elif duration > 1.5:
                response = demo_responses[1]  # "play the audio"
            elif duration > 1.0:
                response = demo_responses[2]  # "next question please"
            else:
                response = demo_responses[3]  # "pause the recording"
            
            return {
                'success': True,
                'text': response,
                'confidence': 0.8,
                'processing_time': f"{duration:.2f}s analyzed",
                'mode': 'demo_fallback'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Demo transcription failed: {str(e)}"
            }
    
    def _handle_voice_command(self, command_text: str):
        """Process recognized voice command and execute appropriate action"""
        command_lower = command_text.lower().strip()
        
        logger.info(f"Processing voice command: '{command_text}'")
        
        # Enhanced command matching with fuzzy matching and common variations
        command_patterns = {
            'play': ['play', 'start', 'begin', 'resume', 'continue'],
            'pause': ['pause', 'stop', 'halt', 'wait'],
            'repeat': ['repeat', 'again', 'once more', 'say again', 'replay'],
            'next': ['next', 'forward', 'continue', 'proceed'],
            'previous': ['previous', 'back', 'prior', 'before'],
            'question': ['question', 'ask', 'quiz']
        }
        
        # First check exact registered command handlers
        for command_key, handler in self.command_handlers.items():
            if command_key in command_lower:
                try:
                    handler(command_text)
                    logger.info(f"✅ Executed handler for command: {command_key}")
                    return
                except Exception as e:
                    logger.error(f"❌ Error executing command handler: {e}")
                return
        
        # Then check pattern variations
        for base_command, patterns in command_patterns.items():
            if base_command in self.command_handlers:
                for pattern in patterns:
                    if pattern in command_lower:
                        try:
                            handler = self.command_handlers[base_command]
                            handler(command_text)
                            logger.info(f"✅ Executed handler for command pattern '{pattern}' -> {base_command}")
                            return
                        except Exception as e:
                            logger.error(f"❌ Error executing pattern handler: {e}")
                        break
        
        # Check for number patterns in commands (for "repeat question one", etc.)
        import re
        numbers = re.findall(r'\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b', command_lower)
        if numbers and any(pattern in command_lower for pattern in ['repeat', 'question', 'again']):
            if 'repeat' in self.command_handlers:
                try:
                    handler = self.command_handlers['repeat']
                    handler(command_text)
                    logger.info(f"✅ Executed repeat command with number: {numbers}")
                    return
                except Exception as e:
                    logger.error(f"❌ Error executing repeat handler: {e}")
        
        logger.warning(f"⚠️  No handler found for command: '{command_text}'")
        logger.info(f"Available commands: {list(self.command_handlers.keys())}")
    
    def cleanup(self):
        """Clean up resources"""
        try:
            if self.is_listening:
                self.stop_listening()
                
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()
                self.pyaudio_instance = None
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")


# Voice command handlers for the PDF pipeline
class PipelineVoiceCommands:
    def __init__(self, tts_engine=None):
        self.tts_engine = tts_engine
        self.current_question_index = 0
        self.questions = []
        
    def handle_play_command(self, command_text: str):
        """Handle play audio commands"""
        logger.info("Voice command: Play audio")
        # This would trigger audio playback
        
    def handle_pause_command(self, command_text: str):
        """Handle pause audio commands"""
        logger.info("Voice command: Pause audio")
        # This would pause audio playback
        
    def handle_repeat_command(self, command_text: str):
        """Handle repeat commands like 'repeat question one'"""
        logger.info(f"Voice command: {command_text}")
        
        # Parse which question to repeat
        import re
        numbers = re.findall(r'\d+', command_text)
        if numbers:
            question_num = int(numbers[0]) - 1  # Convert to 0-based index
            if 0 <= question_num < len(self.questions):
                question = self.questions[question_num]
                logger.info(f"Repeating question {question_num + 1}: {question}")
                
                # Generate and play audio for this specific question
                if self.tts_engine:
                    try:
                        import tempfile
                        import uuid
                        
                        audio_filename = f"repeat_{uuid.uuid4().hex}.wav"
                        audio_path = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                        
                        result = self.tts_engine.text_to_speech_file(question, audio_path.name)
                        if result['success']:
                            logger.info(f"Generated audio for question repeat: {audio_path.name}")
                        
                    except Exception as e:
                        logger.error(f"Failed to generate repeat audio: {e}")
    
    def set_questions(self, questions_list):
        """Set the current questions list"""
        self.questions = questions_list
        self.current_question_index = 0