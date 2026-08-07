PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
CLI := PYTHONPATH=backend $(VENV_PYTHON) -m kindle_brief.cli

.PHONY: bootstrap test lint validate preview preview-live build-demo deploy feeds-check package-kindle install-kindle uninstall-kindle verify-backup

bootstrap:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -e '.[dev]'

test:
	PYTHONPATH=backend $(VENV_PYTHON) -m pytest

lint:
	PYTHONPATH=backend $(VENV_PYTHON) -m ruff check backend tests

validate:
	$(CLI) validate --config config/config.example.yaml --feeds config/feeds.yaml

preview:
	$(CLI) preview --config config/config.example.yaml --feeds config/feeds.yaml --output previews --demo

preview-live:
	$(CLI) preview --config config/config.example.yaml --feeds config/feeds.yaml --cache .cache/kindle-brief --output previews --live

build-demo:
	$(CLI) build --config config/config.example.yaml --feeds config/feeds.yaml --output public --demo

deploy:
	$(CLI) build --config config/config.example.yaml --feeds config/feeds.yaml --cache .cache/kindle-brief --output public --live

feeds-check:
	$(CLI) feeds-check --feeds config/feeds.yaml --timeout 20

package-kindle:
	./kindle/install/package.sh

install-kindle: package-kindle
	./kindle/install/install.sh "$${KINDLE_MOUNT:-/Volumes/Kindle}"

uninstall-kindle:
	./kindle/install/uninstall.sh "$${KINDLE_MOUNT:-/Volumes/Kindle}"

verify-backup:
	./kindle/install/verify-backup.sh "$${KINDLE_MOUNT:-/Volumes/Kindle}" "device-backups/2026-08-07-kt5-pre-jailbreak"
