"""
PDF Processing Module
Handles PDF text extraction and OCR processing using easyocr
"""

import fitz  # PyMuPDF
import easyocr
import re
import numpy as np
from PIL import Image
import io
import logging

class PDFProcessor:
    def __init__(self):
        self.ocr_reader = None
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging for PDF processing"""
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def init_ocr(self, languages=['en']):
        """Initialize OCR reader (lazy loading)"""
        try:
            if self.ocr_reader is None:
                self.logger.info("Initializing EasyOCR...")
                self.ocr_reader = easyocr.Reader(languages, gpu=False)
                self.logger.info("EasyOCR initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize OCR: {e}")
            return False
    
    def extract_text_from_pdf(self, pdf_path, use_ocr=False):
        """
        Extract text from PDF file
        
        Args:
            pdf_path (str): Path to PDF file
            use_ocr (bool): Whether to use OCR for text extraction
            
        Returns:
            str: Extracted text content
        """
        try:
            doc = fitz.open(pdf_path)
            full_text = ""
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                
                # Try to extract text directly first
                text = page.get_text()
                
                # If no text found or OCR is forced, use OCR
                if (not text.strip() and use_ocr) or (use_ocr and len(text.strip()) < 50):
                    self.logger.info(f"Using OCR for page {page_num + 1}")
                    text = self._extract_text_with_ocr(page)
                
                if text.strip():
                    full_text += f"\n\n--- Page {page_num + 1} ---\n"
                    full_text += text
            
            doc.close()
            return full_text.strip()
            
        except Exception as e:
            self.logger.error(f"Error extracting text from PDF: {e}")
            return ""
    
    def _extract_text_with_ocr(self, page):
        """Extract text from PDF page using OCR"""
        try:
            # Initialize OCR if not already done
            if not self.init_ocr():
                return ""
            
            # Convert PDF page to image
            mat = fitz.Matrix(2.0, 2.0)  # Increase resolution
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            
            # Convert to PIL Image
            image = Image.open(io.BytesIO(img_data))
            img_array = np.array(image)
            
            # Perform OCR
            results = self.ocr_reader.readtext(img_array)
            
            # Extract text from results
            text_parts = []
            for (bbox, text, confidence) in results:
                if confidence > 0.5:  # Filter low confidence results
                    text_parts.append(text)
            
            return " ".join(text_parts)
            
        except Exception as e:
            self.logger.error(f"OCR processing failed: {e}")
            return ""
    
    def extract_questions(self, text):
        """
        Extract questions from text using various patterns
        
        Args:
            text (str): Input text to analyze
            
        Returns:
            list: List of extracted questions
        """
        questions = []
        
        # Pattern 1: Lines starting with "Question" followed by number/letter
        pattern1 = re.compile(r'^(?:Question|Q\.?)\s*(?:\d+|[a-zA-Z])[\.\)\:]\s*(.+?)(?=(?:Question|Q\.?|\n\n|\Z))', 
                             re.MULTILINE | re.DOTALL | re.IGNORECASE)
        
        matches1 = pattern1.findall(text)
        for match in matches1:
            clean_question = self._clean_question_text(match)
            if clean_question:
                questions.append(clean_question)
        
        # Pattern 2: Lines ending with question mark
        pattern2 = re.compile(r'([^.!?]*\?)', re.MULTILINE)
        matches2 = pattern2.findall(text)
        
        for match in matches2:
            clean_question = self._clean_question_text(match)
            if clean_question and len(clean_question.split()) > 3:  # Filter short fragments
                # Check if not already added
                if not any(clean_question.lower() in existing.lower() or 
                          existing.lower() in clean_question.lower() 
                          for existing in questions):
                    questions.append(clean_question)
        
        # Pattern 3: Common question starters
        question_starters = [
            r'\b(?:What|How|Why|When|Where|Who|Which|Can|Could|Would|Should|Do|Does|Did|Is|Are|Will|Have|Has)\b.*\?',
            r'\bExplain\b.*[\.?]',
            r'\bDescribe\b.*[\.?]',
            r'\bDiscuss\b.*[\.?]',
            r'\bAnalyze\b.*[\.?]',
            r'\bCompare\b.*[\.?]',
        ]
        
        for starter_pattern in question_starters:
            pattern = re.compile(starter_pattern, re.IGNORECASE | re.MULTILINE)
            matches = pattern.findall(text)
            
            for match in matches:
                clean_question = self._clean_question_text(match)
                if clean_question and len(clean_question.split()) > 4:
                    # Check if not already added
                    if not any(clean_question.lower() in existing.lower() or 
                              existing.lower() in clean_question.lower() 
                              for existing in questions):
                        questions.append(clean_question)
        
        # Remove duplicates and filter
        unique_questions = []
        for q in questions:
            if len(q.split()) >= 5 and len(q) <= 500:  # Reasonable length questions
                unique_questions.append(q)
        
        return unique_questions[:20]  # Limit to 20 questions
    
    def _clean_question_text(self, text):
        """Clean and format question text"""
        if not text:
            return ""
        
        # Remove excessive whitespace
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Remove page markers
        cleaned = re.sub(r'--- Page \d+ ---', '', cleaned)
        
        # Remove leading numbers/letters if they look like question numbering
        cleaned = re.sub(r'^\d+[\.\)]\s*', '', cleaned)
        cleaned = re.sub(r'^[a-zA-Z][\.\)]\s*', '', cleaned)
        
        # Ensure proper capitalization
        cleaned = cleaned.strip()
        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]
        
        # Ensure ends with question mark or period
        if cleaned and not cleaned.endswith(('?', '.')):
            if any(word in cleaned.lower() for word in ['what', 'how', 'why', 'when', 'where', 'who', 'which']):
                cleaned += '?'
            else:
                cleaned += '.'
        
        return cleaned
    
    def chunk_text_by_sentences(self, text, max_chunk_size=1000):
        """
        Split text into manageable chunks for TTS
        
        Args:
            text (str): Input text
            max_chunk_size (int): Maximum characters per chunk
            
        Returns:
            list: List of text chunks
        """
        # Split by sentences
        sentences = re.split(r'[.!?]+', text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # If adding this sentence would exceed limit, start new chunk
            if len(current_chunk) + len(sentence) > max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += ". " + sentence
                else:
                    current_chunk = sentence
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def get_pdf_info(self, pdf_path):
        """
        Get basic information about the PDF
        
        Args:
            pdf_path (str): Path to PDF file
            
        Returns:
            dict: PDF information
        """
        try:
            doc = fitz.open(pdf_path)
            info = {
                'title': doc.metadata.get('title', 'Unknown'),
                'author': doc.metadata.get('author', 'Unknown'),
                'subject': doc.metadata.get('subject', ''),
                'page_count': doc.page_count,
                'created': doc.metadata.get('creationDate', ''),
                'modified': doc.metadata.get('modDate', ''),
                'has_text': False
            }
            
            # Check if PDF has extractable text
            text_length = 0
            for page_num in range(min(3, doc.page_count)):  # Check first 3 pages
                page = doc[page_num]
                text = page.get_text()
                text_length += len(text.strip())
            
            info['has_text'] = text_length > 100
            doc.close()
            
            return info
            
        except Exception as e:
            self.logger.error(f"Error getting PDF info: {e}")
            return {}

# Example usage and testing
def test_pdf_processor():
    """Test function for PDF processor"""
    processor = PDFProcessor()
    
    # Test with a sample text
    sample_text = """
    Question 1: What is machine learning and how does it work?
    
    Machine learning is a subset of artificial intelligence that focuses on algorithms.
    
    Q2. Explain the difference between supervised and unsupervised learning?
    
    How do neural networks process information? This is an important concept.
    
    Describe the applications of deep learning in computer vision.
    """
    
    questions = processor.extract_questions(sample_text)
    print("Extracted questions:")
    for i, q in enumerate(questions, 1):
        print(f"{i}. {q}")

if __name__ == "__main__":
    test_pdf_processor()