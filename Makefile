# Makefile for linting Python code with flake8

.PHONY: fmt lint tests clean

# Directory containing Python files
PYTHON_DIR = ./app

# format all files
fmt:
	@echo "Running black formatter..."
	uv run black --config pyproject.toml ${PYTHON_DIR}

# Lint the Python files with flake8
lint:
	@echo "Running flake8 linter..."
	uv run flake8 ${PYTHON_DIR} --count --select=E9,F63,F7,F82 --show-source --statistics
 	# exit-zero treats all errors as warnings. The GitHub editor is 127 chars wide
	uv run flake8 ${PYTHON_DIR} --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics --ignore=F841,W503

docker:
	docker compose --file docker-compose.yml --progress=plain build

tests:
	DB_ENGINE="sqlite" DB_DATABASE=":memory:" uv run pytest

coverage:
	DB_ENGINE="sqlite" DB_DATABASE=":memory:" uv run coverage run -m pytest
	uv run coverage report -m


# Clean up flake8 cache and temporary files
clean:
	@echo "Cleaning up..."
	rm -rf .flake8
