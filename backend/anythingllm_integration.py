"""
AnythingLLM Integration for iLumina Exam Helper
Designed specifically for dyslexic and visually impaired students
Provides exam question reading assistance without academic help
"""

import requests
import yaml
import json
import logging
from typing import Dict, Any, Optional, List
import os
import time
import re

logger = logging.getLogger(__name__)

class AnythingLLMExamReader:
    def __init__(self, config_path: str = None):
        """
        Initialize AnythingLLM exam reader for accessibility
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path or os.path.join(
            os.path.dirname(__file__), 'anythingllm_config.yaml'
        )
        
        self.available = False  # Start as unavailable
        
        try:
            self.config = self._load_config()
            self.session = requests.Session()
            self.session.headers.update({
                'Authorization': f'Bearer {self.config["api_key"]}',
                'Content-Type': 'application/json'
            })
            
            # Test connection but don't fail startup if not available
            try:
                self._test_connection()
                self.available = True
                print("✅ AnythingLLM integration available for exam helper")
            except Exception as e:
                print(f"⚠️  AnythingLLM server not available: {e}")
                print("📝 Exam system will use fallback question parsing")
                self.available = False
                
        except Exception as e:
            print(f"❌ Error initializing AnythingLLM integration: {e}")
            self.available = False
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            required_keys = ['api_key', 'model_server_base_url', 'workspace_slug']
            for key in required_keys:
                if not config.get(key):
                    raise ValueError(f"Missing required config key: {key}")
            
            logger.info("✅ AnythingLLM exam reader configuration loaded")
            return config
            
        except FileNotFoundError:
            logger.error(f"❌ Config file not found: {self.config_path}")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to load config: {e}")
            raise
    
    def _test_connection(self) -> bool:
        """Test connection to AnythingLLM server"""
        try:
            # Try multiple endpoints to test AnythingLLM connectivity
            base_url = self.config['model_server_base_url']
            
            # Test endpoints in order of preference
            test_endpoints = [
                f"{base_url}/system/ping",  # Health check endpoint
                f"{base_url}/auth/me",      # User authentication endpoint
                f"{base_url}/workspaces",   # Workspaces endpoint
                f"{base_url}"               # Base API endpoint
            ]
            
            for endpoint in test_endpoints:
                try:
                    logger.info(f"Testing AnythingLLM endpoint: {endpoint}")
                    response = self.session.get(endpoint, timeout=5)
                    
                    if response.status_code == 200:
                        logger.info("✅ AnythingLLM server connected successfully")
                        return True
                    elif response.status_code == 401:
                        logger.warning("⚠️ Authentication failed - check API key")
                        # 401 means server is running but auth failed
                        return True  
                    elif response.status_code == 403:
                        logger.warning("⚠️ Access forbidden - check permissions")
                        return True  # Server is running
                    elif response.status_code == 404:
                        # Try next endpoint
                        continue
                    else:
                        logger.info(f"ℹ️ Server responded with: {response.status_code}")
                        return True  # Server is responding
                        
                except requests.exceptions.ConnectionError:
                    # Try next endpoint
                    continue
                except requests.exceptions.Timeout:
                    # Try next endpoint
                    continue
            
            # If all endpoints failed
            logger.error("❌ AnythingLLM server not reachable on any endpoint")
            return False
                
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False
    
    def _send_to_llm(self, message: str, system_prompt: str = None) -> Dict[str, Any]:
        """Send message to AnythingLLM with exam reading constraints"""
        try:
            workspace = self.config['workspace_slug']
            
            # Use the exact URL structure from the working chatbot
            if self.config.get('stream', False):
                url = f"{self.config['model_server_base_url']}/workspace/{workspace}/stream-chat"
            else:
                url = f"{self.config['model_server_base_url']}/workspace/{workspace}/chat"
            
            # Prepend system prompt to message if provided (AnythingLLM doesn't support separate system prompts in API)
            full_message = message
            if system_prompt:
                full_message = f"System Instructions: {system_prompt}\n\nUser Query: {message}"
            
            # Use exact data structure from working chatbot
            payload = {
                "message": full_message,
                "mode": "chat", 
                "sessionId": f"exam-reader-{int(time.time())}",
                "attachments": []
            }
            
            logger.info(f"Sending request to: {url}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = self.session.post(
                url, 
                json=payload, 
                timeout=self.config.get('stream_timeout', 60)
            )
            
            logger.info(f"Response status: {response.status_code}")
            
            # Handle different response scenarios
            if response.status_code == 404:
                logger.error("❌ Chat endpoint not found - check workspace configuration")
                return {
                    'success': False,
                    'error': 'Chat endpoint not available - workspace may not have a model configured'
                }
            elif response.status_code == 500:
                logger.error("❌ Server error - likely no model configured in workspace")
                return {
                    'success': False,
                    'error': 'Server error - please configure a chat model in the AnythingLLM workspace'
                }
            
            response.raise_for_status()
            
            # Handle empty response
            if not response.text.strip():
                logger.error("❌ Empty response from AnythingLLM")
                return {
                    'success': False,
                    'error': 'Empty response - check if model is properly configured'
                }
            
            try:
                result = response.json()
                logger.debug(f"Response JSON: {json.dumps(result, indent=2)}")
                
                # Handle response format from working chatbot
                if 'textResponse' in result and result['textResponse']:
                    return {
                        'success': True,
                        'response': result['textResponse'],
                        'workspace': workspace
                    }
                else:
                    logger.warning(f"No textResponse in result: {result}")
                    return {
                        'success': False,
                        'error': 'No textResponse in API response - model may not be configured',
                        'raw_response': result
                    }
                    
            except json.JSONDecodeError as e:
                logger.error(f"❌ Invalid JSON response: {e}")
                logger.error(f"Raw response: {response.text}")
                return {
                    'success': False,
                    'error': f'Invalid JSON response: {e}'
                }
                
        except Exception as e:
            logger.error(f"❌ LLM request failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def parse_exam_questions(self, pdf_text: str) -> List[Dict[str, Any]]:
        """
        Use AnythingLLM to intelligently parse PDF text to extract questions and options
        
        Args:
            pdf_text: Raw text from PDF
            
        Returns:
            List of questions with options
        """
        try:
            # Create a prompt for AnythingLLM to extract questions
            extraction_prompt = f"""
            Please analyze this exam text and extract all questions with their multiple choice options. 
            Return the data in a structured JSON format. Each question should have:
            - question_number: The question number (1, 2, 3, etc.)
            - question_text: The main question text
            - options: Array of options with label (A, B, C, D) and text
            
            Here is the exam text:
            
            {pdf_text[:4000]}  # Limit text to avoid token limits
            
            Please extract questions and format them as JSON. If no questions are found, return an empty array.
            Respond ONLY with valid JSON, no additional text or explanations.
            """
            
            result = self._send_to_llm(
                extraction_prompt,
                system_prompt="You are an expert at extracting structured data from exam papers. Extract questions and options in valid JSON format only."
            )
            
            if result['success']:
                response_text = result['response'].strip()
                
                # Try to extract JSON from the response
                try:
                    # Look for JSON content between ```json and ``` or just parse directly
                    if '```json' in response_text:
                        json_start = response_text.find('```json') + 7
                        json_end = response_text.find('```', json_start)
                        json_text = response_text[json_start:json_end].strip()
                    elif response_text.startswith('[') or response_text.startswith('{'):
                        json_text = response_text
                    else:
                        # Try to find JSON-like content
                        import re
                        json_match = re.search(r'(\[.*\]|\{.*\})', response_text, re.DOTALL)
                        json_text = json_match.group(1) if json_match else response_text
                    
                    questions_data = json.loads(json_text)
                    
                    # Convert to our format
                    questions = []
                    if isinstance(questions_data, list):
                        for idx, q in enumerate(questions_data):
                            question = {
                                'number': str(q.get('question_number', idx + 1)),
                                'question': q.get('question_text', ''),
                                'options': q.get('options', [])
                            }
                            
                            # Ensure options have the right format
                            formatted_options = []
                            for opt in question['options']:
                                if isinstance(opt, dict):
                                    formatted_options.append({
                                        'label': opt.get('label', ''),
                                        'text': opt.get('text', '')
                                    })
                                elif isinstance(opt, str):
                                    # Parse "A) Option text" format
                                    match = re.match(r'([A-E])[\)\.]?\s*(.*)', opt.strip())
                                    if match:
                                        formatted_options.append({
                                            'label': match.group(1) + ')',
                                            'text': match.group(2).strip()
                                        })
                            
                            question['options'] = formatted_options
                            questions.append(question)
                    
                    if questions:
                        logger.info(f"📋 Successfully extracted {len(questions)} questions using AnythingLLM")
                        return questions
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON response from AnythingLLM: {e}")
                    logger.warning(f"Response was: {response_text[:500]}...")
            
            # Fallback to pattern matching if LLM extraction fails
            logger.info("Falling back to pattern-based question extraction")
            return self._fallback_parse_questions(pdf_text)
            
        except Exception as e:
            logger.error(f"❌ Question extraction failed: {e}")
            return self._fallback_parse_questions(pdf_text)
    
    def _fallback_parse_questions(self, pdf_text: str) -> List[Dict[str, Any]]:
        """Fallback pattern-based question parsing"""
        questions = []
        
        # Enhanced pattern matching for common question formats
        # Split by question numbers (1., 2., etc. or Q1, Q2, etc.)
        question_patterns = [
            r'(?:^|\n)(?:Question\s*)?(\d+)[\.\)]?\s*',
            r'(?:^|\n)Q\.?\s*(\d+)[\.\)]?\s*',
            r'(?:^|\n)(\d+)[\.\)]\s*'
        ]
        
        for pattern in question_patterns:
            parts = re.split(pattern, pdf_text, flags=re.MULTILINE | re.IGNORECASE)
            
            if len(parts) > 2:  # Found at least one question
                for i in range(1, len(parts), 2):
                    if i + 1 < len(parts):
                        question_num = parts[i].strip()
                        question_text = parts[i + 1].strip()
                        
                        # Extract options (A), B), etc. - Fixed regex patterns
                        option_patterns = [
                            r'([A-E])[\)\.]]\s*([^\n]+(?:\n(?![A-E][\)\.])[^\n]*)*)',
                            r'([A-E])\s*[\)\.]?\s*([^\n]+)',
                            r'([a-e])[\)\.]]\s*([^\n]+(?:\n(?![a-e][\)\.])[^\n]*)*)'
                        ]
                        
                        options = []
                        for opt_pattern in option_patterns:
                            try:
                                found_options = re.findall(opt_pattern, question_text, re.MULTILINE)
                                if found_options:
                                    options = found_options
                                    break
                            except re.error:
                                continue
                        
                        # Clean question text (remove options)
                        clean_question = question_text
                        for opt_pattern in option_patterns:
                            try:
                                clean_question = re.sub(opt_pattern, '', clean_question, flags=re.MULTILINE)
                            except re.error:
                                continue
                        
                        clean_question = clean_question.strip()
                        
                        # Skip if question is too short
                        if len(clean_question) < 10:
                            continue
                        
                        question_data = {
                            'number': question_num,
                            'question': clean_question,
                            'options': [{'label': opt[0].upper() + ')', 'text': opt[1].strip()} for opt in options]
                        }
                        
                        questions.append(question_data)
                
                if questions:
                    break  # Use the first pattern that found questions
        
        # If still no questions found, try a simpler approach
        if not questions:
            # Look for any numbered items followed by options
            simple_pattern = r'(\d+)\.?\s*([^A-E]*?)([A-E]\)?\s*[^A-E\n]+(?:\n[A-E]\)?\s*[^A-E\n]+)*)'
            matches = re.findall(simple_pattern, pdf_text, re.MULTILINE | re.DOTALL)
            
            for match in matches:
                question_num, question_text, options_text = match
                question_text = question_text.strip()
                
                if len(question_text) > 10:  # Valid question
                    # Extract options from options_text
                    option_matches = re.findall(r'([A-E])\)?\s*([^\n]+)', options_text)
                    
                    questions.append({
                        'number': question_num,
                        'question': question_text,
                        'options': [{'label': opt[0] + ')', 'text': opt[1].strip()} for opt in option_matches]
                    })
        
        logger.info(f"📋 Fallback parsing found {len(questions)} questions")
        return questions
    
    def read_question(self, question_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate audio-friendly reading of a question
        
        Args:
            question_data: Question with number, text, and options
            
        Returns:
            Dict with formatted text for TTS
        """
        try:
            question_num = question_data.get('number', '?')
            question_text = question_data.get('question', '')
            options = question_data.get('options', [])
            
            # Create reading prompt
            reading_prompt = f"""
            Please read this exam question aloud for a student with visual impairments. 
            Read slowly and clearly, exactly as written:
            
            Question {question_num}: {question_text}
            
            Options:
            """
            
            for option in options:
                reading_prompt += f"\n{option['label']} {option['text']}"
            
            reading_prompt += "\n\nPlease provide the exact text that should be read aloud to the student."
            
            result = self._send_to_llm(
                reading_prompt,
                system_prompt=self.config.get('exam_reader_prompt')
            )
            
            if result['success']:
                return {
                    'success': True,
                    'question_number': question_num,
                    'reading_text': result['response'],
                    'original_question': question_data
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"❌ Failed to read question: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def handle_voice_command(self, command: str, current_question: int, total_questions: int, context: str = "navigation") -> Dict[str, Any]:
        """
        Process voice commands for exam navigation and answer collection
        
        Args:
            command: Voice command from student
            current_question: Current question number
            total_questions: Total number of questions
            context: Context of the command (navigation, answering, etc.)
            
        Returns:
            Dict with action and response
        """
        logger.info(f"🎯 AnythingLLM handling voice command: '{command}' (Q{current_question}/{total_questions}, context: {context})")
        
        command_lower = command.lower().strip()
        
        # Use AnythingLLM to intelligently understand the command
        command_analysis_prompt = f"""
        Analyze this voice command from a student taking an exam and determine the intended action.
        The student can use these commands:
        1. "repeat" - repeat the current question
        2. "repeat slower" - repeat the question more slowly
        3. "ready to answer" - switch to answer mode
        4. "next question" - move to next question
        5. "previous question" - go back to previous question
        6. Answer commands (when in answer mode) - like "A", "option A", "the answer is B", etc.
        
        Current context: {context}
        Current question: {current_question} of {total_questions}
        
        Student said: "{command}"
        
        Respond with a JSON object containing:
        {{
            "action": "repeat_question|repeat_slower|ready_to_answer|next_question|previous_question|record_answer|unknown",
            "answer_value": "extracted answer (only if action is record_answer)",
            "confidence": 0.0-1.0,
            "explanation": "brief explanation of what the student wants"
        }}
        
        Respond ONLY with valid JSON.
        """
        
        logger.info(f"📝 Sending prompt to AnythingLLM: {command_analysis_prompt[:200]}...")
        
        try:
            result = self._send_to_llm(
                command_analysis_prompt,
                system_prompt="You are an expert at understanding student voice commands during exams. Return only valid JSON responses."
            )
            
            logger.info(f"🤖 AnythingLLM raw result: {result}")
            
            if result['success']:
                response_text = result['response'].strip()
                logger.info(f"📄 AnythingLLM response text: {response_text}")
                
                # Parse JSON response
                try:
                    if '```json' in response_text:
                        json_start = response_text.find('```json') + 7
                        json_end = response_text.find('```', json_start)
                        json_text = response_text[json_start:json_end].strip()
                    else:
                        json_text = response_text
                    
                    logger.info(f"🔍 Parsed JSON text: {json_text}")
                    command_data = json.loads(json_text)
                    action = command_data.get('action', 'unknown')
                    
                    # Handle the action
                    return self._execute_command_action(action, command_data, current_question, total_questions, command)
                    
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse command analysis JSON: {response_text}")
        
        except Exception as e:
            logger.warning(f"LLM command analysis failed: {e}")
        
        # Fallback to pattern matching
        return self._fallback_command_processing(command_lower, current_question, total_questions)
    
    def _execute_command_action(self, action: str, command_data: Dict, current_question: int, total_questions: int, original_command: str) -> Dict[str, Any]:
        """Execute the determined command action"""
        
        if action == 'repeat_question':
            return {
                'action': 'repeat_question',
                'response': "Repeating the current question",
                'question_number': current_question,
                'reading_speed': 'normal',
                'confidence': command_data.get('confidence', 0.9)
            }
        
        elif action == 'repeat_slower':
            return {
                'action': 'repeat_question',
                'response': "Repeating the question more slowly",
                'question_number': current_question,
                'reading_speed': 'slower',
                'confidence': command_data.get('confidence', 0.9)
            }
        
        elif action == 'ready_to_answer':
            return {
                'action': 'ready_to_answer',
                'response': "Ready to record your answer. Please state your answer clearly.",
                'question_number': current_question,
                'confidence': command_data.get('confidence', 0.9)
            }
        
        elif action == 'next_question':
            if current_question < total_questions:
                return {
                    'action': 'next_question',
                    'response': f"Moving to question {current_question + 1}",
                    'question_number': current_question + 1,
                    'confidence': command_data.get('confidence', 0.9)
                }
            else:
                return {
                    'action': 'end_of_exam',
                    'response': "You have reached the end of the exam. Would you like to finish and generate your answer sheet?",
                    'question_number': current_question,
                    'confidence': command_data.get('confidence', 0.9)
                }
        
        elif action == 'previous_question':
            if current_question > 1:
                return {
                    'action': 'previous_question',
                    'response': f"Going back to question {current_question - 1}",
                    'question_number': current_question - 1,
                    'confidence': command_data.get('confidence', 0.9)
                }
            else:
                return {
                    'action': 'start_of_exam',
                    'response': "You are at the first question",
                    'question_number': current_question,
                    'confidence': command_data.get('confidence', 0.9)
                }
        
        elif action == 'record_answer':
            answer = command_data.get('answer_value', original_command)
            return {
                'action': 'record_answer',
                'response': f"Recorded your answer: {answer}",
                'answer': answer,
                'question_number': current_question,
                'confidence': command_data.get('confidence', 0.8)
            }
        
        else:
            return self._get_help_response(current_question)
    
    def _fallback_command_processing(self, command_lower: str, current_question: int, total_questions: int) -> Dict[str, Any]:
        """Fallback pattern-based command processing"""
        
        # Pattern matching for common commands
        if any(word in command_lower for word in ['repeat', 'again', 'read again']):
            if any(word in command_lower for word in ['slow', 'slower', 'slowly']):
                return {
                    'action': 'repeat_question',
                    'response': "Repeating the question more slowly",
                    'question_number': current_question,
                    'reading_speed': 'slower'
                }
            else:
                return {
                    'action': 'repeat_question',
                    'response': "Repeating the current question",
                    'question_number': current_question,
                    'reading_speed': 'normal'
                }
        
        elif any(phrase in command_lower for phrase in ['ready to answer', 'ready answer', 'answer now', 'i want to answer']):
            return {
                'action': 'ready_to_answer',
                'response': "Ready to record your answer. Please state your answer clearly.",
                'question_number': current_question
            }
        
        elif any(word in command_lower for word in ['next', 'continue', 'move on', 'proceed']):
            if current_question < total_questions:
                return {
                    'action': 'next_question',
                    'response': f"Moving to question {current_question + 1}",
                    'question_number': current_question + 1
                }
            else:
                return {
                    'action': 'end_of_exam',
                    'response': "You have reached the end of the exam",
                    'question_number': current_question
                }
        
        elif any(word in command_lower for word in ['previous', 'back', 'go back']):
            if current_question > 1:
                return {
                    'action': 'previous_question',
                    'response': f"Going back to question {current_question - 1}",
                    'question_number': current_question - 1
                }
            else:
                return {
                    'action': 'start_of_exam',
                    'response': "You are at the first question",
                    'question_number': current_question
                }
        
        # Check if it might be an answer (A, B, C, D, or descriptive answer)
        elif any(pattern in command_lower for pattern in ['option a', 'option b', 'option c', 'option d', 'answer is', 'my answer']):
            # Extract the answer
            answer = self._extract_answer_from_text(command_lower)
            return {
                'action': 'record_answer',
                'response': f"Recorded your answer: {answer}",
                'answer': answer,
                'question_number': current_question
            }
        
        elif re.match(r'^[a-d]$', command_lower.strip()):
            # Single letter answer
            return {
                'action': 'record_answer',
                'response': f"Recorded your answer: {command_lower.upper()}",
                'answer': command_lower.upper(),
                'question_number': current_question
            }
        
        else:
            return self._get_help_response(current_question)
    
    def _extract_answer_from_text(self, text: str) -> str:
        """Extract answer from voice command text"""
        text_lower = text.lower()
        
        # Look for letter answers
        for pattern in [r'option ([a-d])', r'answer is ([a-d])', r'([a-d])\b']:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(1).upper()
        
        # If no letter found, return the cleaned text
        return text.strip()
    
    def _get_help_response(self, current_question: int) -> Dict[str, Any]:
        """Get help response for unknown commands"""
        return {
            'action': 'show_help',
            'response': '''Available commands:
            - Say "repeat" to hear the question again
            - Say "repeat slower" for slower reading  
            - Say "ready to answer" to provide your answer
            - Say "next question" to move forward
            - Say "previous question" to go back
            - To answer, say "A", "B", "C", "D" or "option A", etc.''',
            'question_number': current_question
        }


class ExamAccessibilityHelper:
    def __init__(self, llm_client: AnythingLLMExamReader):
        """
        Exam accessibility helper for dyslexic and visually impaired students
        
        Args:
            llm_client: Configured AnythingLLM exam reader
        """
        self.llm_client = llm_client
        self.exam_questions = []
        self.current_question_index = 0
        self.exam_title = ""
        self.start_time = None
        self.user_answers = {}
        self.exam_state = "intro"  # intro, waiting_for_ready, reading_question, waiting_for_command, waiting_for_answer, exam_complete
        self.last_reading_speed = "normal"
    
    def load_exam(self, pdf_text: str, exam_title: str = "Exam") -> Dict[str, Any]:
        """
        Load exam from PDF text
        
        Args:
            pdf_text: Text extracted from exam PDF
            exam_title: Name of the exam
            
        Returns:
            Dict with exam loading status
        """
        try:
            self.exam_questions = self.llm_client.parse_exam_questions(pdf_text)
            self.exam_title = exam_title
            self.current_question_index = 0
            self.start_time = time.time()
            self.user_answers = {}
            self.exam_state = "intro"
            
            if self.exam_questions:
                return {
                    'success': True,
                    'message': f"Loaded {len(self.exam_questions)} questions from {exam_title}",
                    'total_questions': len(self.exam_questions),
                    'first_question': self.get_current_question_data(),
                    'intro_message': self._generate_intro_message()
                }
            else:
                return {
                    'success': False,
                    'error': 'No questions found in the PDF. Please check the format.'
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to load exam: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_intro_message(self) -> str:
        """Generate the introduction message for the exam"""
        return f"""
        Welcome to the {self.exam_title} accessibility interface.
        
        I am your exam reading assistant. I will read each question and its options clearly and slowly.
        
        You can use these voice commands:
        - Say "repeat" to hear the question again
        - Say "repeat slower" for slower reading
        - Say "ready to answer" when you want to give your answer
        - Say "next question" to move to the next question
        - Say "previous question" to go back
        
        This exam has {len(self.exam_questions)} questions total.
        
        Are you ready to begin the exam? Say "ready" when you want to start.
        """
    
    def get_current_question_data(self) -> Dict[str, Any]:
        """Get the current question data"""
        if not self.exam_questions or self.current_question_index >= len(self.exam_questions):
            return {
                'success': False,
                'error': 'No current question available'
            }
        
        question_data = self.exam_questions[self.current_question_index]
        return {
            'success': True,
            'question_data': question_data,
            'question_number': self.current_question_index + 1,
            'total_questions': len(self.exam_questions)
        }
    
    def get_current_question_for_reading(self, reading_speed: str = "normal") -> Dict[str, Any]:
        """Get the current question formatted for TTS reading"""
        question_result = self.get_current_question_data()
        
        if not question_result['success']:
            return question_result
        
        question_data = question_result['question_data']
        question_number = question_result['question_number']
        total_questions = question_result['total_questions']
        
        # Format for reading
        reading_text = self._format_question_for_reading(
            question_data, question_number, total_questions, reading_speed
        )
        
        return {
            'success': True,
            'reading_text': reading_text,
            'question_data': question_data,
            'question_number': question_number,
            'reading_speed': reading_speed
        }
    
    def _format_question_for_reading(self, question_data: Dict, question_number: int, total_questions: int, speed: str = "normal") -> str:
        """Format question for clear audio reading"""
        pace_indicators = {
            "slower": "Reading slowly. ",
            "slow": "Reading slowly. ",
            "normal": "",
            "fast": "Reading quickly. "
        }
        
        pace_text = pace_indicators.get(speed, "")
        
        reading_text = f"""
        {pace_text}Question {question_number} of {total_questions}.
        
        {question_data.get('question', '')}
        
        The options are:
        """
        
        options = question_data.get('options', [])
        for option in options:
            label = option.get('label', '')
            text = option.get('text', '')
            reading_text += f"\n{label} {text}"
            
            # Add pause between options for slower reading
            if speed in ["slower", "slow"]:
                reading_text += "."
        
        if speed in ["slower", "slow"]:
            reading_text += f"\n\nThis was question {question_number} of {total_questions}. What would you like to do?"
        else:
            reading_text += f"\n\nQuestion {question_number} of {total_questions}. What would you like to do?"
        
        return reading_text
    
    def process_voice_command(self, voice_command: str, context: str = None) -> Dict[str, Any]:
        """
        Process student voice command in the context of current exam state
        
        Args:
            voice_command: Command from speech-to-text
            context: Additional context about the current state
            
        Returns:
            Dict with response and any actions
        """
        if not self.exam_questions:
            return {
                'success': False,
                'error': 'No exam loaded. Please upload an exam PDF first.'
            }
        
        # Determine context from exam state if not provided
        if not context:
            context = self.exam_state
        
        result = self.llm_client.handle_voice_command(
            voice_command,
            self.current_question_index + 1,  # 1-based for user
            len(self.exam_questions),
            context
        )
        
        # Handle navigation and state changes
        return self._handle_command_result(result, voice_command)
    
    def _handle_command_result(self, result: Dict, original_command: str) -> Dict[str, Any]:
        """Handle the result of command processing and update state"""
        action = result.get('action')
        
        if action == 'next_question':
            if self.current_question_index < len(self.exam_questions) - 1:
                self.current_question_index += 1
                self.exam_state = "reading_question"
                result['question_data'] = self.get_current_question_for_reading()
            else:
                self.exam_state = "exam_complete"
                result['exam_complete'] = True
        
        elif action == 'previous_question':
            if self.current_question_index > 0:
                self.current_question_index -= 1
                self.exam_state = "reading_question"
                result['question_data'] = self.get_current_question_for_reading()
        
        elif action == 'repeat_question':
            reading_speed = result.get('reading_speed', 'normal')
            self.last_reading_speed = reading_speed
            self.exam_state = "waiting_for_command"
            result['question_data'] = self.get_current_question_for_reading(reading_speed)
        
        elif action == 'ready_to_answer':
            self.exam_state = "waiting_for_answer"
        
        elif action == 'record_answer':
            answer = result.get('answer', original_command)
            self.record_answer(self.current_question_index, answer)
            result['answer_recorded'] = True
            result['total_answered'] = len(self.user_answers)
            
            # Check if this is the last question
            if self.current_question_index >= len(self.exam_questions) - 1:
                self.exam_state = "exam_complete"
                result['is_last_question'] = True
                result['completion_message'] = self._generate_completion_message()
            else:
                # Ask if they want to move to next question
                result['prompt_next_question'] = True
                result['next_question_prompt'] = f"Answer recorded. Would you like to move to question {self.current_question_index + 2}? Say 'next question' to continue."
        
        elif action == 'end_of_exam':
            self.exam_state = "exam_complete"
            result['completion_message'] = self._generate_completion_message()
        
        # Add current state to all responses
        result['exam_state'] = self.exam_state
        result['progress'] = self.get_exam_status()
        
        return result
    
    def record_answer(self, question_index: int, answer: str) -> Dict[str, Any]:
        """Record user's answer for a question"""
        self.user_answers[question_index] = {
            'answer': answer.strip(),
            'timestamp': time.time(),
            'question_number': question_index + 1
        }
        
        logger.info(f"Recorded answer for question {question_index + 1}: {answer}")
        
        return {
            'success': True,
            'question_number': question_index + 1,
            'answer': answer,
            'total_answered': len(self.user_answers)
        }
    
    def _generate_completion_message(self) -> str:
        """Generate completion message when exam is finished"""
        answered = len(self.user_answers)
        total = len(self.exam_questions)
        
        return f"""
        You have completed the exam!
        
        You answered {answered} out of {total} questions.
        
        Would you like me to generate your answer sheet? 
        Say "yes" to generate it or "review" to review your answers first.
        """
    
    def generate_answer_sheet(self) -> Dict[str, Any]:
        """Generate final answer sheet"""
        completion_time = time.time()
        duration = completion_time - self.start_time if self.start_time else 0
        
        answer_sheet = {
            'exam_title': self.exam_title,
            'start_time': self.start_time,
            'completion_time': completion_time,
            'duration_minutes': round(duration / 60, 1),
            'total_questions': len(self.exam_questions),
            'answers_provided': len(self.user_answers),
            'completion_percentage': round(len(self.user_answers) / len(self.exam_questions) * 100, 1) if self.exam_questions else 0,
            'answers': []
        }
        
        for i, question in enumerate(self.exam_questions):
            answer_data = {
                'question_number': i + 1,
                'question_text': question.get('question', ''),
                'options': question.get('options', []),
                'user_answer': self.user_answers.get(i, {}).get('answer', 'No answer provided'),
                'answered_at': self.user_answers.get(i, {}).get('timestamp', None),
                'answer_status': 'answered' if i in self.user_answers else 'unanswered'
            }
            answer_sheet['answers'].append(answer_data)
        
        return answer_sheet
    
    def get_exam_status(self) -> Dict[str, Any]:
        """Get current exam status"""
        return {
            'exam_title': self.exam_title,
            'total_questions': len(self.exam_questions),
            'current_question': self.current_question_index + 1,
            'answers_provided': len(self.user_answers),
            'progress_percentage': round((self.current_question_index + 1) / len(self.exam_questions) * 100, 1) if self.exam_questions else 0,
            'completion_percentage': round(len(self.user_answers) / len(self.exam_questions) * 100, 1) if self.exam_questions else 0,
            'elapsed_time_minutes': round((time.time() - self.start_time) / 60, 1) if self.start_time else 0,
            'exam_state': self.exam_state
        }
    
    def start_exam(self) -> Dict[str, Any]:
        """Start the exam after intro"""
        if not self.exam_questions:
            return {
                'success': False,
                'error': 'No exam loaded'
            }
        
        self.exam_state = "reading_question"
        self.current_question_index = 0
        
        return {
            'success': True,
            'message': 'Starting exam. Reading first question.',
            'question_data': self.get_current_question_for_reading(),
            'exam_state': self.exam_state
        }