"""
Text-to-Speech Module
Handles audio generation and playback with speed controls
"""

import pyttsx3
import pygame
import threading
import queue
import tempfile
import os
import time
from pathlib import Path
import logging

class TTSEngine:
    def __init__(self):
        self.engine = None
        self.pygame_initialized = False
        self.current_audio_file = None
        self.is_playing = False
        self.is_paused = False
        self.playback_thread = None
        self.audio_queue = queue.Queue()
        self.setup_logging()
        
        self.init_engine()
        self.init_pygame()
    
    def setup_logging(self):
        """Setup logging for TTS engine"""
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def init_engine(self):
        """Initialize the TTS engine"""
        try:
            self.engine = pyttsx3.init()
            
            # Get available voices
            voices = self.engine.getProperty('voices')
            if voices:
                # Prefer female voice if available
                for voice in voices:
                    if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                        self.engine.setProperty('voice', voice.id)
                        break
                else:
                    self.engine.setProperty('voice', voices[0].id)
            
            # Set default properties
            self.engine.setProperty('rate', 200)  # Speaking rate
            self.engine.setProperty('volume', 0.9)  # Volume level (0.0 to 1.0)
            
            self.logger.info("TTS engine initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize TTS engine: {e}")
            return False
    
    def init_pygame(self):
        """Initialize pygame for audio playback"""
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self.pygame_initialized = True
            self.logger.info("Pygame audio mixer initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize pygame: {e}")
            return False
    
    def get_available_voices(self):
        """Get list of available TTS voices"""
        if not self.engine:
            return []
        
        try:
            voices = self.engine.getProperty('voices')
            voice_info = []
            
            for voice in voices:
                voice_info.append({
                    'id': voice.id,
                    'name': voice.name,
                    'languages': getattr(voice, 'languages', []),
                    'gender': getattr(voice, 'gender', 'unknown')
                })
            
            return voice_info
        except Exception as e:
            self.logger.error(f"Error getting voices: {e}")
            return []
    
    def set_voice(self, voice_id):
        """Set the TTS voice"""
        if not self.engine:
            return False
        
        try:
            self.engine.setProperty('voice', voice_id)
            return True
        except Exception as e:
            self.logger.error(f"Error setting voice: {e}")
            return False
    
    def set_speed(self, rate):
        """
        Set speaking rate
        Args:
            rate (float): Speaking rate multiplier (0.5 to 2.0)
        """
        if not self.engine:
            return
        
        try:
            # Convert multiplier to actual rate (default is ~200)
            actual_rate = int(200 * rate)
            actual_rate = max(100, min(400, actual_rate))  # Clamp between 100-400
            
            self.engine.setProperty('rate', actual_rate)
            self.logger.info(f"Set speaking rate to {actual_rate} (multiplier: {rate})")
        except Exception as e:
            self.logger.error(f"Error setting speed: {e}")
    
    def set_volume(self, volume):
        """
        Set speaking volume
        Args:
            volume (float): Volume level (0.0 to 1.0)
        """
        if not self.engine:
            return
        
        try:
            volume = max(0.0, min(1.0, volume))
            self.engine.setProperty('volume', volume)
            self.logger.info(f"Set volume to {volume}")
        except Exception as e:
            self.logger.error(f"Error setting volume: {e}")
    
    def text_to_audio_file(self, text, filename=None, speed=1.0):
        """
        Convert text to audio file
        Args:
            text (str): Text to convert
            filename (str): Output filename (optional)
            speed (float): Speaking rate multiplier
        Returns:
            str: Path to generated audio file
        """
        if not self.engine:
            return None
        
        try:
            # Set speed
            self.set_speed(speed)
            
            # Generate filename if not provided
            if not filename:
                temp_dir = tempfile.gettempdir()
                filename = os.path.join(temp_dir, f"tts_audio_{int(time.time())}.wav")
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            # Convert text to speech and save to file
            self.engine.save_to_file(text, filename)
            self.engine.runAndWait()
            
            if os.path.exists(filename):
                self.logger.info(f"Audio file created: {filename}")
                return filename
            else:
                self.logger.error("Audio file was not created")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating audio file: {e}")
            return None
    
    def speak_text_direct(self, text, speed=1.0):
        """
        Speak text directly without saving to file
        Args:
            text (str): Text to speak
            speed (float): Speaking rate multiplier
        """
        if not self.engine:
            return
        
        try:
            self.set_speed(speed)
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            self.logger.error(f"Error speaking text: {e}")
    
    def play_audio_file(self, audio_file):
        """
        Play audio file using pygame
        Args:
            audio_file (str): Path to audio file
        Returns:
            bool: Success status
        """
        if not self.pygame_initialized:
            self.logger.error("Pygame not initialized")
            return False
        
        try:
            # Stop current playback if any
            self.stop_playback()
            
            # Load and play the audio file
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            
            self.current_audio_file = audio_file
            self.is_playing = True
            self.is_paused = False
            
            self.logger.info(f"Started playing: {audio_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error playing audio file: {e}")
            return False
    
    def pause_playback(self):
        """Pause current audio playback"""
        if not self.pygame_initialized or not self.is_playing:
            return False
        
        try:
            pygame.mixer.music.pause()
            self.is_paused = True
            self.logger.info("Audio playback paused")
            return True
        except Exception as e:
            self.logger.error(f"Error pausing playback: {e}")
            return False
    
    def resume_playback(self):
        """Resume paused audio playback"""
        if not self.pygame_initialized or not self.is_paused:
            return False
        
        try:
            pygame.mixer.music.unpause()
            self.is_paused = False
            self.logger.info("Audio playback resumed")
            return True
        except Exception as e:
            self.logger.error(f"Error resuming playback: {e}")
            return False
    
    def stop_playback(self):
        """Stop current audio playback"""
        if not self.pygame_initialized:
            return False
        
        try:
            pygame.mixer.music.stop()
            self.is_playing = False
            self.is_paused = False
            
            # Clean up temporary files
            if self.current_audio_file and os.path.exists(self.current_audio_file):
                try:
                    os.remove(self.current_audio_file)
                except:
                    pass  # Ignore errors when cleaning up temp files
            
            self.current_audio_file = None
            self.logger.info("Audio playback stopped")
            return True
        except Exception as e:
            self.logger.error(f"Error stopping playback: {e}")
            return False
    
    def is_playing_audio(self):
        """Check if audio is currently playing"""
        if not self.pygame_initialized:
            return False
        
        try:
            return pygame.mixer.music.get_busy() and not self.is_paused
        except:
            return False
    
    def get_playback_position(self):
        """Get current playback position (if supported)"""
        if not self.pygame_initialized or not self.is_playing:
            return 0
        
        try:
            return pygame.mixer.music.get_pos()
        except:
            return 0
    
    def speak_text_async(self, text, speed=1.0, callback=None):
        """
        Speak text asynchronously with full playback control
        Args:
            text (str): Text to speak
            speed (float): Speaking rate multiplier
            callback (function): Callback function when playback completes
        Returns:
            bool: Success status
        """
        def async_speak():
            try:
                # Generate audio file
                audio_file = self.text_to_audio_file(text, speed=speed)
                if not audio_file:
                    if callback:
                        callback(False, "Failed to generate audio")
                    return
                
                # Play the audio file
                success = self.play_audio_file(audio_file)
                if not success:
                    if callback:
                        callback(False, "Failed to play audio")
                    return
                
                # Wait for playback to complete
                while self.is_playing_audio():
                    time.sleep(0.1)
                
                # Clean up
                self.stop_playback()
                
                if callback:
                    callback(True, "Playback completed")
                    
            except Exception as e:
                self.logger.error(f"Error in async speak: {e}")
                if callback:
                    callback(False, str(e))
        
        # Start in separate thread
        thread = threading.Thread(target=async_speak, daemon=True)
        thread.start()
        return True
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.stop_playback()
            
            if self.engine:
                self.engine.stop()
            
            if self.pygame_initialized:
                pygame.mixer.quit()
                
            self.logger.info("TTS engine cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

# Audio Controller for integration with GUI
class AudioController:
    def __init__(self, update_callback=None):
        self.tts = TTSEngine()
        self.update_callback = update_callback
        self.current_text = ""
        self.current_speed = 1.0
    
    def play_text(self, text, speed=1.0):
        """Play text with given speed"""
        self.current_text = text
        self.current_speed = speed
        
        def playback_callback(success, message):
            if self.update_callback:
                self.update_callback('completed' if success else 'error', message)
        
        if self.update_callback:
            self.update_callback('playing', f"Playing text at {speed}x speed")
        
        return self.tts.speak_text_async(text, speed, playback_callback)
    
    def pause(self):
        """Pause current playback"""
        success = self.tts.pause_playback()
        if self.update_callback:
            status = 'paused' if success else 'error'
            self.update_callback(status, 'Playback paused' if success else 'Failed to pause')
        return success
    
    def resume(self):
        """Resume paused playback"""
        success = self.tts.resume_playback()
        if self.update_callback:
            status = 'playing' if success else 'error'
            self.update_callback(status, 'Playback resumed' if success else 'Failed to resume')
        return success
    
    def stop(self):
        """Stop current playback"""
        success = self.tts.stop_playback()
        if self.update_callback:
            status = 'stopped' if success else 'error'
            self.update_callback(status, 'Playback stopped' if success else 'Failed to stop')
        return success
    
    def repeat(self):
        """Repeat current text"""
        if self.current_text:
            return self.play_text(self.current_text, self.current_speed)
        return False
    
    def is_playing(self):
        """Check if currently playing"""
        return self.tts.is_playing_audio()
    
    def is_paused(self):
        """Check if currently paused"""
        return self.tts.is_paused
    
    def get_voices(self):
        """Get available voices"""
        return self.tts.get_available_voices()
    
    def set_voice(self, voice_id):
        """Set TTS voice"""
        return self.tts.set_voice(voice_id)
    
    def set_volume(self, volume):
        """Set playback volume"""
        self.tts.set_volume(volume)

# Test function
def test_tts():
    """Test TTS functionality"""
    def status_callback(status, message):
        print(f"Status: {status}, Message: {message}")
    
    controller = AudioController(status_callback)
    
    test_text = "Hello! This is a test of the text-to-speech functionality. How does it sound?"
    
    print("Testing normal speed...")
    controller.play_text(test_text, speed=1.0)
    
    time.sleep(5)
    
    print("Testing slow speed...")
    controller.play_text(test_text, speed=0.7)

if __name__ == "__main__":
    test_tts()