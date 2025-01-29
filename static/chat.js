let ws = null;
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];

function connect() {
    ws = new WebSocket(`${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`);
    
    ws.onopen = () => {
        console.log('Connected to relay');
        // Send init session message
        ws.send(JSON.stringify({
            type: "init_session",
            session_config: {
                model: "gpt-4o-realtime-preview-2024-12-17",
                modalities: ["text", "audio"],
                instructions: "You are a helpful AI assistant.",
                voice: "alloy",
                input_audio_format: "pcm16",
                output_audio_format: "pcm16",
                input_audio_transcription: {
                    model: "whisper-1"
                },
                turn_detection: {
                    type: "server_vad",
                    threshold: 0.5,
                    prefix_padding_ms: 300,
                    silence_duration_ms: 500,
                    create_response: true
                }
            }
        }));
    };

    ws.onmessage = handleMessage;
    ws.onerror = (error) => console.error('WebSocket error:', error);
    ws.onclose = () => {
        console.log('Connection closed, attempting to reconnect...');
        setTimeout(connect, 1000);
    };
}

function handleMessage(event) {
    const data = JSON.parse(event.data);
    const messagesDiv = document.getElementById('chat-messages');
    
    switch(data.type) {
        case 'response.text.delta':
            let messageDiv = document.querySelector('.assistant-message:last-child');
            if (!messageDiv) {
                messageDiv = document.createElement('div');
                messageDiv.className = 'message assistant-message';
                messagesDiv.appendChild(messageDiv);
            }
            messageDiv.textContent += data.delta;
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            break;
            
        case 'response.audio.delta':
            // Handle audio playback
            const audio = new Audio(`data:audio/wav;base64,${data.delta}`);
            audio.play();
            break;
            
        case 'conversation.item.input_audio_transcription.completed':
            const userMessage = document.createElement('div');
            userMessage.className = 'message user-message';
            userMessage.textContent = data.transcript;
            messagesDiv.appendChild(userMessage);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            break;
    }
}

document.getElementById('send-button').onclick = () => {
    const input = document.getElementById('message-input');
    const message = input.value.trim();
    if (message) {
        ws.send(JSON.stringify({
            type: 'text',
            text: message
        }));
        
        const messagesDiv = document.getElementById('chat-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        messageDiv.textContent = message;
        messagesDiv.appendChild(messageDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        
        input.value = '';
    }
};

document.getElementById('voice-button').onclick = async () => {
    if (!isRecording) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            
            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };
            
            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks);
                const reader = new FileReader();
                reader.onloadend = () => {
                    const base64Audio = reader.result.split(',')[1];
                    ws.send(JSON.stringify({
                        type: 'input_audio_buffer.append',
                        audio: base64Audio
                    }));
                };
                reader.readAsDataURL(audioBlob);
                audioChunks = [];
            };
            
            mediaRecorder.start(100);
            isRecording = true;
            document.getElementById('voice-button').style.background = '#f44336';
        } catch (err) {
            console.error('Error accessing microphone:', err);
        }
    } else {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
        isRecording = false;
        document.getElementById('voice-button').style.background = '#4caf50';
    }
};

document.getElementById('message-input').onkeypress = (e) => {
    if (e.key === 'Enter') {
        document.getElementById('send-button').click();
    }
};

// Connect when page loads
connect();
