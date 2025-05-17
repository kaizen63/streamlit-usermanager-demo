# Makefile for linting Python code with flake8

.PHONY: fmt lint tests clean update

# Directory containing Python files
PYTHON_DIR = ./app

# format all files
fmt:
	@echo "Running isort"
	uv run isort ${PYTHON_DIR}
	@echo "Running formatter..."
	uv run ruff format --config pyproject.toml ${PYTHON_DIR}
# Lint the Python files with flake8
lint:
	@echo "Running flake8 linter..."
	uv run flake8 ${PYTHON_DIR} --count --select=E9,F63,F7,F82 --show-source --statistics
 	# exit-zero treats all errors as warnings. The GitHub editor is 127 chars wide
	uv run flake8 ${PYTHON_DIR} --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics --ignore=F841,W503

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
