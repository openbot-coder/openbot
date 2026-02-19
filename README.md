# OpenBot

AI Bot with multi-channel support and self-evolution capabilities

## Overview

OpenBot is a command-line AI assistant that provides:

- **Multi-channel interaction** (Console Channel in MVP)
- **AI-powered conversation** using LangChain and OpenAI
- **Self-evolution capabilities** with code modification and approval system
- **Extensible architecture** for future integrations

## Installation

### Prerequisites

- Python 3.13+
- OpenAI API key (for OpenAI models)

### Install from source

```bash
# Clone the repository
git clone <repository-url>
cd openbot

# Install dependencies
pip install -e .

# Set up environment variables
export OPENAI_API_KEY=your-api-key
```

## Usage

### Basic usage

```bash
# Start OpenBot in REPL mode
openbot

# Start with custom configuration
openbot --config examples/config.json

# Specify channel (currently only "console" is supported)
openbot --channel console
```

### Example conversation

```
OpenBot Console Channel started. Type 'exit' to quit.
openbot> Hello, what can you do?

I'm OpenBot, an AI assistant with multi-channel support and self-evolution capabilities. I can:
- Answer questions on a wide range of topics
- Help with tasks and problem-solving
- Provide information and explanations
- Evolve over time through code modifications

How can I assist you today?

openbot> exit
OpenBot Console Channel stopped.
```

## Configuration

OpenBot uses JSON configuration files with the following structure:

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "api_key": "${OPENAI_API_KEY}",
    "temperature": 0.7
  },
  "channels": {
    "console": {
      "enabled": true,
      "prompt": "openbot> "
    }
  },
  "evolution": {
    "enabled": true,
    "auto_test": true,
    "require_approval": true
  }
}
```

### Environment Variables

OpenBot supports environment variable references in configuration files using the `${VAR_NAME}` syntax.

## Architecture

### Core Components

1. **ChatChannel Layer** - Handles input/output from different channels
2. **BotFlow** - Orchestrates the bot's behavior and manages sessions
3. **DeepAgents Core** - Provides AI capabilities using LangChain
4. **Evolution Controller** - Manages self-modification and code evolution

### Directory Structure

```
openbot/
├── src/openbot/          # Source code
│   ├── channels/         # Channel implementations
│   ├── botflow/          # Core bot logic
│   ├── agents/           # AI agent integration
│   ├── config.py         # Configuration management
│   └── main.py           # CLI entry point
├── examples/             # Example files
│   └── config.json       # Example configuration
├── pyproject.toml        # Project configuration
└── README.md             # This file
```

## Extensions

### Future Plans

- **Additional ChatChannels**: WebSocket, WeChat, DingTalk, etc.
- **Memory System**: User profiles, key facts, short/long-term memory
- **Skills System**: Extendable skill framework
- **MCP Integration**: Model Context Protocol support

## Security

### Code Self-modification Safety

1. **Change proposal**: Generates modification plan with diff
2. **User approval**: Requires user confirmation before execution
3. **Git commit**: Records all changes with commit history
4. **Rollback support**: Ability to revert to previous versions

### API Key Management

- API keys are loaded from environment variables
- No hardcoding of secrets in configuration files

## License

[MIT](LICENSE)
