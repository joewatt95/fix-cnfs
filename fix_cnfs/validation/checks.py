from pathlib import Path
import re
from typing import NamedTuple, Any, Optional

from returns.result import Result, Success, Failure

from .cnf_xor_parser import CnfXorFile, CnfClause

class ValidationFailure(NamedTuple):
    """Base for detailed validation failures."""
    file: Path
    message: str
    line: Optional[int] = None
    col: Optional[int] = None

    @property
    def error_type(self) -> str:
        return self.__class__.__name__


class EmptyFileFailure(ValidationFailure): ...
class ClauseCountMismatchFailure(ValidationFailure): ...
class InvalidLiteralFailure(ValidationFailure): ...
class VariableOutOfRangeFailure(ValidationFailure): ...
class TautologyFailure(ValidationFailure): ...
class ParseFailure(ValidationFailure): ...
class DuplicateHeaderFailure(ValidationFailure): ...


# The result of a validation check on a single file.
# On success, it can hold any value (e.g., the data that was validated).
# On failure, it holds a DetailedValidationFailure.
ValidationResult = Result[Any, ValidationFailure]


def check_empty_file(file_path: Path, content: str) -> Result[str, ValidationFailure]:
    """Checks if the file is empty or contains only whitespace."""
    if not content.strip():
        return Failure(EmptyFileFailure(
            file=file_path,
            message="File is empty or contains only whitespace.",
        ))
    return Success(content)


def check_duplicate_headers(file_path: Path, content: str) -> Result[str, ValidationFailure]:
    """Checks for multiple 'p cnf ...' header lines."""
    lines = content.splitlines()
    # Use regex to be flexible with whitespace
    header_pattern = re.compile(r"^\s*p\s+cnf")
    header_lines = [(i + 1, line) for i, line in enumerate(lines) if header_pattern.match(line)]
    if len(header_lines) > 1:
        first_line_num = header_lines[0][0]
        duplicate_line_nums = ", ".join(str(num) for num, _ in header_lines[1:])
        return Failure(DuplicateHeaderFailure(
            file=file_path,
            message=f"Multiple header lines found. First at line {first_line_num}, duplicates at lines: {duplicate_line_nums}",
        ))
    return Success(content)


def check_clause_count(parsed_data: CnfXorFile, file_path: Path) -> Result[CnfXorFile, ValidationFailure]:
    """Validates that the number of clauses matches the header declaration."""
    num_clauses_header = parsed_data.header.num_clauses
    actual_clauses = parsed_data.clauses

    if len(actual_clauses) != num_clauses_header:
        return Failure(ClauseCountMismatchFailure(
            file=file_path,
            message=f"Header declares {num_clauses_header} clauses, but {len(actual_clauses)} were found.",
        ))
    return Success(parsed_data)


def check_literals_validity(parsed_data: CnfXorFile, file_path: Path) -> Result[CnfXorFile, ValidationFailure]:
    """Validates literals: non-zero and within the declared variable range."""
    num_vars = parsed_data.header.num_vars
    actual_clauses = parsed_data.clauses

    for clause_idx, clause_data in enumerate(actual_clauses):
        literals = clause_data.literals
        # The line number would ideally come from the parser, but we can estimate
        # or pass it down. For now, we'll omit it for simplicity in this check.

        for lit_idx, literal in enumerate(literals):
            if literal == 0:
                return Failure(InvalidLiteralFailure(
                    file=file_path,
                    message=f"Clause {clause_idx + 1}, literal {lit_idx + 1}: contains an invalid literal '0' before the end of the line.",
                ))
            if abs(literal) > num_vars:
                return Failure(VariableOutOfRangeFailure(
                    file=file_path,
                    message=f"Clause {clause_idx + 1}, literal {lit_idx + 1}: uses variable {abs(literal)}, which exceeds the {num_vars} declared in the header.",
                ))
    return Success(parsed_data)


def check_cnf_tautologies(parsed_data: CnfXorFile, file_path: Path) -> Result[CnfXorFile, ValidationFailure]:
    """Checks for tautologies in CNF clauses."""
    actual_clauses = parsed_data.clauses

    for clause_idx, clause_data in enumerate(actual_clauses):
        # Tautology check for CNF clauses only
        if isinstance(clause_data, CnfClause):
            seen_literals = set()
            for literal in clause_data.literals:
                if -literal in seen_literals:
                    return Failure(TautologyFailure(
                        file=file_path,
                        message=f"CNF clause {clause_idx + 1} is a tautology (contains both {abs(literal)} and -{abs(literal)}).",
                    ))
                seen_literals.add(literal)
    return Success(parsed_data)