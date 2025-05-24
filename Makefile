# Makefile for linting Python code with flake8

.PHONY: fmt lint tests clean update

# Directory containing Python files
PYTHON_DIR = ./app

# format all files
fmt:
	@echo "Running formatter..."
	uv run ruff format --config ruff.toml ${PYTHON_DIR}


lint:
	@echo "Running ruff linter..."
	(uv run ruff check --config ruff.toml ${PYTHON_DIR} || uv run ruff check --config ruff.toml --statistics ${PYTHON_DIR}) | tee ruff_output.txt

docker:
	docker compose --file docker-compose.yml --progress=plain build
	docker image ls | grep stusermanagerdemo

tests:
	DB_ENGINE="sqlite" DB_DATABASE=":memory:" uv run pytest

coverage:
	DB_ENGINE="sqlite" DB_DATABASE=":memory:" uv run coverage run -m pytest
	uv run coverage report -m


# Clean up flake8 cache and temporary files
clean:
	@echo "Cleaning up..."
	rm -rf .flake8

update:
	@echo "Updating..."
	uv sync -U
	@echo "Show latest available version of each package..."
	uv tree --depth 1 --outdated
