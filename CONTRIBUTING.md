# Contributing to Crypto Perps Tracker

Thank you for your interest in contributing to Crypto Perps Tracker! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Adding New Exchanges](#adding-new-exchanges)
- [Reporting Issues](#reporting-issues)

## Development Setup

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Git

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/crypto-perps-tracker.git
   cd crypto-perps-tracker
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

### Running the Application

```bash
# Run the dashboard
python dashboard/app.py

# Run market analysis
python scripts/compare_all_exchanges.py
```

## Code Style

We follow Python best practices and PEP 8 guidelines with the following tools:

### Formatting

- **Black** for code formatting (line length: 120)
- **isort** for import sorting

```bash
# Format code
black src/ tests/ dashboard/

# Sort imports
isort src/ tests/ dashboard/
```

### Linting

- **flake8** for linting
- **mypy** for type checking

```bash
# Run linting
flake8 src/

# Run type checking
mypy src/ --ignore-missing-imports
```

### Pre-commit Hooks (Recommended)

Install pre-commit hooks to automatically check code before commits:

```bash
pip install pre-commit
pre-commit install
```

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=html

# Run specific test file
pytest tests/test_services/test_exchange_service.py -v

# Run tests matching a pattern
pytest tests/ -k "test_fetch" -v
```

### Writing Tests

- Place tests in the `tests/` directory, mirroring the `src/` structure
- Use pytest fixtures from `tests/conftest.py`
- Use mock data from `tests/fixtures/mock_data.py`
- Aim for 80%+ code coverage

Example test structure:
```python
"""Tests for ExchangeService"""

import pytest
from src.services.exchange import ExchangeService

class TestExchangeService:
    """Tests for ExchangeService"""

    @pytest.fixture
    def service(self, mock_cache, mock_client_factory):
        return ExchangeService(cache=mock_cache, client_factory=mock_client_factory)

    def test_fetch_all_markets_returns_list(self, service):
        results = service.fetch_all_markets()
        assert isinstance(results, list)
```

## Pull Request Process

1. **Fork the repository** and create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the code style guidelines

3. **Add tests** for new functionality

4. **Run the test suite** to ensure all tests pass:
   ```bash
   pytest tests/ -v
   ```

5. **Update documentation** if needed

6. **Commit your changes** with a descriptive message:
   ```bash
   git commit -m "Add feature: description of changes"
   ```

7. **Push to your fork** and create a Pull Request

### PR Requirements

- All tests must pass
- Code must be formatted with Black
- No new linting errors
- Documentation updated if applicable
- Descriptive PR title and description

## Adding New Exchanges

To add support for a new cryptocurrency exchange:

1. **Create a new client** in `src/clients/`:
   ```python
   # src/clients/new_exchange.py
   from src.clients.base import BaseExchangeClient
   from src.models.market import ExchangeType, MarketData

   class NewExchangeClient(BaseExchangeClient):
       @property
       def exchange_type(self) -> ExchangeType:
           return ExchangeType.NEW_EXCHANGE

       @property
       def base_url(self) -> str:
           return "https://api.newexchange.com"

       def fetch_volume(self) -> MarketData:
           # Implementation
           pass

       def fetch_symbol(self, symbol: str) -> Optional[SymbolData]:
           # Implementation
           pass
   ```

2. **Add the exchange type** to `src/models/market.py`:
   ```python
   class ExchangeType(str, Enum):
       # ... existing exchanges
       NEW_EXCHANGE = "NewExchange"
   ```

3. **Register in the factory** (`src/clients/factory.py`):
   ```python
   from src.clients.new_exchange import NewExchangeClient

   # In ClientFactory
   _clients = {
       # ... existing clients
       'new_exchange': NewExchangeClient,
   }
   ```

4. **Add to configuration** (`config/config.yaml`):
   ```yaml
   exchanges:
     cex:
       - new_exchange
   ```

5. **Add tests** in `tests/test_clients/test_new_exchange.py`

6. **Update documentation** with the new exchange

## Reporting Issues

### Bug Reports

When reporting bugs, please include:

- Python version
- Operating system
- Steps to reproduce
- Expected behavior
- Actual behavior
- Error messages/logs

### Feature Requests

For feature requests, please describe:

- The problem you're trying to solve
- Your proposed solution
- Any alternatives you've considered

## Architecture Overview

```
src/
├── clients/          # Exchange API clients
├── models/           # Pydantic data models
├── services/         # Business logic services
├── repositories/     # Data persistence layer
├── alerts/           # Alert system components
└── utils/            # Shared utilities

dashboard/            # Dash web application
scripts/              # Standalone scripts
tests/                # Test suite
config/               # Configuration files
```

## Questions?

If you have questions, feel free to:

1. Open a GitHub Issue
2. Check existing documentation in `/docs`
3. Review the codebase examples

Thank you for contributing!
