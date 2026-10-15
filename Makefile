.PHONY: hooks clean

hooks:
	git config core.hooksPath .githooks

clean:
	rm -rf .venv .ruff_cache .mypy_cache .pytest_cache
	find . -maxdepth 1 \( -name .coverage -o -name '.coverage.*' \) -delete
