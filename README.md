# realtime-agent-cli

OpenAI Realtime API Relay Server / CLI in Python with dynamic function registration capabilities.

## Features

- Natural voice conversations with OpenAI's Realtime API
- Dynamic function registration and execution
- Built-in system command support
- Audio streaming and transcription
- Tool registry integration

## Getting Started

1. Set up environment variables:
```bash
export OPENAI_API_KEY="your-api-key"
```

2. Run the CLI:
```bash
python cli.py
```

3. Start talking! The agent can:
- Execute system commands ("What files are in this directory?")
- Read files ("Show me the contents of README.md")
- List directories ("List all Python files")
- And more through dynamic function registration

## Architecture

- `cli.py`: Main CLI interface with audio handling and event processing
- `session_manager.py`: Manages dynamic session configuration and function execution
- `relay_server.py`: WebSocket relay server for the Realtime API
- `tool_registry.py`: Registry for dynamic tool/function registration

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request
