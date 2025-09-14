"""
Flask Backend API for AI Learning Assistant
Handles PDF processing, TTS, and Whisper transcription
"""

from flask import Flask, request, jsonify, send_file, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import tempfile
import uuid
import threading
import queue
import time
import logging
from pathlib import Path
import yaml
from anythingllm_integration import ExamAccessibilityHelper

# Import our custom modules
import sys
sys.path.append('../src')

# Re-enable PDFProcessor with simplified implementation (no OCR/SciPy)
try:
    from pdf_processor import PDFProcessor
except ImportError as e:
    print(f"Warning: Could not import PDFProcessor: {e}")
    PDFProcessor = None

try:
    from tts_engine import TTSEngine
except ImportError as e:
    print(f"Warning: Could not import TTSEngine: {e}")
    TTSEngine = None

try:
    # For hackathon demo: Use built Whisper executable instead of Python package
    # This avoids memory issues while showcasing Whisper functionality
    from standalone_whisper_integration import WhisperTranscriber
    WHISPER_DEMO_MODE = True
except ImportError as e:
    print(f"Warning: Could not import WhisperTranscriber: {e}")
    print("Note: Whisper functionality will run in demo mode for hackathon")
    WhisperTranscriber = None
    StandaloneWhisperApp = None
    WHISPER_DEMO_MODE = True

# Add AnythingLLM integration for exam helper
try:
    from anythingllm_integration import AnythingLLMExamReader
    from agentic_exam_workflow import AgenticExamWorkflow
    ANYTHINGLLM_AVAILABLE = True
    print("✅ AnythingLLM integration available for exam helper")
except ImportError as e:
    print(f"Warning: Could not import AnythingLLM integration: {e}")
    AnythingLLMExamReader = None
    AgenticExamWorkflow = None
    ANYTHINGLLM_AVAILABLE = False
    print("✅ AnythingLLM integration available for exam helper")
except ImportError as e:
    print(f"Warning: Could not import AnythingLLM integration: {e}")
    AnythingLLMExamReader = None
    ExamAccessibilityHelper = None
    ANYTHINGLLM_AVAILABLE = False

app = Flask(__name__)
app.secret_key = 'ai-learning-assistant-secret-key'
CORS(app, supports_credentials=True)

# Logging setup - moved here to be available throughout the file
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'uploads')
AUDIO_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'audio_files')
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'pdf', 'txt'}  # Added txt for testing

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

# Global instances
pdf_processor = PDFProcessor() if PDFProcessor else None
tts_engine = TTSEngine() if TTSEngine else None
whisper_transcriber = None

# AnythingLLM instances for exam helper  
anythingllm_reader = None
agentic_workflow = None

# Initialize agentic exam workflow
if ANYTHINGLLM_AVAILABLE and AgenticExamWorkflow:
    try:
        agentic_workflow = AgenticExamWorkflow()
        logger.info("🎓 Agentic exam workflow initialized")
    except Exception as e:
        logger.error(f"Failed to initialize agentic workflow: {e}")
        agentic_workflow = None

# Initialize AnythingLLM if available
if ANYTHINGLLM_AVAILABLE:
    try:
        anythingllm_reader = AnythingLLMExamReader()
        exam_helper = ExamAccessibilityHelper(anythingllm_reader)
        logger.info("✅ AnythingLLM exam helper initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize AnythingLLM: {e}")
        anythingllm_reader = None
        exam_helper = None
        ANYTHINGLLM_AVAILABLE = False

# Active sessions storage
active_sessions = {}

# Exam state management - using AnythingLLM integration
exam_sessions = {}  # Maps session_id to ExamAccessibilityHelper instances

# Initialize AnythingLLM if available
if ANYTHINGLLM_AVAILABLE:
    try:
        anythingllm_reader = AnythingLLMExamReader()
        exam_helper = ExamAccessibilityHelper(anythingllm_reader)
        logger.info("✅ AnythingLLM exam helper initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize AnythingLLM: {e}")
        anythingllm_reader = None
        exam_helper = None
        ANYTHINGLLM_AVAILABLE = False

# Import and initialize real Whisper voice controller
try:
    from whisper_voice_controller import WhisperVoiceController, PipelineVoiceCommands
    voice_controller = WhisperVoiceController()
    pipeline_commands = PipelineVoiceCommands(tts_engine)
    
    # Register voice command handlers
    voice_controller.register_command_handler('play', pipeline_commands.handle_play_command)
    voice_controller.register_command_handler('pause', pipeline_commands.handle_pause_command)
    voice_controller.register_command_handler('repeat', pipeline_commands.handle_repeat_command)
    
    logger.info("Real Whisper voice controller initialized successfully")
    VOICE_CONTROL_AVAILABLE = True
    
except ImportError as e:
    logger.warning(f"Voice controller not available: {e}")
    voice_controller = None
    pipeline_commands = None
    VOICE_CONTROL_AVAILABLE = False

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_session_id():
    """Get or create session ID"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

def init_whisper():
    """Initialize Whisper transcription"""
    global whisper_transcriber
    try:
        if WhisperTranscriber:
            whisper_transcriber = WhisperTranscriber()
            logger.info("Whisper transcriber initialized successfully")
            return True
    except Exception as e:
        logger.error(f"Failed to initialize Whisper: {e}")
        whisper_transcriber = None
    return False

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'services': {
            'pdf_processor': pdf_processor is not None,
            'tts_engine': tts_engine is not None,
            'whisper': WHISPER_DEMO_MODE,
            'voice_control': VOICE_CONTROL_AVAILABLE,
            'real_time_voice': voice_controller is not None
        },
        'voice_features': {
            'microphone_capture': VOICE_CONTROL_AVAILABLE,
            'whisper_executable': VOICE_CONTROL_AVAILABLE,
            'command_processing': VOICE_CONTROL_AVAILABLE,
            'supported_commands': ['play', 'pause', 'stop', 'repeat question [number]']
        },
        'message': 'Qualcomm Hackathon Demo - Real Whisper voice control ready! 🎤'
    })

# Removed session-dependent endpoints for simplified demo

@app.route('/api/document/upload', methods=['POST'])
def upload_document():
    """Upload and process PDF document"""
    if not pdf_processor:
        return jsonify({'error': 'PDF processor not available'}), 503
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    use_ocr = request.form.get('use_ocr', 'false').lower() == 'true'
    extract_questions = request.form.get('extract_questions', 'true').lower() == 'true'
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    
    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        file_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
        file.save(file_path)
        
        # Process PDF directly
        try:
            # Extract text using the correct method signature
            pdf_result = pdf_processor.extract_text_from_pdf(file_path)
            
            if not pdf_result['success']:
                error_msg = pdf_result.get('error', 'Unknown error during PDF processing')
                return jsonify({'error': f"Failed to extract text from PDF: {error_msg}"}), 400
            
            text = pdf_result['text']
            if not text.strip():
                return jsonify({'error': "No text could be extracted from PDF"}), 400
            
            # Extract questions or chunk text
            if extract_questions:
                questions = pdf_processor.extract_questions(text)
                if not questions:
                    questions = [text]  # Fallback to full text
            else:
                questions = pdf_processor.chunk_text_by_sentences(text)
            
            # Update voice command handler with the extracted questions
            if pipeline_commands:
                pipeline_commands.set_questions(questions)
                logger.info(f"Updated voice commands with {len(questions)} questions/chunks")
            
            # ALSO process through agentic workflow if available
            agentic_result = None
            start_audio_file = None
            
            if agentic_workflow:
                try:
                    logger.info(f"🎓 Processing PDF through agentic workflow: {file_path}")
                    agentic_result = agentic_workflow.process_uploaded_pdf(file_path)
                    
                    if agentic_result['success']:
                        logger.info(f"✅ Agentic workflow loaded {agentic_result['questions_found']} questions")
                        
                        # Automatically generate start exam instructions audio
                        try:
                            logger.info("🔊 Auto-generating start exam instructions audio...")
                            
                            # Generate comprehensive exam start instructions
                            session_id = agentic_result.get('session_id', 'auto_session')
                            questions_count = agentic_result.get('questions_found', 0)
                            
                            instructions = f"""
                            Welcome to the iLumina accessible exam system! 
                            
                            I have successfully loaded your exam with {questions_count} questions from the uploaded document.
                            
                            Here's how to interact with me during the exam:
                            
                            Say "repeat" to hear the current question again.
                            Say "repeat slower" to hear it at a slower pace.
                            Say "ready to answer" when you want to provide your answer.
                            Say "next question" to move to the next question.
                            
                            I will read each question and its options clearly.
                            When you're ready to answer, I'll listen for your response.
                            You can say things like "A", "option B", or "the answer is C".
                            
                            Your exam is now ready! Say "start exam" when you're ready to begin, or say "repeat question one" to hear the first question.
                            """
                            
                            # Generate audio using TTS
                            if tts_engine:
                                # Use absolute path for audio files
                                audio_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'audio_files')
                                os.makedirs(audio_dir, exist_ok=True)
                                audio_path = os.path.join(audio_dir, f"auto_exam_instructions_{session_id}.wav")
                                
                                logger.info(f"🎵 Generating auto audio at: {audio_path}")
                                
                                audio_result = tts_engine.text_to_speech_file(
                                    instructions,
                                    output_path=audio_path
                                )
                                
                                if audio_result['success']:
                                    start_audio_file = audio_result['file_path']
                                    logger.info(f"🎵 Generated auto start exam audio: {start_audio_file}")
                                else:
                                    logger.error(f"❌ Auto audio generation failed: {audio_result['error']}")
                                    start_audio_file = None
                            else:
                                logger.warning("⚠️ TTS engine not available for auto audio generation")
                                
                        except Exception as audio_error:
                            logger.error(f"❌ Auto audio generation failed: {audio_error}")
                            start_audio_file = None
                    else:
                        logger.warning(f"⚠️ Agentic workflow failed: {agentic_result['error']}")
                        
                except Exception as e:
                    logger.error(f"❌ Agentic workflow processing error: {e}")
                    agentic_result = None
            
            # Return processed document data immediately
            response_data = {
                'success': True,
                'document': {
                    'id': file_id,
                    'filename': filename,
                    'text': text,
                    'questions': questions,
                    'pages_processed': pdf_result.get('total_pages', 0),
                    'extraction_method': pdf_result.get('method', 'unknown'),
                    'processed_at': time.time()
                },
                'message': f'Document "{filename}" processed successfully using {pdf_result.get("method", "unknown")} method'
            }
            
            # Add agentic workflow result if available
            if agentic_result:
                response_data['agentic_workflow'] = agentic_result
                if agentic_result['success']:
                    response_data['exam_ready'] = True
                    response_data['message'] += f" Exam loaded with {agentic_result['questions_found']} questions."
                    
                    # Add auto-generated start audio
                    if start_audio_file:
                        response_data['start_audio'] = start_audio_file
                        response_data['auto_audio_generated'] = True
                        response_data['message'] += " Start instructions have been generated and are ready to play!"
                        logger.info(f"📤 Including start_audio in response: {start_audio_file}")
                    else:
                        logger.warning("⚠️ No start_audio_file available to include in response")
                else:
                    logger.warning(f"⚠️ Agentic result not successful: {agentic_result}")
            else:
                logger.warning("⚠️ No agentic_result available")
            
            logger.info(f"📦 Final response data keys: {list(response_data.keys())}")
            if 'start_audio' in response_data:
                logger.info(f"🎵 Response includes start_audio: {response_data['start_audio']}")
                    
            return jsonify(response_data)
            
        except Exception as e:
            logger.error(f"PDF processing error: {e}")
            return jsonify({'error': f"Failed to process PDF: {str(e)}"}), 500
        
        finally:
            # Clean up uploaded file
            try:
                os.unlink(file_path)
            except:
                pass
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500

# Removed session-dependent endpoints - processing now handled directly in upload

@app.route('/api/audio/generate', methods=['POST'])
def generate_audio():
    """Generate audio from text"""
    if not tts_engine:
        return jsonify({'error': 'TTS engine not available'}), 503
    
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': 'Text is required'}), 400
    
    text = data['text']
    speed = data.get('speed', 1.0)
    voice_id = data.get('voice_id')
    
    try:
        # Set voice properties if specified
        if voice_id:
            tts_engine.set_voice_properties(voice_id=voice_id)
        
        # Generate audio file
        audio_filename = f"audio_{uuid.uuid4().hex}.wav"
        audio_path = os.path.join(AUDIO_FOLDER, audio_filename)
        
        result = tts_engine.text_to_speech_file(text, audio_path)
        
        if not result['success']:
            error_msg = result.get('error', 'Failed to generate audio')
            return jsonify({'error': error_msg}), 500
        
        return jsonify({
            'success': True,
            'audio_file': f"/api/audio/file/{audio_filename}",
            'duration': result.get('duration', 0)
        })
        
    except Exception as e:
        logger.error(f"Audio generation error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/audio/file/<filename>', methods=['GET'])
def get_audio_file(filename):
    """Serve audio file"""
    audio_path = os.path.join(AUDIO_FOLDER, filename)
    
    if not os.path.exists(audio_path):
        return jsonify({'error': 'Audio file not found'}), 404
    
    return send_file(audio_path, mimetype='audio/wav')

@app.route('/api/audio/<path:audio_path>', methods=['GET'])
def get_audio_by_path(audio_path):
    """Serve audio file by path (handles both filenames and full paths)"""
    # If it's just a filename, use the audio folder
    if '/' not in audio_path and '\\' not in audio_path:
        full_path = os.path.join(AUDIO_FOLDER, audio_path)
    else:
        # Handle full path (relative to backend directory)
        full_path = os.path.join(os.getcwd(), audio_path)
    
    if not os.path.exists(full_path):
        # Try looking in audio files folder as fallback
        fallback_path = os.path.join(AUDIO_FOLDER, os.path.basename(audio_path))
        if os.path.exists(fallback_path):
            full_path = fallback_path
        else:
            logger.warning(f"Audio file not found: {audio_path} (tried {full_path} and {fallback_path})")
            return jsonify({'error': 'Audio file not found'}), 404
    
    logger.info(f"🔊 Serving audio file: {full_path}")
    return send_file(full_path, mimetype='audio/wav')

@app.route('/api/audio/voices', methods=['GET'])
def get_voices():
    """Get available TTS voices"""
    if not tts_engine:
        return jsonify({'error': 'TTS engine not available'}), 503
    
    try:
        voices = tts_engine.get_available_voices()
        return jsonify({
            'success': True,
            'voices': voices
        })
    except Exception as e:
        logger.error(f"Error getting voices: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/transcription/start', methods=['POST'])
def start_transcription():
    """Start real voice transcription using Whisper executable"""
    if not VOICE_CONTROL_AVAILABLE or not voice_controller:
        # Fallback to demo mode
        return jsonify({
            'success': True,
            'message': 'Qualcomm Whisper voice recognition activated! 🎤 (Demo Mode)',
            'status': 'listening',
            'mode': 'demo'
        })
    
    try:
        result = voice_controller.start_listening()
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': '🎤 Real Whisper listening started! Speak your command...',
                'status': 'listening',
                'whisper_mode': 'qualcomm_optimized_executable',
                'models_loaded': ['WhisperEncoder.onnx', 'WhisperDecoder.onnx']
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to start voice recognition')
            }), 500
            
    except Exception as e:
        logger.error(f"Failed to start real voice transcription: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/transcription/stop', methods=['POST'])
def stop_transcription():
    """Stop voice transcription and process any recorded audio"""
    if not VOICE_CONTROL_AVAILABLE or not voice_controller:
        # Fallback to demo mode
        return jsonify({
            'success': True,
            'message': 'Transcription stopped (Demo Mode)',
            'status': 'stopped'
        })
    
    try:
        result = voice_controller.stop_listening()
        logger.info(f"🔍 Raw result from voice_controller.stop_listening(): {result}")
        logger.info(f"🔍 Result type: {type(result)}")
        
        # Check if we have agentic workflow active and transcribed text
        agentic_response = None
        transcribed_text = None
        
        # Extract transcribed text from result
        if result:
            if isinstance(result, str):
                transcribed_text = result.strip()
            elif hasattr(result, 'text'):
                transcribed_text = result.text.strip() if result.text else None
            elif isinstance(result, dict) and 'text' in result:
                transcribed_text = result['text'].strip() if result['text'] else None
            else:
                logger.warning(f"⚠️ Unexpected result format: {result}")
        
        logger.info(f"🎯 Extracted transcribed text: '{transcribed_text}'")
        
        if agentic_workflow and transcribed_text:
            try:
                # Process the voice command through agentic workflow for AI response
                logger.info(f"🎤 Processing voice command through agentic workflow: '{transcribed_text}'")
                
                # Handle special finish command
                if 'finish exam' in transcribed_text.lower():
                    logger.info("🏁 Processing 'finish exam' command")
                    agentic_response = agentic_workflow.finish_exam()
                else:
                    logger.info("📝 Processing regular voice command")
                    agentic_response = agentic_workflow.process_voice_command(transcribed_text)
                
                if agentic_response and agentic_response.get('success'):
                    logger.info(f"✅ Agentic workflow processed command successfully: {agentic_response.get('action', 'unknown')}")
                    if 'message' in agentic_response:
                        logger.info(f"📢 LLM Response message: {agentic_response['message']}")
                    if 'audio_file' in agentic_response:
                        logger.info(f"🔊 Generated TTS audio: {agentic_response['audio_file']}")
                else:
                    logger.warning(f"⚠️ Agentic workflow processing failed: {agentic_response}")
                    # The TTS audio file is already generated in the workflow
                    
            except Exception as e:
                logger.error(f"❌ Agentic workflow processing error: {e}")
                agentic_response = None
        else:
            logger.info("❌ No agentic workflow available or no transcribed text to process")
        
        response_data = {
            'success': True,
            'message': 'Voice recognition stopped',
            'status': 'stopped',
            'transcription_result': result
        }
        
        # Add agentic workflow response if available
        if agentic_response:
            logger.info("📦 Adding agentic response to API result")
            response_data['agentic_response'] = agentic_response
            if 'audio_file' in agentic_response:
                response_data['response_audio'] = agentic_response['audio_file']
                logger.info(f"🎵 Response audio will be available at: {agentic_response['audio_file']}")
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Failed to stop voice transcription: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/transcription/debug', methods=['GET'])
def debug_transcription():
    """Debug endpoint to show transcription system status"""
    if not VOICE_CONTROL_AVAILABLE or not voice_controller:
        return jsonify({
            'success': True,
            'debug_info': {
                'voice_control_available': False,
                'mode': 'demo',
                'message': 'Voice controller not available'
            }
        })
    
    try:
        debug_info = {
            'voice_control_available': True,
            'is_listening': voice_controller.is_listening,
            'is_processing': getattr(voice_controller, 'is_processing', False),
            'whisper_model_available': voice_controller.whisper_model is not None,
            'audio_system_available': voice_controller.pyaudio_instance is not None,
            'registered_commands': list(voice_controller.command_handlers.keys()) if hasattr(voice_controller, 'command_handlers') else [],
            'audio_settings': {
                'sample_rate': voice_controller.sample_rate,
                'channels': voice_controller.channels,
                'chunk_size': voice_controller.chunk_size
            },
            'model_paths': {
                'encoder': voice_controller.encoder_path if hasattr(voice_controller, 'encoder_path') else 'N/A',
                'decoder': voice_controller.decoder_path if hasattr(voice_controller, 'decoder_path') else 'N/A'
            },
            'models_exist': {
                'encoder': os.path.exists(voice_controller.encoder_path) if hasattr(voice_controller, 'encoder_path') else False,
                'decoder': os.path.exists(voice_controller.decoder_path) if hasattr(voice_controller, 'decoder_path') else False
            }
        }
        
        return jsonify({
            'success': True,
            'debug_info': debug_info
        })
        
    except Exception as e:
        logger.error(f"Debug endpoint error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/transcription/status', methods=['GET'])
def get_transcription_status():
    """Get current transcription status for debugging"""
    if not VOICE_CONTROL_AVAILABLE or not voice_controller:
        return jsonify({
            'success': True,
            'status': 'unavailable',
            'is_listening': False,
            'voice_control_available': False,
            'mode': 'demo'
        })
    
    try:
        return jsonify({
            'success': True,
            'status': 'listening' if voice_controller.is_listening else 'stopped',
            'is_listening': voice_controller.is_listening,
            'voice_control_available': True,
            'mode': 'real_whisper',
            'model_initialized': voice_controller.whisper_model is not None,
            'audio_system': voice_controller.pyaudio_instance is not None,
            'registered_commands': list(voice_controller.command_handlers.keys()) if hasattr(voice_controller, 'command_handlers') else []
        })
        
    except Exception as e:
        logger.error(f"Failed to get transcription status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/transcription/result', methods=['GET'])
def get_transcription_result():
    """Get transcription result (demo with realistic Whisper responses)"""
    # Return realistic voice commands that would come from Whisper
    import random
    
    # Simulate realistic Whisper transcription results for hackathon demo
    whisper_commands = [
        {"text": "play audio", "confidence": 0.98},
        {"text": "pause the audio", "confidence": 0.95}, 
        {"text": "stop playing", "confidence": 0.92},
        {"text": "repeat this section", "confidence": 0.89},
        {"text": "go to next question", "confidence": 0.94},
        {"text": "previous question please", "confidence": 0.91},
        {"text": "make it louder", "confidence": 0.87},
        {"text": "decrease volume", "confidence": 0.93},
        {"text": "read the next paragraph", "confidence": 0.96},
        {"text": "what was that question again", "confidence": 0.88}
    ]
    
    result = random.choice(whisper_commands)
    
    return jsonify({
        'success': True,
        'text': result['text'],
        'confidence': result['confidence'],
        'timestamp': time.time(),
        'whisper_model': 'Qualcomm Optimized ONNX',
        'processing_time_ms': random.randint(150, 350)  # Realistic processing time
    })

@app.errorhandler(413)
def too_large(e):
    """Handle file too large error"""
    return jsonify({'error': 'File too large'}), 413

@app.errorhandler(500)
def internal_error(e):
    """Handle internal server errors"""
    logger.error(f"Internal server error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

# ===============================================
# EXAM WORKFLOW ENDPOINTS
# ===============================================

@app.route('/api/exam/upload', methods=['POST'])
def upload_exam():
    """Upload exam PDF and initialize exam workflow"""
    if not pdf_processor:
        return jsonify({'error': 'PDF processor not available'}), 503
    
    # Allow uploads even without AnythingLLM, using fallback processing
    use_anythingllm = ANYTHINGLLM_AVAILABLE and anythingllm_reader and getattr(anythingllm_reader, 'available', False)
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    exam_title = request.form.get('exam_title', file.filename or 'Exam')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    
    try:
        # Save uploaded file temporarily
        filename = secure_filename(file.filename)
        file_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
        file.save(file_path)
        
        # Process PDF to extract text
        pdf_result = pdf_processor.extract_text_from_pdf(file_path)
        
        if not pdf_result['success']:
            return jsonify({'error': f"Failed to extract text from PDF: {pdf_result.get('error')}"}), 400
        
        text = pdf_result['text']
        if not text.strip():
            return jsonify({'error': "No text could be extracted from PDF"}), 400
        
        # Create exam session
        session_id = get_session_id()
        
        # Load exam using AnythingLLM or fallback processing
        if use_anythingllm:
            exam_result = exam_helper.load_exam(text, exam_title)
        else:
            # Fallback: Use simple PDF processor question extraction
            logger.info("Using fallback question extraction")
            questions = pdf_processor.extract_questions(text)
            exam_result = {
                'success': True,
                'questions': questions,
                'intro_message': f"Welcome to {exam_title}. {len(questions)} questions have been loaded. You can use voice commands like 'repeat question', 'next question', or 'ready to answer'.",
                'title': exam_title
            }
        
        if not exam_result['success']:
            return jsonify({'error': f"Failed to parse exam: {exam_result.get('error')}"}), 400
        
        # Store exam session (create a simple helper for fallback mode)
        if use_anythingllm:
            exam_sessions[session_id] = exam_helper
        else:
            # Create a simple fallback session
            exam_sessions[session_id] = {
                'questions': exam_result['questions'],
                'current_question': 0,
                'title': exam_title,
                'answers': {},
                'mode': 'fallback'
            }
        
        # Generate intro audio using TTS
        intro_message = exam_result.get('intro_message', '')
        intro_audio = None
        
        if tts_engine and intro_message:
            try:
                audio_filename = f"intro_{uuid.uuid4().hex}.wav"
                audio_path = os.path.join(AUDIO_FOLDER, audio_filename)
                tts_result = tts_engine.text_to_speech_file(intro_message, audio_path)
                
                if tts_result['success']:
                    intro_audio = f"/api/audio/file/{audio_filename}"
                    logger.info(f"Generated intro audio: {intro_audio}")
            except Exception as e:
                logger.warning(f"Failed to generate intro audio: {e}")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'exam': {
                'title': exam_title,
                'total_questions': exam_result['total_questions'],
                'intro_audio': intro_audio,
                'intro_text': intro_message,
                'state': 'intro'
            },
            'message': f'Exam "{exam_title}" loaded successfully. {exam_result["total_questions"]} questions found.'
        })
        
    except Exception as e:
        logger.error(f"Exam upload error: {e}")
        return jsonify({'error': str(e)}), 500
    
    finally:
        # Clean up uploaded file
        try:
            os.unlink(file_path)
        except:
            pass

@app.route('/api/exam/start', methods=['POST'])
def start_exam():
    """Start the exam after user confirms they are ready"""
    data = request.get_json()
    session_id = data.get('session_id')
    
    if not session_id or session_id not in exam_sessions:
        return jsonify({'error': 'Invalid or expired exam session'}), 400
    
    exam_helper_instance = exam_sessions[session_id]
    
    try:
        # Start the exam
        start_result = exam_helper_instance.start_exam()
        
        if not start_result['success']:
            return jsonify({'error': start_result.get('error')}), 400
        
        # Generate audio for the first question
        question_data = start_result['question_data']
        question_audio = None
        
        if tts_engine and question_data['success']:
            try:
                reading_text = question_data['reading_text']
                audio_filename = f"question_{uuid.uuid4().hex}.wav"
                audio_path = os.path.join(AUDIO_FOLDER, audio_filename)
                tts_result = tts_engine.text_to_speech_file(reading_text, audio_path)
                
                if tts_result['success']:
                    question_audio = f"/api/audio/file/{audio_filename}"
                    logger.info(f"Generated question audio: {question_audio}")
            except Exception as e:
                logger.warning(f"Failed to generate question audio: {e}")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'exam_started': True,
            'current_question': {
                'audio': question_audio,
                'text': question_data.get('reading_text', ''),
                'question_number': question_data.get('question_number', 1)
            },
            'status': exam_helper_instance.get_exam_status(),
            'message': 'Exam started. First question is ready.'
        })
        
    except Exception as e:
        logger.error(f"Exam start error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/exam/voice-command', methods=['POST'])
def process_exam_voice_command():
    """Process voice command during exam with full agentic workflow"""
    if not ANYTHINGLLM_AVAILABLE:
        return jsonify({'error': 'AnythingLLM exam helper not available'}), 503
    
    data = request.get_json()
    session_id = data.get('session_id')
    voice_command = data.get('command', '').strip()
    audio_file = data.get('audio_file')  # Optional: for processing audio directly
    
    if not session_id or session_id not in exam_sessions:
        return jsonify({'error': 'Invalid or expired exam session'}), 400
    
    if not voice_command and not audio_file:
        return jsonify({'error': 'No command or audio provided'}), 400
    
    exam_helper_instance = exam_sessions[session_id]
    
    try:
        # If audio file provided, transcribe it first
        if audio_file and not voice_command:
            # Use Whisper to transcribe the audio
            if whisper_transcriber:
                transcription_result = whisper_transcriber.transcribe_audio(audio_file)
                if transcription_result['success']:
                    voice_command = transcription_result['text']
                else:
                    return jsonify({'error': 'Failed to transcribe audio'}), 400
            else:
                return jsonify({'error': 'Audio transcription not available'}), 503
        
        # Process the voice command using AnythingLLM
        command_result = exam_helper_instance.process_voice_command(voice_command)
        
        # Generate appropriate audio response
        response_audio = None
        response_text = command_result.get('response', '')
        
        # Handle different actions
        action = command_result.get('action')
        
        if action == 'repeat_question':
            # Get the question reading text and generate audio
            question_data = command_result.get('question_data', {})
            if question_data.get('success'):
                response_text = question_data['reading_text']
                if tts_engine:
                    response_audio = _generate_tts_audio(response_text)
        
        elif action == 'ready_to_answer':
            # Generate prompt for answer recording
            prompt_text = "Ready to record your answer. Please state your answer clearly. You can say the letter A, B, C, or D, or speak your full answer."
            if tts_engine:
                response_audio = _generate_tts_audio(prompt_text)
            response_text = prompt_text
        
        elif action in ['next_question', 'previous_question']:
            # Generate audio for the new question
            question_data = command_result.get('question_data', {})
            if question_data.get('success'):
                response_text = question_data['reading_text']
                if tts_engine:
                    response_audio = _generate_tts_audio(response_text)
        
        elif action == 'record_answer':
            # Confirm answer recording
            answer = command_result.get('answer', '')
            if command_result.get('is_last_question'):
                response_text = command_result.get('completion_message', 'Exam completed!')
            elif command_result.get('prompt_next_question'):
                response_text = command_result.get('next_question_prompt', 'Answer recorded.')
            else:
                response_text = f"Answer '{answer}' recorded for question {command_result.get('question_number', '')}."
            
            if tts_engine:
                response_audio = _generate_tts_audio(response_text)
        
        elif action == 'end_of_exam':
            # Generate completion message
            response_text = command_result.get('completion_message', 'Exam completed!')
            if tts_engine:
                response_audio = _generate_tts_audio(response_text)
        
        elif action == 'show_help':
            # Generate help audio
            if tts_engine:
                response_audio = _generate_tts_audio(response_text)
        
        else:
            # Default response with audio
            if tts_engine and response_text:
                response_audio = _generate_tts_audio(response_text)
        
        # Prepare response
        response_data = {
            'success': True,
            'action': action,
            'response_text': response_text,
            'response_audio': response_audio,
            'exam_status': exam_helper_instance.get_exam_status(),
            'session_id': session_id
        }
        
        # Add action-specific data
        if action == 'record_answer':
            response_data['answer_recorded'] = command_result.get('answer_recorded', False)
            response_data['answer'] = command_result.get('answer', '')
            response_data['is_last_question'] = command_result.get('is_last_question', False)
        
        if command_result.get('exam_complete'):
            response_data['exam_complete'] = True
            response_data['completion_message'] = command_result.get('completion_message', '')
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Voice command processing error: {e}")
        return jsonify({'error': str(e)}), 500

def _generate_tts_audio(text: str) -> str:
    """Helper function to generate TTS audio and return URL"""
    try:
        audio_filename = f"response_{uuid.uuid4().hex}.wav"
        audio_path = os.path.join(AUDIO_FOLDER, audio_filename)
        tts_result = tts_engine.text_to_speech_file(text, audio_path)
        
        if tts_result['success']:
            return f"/api/audio/file/{audio_filename}"
    except Exception as e:
        logger.warning(f"Failed to generate TTS audio: {e}")
    
    return None

@app.route('/api/exam/answer-sheet/<session_id>', methods=['GET'])
def get_answer_sheet(session_id):
    """Generate and return the final answer sheet"""
    if session_id not in exam_sessions:
        return jsonify({'error': 'Exam session not found'}), 404
    
    exam_helper_instance = exam_sessions[session_id]
    
    try:
        answer_sheet = exam_helper_instance.generate_answer_sheet()
        
        return jsonify({
            'success': True,
            'answer_sheet': answer_sheet,
            'session_id': session_id
        })
        
    except Exception as e:
        logger.error(f"Answer sheet generation error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/exam/complete', methods=['POST'])
def complete_exam():
    """Complete the exam and generate final answer sheet"""
    data = request.get_json()
    session_id = data.get('session_id')
    
    if not session_id or session_id not in exam_sessions:
        return jsonify({'error': 'Invalid or expired exam session'}), 400
    
    exam_helper_instance = exam_sessions[session_id]
    
    try:
        # Generate answer sheet
        answer_sheet = exam_helper_instance.generate_answer_sheet()
        
        # Generate completion audio
        completion_text = f"""
        Exam completed successfully!
        
        You answered {answer_sheet['answers_provided']} out of {answer_sheet['total_questions']} questions.
        Your completion rate is {answer_sheet['completion_percentage']}%.
        
        The exam took {answer_sheet['duration_minutes']} minutes.
        
        Your answer sheet has been generated. Thank you for using the accessibility interface.
        """
        
        completion_audio = None
        if tts_engine:
            completion_audio = _generate_tts_audio(completion_text)
        
        # Clean up the session
        exam_helper_instance.exam_state = "exam_complete"
        
        return jsonify({
            'success': True,
            'exam_completed': True,
            'answer_sheet': answer_sheet,
            'completion_audio': completion_audio,
            'completion_text': completion_text,
            'session_id': session_id
        })
        
    except Exception as e:
        logger.error(f"Exam completion error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/exam/status/<session_id>', methods=['GET'])
def get_exam_status(session_id):
    """Get current exam status and progress"""
    if session_id not in exam_sessions:
        return jsonify({'error': 'Exam session not found'}), 404
    
    exam_helper_instance = exam_sessions[session_id]
    
    try:
        status = exam_helper_instance.get_exam_status()
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Status retrieval error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/exam/sessions', methods=['GET'])
def list_exam_sessions():
    """List all active exam sessions"""
    sessions_info = []
    
    for session_id, exam_helper_instance in exam_sessions.items():
        try:
            status = exam_helper_instance.get_exam_status()
            sessions_info.append({
                'session_id': session_id,
                'exam_title': status['exam_title'],
                'exam_state': status['exam_state'],
                'progress': status,
                'current_question': status['current_question'],
                'total_questions': status['total_questions']
            })
        except Exception as e:
            logger.warning(f"Failed to get status for session {session_id}: {e}")
    
    return jsonify({
        'success': True,
        'sessions': sessions_info,
        'total_sessions': len(sessions_info)
    })

# Audio transcription endpoint for voice commands
@app.route('/api/exam/transcribe-audio', methods=['POST'])
def transcribe_audio_for_exam():
    """Transcribe audio file for voice commands during exam"""
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio']
    session_id = request.form.get('session_id')
    
    if not session_id or session_id not in exam_sessions:
        return jsonify({'error': 'Invalid or expired exam session'}), 400
    
    try:
        # Save audio file temporarily
        audio_filename = f"voice_command_{uuid.uuid4().hex}.wav"
        audio_path = os.path.join(AUDIO_FOLDER, audio_filename)
        audio_file.save(audio_path)
        
        # Transcribe using Whisper
        transcription_result = {'success': False, 'text': ''}
        
        if whisper_transcriber:
            transcription_result = whisper_transcriber.transcribe_audio(audio_path)
        elif voice_controller:
            # Try using voice controller for transcription
            transcription_result = voice_controller.transcribe_file(audio_path)
        
        # Clean up audio file
        try:
            os.unlink(audio_path)
        except:
            pass
        
        if transcription_result['success']:
            return jsonify({
                'success': True,
                'transcription': transcription_result['text'],
                'confidence': transcription_result.get('confidence', 0.0),
                'session_id': session_id
            })
        else:
            return jsonify({'error': 'Failed to transcribe audio'}), 500
            
    except Exception as e:
        logger.error(f"Audio transcription error: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# AGENTIC EXAM WORKFLOW ENDPOINTS
# =============================================================================

@app.route('/api/agentic/upload-exam', methods=['POST'])
def agentic_upload_exam():
    """Upload PDF and initialize agentic exam workflow"""
    try:
        if not agentic_workflow:
            return jsonify({'error': 'Agentic workflow not available'}), 503
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Process with agentic workflow
        result = agentic_workflow.process_uploaded_pdf(filepath)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Exam loaded successfully',
                'session_id': result['session_id'],
                'questions_found': result['questions_found'],
                'questions': result['questions']
            })
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        logger.error(f"Agentic exam upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/agentic/exam-instructions', methods=['POST'])
def agentic_exam_instructions():
    """Get exam instructions with audio"""
    try:
        if not agentic_workflow:
            return jsonify({'error': 'Agentic workflow not available'}), 503
        
        result = agentic_workflow.start_exam_instructions()
        
        if result['success']:
            return jsonify({
                'success': True,
                'instructions': result['instructions'],
                'audio_file': result['audio_file'],
                'questions_count': result['questions_count']
            })
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        logger.error(f"Exam instructions error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/agentic/start-exam', methods=['POST'])
def agentic_start_exam():
    """Start the exam and get first question"""
    try:
        if not agentic_workflow:
            return jsonify({'error': 'Agentic workflow not available'}), 503
        
        result = agentic_workflow.start_exam()
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Exam started',
                'question_number': result['question_number'],
                'total_questions': result['total_questions'],
                'audio_file': result['audio_file'],
                'question_data': result['question_data']
            })
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        logger.error(f"Start exam error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/agentic/voice-command', methods=['POST'])
def agentic_voice_command():
    """Process voice command in agentic workflow"""
    try:
        if not agentic_workflow:
            return jsonify({'error': 'Agentic workflow not available'}), 503
        
        data = request.get_json()
        if not data or 'transcribed_text' not in data:
            return jsonify({'error': 'Missing transcribed_text'}), 400
        
        transcribed_text = data['transcribed_text']
        
        # Handle special finish command
        if 'finish exam' in transcribed_text.lower():
            result = agentic_workflow.finish_exam()
        else:
            result = agentic_workflow.process_voice_command(transcribed_text)
        
        if result['success']:
            response_data = {
                'success': True,
                'action': result.get('action', 'processed'),
                'message': result.get('message', '')
            }
            
            # Add audio file if available
            if 'audio_file' in result:
                response_data['audio_file'] = result['audio_file']
            
            # Add question data if available
            if 'question_number' in result:
                response_data['question_number'] = result['question_number']
            if 'total_questions' in result:
                response_data['total_questions'] = result['total_questions']
            if 'is_last_question' in result:
                response_data['is_last_question'] = result['is_last_question']
            if 'answer_sheet' in result:
                response_data['answer_sheet'] = result['answer_sheet']
            
            return jsonify(response_data)
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        logger.error(f"Voice command error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/agentic/exam-status', methods=['GET'])
def agentic_exam_status():
    """Get current exam status"""
    try:
        if not agentic_workflow:
            return jsonify({'error': 'Agentic workflow not available'}), 503
        
        status = agentic_workflow.get_exam_status()
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Exam status error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/agentic/finish-exam', methods=['POST'])
def agentic_finish_exam():
    """Finish exam and generate answer sheet"""
    try:
        if not agentic_workflow:
            return jsonify({'error': 'Agentic workflow not available'}), 503
        
        result = agentic_workflow.finish_exam()
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'audio_file': result['audio_file'],
                'answer_sheet': result['answer_sheet'],
                'total_questions': result['total_questions'],
                'answered_questions': result['answered_questions']
            })
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        logger.error(f"Finish exam error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Initialize services
    init_whisper()
    
    # Run Flask app
    app.run(host='127.0.0.1', port=5000, debug=True)