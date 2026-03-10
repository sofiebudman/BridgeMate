//===== user info
// User context comes from localStorage (set by welcome form / index.html inline script)
function getUserContext() {
    return {
        userName: localStorage.getItem('userName') || 'User',
        userLanguage: localStorage.getItem('userLanguage') || 'en',
        userCountry: localStorage.getItem('userCountry') || 'US',
    };
}

// ================== STATE ==================
const state = {
    isRecording: false,
    mediaRecorder: null,
    audioChunks: [],
    currentLanguage: localStorage.getItem('userLanguage') || 'en',
    currentCountry: localStorage.getItem('userCountry') || 'US',
    lastAudioBlob: null,
    inInterviewMode: false,
    lastBotMessage: null,
    lastBotMessageEl: null,
    shouldAutoFollowMessages: true,
};

const AUTO_FOLLOW_THRESHOLD_PX = 48;

function isNearBottom(container) {
    const distanceFromBottom =
        container.scrollHeight - (container.scrollTop + container.clientHeight);
    return distanceFromBottom <= AUTO_FOLLOW_THRESHOLD_PX;
}

function updateAutoFollowState() {
    state.shouldAutoFollowMessages = isNearBottom(elements.messagesContainer);
}

function scrollMessagesToBottom() {
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
    state.shouldAutoFollowMessages = true;
}

// ================== TRANSLATIONS ==================



const API_BASE = (() => {
    if (window.location.protocol === 'file:') {
        setTimeout(() => {
            showStatus(
                'The app must be served over HTTP.  Please start the Flask server ' +
                    'and load the page through it (e.g. http://localhost:4000).',
                'error'
            );
        }, 0);
        return '';
    }
    return window.location.origin;
})();

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

async function apiFetch(path, opts) {
    if (!API_BASE) {
        throw new Error('no server');
    }
    return fetch(`${API_BASE}${path}`, opts);
}

// ================== DOM ELEMENTS ==================
const elements = {
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    recordBtn: document.getElementById('recordBtn'),
    playBtn: document.getElementById('playBtn'),
    interviewBtn: document.getElementById('interviewBtn'),
    clearBtn: document.getElementById('clearBtn'),
    resetBtn: document.getElementById('resetBtn'),
    messagesContainer: document.getElementById('messagesContainer'),
    audioPlayer: document.getElementById('audioPlayer'),
    statusMessage: document.getElementById('statusMessage'),
    recordingIndicator: document.getElementById('recordingIndicator'),
    recordingTime: document.getElementById('recordingTime'),
    // Interview elements
    interviewModal: document.getElementById('interviewModal'),
    interviewTopic: document.getElementById('interviewTopic'),
    interviewTopicSelect: document.getElementById('interviewTopicSelect'),
    startInterviewBtn: document.getElementById('startInterviewBtn'),
    cancelInterviewBtn: document.getElementById('cancelInterviewBtn'),
    closeModal: document.getElementById('closeModal'),
    chatInputArea: document.getElementById('chatInputArea'),
    interviewInputArea: document.getElementById('interviewInputArea'),
    interviewInput: document.getElementById('interviewInput'),
    submitAnswerBtn: document.getElementById('submitAnswerBtn'),
    recordInterviewBtn: document.getElementById('recordInterviewBtn'),
    endInterviewBtn: document.getElementById('endInterviewBtn'),
    interviewTopicDisplay: document.getElementById('interviewTopic'),
    interviewQuestion: document.getElementById('interviewQuestion'),
};

// ================== BUTTON LABEL HELPER ==================
// Updates only the text node inside a button, leaving any SVG icons intact.
function setBtnLabel(btn, label) {
    // Find or create a span that holds the text label
    let span = btn.querySelector('.btn-label');
    if (!span) {
        // First call: wrap existing text nodes into a span
        span = document.createElement('span');
        span.className = 'btn-label';
        // Move text nodes into the span
        [...btn.childNodes].forEach(node => {
            if (node.nodeType === Node.TEXT_NODE) btn.removeChild(node);
        });
        btn.appendChild(span);
    }
    span.textContent = label;
}

// ================== INITIALIZATION ==================
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    requestMicrophoneAccess();

    // Initialize state from localStorage (welcome form / chat URL params)
    const ctx = getUserContext();
    state.currentLanguage = ctx.userLanguage;
    state.currentCountry = ctx.userCountry;

    updateInitialMessage();
});

function setupEventListeners() {
    // Chat
    elements.sendBtn.addEventListener('click', sendMessage);
    elements.messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    // Recording
    elements.recordBtn.addEventListener('click', toggleRecording);
    elements.recordInterviewBtn.addEventListener('click', toggleInterviewRecording);
    elements.playBtn.addEventListener('click', playLastAudio);

    // Interview
    elements.interviewBtn.addEventListener('click', openInterviewModal);
    elements.startInterviewBtn.addEventListener('click', startInterview);
    elements.cancelInterviewBtn.addEventListener('click', closeInterviewModal);
    elements.closeModal.addEventListener('click', closeInterviewModal);
    elements.submitAnswerBtn.addEventListener('click', submitInterviewAnswer);
    elements.endInterviewBtn.addEventListener('click', endInterview);

    // Settings
    elements.clearBtn.addEventListener('click', clearChat);
    elements.resetBtn.addEventListener('click', resetToWelcome);

    // Modal close on background click
    elements.interviewModal.addEventListener('click', (e) => {
        if (e.target === elements.interviewModal) closeInterviewModal();
    });

    // Pause auto-follow when user scrolls up to read older messages.
    elements.messagesContainer.addEventListener('scroll', updateAutoFollowState);
}

// ================== MICROPHONE ACCESS ==================
async function requestMicrophoneAccess() {
    try {
        await navigator.mediaDevices.getUserMedia({ audio: true });
        elements.recordBtn.disabled = false;
        elements.recordInterviewBtn.disabled = false;
    } catch (error) {
        showStatus('Microphone access denied. Speech input will not be available.', 'error');
        elements.recordBtn.disabled = true;
        elements.recordInterviewBtn.disabled = true;
    }
}

// ================== LANGUAGE SWITCH ==================
async function translateLastMessage() {
    if (!state.lastBotMessage || !state.lastBotMessageEl) return;
    showStatus('Translating...', 'info');
    try {
        const ctx = getUserContext();
        const response = await apiFetch('/api/translate-last', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: state.lastBotMessage,
                userLanguage: ctx.userLanguage,
            }),
        });
        if (!response.ok) throw new Error('Translation failed');
        const data = await response.json();
        // renderMessageContent(state.lastBotMessageEl, data.message);
        // state.lastBotMessage = data.message;
        // showStatus('', '');
        addMessageToUI(data.message, 'bot');
        showStatus('', '');
        //playTextToSpeech(data.message);
    } catch (error) {
        showStatus('Translation failed: ' + error.message, 'error');
    }
}

// ================== CHAT FUNCTIONALITY ==================
async function sendMessage() {
    const message = elements.messageInput.value.trim();
    if (!message) return;

    addMessageToUI(message, 'user');
    elements.messageInput.value = '';
    elements.sendBtn.disabled = true;
    showStatus('Assistant is typing...', 'info');

    const botTextEl = addMessageToUI('', 'bot');
    let assistantMessage = '';

    // Get user context from welcome form (stored in localStorage)
    const ctx = getUserContext();

    try {
        const response = await apiFetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                country: ctx.userCountry,
                userName: ctx.userName,
                userLanguage: ctx.userLanguage,
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to get response');
        }

        if (!response.body) {
            throw new Error('Streaming not supported by this browser');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            let eventBoundary = buffer.indexOf('\n\n');
            while (eventBoundary !== -1) {
                const rawEvent = buffer.slice(0, eventBoundary);
                buffer = buffer.slice(eventBoundary + 2);

                const dataLine = rawEvent
                    .split('\n')
                    .find((line) => line.startsWith('data: '));

                if (dataLine) {
                    const payload = JSON.parse(dataLine.slice(6));

                    if (payload.type === 'token') {
                        assistantMessage += payload.content || '';
                        renderMessageContent(botTextEl, assistantMessage);
                        if (state.shouldAutoFollowMessages) {
                            scrollMessagesToBottom();
                        }
                    } else if (payload.type === 'done') {
                        assistantMessage = payload.message || assistantMessage;
                        renderMessageContent(botTextEl, assistantMessage);
                    } else if (payload.type === 'error') {
                        throw new Error(payload.error || 'Streaming failed');
                    }
                }

                eventBoundary = buffer.indexOf('\n\n');
            }
        }

        if (!assistantMessage.trim()) {
            throw new Error('No response');
        }

        state.lastBotMessage = assistantMessage;
        state.lastBotMessageEl = botTextEl;
        showStatus('', '');
        await showSuggestions(assistantMessage, botTextEl.closest('.message')); // ← add here

        if (assistantMessage) {
            // only speak responses that are reasonably short to avoid eating
            // through credits when the model returns long replies.
            //playTextToSpeech(assistantMessage);
          
        }
    } catch (error) {
        if (!botTextEl.textContent.trim()) {
            renderMessageContent(botTextEl, "Sorry, I don't understand what you're trying to say, please try again.");
        }
        showStatus('Error: ' + error.message, 'error');
    } finally {
        elements.sendBtn.disabled = false;
    }
}

async function showSuggestions(botMessage, messageDiv) {
    // Remove any previous suggestion bar
    document.querySelectorAll('.suggestions-bar').forEach(el => el.remove());

    try {
        const ctx = getUserContext();
        const response = await apiFetch('/api/suggestions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: botMessage,
                userLanguage: ctx.userLanguage,
            }),
        });
        if (!response.ok) return;
        const data = await response.json();
        console.log('[suggestions] API response:', data);
        if (!data.suggestions?.length) return;

        const bar = document.createElement('div');
        bar.className = 'suggestions-bar';

        data.suggestions.forEach(q => {
            const btn = document.createElement('button');
            btn.className = 'suggestion-btn';
            btn.textContent = q;
            btn.addEventListener('click', () => {
                elements.messageInput.value = q;
                sendMessage();
            });
            bar.appendChild(btn);
        });

        messageDiv.appendChild(bar);
        if (state.shouldAutoFollowMessages) {
            scrollMessagesToBottom();
        }
    } catch (err) {
        console.error('[suggestions] failed:', err);
    }
}

function addMessageToUI(message, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;

    const contentEl = document.createElement('div');
    contentEl.className = 'message-content';
    renderMessageContent(contentEl, message);
    messageDiv.appendChild(contentEl);

    elements.messagesContainer.appendChild(messageDiv);
    scrollMessagesToBottom();
 
    if (sender === 'bot') {
        state.lastBotMessage = message;
        state.lastBotMessageEl = contentEl;
    }

    return contentEl;
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

function playLastAudio() {
    if (state.lastBotMessage) {
        playTextToSpeech(state.lastBotMessage);
    }
}

// ================== RECORDING FUNCTIONALITY ==================
async function toggleRecording() {
    if (state.isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
}

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        state.mediaRecorder = new MediaRecorder(stream);
        state.audioChunks = [];
        state.isRecording = true;

        elements.recordBtn.classList.add('recording');
        setBtnLabel(elements.recordBtn, 'Stop');          // ← preserves SVG icon
        elements.recordingIndicator.style.display = 'flex';

        let recordingSeconds = 0;
        const recordingInterval = setInterval(() => {
            recordingSeconds++;
            const minutes = Math.floor(recordingSeconds / 60);
            const seconds = recordingSeconds % 60;
            elements.recordingTime.textContent = `${minutes.toString().padStart(2, '0')}:${seconds
                .toString()
                .padStart(2, '0')}`;
        }, 1000);

        state.mediaRecorder.ondataavailable = (e) => {
            state.audioChunks.push(e.data);
        };

        state.mediaRecorder.onstop = async () => {
            clearInterval(recordingInterval);
            elements.recordingIndicator.style.display = 'none';
            elements.recordingTime.textContent = '00:00';

            const audioBlob = new Blob(state.audioChunks, { type: 'audio/wav' });
            await transcribeAudio(audioBlob);

            stream.getTracks().forEach((track) => track.stop());
        };

        state.mediaRecorder.start();
    } catch (error) {
        showStatus('Error accessing microphone: ' + error.message, 'error');
    }
}

function stopRecording() {
    if (state.mediaRecorder && state.isRecording) {
        state.mediaRecorder.stop();
        state.isRecording = false;
        elements.recordBtn.classList.remove('recording');
        setBtnLabel(elements.recordBtn, 'Record');        // ← preserves SVG icon
    }
}

async function transcribeAudio(audioBlob) {
    if (!API_BASE) {
        showStatus('Unable to transcribe – application not served over HTTP.', 'error');
        return;
    }
    try {
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.wav');

        const response = await apiFetch('/api/speech-to-text', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error);
        }

        const data = await response.json();
        elements.messageInput.value = data.text;
        showStatus('Transcription complete!', 'success');
    } catch (error) {
        showStatus('Transcription error: ' + error.message, 'error');
    }
}

// ================== INTERVIEW FUNCTIONALITY ==================
function openInterviewModal() {
    elements.interviewModal.style.display = 'flex';
}

function closeInterviewModal() {
    elements.interviewModal.style.display = 'none';
}

async function startInterview() {
    const topic = (elements.interviewTopicSelect && elements.interviewTopicSelect.value) || 'consular';
    const ctx = getUserContext();

    try {
        closeInterviewModal();
        showStatus('Starting interview...', 'success');

        const response = await apiFetch('/api/interview/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                topic: topic,
                userLanguage: ctx.userLanguage,
                country: ctx.userCountry,
                userName: ctx.userName,
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error);
        }

        const data = await response.json();

        // Store interview info in sessionStorage for the interview page
        sessionStorage.setItem('interviewTopic', topic);
        sessionStorage.setItem('interviewStarted', 'true');
        sessionStorage.setItem('interviewOpeningQuestion', data.question);

        // Navigate to interview page
        window.location.href = `/interview?lang=${ctx.userLanguage}&name=${encodeURIComponent(ctx.userName)}&country=${ctx.userCountry}`;

    } catch (error) {
        showStatus('Error starting interview: ' + error.message, 'error');
    }
}

async function submitInterviewAnswer() {
    const answer = elements.interviewInput.value.trim();
    if (!answer) {
        showStatus('Please provide an answer', 'error');
        return;
    }

    addMessageToUI(answer, 'user');
    elements.interviewInput.value = '';

    try {
        const response = await apiFetch('/api/interview/respond', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ response: answer }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error);
        }

        const data = await response.json();
        addMessageToUI(data.message, 'bot');
        elements.interviewQuestion.textContent = data.message;

        await playTextToSpeech(data.message);
    } catch (error) {
        showStatus('Error: ' + error.message, 'error');
    }
}

async function toggleInterviewRecording() {
    if (state.isRecording) {
        stopInterviewRecording();
    } else {
        startInterviewRecording();
    }
}

async function startInterviewRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        state.mediaRecorder = new MediaRecorder(stream);
        state.audioChunks = [];
        state.isRecording = true;

        elements.recordInterviewBtn.classList.add('recording');
        setBtnLabel(elements.recordInterviewBtn, 'Stop');  // ← preserves SVG icon
        elements.recordingIndicator.style.display = 'flex';

        let recordingSeconds = 0;
        const recordingInterval = setInterval(() => {
            recordingSeconds++;
            const minutes = Math.floor(recordingSeconds / 60);
            const seconds = recordingSeconds % 60;
            elements.recordingTime.textContent = `${minutes.toString().padStart(2, '0')}:${seconds
                .toString()
                .padStart(2, '0')}`;
        }, 1000);

        state.mediaRecorder.ondataavailable = (e) => {
            state.audioChunks.push(e.data);
        };

        state.mediaRecorder.onstop = async () => {
            clearInterval(recordingInterval);
            elements.recordingIndicator.style.display = 'none';
            elements.recordingTime.textContent = '00:00';

            const audioBlob = new Blob(state.audioChunks, { type: 'audio/wav' });
            await transcribeInterviewAudio(audioBlob);

            stream.getTracks().forEach((track) => track.stop());
        };

        state.mediaRecorder.start();
    } catch (error) {
        showStatus('Error accessing microphone: ' + error.message, 'error');
    }
}

function stopInterviewRecording() {
    if (state.mediaRecorder && state.isRecording) {
        state.mediaRecorder.stop();
        state.isRecording = false;
        elements.recordInterviewBtn.classList.remove('recording');
        setBtnLabel(elements.recordInterviewBtn, 'Record Answer'); // ← preserves SVG icon
    }
}

async function transcribeInterviewAudio(audioBlob) {
    if (!API_BASE) {
        showStatus('Unable to transcribe – application not served over HTTP.', 'error');
        return;
    }
    try {
        const formData = new FormData();
        formData.append('audio', audioBlob, 'answer.wav');

        const response = await apiFetch('/api/speech-to-text', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error);
        }

        const data = await response.json();
        elements.interviewInput.value = data.text;
        showStatus('Answer transcribed!', 'success');

        // automatically submit the transcribed answer; since the text field is
        // disabled during interview we can't rely on the user clicking submit.
        if (state.inInterviewMode) {
            // wait for the interview answer submission to complete before
            // returning to the caller so errors can be surfaced if needed.
            await submitInterviewAnswer();
        }
    } catch (error) {
        showStatus('Transcription error: ' + error.message, 'error');
    }
}

async function endInterview() {
    try {
        showStatus('Ending interview...', 'success');

        const response = await apiFetch('/api/interview/end', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error);
        }

        const data = await response.json();

        addMessageToUI('Interview Complete! Here is your feedback:\n\n' + data.feedback, 'bot');
        playTextToSpeech(data.feedback);

        state.inInterviewMode = false;
        elements.interviewInputArea.style.display = 'none';
        elements.chatInputArea.style.display = 'block';

        // restore normal typing controls
        const interviewInputGroup = elements.interviewInput.closest('.input-group');
        if (interviewInputGroup) interviewInputGroup.style.display = '';
        elements.interviewInput.disabled = false;
        elements.submitAnswerBtn.disabled = false;
        elements.interviewInput.placeholder = 'Type your answer...';

        showStatus('Interview ended', 'success');
    } catch (error) {
        showStatus('Error: ' + error.message, 'error');
    }
}

// ================== UTILITY FUNCTIONS ==================
function clearChat() {
    if (confirm('Are you sure you want to clear the chat history?')) {
        elements.messagesContainer.innerHTML = '';
        apiFetch('/api/clear', { method: 'POST' }).catch(console.error);
        showStatus('Chat cleared', 'success');
    }
}

function resetToWelcome() {
    if (confirm('Are you sure you want to reset? You will be taken back to the welcome screen.')) {
        localStorage.removeItem('userName');
        localStorage.removeItem('userLanguage');
        localStorage.removeItem('userCountry');
        window.location.href = '/welcome';
    }
}

function showStatus(message, type = 'info') {
    elements.statusMessage.textContent = message;
    elements.statusMessage.className = `status-message ${type}`;
    elements.statusMessage.style.display = 'block';

    setTimeout(() => {
        elements.statusMessage.style.display = 'none';
    }, 4000);
}