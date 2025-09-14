"""
Complete Agentic Exam Workflow for iLumina
Integrates AnythingLLM with existing TTS, Whisper, and PDF processing
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from anythingllm_integration import AnythingLLMExamReader
from tts_engine import TTSEngine
from pdf_processor import PDFProcessor

logger = logging.getLogger(__name__)

class ExamState:
    """Tracks the current state of the exam"""
    def __init__(self):
        self.current_question = 0
        self.total_questions = 0
        self.questions = []
        self.answers = {}
        self.exam_started = False
        self.exam_completed = False
        self.session_id = None
        self.start_time = None
        self.end_time = None
        
    def reset(self):
        """Reset exam state for new exam"""
        self.__init__()

class AgenticExamWorkflow:
    """
    Complete agentic workflow for accessible exam taking
    
    Workflow:
    1. PDF uploaded -> text extracted
    2. AnythingLLM identifies questions
    3. Audio instructions given
    4. Voice-controlled exam taking
    5. Answer collection
    6. Answer sheet generation
    """
    
    def __init__(self):
        """Initialize the agentic exam workflow"""
        self.llm_reader = AnythingLLMExamReader()
        self.tts_engine = TTSEngine()
        self.pdf_processor = PDFProcessor()
        self.state = ExamState()
        
        logger.info("🎓 Agentic Exam Workflow initialized")
        
    def process_uploaded_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Process uploaded PDF and extract questions using AnythingLLM
        
        Args:
            pdf_path: Path to uploaded PDF
            
        Returns:
            Dict with success status and extracted questions
        """
        try:
            logger.info(f"📄 Processing PDF: {pdf_path}")
            
            # Step 1: Extract text from PDF
            pdf_result = self.pdf_processor.extract_text_from_pdf(pdf_path)
            if not pdf_result['success']:
                return {
                    'success': False,
                    'error': f"PDF extraction failed: {pdf_result['error']}"
                }
            
            pdf_text = pdf_result['text']
            logger.info(f"📝 Extracted {len(pdf_text)} characters from PDF")
            
            # Step 2: Use AnythingLLM to identify questions
            questions = self.llm_reader.parse_exam_questions(pdf_text)
            
            if not questions:
                return {
                    'success': False,
                    'error': "No questions found in PDF"
                }
            
            # Step 3: Initialize exam state
            self.state.reset()
            self.state.questions = questions
            self.state.total_questions = len(questions)
            self.state.session_id = f"exam_{int(datetime.now().timestamp())}"
            
            logger.info(f"✅ Found {len(questions)} questions in exam")
            
            return {
                'success': True,
                'questions_found': len(questions),
                'questions': questions,
                'session_id': self.state.session_id
            }
            
        except Exception as e:
            logger.error(f"❌ PDF processing failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def start_exam_instructions(self) -> Dict[str, Any]:
        """
        Provide initial exam instructions via audio
        
        Returns:
            Dict with audio file path and instructions
        """
        try:
            if not self.state.questions:
                return {
                    'success': False,
                    'error': "No exam loaded"
                }
            
            # Create comprehensive instructions
            instructions = f"""
            Welcome to the iLumina accessible exam system. 
            
            I have loaded your exam with {self.state.total_questions} questions.
            
            Here's how to interact with me during the exam:
            
            Say "repeat" to hear the current question again.
            Say "repeat slower" to hear it at a slower pace.
            Say "ready to answer" when you want to provide your answer.
            Say "next question" to move to the next question.
            
            I will read each question and its options clearly.
            When you're ready to answer, I'll listen for your response.
            You can say things like "A", "option B", or "the answer is C".
            
            Are you ready to begin the exam? Say "start exam" when you're ready.
            """
            
            # Generate audio
            audio_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'audio_files')
            os.makedirs(audio_dir, exist_ok=True)
            audio_path = os.path.join(audio_dir, f"exam_instructions_{self.state.session_id}.wav")
            
            audio_result = self.tts_engine.text_to_speech_file(
                instructions, 
                output_path=audio_path
            )
            
            if not audio_result['success']:
                return {
                    'success': False,
                    'error': f"Audio generation failed: {audio_result['error']}"
                }
            
            audio_file = audio_result['file_path']
            
            return {
                'success': True,
                'instructions': instructions,
                'audio_file': audio_file,
                'questions_count': self.state.total_questions
            }
            
        except Exception as e:
            logger.error(f"❌ Instructions generation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def start_exam(self) -> Dict[str, Any]:
        """
        Start the exam and provide instructions, then read the first question
        
        Returns:
            Dict with exam instructions and first question audio
        """
        try:
            if not self.state.questions:
                return {
                    'success': False,
                    'error': "No exam loaded"
                }
            
            self.state.exam_started = True
            self.state.start_time = datetime.now()
            self.state.current_question = 0
            
            logger.info("🎯 Starting exam - generating instructions first")
            
            # Generate exam instructions audio
            instructions = f"""
            Welcome to your exam! I have loaded your exam with {self.state.total_questions} questions.
            
            Here's how to interact with me during the exam:
            
            Say "repeat" to hear the current question again.
            Say "repeat slower" to hear it at a slower pace.
            Say "ready to answer" when you want to provide your answer.
            Say "next question" to move to the next question.
            
            I will read each question and its options clearly.
            When you're ready to answer, I'll listen for your response.
            You can say things like "A", "option B", or "the answer is C".
            
            Let's begin with the first question!
            """
            
            # Generate instructions audio
            audio_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'audio_files')
            os.makedirs(audio_dir, exist_ok=True)
            audio_path = os.path.join(audio_dir, f"exam_start_{self.state.session_id}.wav")
            
            instructions_result = self.tts_engine.text_to_speech_file(
                instructions, 
                output_path=audio_path
            )
            
            if not instructions_result['success']:
                return {
                    'success': False,
                    'error': f"Audio generation failed: {instructions_result['error']}"
                }
            
            instructions_audio = instructions_result['file_path']
            
            logger.info(f"🔊 Generated exam start instructions: {instructions_audio}")
            
            # Return the instructions audio - the first question will be read when the instructions finish
            return {
                'success': True,
                'action': 'exam_started',
                'message': instructions,
                'audio_file': instructions_audio,
                'questions_count': self.state.total_questions,
                'current_question': 1,
                'instructions': instructions,
                'next_action': 'Will read first question after instructions'
            }
            
        except Exception as e:
            logger.error(f"❌ Exam start failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def read_current_question(self, slower: bool = False) -> Dict[str, Any]:
        """
        Read the current question aloud
        
        Args:
            slower: Whether to read at slower pace
            
        Returns:
            Dict with question audio and details
        """
        try:
            if not self.state.exam_started:
                return {
                    'success': False,
                    'error': "Exam not started"
                }
            
            if self.state.current_question >= len(self.state.questions):
                return {
                    'success': False,
                    'error': "No more questions"
                }
            
            question = self.state.questions[self.state.current_question]
            question_num = self.state.current_question + 1
            
            # Format question for reading
            question_text = f"""
            Question {question_num} of {self.state.total_questions}.
            
            {question.get('question_text', question.get('question', ''))}
            
            The options are:
            """
            
            # Add options
            options = question.get('options', [])
            for option in options:
                if isinstance(option, dict):
                    label = option.get('label', '')
                    text = option.get('text', '')
                    question_text += f"\n{label}: {text}"
                elif isinstance(option, tuple) and len(option) == 2:
                    question_text += f"\n{option[0]}: {option[1]}"
            
            question_text += "\n\nWhat would you like to do? You can say repeat, repeat slower, ready to answer, or next question."
            
            # Generate audio with appropriate speed
            # Note: pyttsx3 speed control is handled differently
            audio_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'audio_files')
            os.makedirs(audio_dir, exist_ok=True)
            audio_path = os.path.join(audio_dir, f"question_{question_num}_{self.state.session_id}.wav")
            
            audio_result = self.tts_engine.text_to_speech_file(
                question_text,
                output_path=audio_path
            )
            
            if not audio_result['success']:
                return {
                    'success': False,
                    'error': f"Audio generation failed: {audio_result['error']}"
                }
            
            audio_file = audio_result['file_path']
            
            return {
                'success': True,
                'question_number': question_num,
                'total_questions': self.state.total_questions,
                'question_text': question_text,
                'audio_file': audio_file,
                'question_data': question
            }
            
        except Exception as e:
            logger.error(f"❌ Question reading failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def process_voice_command(self, transcribed_text: str) -> Dict[str, Any]:
        """
        Process voice command using AnythingLLM for intelligent understanding
        
        Args:
            transcribed_text: Text from Whisper transcription
            
        Returns:
            Dict with action and response
        """
        try:
            logger.info(f"🎤 Processing voice command: '{transcribed_text}'")
            logger.info(f"📊 Exam state - started: {self.state.exam_started}, current_q: {self.state.current_question}, total_q: {self.state.total_questions}")
            
            if not self.state.exam_started:
                logger.info("❌ Exam not started, checking for start command")
                # Handle pre-exam commands
                if "start exam" in transcribed_text.lower():
                    logger.info("🚀 Starting exam...")
                    return self.start_exam()
                else:
                    logger.info("⏳ Waiting for 'start exam' command")
                    return {
                        'success': True,
                        'action': 'waiting_to_start',
                        'message': "Say 'start exam' when you're ready to begin."
                    }
            
            # Log current question context for AnythingLLM
            current_question_data = None
            if self.state.questions and self.state.current_question < len(self.state.questions):
                current_question_data = self.state.questions[self.state.current_question]
                logger.info(f"📝 Current question context: Q{self.state.current_question + 1} - {current_question_data.get('question_text', 'No text')[:100]}...")
            
            # Use AnythingLLM to understand the command
            logger.info(f"🤖 Sending to AnythingLLM - command: '{transcribed_text}', question: {self.state.current_question + 1}/{self.state.total_questions}")
            
            command_result = self.llm_reader.handle_voice_command(
                transcribed_text,
                self.state.current_question + 1,
                self.state.total_questions,
                "exam_taking"
            )
            
            logger.info(f"🔄 AnythingLLM response: {command_result}")
            
            if not command_result['success']:
                logger.warning("⚠️ AnythingLLM failed, using fallback processing")
                # Fallback to simple keyword matching
                return self._fallback_command_processing(transcribed_text)
            
            action = command_result.get('action', 'unknown')
            logger.info(f"🎯 Determined action: {action}")
            
            # Execute the determined action
            if action == 'repeat_question':
                logger.info("🔁 Repeating current question")
                # If we just started the exam, read the first question
                if self.state.current_question == 0 and self.state.exam_started:
                    logger.info("📖 Reading first question after exam start")
                return self.read_current_question(slower=False)
            elif action == 'repeat_slower':
                logger.info("🐌 Repeating current question slower")
                return self.read_current_question(slower=True)
            elif action == 'ready_to_answer':
                logger.info("✋ Preparing for answer")
                return self._prepare_for_answer()
            elif action == 'next_question':
                logger.info("➡️ Moving to next question")
                return self.next_question()
            elif action == 'record_answer':
                answer = command_result.get('answer_value', '')
                logger.info(f"📝 Recording answer: {answer}")
                return self.record_answer(answer)
            else:
                logger.warning(f"❓ Unknown action: {action}")
                return {
                    'success': True,
                    'action': 'clarification_needed',
                    'message': "I didn't understand that command. You can say: repeat, repeat slower, ready to answer, or next question."
                }
                
        except Exception as e:
            logger.error(f"❌ Voice command processing failed: {e}")
            return self._fallback_command_processing(transcribed_text)
    
    def _fallback_command_processing(self, text: str) -> Dict[str, Any]:
        """Fallback command processing using keywords"""
        text_lower = text.lower()
        
        if "repeat slower" in text_lower or "slower" in text_lower:
            return self.read_current_question(slower=True)
        elif "repeat" in text_lower:
            return self.read_current_question(slower=False)
        elif "ready" in text_lower or "answer" in text_lower:
            return self._prepare_for_answer()
        elif "next" in text_lower:
            return self.next_question()
        elif any(option in text_lower for option in ['a', 'b', 'c', 'd', 'option']):
            # Extract answer
            for option in ['a', 'b', 'c', 'd']:
                if option in text_lower:
                    return self.record_answer(option.upper())
            return self.record_answer(text)
        else:
            return {
                'success': True,
                'action': 'clarification_needed',
                'message': "I didn't understand. Say: repeat, repeat slower, ready to answer, or next question."
            }
    
    def _prepare_for_answer(self) -> Dict[str, Any]:
        """Prepare to receive an answer"""
        instruction = "Please provide your answer. You can say A, B, C, D, or say 'option A', 'the answer is B', etc."
        
        audio_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'audio_files')
        os.makedirs(audio_dir, exist_ok=True)
        audio_path = os.path.join(audio_dir, f"answer_prompt_{self.state.session_id}.wav")
        
        audio_result = self.tts_engine.text_to_speech_file(
            instruction,
            output_path=audio_path
        )
        
        if not audio_result['success']:
            return {
                'success': False,
                'error': f"Audio generation failed: {audio_result['error']}"
            }
        
        audio_file = audio_result['file_path']
        
        return {
            'success': True,
            'action': 'awaiting_answer',
            'message': instruction,
            'audio_file': audio_file
        }
    
    def record_answer(self, answer: str) -> Dict[str, Any]:
        """
        Record student's answer
        
        Args:
            answer: Student's answer
            
        Returns:
            Dict with confirmation and next action
        """
        try:
            question_num = self.state.current_question + 1
            self.state.answers[question_num] = {
                'answer': answer.strip().upper(),
                'timestamp': datetime.now().isoformat(),
                'question_text': self.state.questions[self.state.current_question].get('question_text', '')
            }
            
            confirmation = f"I recorded your answer as {answer}."
            
            # Check if this is the last question
            if self.state.current_question >= self.state.total_questions - 1:
                confirmation += f" This was the last question. You have completed all {self.state.total_questions} questions. Say 'finish exam' to generate your answer sheet."
            else:
                confirmation += " Say 'next question' to continue."
            
            audio_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'audio_files')
            os.makedirs(audio_dir, exist_ok=True)
            audio_path = os.path.join(audio_dir, f"answer_recorded_{question_num}_{self.state.session_id}.wav")
            
            audio_result = self.tts_engine.text_to_speech_file(
                confirmation,
                output_path=audio_path
            )
            
            if not audio_result['success']:
                return {
                    'success': False,
                    'error': f"Audio generation failed: {audio_result['error']}"
                }
            
            audio_file = audio_result['file_path']
            
            logger.info(f"📝 Recorded answer for Q{question_num}: {answer}")
            
            return {
                'success': True,
                'action': 'answer_recorded',
                'message': confirmation,
                'audio_file': audio_file,
                'question_number': question_num,
                'answer': answer,
                'is_last_question': self.state.current_question >= self.state.total_questions - 1
            }
            
        except Exception as e:
            logger.error(f"❌ Answer recording failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def next_question(self) -> Dict[str, Any]:
        """Move to next question"""
        try:
            if self.state.current_question >= self.state.total_questions - 1:
                return {
                    'success': False,
                    'action': 'exam_complete',
                    'message': "You have completed all questions. Say 'finish exam' to generate your answer sheet."
                }
            
            self.state.current_question += 1
            return self.read_current_question()
            
        except Exception as e:
            logger.error(f"❌ Next question failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def finish_exam(self) -> Dict[str, Any]:
        """
        Finish exam and generate answer sheet
        
        Returns:
            Dict with answer sheet details
        """
        try:
            self.state.exam_completed = True
            self.state.end_time = datetime.now()
            
            # Generate answer sheet
            answer_sheet = self._generate_answer_sheet()
            
            completion_message = f"""
            Congratulations! You have completed your exam.
            
            You answered {len(self.state.answers)} out of {self.state.total_questions} questions.
            
            Your answer sheet has been generated and saved.
            
            Thank you for using the iLumina accessible exam system.
            """
            
            audio_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'audio_files')
            os.makedirs(audio_dir, exist_ok=True)
            audio_path = os.path.join(audio_dir, f"exam_complete_{self.state.session_id}.wav")
            
            audio_result = self.tts_engine.text_to_speech_file(
                completion_message,
                output_path=audio_path
            )
            
            if not audio_result['success']:
                return {
                    'success': False,
                    'error': f"Audio generation failed: {audio_result['error']}"
                }
            
            audio_file = audio_result['file_path']
            
            return {
                'success': True,
                'action': 'exam_completed',
                'message': completion_message,
                'audio_file': audio_file,
                'answer_sheet': answer_sheet,
                'total_questions': self.state.total_questions,
                'answered_questions': len(self.state.answers)
            }
            
        except Exception as e:
            logger.error(f"❌ Exam completion failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_answer_sheet(self) -> str:
        """Generate answer sheet file"""
        try:
            answer_sheet_data = {
                'session_id': self.state.session_id,
                'start_time': self.state.start_time.isoformat() if self.state.start_time else None,
                'end_time': self.state.end_time.isoformat() if self.state.end_time else None,
                'total_questions': self.state.total_questions,
                'answered_questions': len(self.state.answers),
                'answers': self.state.answers,
                'questions': self.state.questions
            }
            
            # Save to file
            answer_sheet_file = f"answer_sheet_{self.state.session_id}.json"
            answer_sheet_path = os.path.join("uploads", answer_sheet_file)
            
            os.makedirs("uploads", exist_ok=True)
            
            with open(answer_sheet_path, 'w') as f:
                json.dump(answer_sheet_data, f, indent=2, default=str)
            
            logger.info(f"📋 Answer sheet saved: {answer_sheet_path}")
            
            return answer_sheet_path
            
        except Exception as e:
            logger.error(f"❌ Answer sheet generation failed: {e}")
            return f"Error generating answer sheet: {e}"
    
    def get_exam_status(self) -> Dict[str, Any]:
        """Get current exam status"""
        return {
            'session_id': self.state.session_id,
            'exam_started': self.state.exam_started,
            'exam_completed': self.state.exam_completed,
            'current_question': self.state.current_question + 1 if self.state.exam_started else 0,
            'total_questions': self.state.total_questions,
            'answers_recorded': len(self.state.answers),
            'questions_remaining': self.state.total_questions - self.state.current_question - 1 if self.state.exam_started else self.state.total_questions
        }