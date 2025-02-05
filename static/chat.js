let ws;

function connect() {
    ws = new WebSocket(`${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`);
    
    ws.onopen = () => {
        console.log('Connected to WebSocket');
        appendMessage('System', 'Connected to chat server');
        // Send init message
        ws.send(JSON.stringify({
            type: 'init_session',
            session_config: {
                model: 'gpt-4',
                modalities: ['text']
            }
        }));
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'response.text.delta') {
            appendMessage('Assistant', data.delta);
        } else if (data.type === 'error') {
            console.error('Server error:', data.error);
            appendMessage('System', 'Error: ' + data.error.message);
        } else if (data.type === 'connection.established') {
            console.log('Connection established:', data);
        } else if (data.type === 'session.created') {
            console.log('Session created:', data);
        }
    };

    ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        appendMessage('System', 'Disconnected from chat server');
        // Only attempt reconnect if not a normal closure
        if (event.code !== 1000) {
            setTimeout(connect, 3000);
        }
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        appendMessage('System', 'Connection error occurred');
    };
}

function appendMessage(sender, text) {
    const messages = document.getElementById('messages');
    const messageDiv = document.createElement('div');
    messageDiv.textContent = `${sender}: ${text}`;
    messages.appendChild(messageDiv);
    messages.scrollTop = messages.scrollHeight;
}

function sendMessage() {
    const input = document.getElementById('message-input');
    const message = input.value.trim();
    
    if (message && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'conversation.item.create',
            content: [{
                type: 'text',
                text: message
            }]
        }));
        appendMessage('You', message);
        input.value = '';
    }
}

// Connect when page loads
connect();

// Add enter key handler
document.getElementById('message-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});
