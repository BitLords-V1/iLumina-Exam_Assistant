"""
Text-to-Speech Engine Module
Handles audio generation from text using pyttsx3
"""

import pyttsx3
import pygame
import tempfile
import os
import threading
import time
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class TTSEngine:
    def __init__(self):
        """Initialize TTS engine and pygame mixer"""
        self.engine = None
        self.pygame_initialized = False
        self.current_audio_file = None
        self.is_playing = False
        self.is_paused = False
        self.playback_position = 0
        
        self._initialize_tts()
        self._initialize_pygame()
    
    def _initialize_tts(self):
        """Initialize pyttsx3 TTS engine"""
        try:
            self.engine = pyttsx3.init()
            
            # Set default properties
            voices = self.engine.getProperty('voices')
            if voices:
                self.engine.setProperty('voice', voices[0].id)
            
            self.engine.setProperty('rate', 150)  # Speech rate
            self.engine.setProperty('volume', 0.8)  # Volume level
            
            logger.info("TTS engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize TTS engine: {e}")
            self.engine = None
    
    def _initialize_pygame(self):
        """Initialize pygame mixer for audio playback"""
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self.pygame_initialized = True
            logger.info("Pygame mixer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize pygame mixer: {e}")
            self.pygame_initialized = False
    
    def get_available_voices(self) -> List[Dict[str, str]]:
        """Get list of available TTS voices"""
        voices_list = []
        
        if not self.engine:
            return voices_list
        
        try:
            voices = self.engine.getProperty('voices')
            for i, voice in enumerate(voices):
                voices_list.append({
                    'id': voice.id,
                    'name': voice.name,
                    'language': getattr(voice, 'languages', ['en'])[0] if hasattr(voice, 'languages') else 'en',
                    'gender': getattr(voice, 'gender', 'unknown')
                })
        except Exception as e:
            logger.error(f"Failed to get voices: {e}")
        
        return voices_list
    
    def set_voice_properties(self, voice_id: Optional[str] = None, rate: int = 150, volume: float = 0.8):
        """Set TTS voice properties"""
        if not self.engine:
            return False
        
        try:
            if voice_id:
                self.engine.setProperty('voice', voice_id)
            
            self.engine.setProperty('rate', max(50, min(300, rate)))
            self.engine.setProperty('volume', max(0.0, min(1.0, volume)))
            
            return True
        except Exception as e:
            logger.error(f"Failed to set voice properties: {e}")
            return False
    
    def text_to_speech_file(self, text: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert text to speech and save as audio file
        
        Args:
            text (str): Text to convert
            output_path (str, optional): Output file path. If None, uses temp file.
            
        Returns:
            Dict containing result information
        """
        result = {
            'success': False,
            'file_path': None,
            'duration': 0,
            'error': None
        }
        
        if not self.engine:
            result['error'] = "TTS engine not initialized"
            return result
        
        if not text.strip():
            result['error'] = "Empty text provided"
            return result
        
        try:
            # Use temp file if no output path specified
            if not output_path:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                output_path = temp_file.name
                temp_file.close()
            else:
                # Ensure directory exists for custom output path
                output_dir = os.path.dirname(output_path)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
                    logger.info(f"Created directory: {output_dir}")
            
            logger.info(f"Attempting to generate TTS audio at: {output_path}")
            
            # Generate speech
            self.engine.save_to_file(text, output_path)
            self.engine.runAndWait()
            
            # Check if file was created
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                result.update({
                    'success': True,
                    'file_path': output_path,
                    'duration': self._get_audio_duration(output_path)
                })
                
                logger.info(f"Generated TTS audio: {output_path}")
            else:
                result['error'] = "Failed to generate audio file"
                
        except Exception as e:
            error_msg = f"TTS generation failed: {str(e)}"
            logger.error(error_msg)
            result['error'] = error_msg
        
        return result
    
    def _get_audio_duration(self, file_path: str) -> float:
        """Get audio file duration in seconds"""
        try:
            if self.pygame_initialized:
                sound = pygame.mixer.Sound(file_path)
                return sound.get_length()
        except Exception as e:
            logger.warning(f"Could not get audio duration: {e}")
        
        return 0.0
    
    def play_audio(self, file_path: str) -> bool:
        """Play audio file using pygame"""
        if not self.pygame_initialized:
            return False
        
        try:
            self.stop_audio()  # Stop any current playback
            
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            
            self.current_audio_file = file_path
            self.is_playing = True
            self.is_paused = False
            
            logger.info(f"Started playing audio: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to play audio: {e}")
            return False
    
    def pause_audio(self) -> bool:
        """Pause current audio playback"""
        if not self.pygame_initialized or not self.is_playing:
            return False
        
        try:
            pygame.mixer.music.pause()
            self.is_paused = True
            logger.info("Audio paused")
            return True
        except Exception as e:
            logger.error(f"Failed to pause audio: {e}")
            return False
    
    def resume_audio(self) -> bool:
        """Resume paused audio playback"""
        if not self.pygame_initialized or not self.is_paused:
            return False
        
        try:
            pygame.mixer.music.unpause()
            self.is_paused = False
            logger.info("Audio resumed")
            return True
        except Exception as e:
            logger.error(f"Failed to resume audio: {e}")
            return False
    
    def stop_audio(self) -> bool:
        """Stop current audio playback"""
        if not self.pygame_initialized:
            return False
        
        try:
            pygame.mixer.music.stop()
            self.is_playing = False
            self.is_paused = False
            self.playback_position = 0
            logger.info("Audio stopped")
            return True
        except Exception as e:
            logger.error(f"Failed to stop audio: {e}")
            return False
    
    def get_playback_status(self) -> Dict[str, Any]:
        """Get current playback status"""
        status = {
            'is_playing': False,
            'is_paused': False,
            'current_file': self.current_audio_file,
            'position': self.playback_position
        }
        
        if self.pygame_initialized:
            try:
                pygame_playing = pygame.mixer.music.get_busy()
                status['is_playing'] = pygame_playing and not self.is_paused
                status['is_paused'] = self.is_paused and pygame_playing
            except Exception as e:
                logger.warning(f"Failed to get playback status: {e}")
        
        return status
    
    def cleanup(self):
        """Clean up resources"""
        try:
            if self.pygame_initialized:
                self.stop_audio()
                pygame.mixer.quit()
            
            if self.engine:
                self.engine.stop()
                
            # Clean up temp audio files
            if self.current_audio_file and self.current_audio_file.startswith(tempfile.gettempdir()):
                try:
                    os.unlink(self.current_audio_file)
                except:
                    pass
                    
            logger.info("TTS engine cleaned up")
        except Exception as e:
            logger.error(f"Failed to cleanup TTS engine: {e}")