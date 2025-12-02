import logging
from pathlib import Path
from typing import NamedTuple, Optional

import aiofiles
from parsy import ParseError
from returns.result import Success, Failure

from .cnf_xor_parser import cnf_xor_file_parser, _get_line_col_from_index
from .checks import (
    ValidationResult,
    check_empty_file,
    check_clause_count,
    check_duplicate_headers,
    check_literals_validity,
    check_cnf_tautologies,
    ParseFailure, ValidationFailure,
)
from ..fixer import Fixer

logger = logging.getLogger(__name__)

class ValidationFixed(NamedTuple):
    """Represents a validation that resulted in a fix."""
    file: Path
    content: str


def _run_checks(content: str, file_path: Path, fix: bool) -> ValidationResult:
    """Parses and runs semantic checks on file content."""
    duplicate_header_check = check_duplicate_headers(file_path, content)
    if isinstance(duplicate_header_check, Failure):
        if fix:
            # Allow fixer to handle this before attempting to parse
            return duplicate_header_check
    try:
        parsed_data = cnf_xor_file_parser(content)

        validation_checks = [
            check_clause_count(parsed_data, file_path),
            check_literals_validity(parsed_data, file_path),
            check_cnf_tautologies(parsed_data, file_path),
        ]

        failures = [r.failure() for r in validation_checks if isinstance(r, Failure)]

        if not failures:
            # If we had a duplicate header, but it was fixed, we need to re-parse and re-validate
            if isinstance(duplicate_header_check, Failure):
                return _run_checks(content, file_path, fix)
            return Success(file_path)

        if fix:
            fixer = Fixer(file_path, parsed_data, failures)
            if fixed_content := fixer.get_fixed_content():
                return Success(ValidationFixed(file=file_path, content=fixed_content))

        return Failure(failures[0])

    except ParseError as e:
        line, col = _get_line_col_from_index(content, e.index)
        msg = f"Line {line}, Col {col}: Expected {', '.join(sorted(list(e.expected)))}."
        return Failure(ParseFailure(
            file=file_path, message=msg, line=line, col=col
        ))


async def validate_and_fix_cnf_file(file_path: Path, output_dir: Optional[Path] = None) -> ValidationResult:
    """
    Validates a single CNF-XOR file asynchronously, handling parsing,
    semantic checks, and coordinating with the fixer if enabled.
    """
    logger.debug(f"Processing: {file_path.name}")
    try:
        async with aiofiles.open(file_path, "r", errors="ignore") as f:
            content = await f.read()

        result = check_empty_file(file_path, content).bind(lambda c: _run_checks(c, file_path, output_dir != None))

        if output_dir and isinstance(result, Success) and isinstance(result.unwrap(), ValidationFixed):
            fixed = result.unwrap()
            output_path = output_dir / fixed.file.name
            async with aiofiles.open(output_path, "w") as f:
                await f.write(fixed.content)

        return result

    except Exception as e:
        error_message = str(e).split("\n")[0].strip()
        logger.debug(f"An unexpected error occurred for {file_path.name}: {error_message}")
        return Failure(ValidationFailure(file=file_path, message=error_message))