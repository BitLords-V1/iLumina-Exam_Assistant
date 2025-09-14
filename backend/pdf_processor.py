"""
PDF Processing Module
Handles PDF text extraction functionality (OCR disabled to avoid SciPy conflicts)
"""

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("Warning: PyMuPDF not available. Install with: pip install PyMuPDF")

import os
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class PDFProcessor:
    def __init__(self):
        """Initialize PDF processor (OCR disabled to avoid SciPy import issues)"""
        self.pymupdf_available = PYMUPDF_AVAILABLE
        
        if PYMUPDF_AVAILABLE:
            try:
                # Test PyMuPDF functionality - check if it has the required methods
                if hasattr(fitz, 'open'):
                    # Test with empty document
                    test_doc = fitz.open()
                    test_doc.close()
                    logger.info("PDF processor initialized successfully (OCR disabled)")
                else:
                    # Try alternative initialization
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                        tmp.write(b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000074 00000 n \n0000000120 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n179\n%%EOF')
                        tmp.flush()
                        test_doc = fitz.Document(tmp.name)
                        test_doc.close()
                    os.unlink(tmp.name)
                    logger.info("PDF processor initialized with Document method (OCR disabled)")
                self.ocr_reader = None  # OCR disabled to avoid SciPy conflicts
            except Exception as e:
                logger.error(f"Failed to initialize PDF processor: {e}")
                self.pymupdf_available = False
        else:
            logger.warning("PDF processor initialized in fallback mode - PyMuPDF not available")
            self.ocr_reader = None
    
    def extract_text_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract text from PDF using PyMuPDF and OCR fallback
        
        Args:
            pdf_path (str): Path to the PDF file
            
        Returns:
            Dict containing extracted text and metadata
        """
        result = {
            'success': False,
            'text': '',
            'pages': [],
            'total_pages': 0,
            'method': 'none',
            'error': None
        }
        
        if not self.pymupdf_available:
            result['error'] = "PyMuPDF not available. Please install with: pip install PyMuPDF"
            return result
        
        try:
            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
            # Open PDF - try different methods based on PyMuPDF version
            try:
                if hasattr(fitz, 'open'):
                    doc = fitz.open(pdf_path)
                else:
                    doc = fitz.Document(pdf_path)
            except Exception as open_error:
                # Fallback method
                try:
                    doc = fitz.Document(pdf_path)
                except Exception as fallback_error:
                    raise Exception(f"Could not open PDF with either method: {open_error}, {fallback_error}")
            result['total_pages'] = len(doc)
            
            all_text = []
            pages_info = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # Try text extraction first
                page_text = page.get_text()
                page_info = {
                    'page_number': page_num + 1,
                    'text': page_text,
                    'method': 'text_extraction',
                    'char_count': len(page_text)
                }
                
                # If no text found, note that OCR is disabled
                if not page_text.strip():
                    page_info['text'] = f"[Page {page_num + 1}: No extractable text found - OCR disabled to avoid SciPy conflicts]"
                    page_info['method'] = 'no_text_found'
                    page_info['char_count'] = len(page_info['text'])
                    logger.info(f"No text found on page {page_num + 1} - OCR disabled")
                
                all_text.append(page_info['text'])
                pages_info.append(page_info)
            
            doc.close()
            
            result.update({
                'success': True,
                'text': '\n\n'.join(all_text),
                'pages': pages_info,
                'method': 'text_extraction_only'
            })
            
            logger.info(f"Successfully processed PDF: {len(all_text)} pages, {len(result['text'])} characters")
            
        except Exception as e:
            error_msg = f"PDF processing failed: {str(e)}"
            logger.error(error_msg)
            result['error'] = error_msg
        
        return result
    
    def validate_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Validate PDF file
        
        Args:
            pdf_path (str): Path to the PDF file
            
        Returns:
            Dict containing validation results
        """
        result = {
            'valid': False,
            'error': None,
            'file_size': 0,
            'pages': 0
        }
        
        try:
            if not os.path.exists(pdf_path):
                result['error'] = "File does not exist"
                return result
            
            result['file_size'] = os.path.getsize(pdf_path)
            
            # Try to open PDF
            try:
                if hasattr(fitz, 'open'):
                    doc = fitz.open(pdf_path)
                else:
                    doc = fitz.Document(pdf_path)
            except Exception as open_error:
                try:
                    doc = fitz.Document(pdf_path)
                except Exception as fallback_error:
                    raise Exception(f"Could not open PDF: {open_error}, {fallback_error}")
            
            result['pages'] = len(doc)
            doc.close()
            
            result['valid'] = True
            
        except Exception as e:
            result['error'] = f"PDF validation failed: {str(e)}"
        
        return result
    
    def extract_questions(self, text: str) -> List[str]:
        """
        Extract questions from text (simple implementation)
        
        Args:
            text (str): Input text
            
        Returns:
            List of questions found in text
        """
        if not text or not text.strip():
            return []
        
        questions = []
        sentences = text.split('.')
        
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and '?' in sentence:
                # Split by question marks and clean up
                question_parts = sentence.split('?')
                for part in question_parts[:-1]:  # Skip the last empty part
                    question = part.strip() + '?'
                    if len(question) > 5:  # Filter out very short questions
                        questions.append(question)
        
        # If no questions found, return the text chunked by sentences
        if not questions:
            return self.chunk_text_by_sentences(text, max_chunks=10)
        
        return questions[:20]  # Return max 20 questions
    
    def chunk_text_by_sentences(self, text: str, max_chunks: int = 10) -> List[str]:
        """
        Chunk text into sentences for processing
        
        Args:
            text (str): Input text
            max_chunks (int): Maximum number of chunks to return
            
        Returns:
            List of text chunks
        """
        if not text or not text.strip():
            return []
        
        # Split by periods and other sentence endings
        import re
        sentences = re.split(r'[.!?]+', text)
        
        chunks = []
        current_chunk = ""
        max_chunk_length = 500  # Characters per chunk
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # If adding this sentence would make chunk too long, start new chunk
            if len(current_chunk + sentence) > max_chunk_length and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += (" " if current_chunk else "") + sentence
        
        # Add the last chunk if it exists
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks[:max_chunks]