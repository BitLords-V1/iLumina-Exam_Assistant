// AI Learning Assistant - Frontend Application
const { ipcRenderer } = require('electron');

class AILearningAssistant {
    constructor() {
        this.currentScreen = 'loading';
        this.userData = null;
        this.currentDocument = null;
        this.questions = [];
        this.currentQuestionIndex = 0;
        this.isPlaying = false;
        this.isTranscribing = false;
        this.selectedFilePath = null;
        
        // Wait for DOM to load before initializing
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    init() {
        console.log('Initializing AI Learning Assistant...');
        this.setupEventListeners();
        this.checkBackendConnection();
    }

    setupEventListeners() {
        console.log('Setting up event listeners...');
        
        // IPC listeners for backend communication
        if (typeof ipcRenderer !== 'undefined') {
            // Listen for auto start audio when PDF upload completes
            ipcRenderer.on('auto-start-audio-ready', (event, audioData) => {
                console.log('🎵 RECEIVED auto-start-audio-ready IPC message:', audioData);
                this.handleAutoStartAudio(audioData);
            });
        } else {
            console.warn('ipcRenderer not available - running in non-electron environment');
        }
        
        // Welcome screen
        const getStartedBtn = document.getElementById('get-started-btn');
        if (getStartedBtn) {
            getStartedBtn.addEventListener('click', () => {
                console.log('Get started button clicked');
                this.showScreen('user');
            });
        } else {
            console.error('Get started button not found');
        }

        // User registration
        const userForm = document.getElementById('user-form');
        if (userForm) {
            userForm.addEventListener('submit', (e) => {
                e.preventDefault();
                console.log('User form submitted');
                this.handleUserRegistration();
            });
        }

        const backToWelcomeBtn = document.getElementById('back-to-welcome');
        if (backToWelcomeBtn) {
            backToWelcomeBtn.addEventListener('click', () => {
                console.log('Back to welcome clicked');
                this.showScreen('welcome');
            });
        }

        // File upload
        const selectFileBtn = document.getElementById('select-file-btn');
        if (selectFileBtn) {
            selectFileBtn.addEventListener('click', () => {
                console.log('Select file button clicked');
                this.selectFile();
            });
        }

        const processFileBtn = document.getElementById('process-file-btn');
        if (processFileBtn) {
            processFileBtn.addEventListener('click', () => {
                console.log('Process file button clicked');
                this.processDocument();
            });
        }

        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const section = e.currentTarget.getAttribute('data-section');
                this.showSection(section);
            });
        });

        // Question navigation
        document.getElementById('prev-question')?.addEventListener('click', () => {
            this.previousQuestion();
        });

        document.getElementById('next-question')?.addEventListener('click', () => {
            this.nextQuestion();
        });

        // Audio controls
        document.getElementById('speed-slider')?.addEventListener('input', (e) => {
            this.updateSpeed(e.target.value);
        });

        document.getElementById('play-btn')?.addEventListener('click', () => {
            this.playCurrentQuestion();
        });

        document.getElementById('pause-btn')?.addEventListener('click', () => {
            this.pauseAudio();
        });

        document.getElementById('stop-btn')?.addEventListener('click', () => {
            this.stopAudio();
        });

        document.getElementById('repeat-btn')?.addEventListener('click', () => {
            this.repeatCurrentQuestion();
        });

        // Transcription controls
        document.getElementById('start-transcription')?.addEventListener('click', () => {
            this.startTranscription();
        });

        document.getElementById('stop-transcription')?.addEventListener('click', () => {
            this.stopTranscription();
        });

        // Settings
        document.getElementById('settings-btn')?.addEventListener('click', () => {
            this.showSettings();
        });
    }

    async checkBackendConnection() {
        try {
            const healthy = await ipcRenderer.invoke('backend-health');
            
            if (healthy) {
                this.updateConnectionStatus(true);
                setTimeout(() => {
                    this.showScreen('welcome');
                }, 2000);
            } else {
                this.showConnectionError();
            }
        } catch (error) {
            console.error('Backend connection failed:', error);
            this.showConnectionError();
        }
    }

    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            if (connected) {
                statusElement.className = 'status-indicator';
                statusElement.innerHTML = '<i class="fas fa-wifi"></i><span>Connected</span>';
            } else {
                statusElement.className = 'status-indicator disconnected';
                statusElement.innerHTML = '<i class="fas fa-wifi"></i><span>Disconnected</span>';
            }
        }
    }

    showConnectionError() {
        const loadingText = document.querySelector('.loading-text');
        if (loadingText) {
            loadingText.textContent = 'Failed to connect to backend. Please ensure the Flask server is running.';
            loadingText.style.color = '#ff6b6b';
        }
    }

    showScreen(screenName) {
        // Hide all screens
        document.querySelectorAll('.screen').forEach(screen => {
            screen.classList.remove('active');
        });

        // Show target screen
        const targetScreen = document.getElementById(`${screenName}-screen`);
        if (targetScreen) {
            targetScreen.classList.add('active');
            this.currentScreen = screenName;
        }
    }

    async handleUserRegistration() {
        const formData = new FormData(document.getElementById('user-form'));
        const userData = {
            name: formData.get('name'),
            email: formData.get('email'),
            preferences: {
                learning_goal: formData.get('learning_goal'),
                auto_questions: formData.has('auto_questions'),
                enable_ocr: formData.has('enable_ocr'),
                voice_feedback: formData.has('voice_feedback')
            }
        };

        try {
            const result = await ipcRenderer.invoke('api-request', 'POST', '/api/user/register', userData);
            
            if (result.success) {
                this.userData = userData;
                document.getElementById('user-greeting').textContent = `Hello, ${userData.name}!`;
                this.showScreen('main');
            } else {
                alert('Registration failed: ' + result.error);
            }
        } catch (error) {
            console.error('Registration error:', error);
            alert('Registration failed. Please try again.');
        }
    }

    showSection(sectionName) {
        // Update navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-section="${sectionName}"]`)?.classList.add('active');

        // Update content
        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });
        document.getElementById(`${sectionName}-section`)?.classList.add('active');
    }

    async selectFile() {
        try {
            const result = await ipcRenderer.invoke('select-file');
            
            if (result.success && !result.cancelled) {
                this.selectedFilePath = result.filePath;
                const fileName = result.filePath.split('\\').pop();
                
                // Show upload options
                document.getElementById('upload-options').style.display = 'block';
                document.querySelector('.upload-content h3').textContent = `Selected: ${fileName}`;
                
                // Set default options based on user preferences
                if (this.userData?.preferences?.enable_ocr) {
                    document.getElementById('use-ocr-upload').checked = true;
                }
                if (this.userData?.preferences?.auto_questions) {
                    document.getElementById('extract-questions-upload').checked = true;
                }
            }
        } catch (error) {
            console.error('File selection error:', error);
            alert('Failed to select file. Please try again.');
        }
    }

    async processDocument() {
        if (!this.selectedFilePath) {
            alert('Please select a file first.');
            return;
        }

        const options = {
            use_ocr: document.getElementById('use-ocr-upload').checked,
            extract_questions: document.getElementById('extract-questions-upload').checked
        };

        try {
            // Show processing status
            document.getElementById('upload-options').style.display = 'none';
            document.getElementById('processing-status').style.display = 'block';

            // Upload file
            const uploadResult = await ipcRenderer.invoke('upload-file', this.selectedFilePath, options);
            
            if (!uploadResult.success) {
                throw new Error(uploadResult.error);
            }

            const fileId = uploadResult.data.file_id;
            
            // Poll for processing status
            await this.pollProcessingStatus(fileId);
            
        } catch (error) {
            console.error('Document processing error:', error);
            alert('Failed to process document: ' + error.message);
            this.resetUpload();
        }
    }

    async pollProcessingStatus(fileId) {
        const maxAttempts = 30; // 30 seconds
        let attempts = 0;

        const poll = async () => {
            try {
                const result = await ipcRenderer.invoke('api-request', 'GET', `/api/document/status/${fileId}`);
                
                if (result.success) {
                    const status = result.data.status;
                    
                    if (status === 'completed') {
                        await this.handleProcessingComplete(fileId);
                        return;
                    } else if (status === 'error') {
                        throw new Error(result.data.error);
                    }
                }

                attempts++;
                if (attempts < maxAttempts) {
                    setTimeout(poll, 1000);
                } else {
                    throw new Error('Processing timeout');
                }
            } catch (error) {
                throw error;
            }
        };

        await poll();
    }

    async handleProcessingComplete(fileId) {
        try {
            // Get questions
            const questionsResult = await ipcRenderer.invoke('api-request', 'GET', `/api/document/questions/${fileId}`);
            
            if (questionsResult.success) {
                this.questions = questionsResult.data.questions;
                this.currentQuestionIndex = 0;
                
                // Update UI
                document.getElementById('processing-status').style.display = 'none';
                document.getElementById('questions-count').textContent = this.questions.length;
                
                // Show success message
                alert(`Document processed successfully! Found ${this.questions.length} questions.`);
                
                // Switch to questions view
                this.showSection('questions');
                this.updateQuestionDisplay();
                this.enableAudioControls();
            }
        } catch (error) {
            throw error;
        }
    }

    resetUpload() {
        document.getElementById('upload-options').style.display = 'none';
        document.getElementById('processing-status').style.display = 'none';
        document.querySelector('.upload-content h3').textContent = 'Drop your PDF here or click to select';
        this.selectedFilePath = null;
    }

    updateQuestionDisplay() {
        if (this.questions.length === 0) return;

        const question = this.questions[this.currentQuestionIndex];
        document.getElementById('current-question').textContent = question;
        
        const counter = document.getElementById('question-counter');
        counter.textContent = `Question ${this.currentQuestionIndex + 1} of ${this.questions.length}`;
        
        // Update navigation buttons
        document.getElementById('prev-question').disabled = this.currentQuestionIndex === 0;
        document.getElementById('next-question').disabled = this.currentQuestionIndex === this.questions.length - 1;
    }

    previousQuestion() {
        if (this.currentQuestionIndex > 0) {
            this.currentQuestionIndex--;
            this.updateQuestionDisplay();
        }
    }

    nextQuestion() {
        if (this.currentQuestionIndex < this.questions.length - 1) {
            this.currentQuestionIndex++;
            this.updateQuestionDisplay();
        }
    }

    updateSpeed(value) {
        document.getElementById('speed-value').textContent = `${parseFloat(value).toFixed(1)}x`;
    }

    enableAudioControls() {
        document.getElementById('play-btn').disabled = false;
        document.getElementById('repeat-btn').disabled = false;
    }

    async playCurrentQuestion() {
        if (this.questions.length === 0) return;

        const question = this.questions[this.currentQuestionIndex];
        const speed = parseFloat(document.getElementById('speed-slider').value);

        try {
            this.updateAudioStatus('Generating audio...', 'info');
            
            const result = await ipcRenderer.invoke('api-request', 'POST', '/api/audio/generate', {
                text: question,
                speed: speed
            });

            if (result.success) {
                // In a real implementation, you would play the audio file
                // For now, simulate playback
                this.simulateAudioPlayback();
            } else {
                throw new Error(result.error);
            }
        } catch (error) {
            console.error('Audio playback error:', error);
            this.updateAudioStatus('Failed to play audio', 'error');
        }
    }

    simulateAudioPlayback() {
        this.isPlaying = true;
        this.updateAudioStatus('Playing...', 'playing');
        
        document.getElementById('play-btn').disabled = true;
        document.getElementById('pause-btn').disabled = false;
        document.getElementById('stop-btn').disabled = false;

        // Simulate playback duration
        setTimeout(() => {
            this.stopAudio();
        }, 5000);
    }

    pauseAudio() {
        this.isPlaying = false;
        this.updateAudioStatus('Paused', 'paused');
        
        document.getElementById('play-btn').disabled = false;
        document.getElementById('pause-btn').disabled = true;
        document.getElementById('stop-btn').disabled = false;
    }

    stopAudio() {
        this.isPlaying = false;
        this.updateAudioStatus('Ready to play', 'ready');
        
        document.getElementById('play-btn').disabled = false;
        document.getElementById('pause-btn').disabled = true;
        document.getElementById('stop-btn').disabled = true;
    }

    repeatCurrentQuestion() {
        this.stopAudio();
        setTimeout(() => {
            this.playCurrentQuestion();
        }, 100);
    }

    updateAudioStatus(message, type) {
        const statusElement = document.getElementById('audio-status');
        if (statusElement) {
            let icon = 'fas fa-info-circle';
            
            switch (type) {
                case 'playing':
                    icon = 'fas fa-play';
                    break;
                case 'paused':
                    icon = 'fas fa-pause';
                    break;
                case 'error':
                    icon = 'fas fa-exclamation-triangle';
                    break;
            }
            
            statusElement.innerHTML = `<i class="${icon}"></i><span>${message}</span>`;
        }
    }

    async startTranscription() {
        try {
            const result = await ipcRenderer.invoke('api-request', 'POST', '/api/transcription/start');
            
            if (result.success) {
                this.isTranscribing = true;
                document.getElementById('start-transcription').style.display = 'none';
                document.getElementById('stop-transcription').style.display = 'inline-flex';
                document.getElementById('transcription-status').innerHTML = 
                    '<i class="fas fa-microphone"></i><span>Listening...</span>';
                
                // Start getting transcription results
                this.pollTranscriptionResults();
            } else {
                throw new Error(result.error);
            }
        } catch (error) {
            console.error('Transcription start error:', error);
            alert('Failed to start transcription: ' + error.message);
        }
    }

    async stopTranscription() {
        // Prevent double-clicking
        if (!this.isTranscribing) {
            console.log('Stop transcription called but not transcribing');
            return;
        }
        
        // Immediately update UI to prevent double-clicks
        this.isTranscribing = false;
        const startBtn = document.getElementById('start-transcription');
        const stopBtn = document.getElementById('stop-transcription');
        const statusEl = document.getElementById('transcription-status');
        
        // Show processing state
        stopBtn.disabled = true;
        statusEl.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Processing...</span>';
        
        try {
            const result = await ipcRenderer.invoke('api-request', 'POST', '/api/transcription/stop');
            
            // Update UI to stopped state
            startBtn.style.display = 'inline-flex';
            stopBtn.style.display = 'none';
            stopBtn.disabled = false;
            statusEl.innerHTML = '<i class="fas fa-info-circle"></i><span>Ready to listen</span>';
            
            // Show transcription result if any
            if (result.transcription_result && result.transcription_result.text) {
                console.log('Transcription result:', result.transcription_result.text);
                statusEl.innerHTML = `<i class="fas fa-check"></i><span>Heard: "${result.transcription_result.text}"</span>`;
            }
            
            // Check for agentic workflow response with TTS audio
            if (result.agentic_response) {
                console.log('Agentic workflow response received:', result.agentic_response);
                
                const action = result.agentic_response.action || 'unknown';
                
                // Update status based on action type
                if (action === 'repeat_question' || action.includes('repeat')) {
                    statusEl.innerHTML = '<i class="fas fa-repeat"></i><span>Repeating audio...</span>';
                } else {
                    statusEl.innerHTML = '<i class="fas fa-robot"></i><span>AI is responding...</span>';
                }
                
                // Auto-play the TTS response if available
                if (result.response_audio) {
                    console.log('Auto-playing TTS response:', result.response_audio);
                    
                    // Show specific status for repeat commands
                    if (action === 'repeat_question' || action.includes('repeat')) {
                        statusEl.innerHTML = '<i class="fas fa-volume-up"></i><span>🔁 Repeating audio</span>';
                    } else {
                        statusEl.innerHTML = '<i class="fas fa-volume-up"></i><span>Playing response</span>';
                    }
                    
                    await this.playAudioFile(result.response_audio);
                    
                    // Update status after playback
                    statusEl.innerHTML = '<i class="fas fa-check-circle"></i><span>Audio complete - Ready for next command</span>';
                    
                } else if (result.agentic_response.message) {
                    // Show message if no audio
                    statusEl.innerHTML = `<i class="fas fa-comment"></i><span>${result.agentic_response.message}</span>`;
                }
                
                // Update exam status if question navigation occurred
                if (result.agentic_response.question_number) {
                    console.log('Question navigation:', result.agentic_response.question_number);
                    // Update question counter or other UI elements as needed
                }
            }
            
        } catch (error) {
            console.error('Transcription stop error:', error);
            // Reset UI on error
            startBtn.style.display = 'inline-flex';
            stopBtn.style.display = 'none';
            stopBtn.disabled = false;
            statusEl.innerHTML = '<i class="fas fa-exclamation-triangle"></i><span>Error stopping transcription</span>';
        }
    }

    async pollTranscriptionResults() {
        if (!this.isTranscribing) return;

        try {
            const result = await ipcRenderer.invoke('api-request', 'GET', '/api/transcription/result');
            
            if (result.success && result.data.text) {
                document.getElementById('transcription-text').value = result.data.text;
            }
        } catch (error) {
            console.error('Transcription polling error:', error);
        }

        // Continue polling if still transcribing
        if (this.isTranscribing) {
            setTimeout(() => this.pollTranscriptionResults(), 1000);
        }
    }

    async playAudioFile(audioFilePath) {
        // Play an audio file from the backend
        return new Promise((resolve, reject) => {
            try {
                console.log('Playing audio file:', audioFilePath);
                
                // Create audio element
                const audio = new Audio();
                
                // Set up event listeners
                audio.addEventListener('loadstart', () => {
                    console.log('Audio loading started');
                });
                
                audio.addEventListener('canplay', () => {
                    console.log('Audio can start playing');
                });
                
                audio.addEventListener('ended', () => {
                    console.log('Audio playback finished');
                    resolve();
                });
                
                audio.addEventListener('error', (e) => {
                    console.error('Audio playback error:', e);
                    reject(e);
                });
                
                // Set the audio source (backend will serve the file)
                const audioUrl = `http://127.0.0.1:5000/api/audio/${encodeURIComponent(audioFilePath)}`;
                audio.src = audioUrl;
                
                // Play the audio
                audio.play().catch(err => {
                    console.error('Play failed:', err);
                    reject(err);
                });
                
            } catch (error) {
                console.error('Audio playback setup error:', error);
                reject(error);
            }
        });
    }

    async handleAutoStartAudio(audioData) {
        try {
            console.log('Handling auto start audio:', audioData);
            
            // Update status to show that instructions are ready
            const statusEl = document.getElementById('transcription-status');
            if (statusEl) {
                statusEl.innerHTML = '<i class="fas fa-graduation-cap"></i><span>Exam instructions ready - playing automatically...</span>';
            }
            
            // Automatically play the start audio
            if (audioData.audio_file) {
                console.log('Auto-playing start instructions:', audioData.audio_file);
                await this.playAudioFile(audioData.audio_file);
                
                // Update status after audio finishes
                if (statusEl) {
                    statusEl.innerHTML = '<i class="fas fa-check-circle"></i><span>Instructions complete - exam ready! Say "repeat question one" to begin.</span>';
                }
            }
            
            // Show message in UI
            if (audioData.message) {
                console.log('Auto start message:', audioData.message);
                // You could show this in a notification or status area
            }
            
        } catch (error) {
            console.error('Auto start audio error:', error);
            const statusEl = document.getElementById('transcription-status');
            if (statusEl) {
                statusEl.innerHTML = '<i class="fas fa-exclamation-triangle"></i><span>Auto audio failed - exam still ready for voice commands</span>';
            }
        }
    }

    showSettings() {
        // Implement settings modal
        alert('Settings panel coming soon!');
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.aiApp = new AILearningAssistant();
});