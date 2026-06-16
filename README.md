# Pasokon

A Python CLI application.

## Installation

### For Development

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install the package in editable mode with dev dependencies
pip install -e ".[dev]"
```

### For Users

```bash
pip install pasokon
```

## Usage

```bash
pasokon --help
```

### Examples

```bash
# Run the hello command
pasokon hello

# Provide a custom name
pasokon hello --name "World"
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black src/ tests/
```

### Linting

```bash
flake8 src/ tests/
mypy src/
```

## Project Structure

```
pasokon/
├── src/
│   └── pasokon/
│       ├── __init__.py
│       ├── cli.py          # CLI entry point
│       └── commands/       # Command modules
│           ├── __init__.py
│           └── hello.py
├── tests/
│   ├── __init__.py
│   └── test_cli.py
├── pyproject.toml          # Project configuration
├── README.md
└── .gitignore
```

## License

MIT License
