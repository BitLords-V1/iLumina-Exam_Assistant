"""
Standalone Whisper Integration Module
Provides integration with the existing Whisper transcription functionality
"""

import sys
import os
import logging
from typing import Dict, Any, Optional

# Add the src directory to the path to import the standalone whisper module
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from standalone_model import StandaloneWhisperModel
    WHISPER_AVAILABLE = True
    print("✅ StandaloneWhisperModel imported successfully")
except ImportError as e:
    logging.warning(f"Could not import StandaloneWhisperModel: {e}")
    print("ℹ️  Using simplified audio processing for demo")
    StandaloneWhisperModel = None
    WHISPER_AVAILABLE = False

logger = logging.getLogger(__name__)

class WhisperTranscriber:
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize Whisper transcriber with simplified integration
        
        Args:
            config_path (str, optional): Path to config file
        """
        self.whisper_model = None
        self.is_initialized = False
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
        
        # Model paths - look in the backend/models directory
        self.models_path = os.path.join(os.path.dirname(__file__), 'models')
        self.encoder_path = os.path.join(self.models_path, 'WhisperEncoder.onnx')
        self.decoder_path = os.path.join(self.models_path, 'WhisperDecoder.onnx')
        
        self._initialize_whisper()
    
    def _initialize_whisper(self):
        """Initialize the Whisper model"""
        try:
            if not WHISPER_AVAILABLE:
                logger.info("StandaloneWhisperModel not available - running in demo mode")
                self.is_initialized = True  # Still mark as initialized for demo
                return
            
            # Check if model files exist
            if not os.path.exists(self.encoder_path) or not os.path.exists(self.decoder_path):
                logger.warning(f"Model files not found at {self.models_path}")
                self.is_initialized = True  # Demo mode
                return
            
            # Initialize the model
            self.whisper_model = StandaloneWhisperModel(
                encoder_path=self.encoder_path,
                decoder_path=self.decoder_path
            )
            
            self.is_initialized = True
            logger.info("✅ Whisper model initialized successfully")
            
        except Exception as e:
            logger.warning(f"Failed to initialize Whisper model: {e}")
            logger.info("Continuing in demo mode")
            self.is_initialized = True  # Demo mode
    
    def start_transcription(self) -> Dict[str, Any]:
        """
        Start transcription session (simplified for demo)
        
        Returns:
            Dict containing operation result
        """
        if not self.is_initialized:
            return {
                'success': False,
                'message': '',
                'error': "Whisper transcriber not initialized"
            }
        
        # For now, just return success - the actual transcription happens in voice controller
        return {
            'success': True,
            'message': 'Whisper transcription ready' + (' (Real ONNX Model)' if self.whisper_model else ' (Demo Mode)'),
            'model_available': self.whisper_model is not None
        }
    
    def stop_transcription(self) -> Dict[str, Any]:
        """
        Stop real-time transcription
        
        Returns:
            Dict containing operation result
        """
        result = {
            'success': False,
            'message': '',
            'error': None
        }
        
        if not self.is_initialized:
            result['error'] = "Whisper transcriber not initialized"
            return result
        
        try:
            if hasattr(self.whisper_app, 'stop_transcription'):
                self.whisper_app.stop_transcription()
                result.update({
                    'success': True,
                    'message': 'Transcription stopped successfully'
                })
                logger.info("Stopped Whisper transcription")
            else:
                result['error'] = "Stop transcription method not available"
                
        except Exception as e:
            error_msg = f"Failed to stop transcription: {str(e)}"
            logger.error(error_msg)
            result['error'] = error_msg
        
        return result
    
    def get_transcription_status(self) -> Dict[str, Any]:
        """
        Get current transcription status
        
        Returns:
            Dict containing transcription status
        """
        status = {
            'initialized': self.is_initialized,
            'running': False,
            'last_text': '',
            'error': None
        }
        
        if not self.is_initialized:
            status['error'] = "Whisper transcriber not initialized"
            return status
        
        try:
            # Check if transcription is running
            if hasattr(self.whisper_app, 'is_transcribing'):
                status['running'] = self.whisper_app.is_transcribing
            
            # Get latest transcribed text
            if hasattr(self.whisper_app, 'get_latest_text'):
                status['last_text'] = self.whisper_app.get_latest_text() or ''
            
        except Exception as e:
            logger.error(f"Failed to get transcription status: {e}")
            status['error'] = str(e)
        
        return status
    
    def transcribe_audio_file(self, audio_file_path: str) -> Dict[str, Any]:
        """
        Transcribe an audio file
        
        Args:
            audio_file_path (str): Path to the audio file
            
        Returns:
            Dict containing transcription result
        """
        result = {
            'success': False,
            'text': '',
            'confidence': 0.0,
            'error': None
        }
        
        if not self.is_initialized:
            result['error'] = "Whisper transcriber not initialized"
            return result
        
        if not os.path.exists(audio_file_path):
            result['error'] = f"Audio file not found: {audio_file_path}"
            return result
        
        try:
            # Use the whisper app to transcribe the file
            if hasattr(self.whisper_app, 'transcribe_file'):
                transcription = self.whisper_app.transcribe_file(audio_file_path)
                if transcription:
                    result.update({
                        'success': True,
                        'text': transcription.get('text', ''),
                        'confidence': transcription.get('confidence', 0.0)
                    })
                else:
                    result['error'] = "No transcription returned"
            else:
                result['error'] = "File transcription method not available"
                
            logger.info(f"Transcribed audio file: {audio_file_path}")
            
        except Exception as e:
            error_msg = f"Failed to transcribe audio file: {str(e)}"
            logger.error(error_msg)
            result['error'] = error_msg
        
        return result
    
    def get_available_models(self) -> Dict[str, Any]:
        """
        Get list of available Whisper models
        
        Returns:
            Dict containing available models
        """
        result = {
            'success': False,
            'models': [],
            'current_model': '',
            'error': None
        }
        
        try:
            # Default Whisper model sizes
            default_models = ['tiny', 'base', 'small', 'medium', 'large']
            
            if self.is_initialized and hasattr(self.whisper_app, 'get_available_models'):
                models = self.whisper_app.get_available_models()
                result['models'] = models
            else:
                result['models'] = default_models
            
            if self.is_initialized and hasattr(self.whisper_app, 'current_model'):
                result['current_model'] = self.whisper_app.current_model
            
            result['success'] = True
            
        except Exception as e:
            logger.error(f"Failed to get available models: {e}")
            result['error'] = str(e)
        
        return result
    
    def cleanup(self):
        """Clean up resources"""
        try:
            if self.whisper_app and hasattr(self.whisper_app, 'cleanup'):
                self.whisper_app.cleanup()
            
            self.is_initialized = False
            logger.info("Whisper transcriber cleaned up")
            
        except Exception as e:
            logger.error(f"Failed to cleanup Whisper transcriber: {e}")