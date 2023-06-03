#!/bin/bash

# mypy --html-report report cgos/*.py cgos/**/*.py tests/*.py tests/*/*.py
mypy --html-report report cgos/ tests/
flake8 cgos/*.py cgos/**/*.py tests/*.py tests/**/*.py
