const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const axios = require('axios');

// Backend configuration
const BACKEND_URL = 'http://127.0.0.1:5000';

let mainWindow;
let backendHealthy = false;

// Check backend health
async function checkBackendHealth() {
    try {
        const response = await axios.get(`${BACKEND_URL}/api/health`);
        backendHealthy = response.data.status === 'healthy';
        return backendHealthy;
    } catch (error) {
        console.error('Backend health check failed:', error.message);
        backendHealthy = false;
        return false;
    }
}

function createWindow() {
    // Create the browser window
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
            enableRemoteModule: true
        },
        icon: path.join(__dirname, 'assets/icon.png'),
        show: false,
        titleBarStyle: 'default'
    });

    // Load the app
    mainWindow.loadFile('renderer/pipeline.html');

    // Show window when ready
    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
        
        // Check backend health periodically
        setInterval(checkBackendHealth, 5000);
        checkBackendHealth();
    });

    // Open DevTools in development
    if (process.argv.includes('--dev')) {
        mainWindow.webContents.openDevTools();
    }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

// App event handlers
app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});

// IPC handlers for frontend-backend communication
ipcMain.handle('backend-health', async () => {
    return await checkBackendHealth();
});

ipcMain.handle('api-request', async (event, method, endpoint, data) => {
    try {
        const config = {
            method: method.toLowerCase(),
            url: `${BACKEND_URL}${endpoint}`,
            withCredentials: true,
        };

        if (data) {
            if (method.toLowerCase() === 'get') {
                config.params = data;
            } else {
                config.data = data;
            }
        }

        const response = await axios(config);
        return { success: true, data: response.data };
    } catch (error) {
        console.error('API request failed:', error);
        return { 
            success: false, 
            error: error.response?.data?.error || error.message 
        };
    }
});

ipcMain.handle('upload-file', async (event, filePath, options = {}) => {
    try {
        const FormData = require('form-data');
        const fs = require('fs');
        
        const form = new FormData();
        form.append('file', fs.createReadStream(filePath));
        
        // Add options
        if (options.use_ocr !== undefined) {
            form.append('use_ocr', options.use_ocr.toString());
        }
        if (options.extract_questions !== undefined) {
            form.append('extract_questions', options.extract_questions.toString());
        }

        const response = await axios.post(`${BACKEND_URL}/api/document/upload`, form, {
            headers: {
                ...form.getHeaders(),
            },
            withCredentials: true,
        });

        console.log('Upload response:', response.data);
        console.log('Response keys:', Object.keys(response.data));
        
        // Check if auto start audio was generated
        if (response.data.start_audio) {
            console.log('Auto start audio generated:', response.data.start_audio);
            // Send auto audio info to renderer
            mainWindow.webContents.send('auto-start-audio-ready', {
                audio_file: response.data.start_audio,
                message: response.data.message || 'Exam instructions ready to play'
            });
            console.log('Sent auto-start-audio-ready IPC message to renderer');
        } else {
            console.log('No start_audio found in response');
            if (response.data.agentic_workflow) {
                console.log('Agentic workflow result:', response.data.agentic_workflow);
            }
        }

        return { success: true, data: response.data };
    } catch (error) {
        console.error('File upload failed:', error);
        return { 
            success: false, 
            error: error.response?.data?.error || error.message 
        };
    }
});

ipcMain.handle('select-file', async () => {
    try {
        const result = await dialog.showOpenDialog(mainWindow, {
            properties: ['openFile'],
            filters: [
                { name: 'PDF Files', extensions: ['pdf'] },
                { name: 'All Files', extensions: ['*'] }
            ]
        });

        if (result.canceled) {
            return { success: false, cancelled: true };
        }

        return { success: true, filePath: result.filePaths[0] };
    } catch (error) {
        console.error('File selection failed:', error);
        return { success: false, error: error.message };
    }
});

// Handle app errors
process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});