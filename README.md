# `fix-cnfs`

![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)

## Features

- **Concurrent Processing**: Leverages `asyncio` to process hundreds or thousands of files concurrently, making it fast and efficient.
- **Clear Progress Tracking**: Displays a real-time progress bar, so you always know the status of the validation or fixing process.
- **Robust Validation**: Uses a custom `parsy`-based parser to detect a wide range of formatting issues.
- **Detailed Reports**: Generates summary and detailed error reports to help you quickly identify problematic files.
- **Automatic & Safe Fixing**: Corrects common issues like duplicate headers, missing clause terminators, and invalid literals, saving corrected files to a separate directory without modifying the originals.

## Table of Contents

- What it does
- Usage
- Getting Started

## What it does

The `validate-and-fix` command inspects all `.cnf` files in a given directory, reports any parsing or semantic errors, and can optionally fix them. It runs all operations concurrently and displays a progress bar while it works.

### Validation
The tool can detect a wide range of formatting issues, such as:

-   Incorrect or missing `p cnf` headers.
-   Duplicate `p cnf` headers.
-   Clause lines that do not end with a `0`.
-   Non-integer literals in clauses.
-   Variables outside the declared range.
-   Tautologies in CNF clauses.

It generates two reports:
-   `validation_summary.log`: A high-level summary of errors, grouped by type.
-   `validation_details.log`: A detailed log of every file that failed validation and the corresponding error.

### Fixing
If fixing is enabled (by using the `--output-dir` option), the tool will attempt to automatically correct the following issues:
-   **Duplicate `p cnf` headers**: Comments out any subsequent header lines, keeping only the first one.
-   **Missing clause terminators**: Appends a `0` to lines that are missing it.
-   **Invalid literals**: Removes literals that are out of the range defined by the header.

Corrected files are always written to the specified output directory, ensuring your original files are never modified.

## Usage

### Global Options

- `--verbose`, `-v`: Enable verbose (DEBUG) logging for detailed output.

### `validate-and-fix`

**Command:**
```bash
fix-cnfs validate-and-fix <TARGET_DIR> [OPTIONS]
```

## Getting Started

### Prerequisites

- Python 3.12+
- [Poetry](https://python-poetry.org/docs/#installation) for dependency management.

### Installation

1.  **Clone the repository (or download the source code):**
    ```bash
    git clone <repository-url>
    cd fix-cnfs
    ```

2.  **Install the dependencies using Poetry:**
    This command will create a virtual environment and install all the required packages.
    ```bash
    poetry install
    ```

3.  **Run the tool:**
    After installation, you can run the commands in two ways:
    1.  Activate the virtual environment using `poetry shell` and then run the commands directly (e.g., `fix-cnfs validate ...`).
    2.  Prefix the commands with `poetry run` (e.g., `poetry run fix-cnfs validate ...`).
