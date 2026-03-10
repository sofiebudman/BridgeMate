// ================== Interview Page State ==================
const interviewState = {
    isRecording: false,
    mediaRecorder: null,
    audioChunks: [],
    inInterview: false,
};

const interviewElements = {
    statusMessage: document.getElementById('statusMessage'),
    recordingIndicator: document.getElementById('recordingIndicator'),
    recordingTime: document.getElementById('recordingTime'),
    recordInterviewBtn: document.getElementById('recordInterviewBtn'),
    interviewInput: document.getElementById('interviewInput'),
    interviewContent: document.getElementById('interviewContent'),
    backBtn: document.getElementById('backBtn'),
    endInterviewBtn: document.getElementById('endInterviewBtn'),
};

// ================== Markdown Rendering ==================
const markdownRenderer =
    typeof globalThis.markdownit === 'function'
        ? globalThis.markdownit({
              html: false,
              linkify: true,
              breaks: true,
          })
        : null;

function renderMessageContent(targetEl, text) {
    const content = typeof text === 'string' ? text : String(text ?? '');

    if (!markdownRenderer || !globalThis.DOMPurify) {
        targetEl.textContent = content;
        return;
    }

    try {
        const renderedHtml = markdownRenderer.render(content);
        targetEl.innerHTML = globalThis.DOMPurify.sanitize(renderedHtml, {
            USE_PROFILES: { html: true },
        });

        targetEl.querySelectorAll('a').forEach((linkEl) => {
            linkEl.setAttribute('target', '_blank');
            linkEl.setAttribute('rel', 'noopener noreferrer nofollow');
        });
    } catch {
        targetEl.textContent = content;
    }
}

// ================== Initialization ==================
document.addEventListener('DOMContentLoaded', async () => {
    setupInterviewEventListeners();
    await requestMicrophoneAccess();
    await initializeInterview();
});

function setupInterviewEventListeners() {
    interviewElements.recordInterviewBtn.addEventListener('click', toggleInterviewRecording);
    interviewElements.endInterviewBtn.addEventListener('click', endInterview);
}

async function requestMicrophoneAccess() {
    try {
        await navigator.mediaDevices.getUserMedia({ audio: true });
        interviewElements.recordInterviewBtn.disabled = false;
    } catch (error) {
        showStatus('Microphone access denied. Speech input will not be available.', 'error');
        interviewElements.recordInterviewBtn.disabled = true;
    }
}

// ================== Interview Flow ==================
async function initializeInterview() {
    const openingQuestion = sessionStorage.getItem('interviewOpeningQuestion');
    
    if (openingQuestion) {
        clearEmptyState();
        addMessage(openingQuestion, 'bot', 'Interviewer');
        interviewState.inInterview = true;
    } else {
        showStatus('Error: Interview not properly initialized. Redirecting...', 'error');
        setTimeout(() => {
            window.location.href = '/chat';
        }, 2000);
    }
}

function clearEmptyState() {
    const content = interviewElements.interviewContent;
    if (content.querySelector('.empty-state')) {
        content.innerHTML = '';
    }
}

function addMessage(text, role, label) {
    clearEmptyState();
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role === 'bot' ? 'bot-message' : 'user-message'}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    renderMessageContent(contentDiv, text);

    messageDiv.appendChild(contentDiv);
    interviewElements.interviewContent.appendChild(messageDiv);
    
    // Auto-scroll to bottom
    setTimeout(() => {
        interviewElements.interviewContent.scrollTop = interviewElements.interviewContent.scrollHeight;
    }, 0);
}
async function playTextToSpeech(text) {
    try {
        const ctx = getUserContext();
        const response = await apiFetch('/api/text-to-speech', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: text,
                userLanguage: ctx.userLanguage,
                country: ctx.userCountry,
            }),
        });

        if (!response.ok) return;
    
        const data = await response.json();
        
        console.log("data", data)
        const binaryString = atob(data.audio);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        
        // create a Blob using the mime type reported by the server (format is usually "mp3")
        const mimeType = data.format ? `audio/${data.format}` : 'audio/mp3';
        const blob = new Blob([bytes], { type: mimeType });
        state.lastAudioBlob = blob;
        elements.playBtn.disabled = false;
    
        const url = URL.createObjectURL(blob);
        elements.audioPlayer.src = url;
    
        elements.audioPlayer.play();
       
    } catch (error) {
        console.error('TTS Error:', error);
    }
}
// ================== Recording ==================
async function toggleInterviewRecording() {
    if (interviewState.isRecording) {
        stopInterviewRecording();
    } else {
        startInterviewRecording();
    }
}

async function startInterviewRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        interviewState.mediaRecorder = new MediaRecorder(stream);
        interviewState.audioChunks = [];
        interviewState.isRecording = true;

        interviewElements.recordInterviewBtn.classList.add('recording');
        setBtnLabel(interviewElements.recordInterviewBtn, 'Stop');
        interviewElements.recordingIndicator.classList.add('show');

        let recordingSeconds = 0;
        const recordingInterval = setInterval(() => {
            recordingSeconds++;
            const minutes = Math.floor(recordingSeconds / 60);
            const seconds = recordingSeconds % 60;
            interviewElements.recordingTime.textContent = `${minutes.toString().padStart(2, '0')}:${seconds
                .toString()
                .padStart(2, '0')}`;
        }, 1000);

        interviewState.mediaRecorder.ondataavailable = (e) => {
            interviewState.audioChunks.push(e.data);
        };

        interviewState.mediaRecorder.onstop = async () => {
            clearInterval(recordingInterval);
            interviewElements.recordingIndicator.classList.remove('show');
            interviewElements.recordingTime.textContent = '00:00';

            const audioBlob = new Blob(interviewState.audioChunks, { type: 'audio/wav' });
            await transcribeInterviewAudio(audioBlob);

            stream.getTracks().forEach((track) => track.stop());
        };

        interviewState.mediaRecorder.start();
    } catch (error) {
        showStatus('Error accessing microphone: ' + error.message, 'error');
    }
}

function stopInterviewRecording() {
    if (interviewState.mediaRecorder && interviewState.isRecording) {
        interviewState.mediaRecorder.stop();
        interviewState.isRecording = false;
        interviewElements.recordInterviewBtn.classList.remove('recording');
        setBtnLabel(interviewElements.recordInterviewBtn, 'Record Answer');
    }
}

function setBtnLabel(btn, label) {
    let span = btn.querySelector('.btn-label');
    if (!span) {
        span = document.createElement('span');
        span.className = 'btn-label';
        [...btn.childNodes].forEach(node => {
            if (node.nodeType === Node.TEXT_NODE) btn.removeChild(node);
        });
        btn.appendChild(span);
    }
    span.textContent = label;
}

async function transcribeInterviewAudio(audioBlob) {
    try {
        showStatus('Transcribing...', 'info');
        const formData = new FormData();
        formData.append('audio', audioBlob, 'answer.wav');

        const API_BASE = window.location.origin;
        const response = await fetch(`${API_BASE}/api/speech-to-text`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error);
        }

        const data = await response.json();
        interviewElements.interviewInput.value = data.text;
        showStatus('Answer transcribed! Click submit to continue.', 'success');
    } catch (error) {
        showStatus('Transcription error: ' + error.message, 'error');
    }
}

// ================== Submit Answer ==================
async function submitInterviewAnswer() {
    const answer = interviewElements.interviewInput.value.trim();
    if (!answer) {
        showStatus('Please provide an answer', 'error');
        return;
    }

    addMessage(answer, 'user', 'You');
    interviewElements.interviewInput.value = '';

    try {
        showStatus('Submitting answer...', 'info');
        
        const API_BASE = window.location.origin;
        const response = await fetch(`${API_BASE}/api/interview/respond`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ response: answer }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error);
        }

        const data = await response.json();
        addMessage(data.message, 'bot', 'Interviewer');
        await playTextToSpeech(data.message);
        showStatus('', '');
    } catch (error) {
        showStatus('Error: ' + error.message, 'error');
    }
}

// ================== End Interview ==================
async function endInterview() {
    if (!confirm('Are you sure you want to end the interview?')) {
        return;
    }

    try {
        showStatus('Ending interview...', 'success');

        const API_BASE = window.location.origin;
        const response = await fetch(`${API_BASE}/api/interview/end`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error);
        }

        const data = await response.json();
        addMessage('Interview Complete! Here is your feedback:\n\n' + data.feedback, 'bot', 'Interviewer');
        await playTextToSpeech(data.feedback)
        interviewState.inInterview = false;
        interviewElements.recordInterviewBtn.disabled = true;
        interviewElements.endInterviewBtn.disabled = true;

        showStatus('Returning to chat in 3 seconds...', 'success');
        
        setTimeout(() => {
            // Get user context to return to chat with preserved params
            const userContext = {
                userName: localStorage.getItem('userName') || 'User',
                userLanguage: localStorage.getItem('userLanguage') || 'en',
                userCountry: localStorage.getItem('userCountry') || 'US',
            };
            const lang = userContext.userLanguage;
            window.location.href = `/chat?lang=${lang}&name=${encodeURIComponent(userContext.userName)}&country=${userContext.userCountry}`;
        }, 3000);
    } catch (error) {
        showStatus('Error ending interview: ' + error.message, 'error');
    }
}

// ================== UI Helpers ==================
function showStatus(message, type) {
    const statusEl = interviewElements.statusMessage;
    if (!message) {
        statusEl.classList.remove('show');
        return;
    }
    
    statusEl.textContent = message;
    statusEl.className = `status-message show ${type}`;
}

// Add submit functionality to interface
document.addEventListener('DOMContentLoaded', () => {
    // After interview.html loads, add submit button listener
    const submitBtn = document.getElementById('submitBtn');
    if (submitBtn) {
        submitBtn.addEventListener('click', submitInterviewAnswer);
        // Ensure button has proper label
        if (!submitBtn.querySelector('.btn-label')) {
            const label = submitBtn.textContent.trim();
            submitBtn.textContent = '';
            const span = document.createElement('span');
            span.className = 'btn-label';
            span.textContent = label;
            submitBtn.appendChild(span);
        }
    }
});
