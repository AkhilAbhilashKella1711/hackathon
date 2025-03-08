## Project Setup

### Prerequisites
1. Python 3.10.12
2. Git



## Installation Process

1. Create a virtual environment using poetry:
```bash
python3 -m venv venv
```

2. Activate the virtual environment:
```bash
source venv/bin/activate
```

3. Upgrade Pip to the latest version:
```bash
pip install --upgrade pip
```

4. Install the required packages:
```bash
pip install -r requirements.txt
```

## Start the application

```bash
python3 -m server.main
```

## Linting & Formatting
1. Static type checking:
```bash
pyright                    # Check all files in the current directory.
```


2. Linting:
```bash
ruff check                  # Lint all files in the current directory.
ruff check --fix            # Lint all files in the current directory, and fix any fixable errors.
```

3. Formatting:
```bash
ruff format                 # Format all files in the current directory.
```