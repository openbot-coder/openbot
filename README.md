# OpenBot

AI Bot with multi-channel support and self-evolution capabilities

## Overview

OpenBot is a command-line AI assistant that provides:

- **Multi-channel interaction** (Console Channel in MVP)
- **AI-powered conversation** using LangChain and OpenAI
- **Self-evolution capabilities** with code modification and approval system
- **Extensible architecture** for future integrations
- **Rich CLI experience** with syntax highlighting and streaming responses
- **Multi-model support** with automatic fallback strategy
- **MCP tool integration** for extended capabilities

## Installation

### Prerequisites

- Python 3.13+
- OpenAI API key (for OpenAI models)
- DeepSeek API key (optional, for DeepSeek models)

### Install from source

```bash
# Clone the repository
git clone <repository-url>
cd openbot

# Install dependencies
pip install -e ".[dev]"

# Set up environment variables
export OPENAI_API_KEY=your-api-key
export DEEPSEEK_API_KEY=your-deepseek-key  # Optional
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
╭──────────────────────────────────────────────────╮
│              OpenBot Console Channel              │
╰──────────────────────────────────────────────────╯

openbot> Hello, what can you do?

I'm OpenBot, an AI assistant with multi-channel support and self-evolution 
capabilities. I can:
- Answer questions on a wide range of topics
- Help with tasks and problem-solving
- Provide information and explanations
- Evolve over time through code modifications
- Use tools to interact with your system

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

**Required:**
- `OPENAI_API_KEY` - OpenAI API key

**Optional:**
- `DEEPSEEK_API_KEY` - DeepSeek API key
- `OPENBOT_CONFIG` - Path to custom configuration file

## Architecture

### Core Components

1. **ChatChannel Layer** - Handles input/output from different channels
2. **BotFlow** - Orchestrates the bot's behavior and manages sessions
3. **DeepAgents Core** - Provides AI capabilities using LangChain
4. **Evolution Controller** - Manages self-modification and code evolution
5. **Model Manager** - Multi-model support with auto fallback strategy
6. **Tools Manager** - MCP tool integration for extended capabilities
7. **CLI Interface** - Rich terminal UI with streaming responses

### Directory Structure

```
openbot/
├── src/openbot/          # Source code
│   ├── channels/         # Channel implementations
│   ├── botflow/          # Core bot logic
│   ├── agents/           # AI agent integration
│   │   ├── core.py       # OpenBotExecutor with lazy loading
│   │   ├── tools.py      # ToolsManager for MCP tools
│   │   ├── models.py     # ModelManager with auto strategy
│   │   └── cli.py        # Rich CLI interface
│   ├── config.py         # Configuration management
│   └── main.py           # CLI entry point
├── tests/                # Test suite
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── docs/                 # Documentation
│   ├── requirements/     # Requirements documents
│   └── design/           # Design documents
├── examples/             # Example files
│   └── config.json       # Example configuration
├── pyproject.toml        # Project configuration
└── README.md             # This file
```

## Documentation

### Requirements Documents

- [v0.2.0 Requirements Analysis](docs/requirements/v0.2.0_requirements_complete.md) - Complete functional and non-functional requirements

### Design Documents

- [v0.2.0 Detailed Design](docs/design/v0.2.0_detailed_design.md) - System architecture, module designs, and sequence diagrams

### API Documentation

Key classes and their responsibilities:

#### OpenBotExecutor (`agents/core.py`)
- Lazy initialization for fast startup
- Retry mechanism with exponential backoff
- Streaming response support
- Session management

#### ToolsManager (`agents/tools.py`)
- MCP tool server management
- Tool discovery and execution
- Built-in tools: get_current_time, remove_file, run_bash_command

#### ModelManager (`agents/models.py`)
- Multi-model support (OpenAI, DeepSeek)
- Auto strategy for automatic fallback
- Temperature and configuration management

#### AgentCLI (`agents/cli.py`)
- Rich terminal UI with syntax highlighting
- Streaming response display
- Background initialization
- Interactive REPL

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src/openbot --cov-report=html

# Run specific test file
pytest tests/unit/test_tools.py

# Run with verbose output
pytest -v
```

### Test Coverage

The project includes comprehensive test coverage:

- **Unit Tests**: 100% coverage for core modules
  - `test_core.py` - OpenBotExecutor tests
  - `test_tools.py` - ToolsManager and tool function tests
  - `test_models.py` - ModelManager tests
  - `test_cli.py` - AgentCLI tests

- **Integration Tests**: End-to-end workflow tests

### Test Structure

```
tests/
├── unit/
│   ├── test_core.py       # OpenBotExecutor tests
│   ├── test_tools.py      # ToolsManager tests (28 test cases)
│   ├── test_models.py     # ModelManager tests
│   └── test_cli.py        # AgentCLI tests
├── integration/
│   └── test_integration.py # Integration tests
└── conftest.py            # Shared fixtures
```

## Extensions

### Future Plans

- **Additional ChatChannels**: WebSocket, WeChat, DingTalk, etc.
- **Memory System**: User profiles, key facts, short/long-term memory
- **Skills System**: Extendable skill framework
- **MCP Integration**: Model Context Protocol support (Partially implemented in v0.2.0)
- **Plugin System**: Third-party plugin support

## Security

### Code Self-modification Safety

1. **Change proposal**: Generates modification plan with diff
2. **User approval**: Requires user confirmation before execution
3. **Git commit**: Records all changes with commit history
4. **Rollback support**: Ability to revert to previous versions

### API Key Management

- API keys are loaded from environment variables
- No hardcoding of secrets in configuration files
- Support for `.env` file loading

### Tool Execution Safety

- All tool executions are logged
- File system operations require explicit paths
- Bash commands are validated before execution

## Development

### Setting up Development Environment

```bash
# Clone the repository
git clone <repository-url>
cd openbot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check src/

# Run type checking
mypy src/
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Changelog

### v0.2.0 (Current)

- ✅ Multi-model support with auto fallback strategy
- ✅ MCP tool integration (get_current_time, remove_file, run_bash_command)
- ✅ Rich CLI with streaming responses and syntax highlighting
- ✅ Lazy loading for fast startup
- ✅ Retry mechanism with exponential backoff
- ✅ Comprehensive test suite (100% coverage)
- ✅ Complete documentation (requirements, design)

### v0.1.0 (Initial Release)

- Basic console channel
- OpenAI integration
- Configuration management
- Self-evolution framework

## License

[MIT](LICENSE)

## Acknowledgments

- Built with [LangChain](https://github.com/langchain-ai/langchain)
- CLI powered by [Rich](https://github.com/Textualize/rich) and [Prompt Toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit)
- Testing with [pytest](https://github.com/pytest-dev/pytest)
