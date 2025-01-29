let ws;

function connect() {
    ws = new WebSocket(`${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`);
    
    ws.onopen = () => {
        console.log('Connected to WebSocket');
        appendMessage('System', 'Connected to chat server');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'message') {
            appendMessage(data.sender, data.text);
        }
    };

    ws.onclose = () => {
        console.log('Disconnected from WebSocket');
        appendMessage('System', 'Disconnected from chat server');
        // Attempt to reconnect
        setTimeout(connect, 1000);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        appendMessage('System', 'Error: ' + error.message);
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
            type: 'message',
            text: message
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
