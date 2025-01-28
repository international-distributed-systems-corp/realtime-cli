# OpenAI Realtime API Guide

A comprehensive guide to using OpenAI's Realtime API for real-time communication with GPT-4 models.

## Overview

The Realtime API enables real-time communication with GPT-4 models using WebRTC or WebSockets. It supports:

- Text and audio inputs/outputs
- Audio transcription
- Real-time streaming responses
- Function calling
- Voice selection
- Turn detection

## Getting Started

### 1. Create a Session Token

First, create an ephemeral session token:

```bash
curl -X POST https://api.openai.com/v1/realtime/sessions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-realtime-preview-2024-12-17",
    "modalities": ["audio", "text"],
    "instructions": "You are a helpful assistant."
  }'
```

The response includes a `client_secret` containing your ephemeral token.

### 2. Connect via WebSocket

Use the token to establish a WebSocket connection:

```javascript
const ws = new WebSocket('wss://realtime.openai.com/v1/chat');
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'session.update',
    session: {
      client_secret: 'ek_abc123'  // Your ephemeral token
    }
  }));
};
```

## Key Concepts

### Sessions

Sessions maintain the conversation state and configuration. Key settings include:

- `modalities`: Array of supported modalities (["text", "audio"])
- `instructions`: System instructions for the model
- `voice`: Voice selection (alloy, ash, ballad, coral, echo, sage, shimmer, verse)
- `input_audio_format`: Format for input audio (pcm16, g711_ulaw, g711_alaw)
- `output_audio_format`: Format for output audio
- `turn_detection`: Configuration for voice activity detection
- `tools`: Available functions/tools
- `temperature`: Sampling temperature (0.6-1.2)

### Turn Detection

Turn detection helps manage conversation flow:

```json
{
  "turn_detection": {
    "type": "server_vad",
    "threshold": 0.5,
    "prefix_padding_ms": 300,
    "silence_duration_ms": 500,
    "create_response": true
  }
}
```

### Audio Handling

For audio input/output:

1. Send audio chunks using `input_audio_buffer.append`
2. Commit the buffer with `input_audio_buffer.commit`
3. Receive audio responses in base64-encoded chunks

## Client Events

Key events you can send:

### Session Management
- `session.update`: Update session configuration
- `conversation.item.create`: Add items to conversation
- `conversation.item.delete`: Remove items
- `conversation.item.truncate`: Truncate audio responses

### Audio Control
- `input_audio_buffer.append`: Send audio data
- `input_audio_buffer.commit`: Commit audio buffer
- `input_audio_buffer.clear`: Clear audio buffer

### Response Control
- `response.create`: Generate a response
- `response.cancel`: Cancel in-progress response

## Server Events

Events you'll receive:

### Session Events
- `session.created`: Initial session creation
- `session.updated`: Configuration updates
- `error`: Error notifications

### Audio Events
- `input_audio_buffer.speech_started`: Speech detected
- `input_audio_buffer.speech_stopped`: Speech ended
- `input_audio_buffer.committed`: Buffer committed
- `input_audio_buffer.cleared`: Buffer cleared

### Response Events
- `response.created`: Response generation started
- `response.done`: Response completed
- `response.text.delta`: Text streaming updates
- `response.audio.delta`: Audio streaming updates
- `response.audio_transcript.delta`: Transcript updates

## Error Handling

Handle errors gracefully:

```javascript
ws.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'error') {
    console.error('Error:', data.error);
    // Handle specific error types
    switch(data.error.type) {
      case 'invalid_request_error':
        // Handle invalid requests
        break;
      case 'rate_limit_error':
        // Handle rate limits
        break;
    }
  }
});
```

## Best Practices

1. **Session Management**
   - Keep sessions short-lived
   - Use appropriate modalities
   - Set clear instructions

2. **Audio Handling**
   - Use appropriate audio formats
   - Handle audio chunks efficiently
   - Monitor VAD events

3. **Error Recovery**
   - Implement reconnection logic
   - Handle rate limits gracefully
   - Log errors for debugging

4. **Performance**
   - Monitor token usage
   - Optimize audio buffer sizes
   - Use appropriate sampling rates

## Rate Limits

Monitor rate limits via `rate_limits.updated` events:

```json
{
  "rate_limits": [
    {
      "name": "requests",
      "limit": 1000,
      "remaining": 999,
      "reset_seconds": 60
    },
    {
      "name": "tokens",
      "limit": 50000,
      "remaining": 49950,
      "reset_seconds": 60
    }
  ]
}
```

## Example Implementation

```javascript
class RealtimeClient {
  constructor(token) {
    this.ws = new WebSocket('wss://realtime.openai.com/v1/chat');
    this.setupEventHandlers();
  }

  setupEventHandlers() {
    this.ws.onopen = () => this.handleOpen();
    this.ws.onmessage = (event) => this.handleMessage(event);
    this.ws.onerror = (error) => this.handleError(error);
    this.ws.onclose = () => this.handleClose();
  }

  handleOpen() {
    // Initialize session
    this.send({
      type: 'session.update',
      session: {
        modalities: ['audio', 'text'],
        instructions: 'You are a helpful assistant.'
      }
    });
  }

  handleMessage(event) {
    const data = JSON.parse(event.data);
    switch(data.type) {
      case 'session.created':
        console.log('Session started');
        break;
      case 'response.text.delta':
        this.handleTextDelta(data);
        break;
      case 'response.audio.delta':
        this.handleAudioDelta(data);
        break;
      case 'error':
        this.handleError(data.error);
        break;
    }
  }

  send(data) {
    this.ws.send(JSON.stringify(data));
  }
}
```

## Troubleshooting

Common issues and solutions:

1. **Connection Failures**
   - Verify token validity
   - Check network connectivity
   - Ensure correct WebSocket URL

2. **Audio Issues**
   - Verify audio format matches configuration
   - Check sample rate and encoding
   - Monitor buffer sizes

3. **Rate Limits**
   - Implement backoff strategies
   - Monitor usage patterns
   - Optimize token usage

4. **Response Issues**
   - Check instruction clarity
   - Verify tool configurations
   - Monitor response sizes

## Additional Resources

- [OpenAI API Documentation](https://platform.openai.com/docs)
- [WebSocket API Reference](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [Audio Processing Guide](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)
