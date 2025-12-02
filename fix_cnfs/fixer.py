import logging
from pathlib import Path
import re
from typing import List, Optional, Union

from .validation.cnf_xor_parser import CnfXorFile, cnf_xor_file_parser
from .validation.checks import ValidationFailure, ParseFailure, InvalidLiteralFailure, DuplicateHeaderFailure

logger = logging.getLogger(__name__)


class Fixer:
    """
    Represents a fixer for CNF files. It takes parsed data and a list of
    validation failures to generate a corrected version of the file.
    """

    def __init__(
        self,
        file_path: Path,
        parsed_data: CnfXorFile,
        failures: List[ValidationFailure],
    ):
        self.file_path = file_path
        self.parsed_data = parsed_data
        self.failures = failures
        self.lines = content.splitlines() if (content := parsed_data.original_content) else []
        self.max_vars = parsed_data.header.num_vars

    def _apply_fixes(self) -> None:
        """
        Iterates through failures and applies the corresponding fix method.
        This is where you would add routing to more fix methods.
        """
        for failure in self.failures:
            match failure:
                case ParseFailure(message=msg) if "terminator" in msg:
                    self._fix_missing_zero(failure)
                case InvalidLiteralFailure():
                    self._fix_invalid_literals(failure)
                case DuplicateHeaderFailure():
                    self._fix_duplicate_header(failure)

    def _fix_missing_zero(self, failure: ValidationFailure) -> None:
        """Appends a ' 0' to a line missing its terminating zero."""
        if failure.line is not None:
            line_index = failure.line - 1
            if 0 <= line_index < len(self.lines):
                self.lines[line_index] = self.lines[line_index].rstrip() + " 0"
                logger.debug(f"Fix applied to {self.file_path.name}: Added missing zero on line {failure.line}")

    def _fix_invalid_literals(self, failure: ValidationFailure) -> None:
        """Removes invalid literals from a clause on a given line."""
        if failure.line is not None:
            line_index = failure.line - 1
            if 0 <= line_index < len(self.lines):
                parts = self.lines[line_index].strip().split()
                valid_parts = [
                    p for p in parts if p.lstrip('-').isdigit() and abs(int(p)) <= self.max_vars
                ]
                if valid_parts and valid_parts[-1] != '0':
                    valid_parts.append('0')
                
                self.lines[line_index] = " ".join(valid_parts)
                logger.debug(f"Fix applied to {self.file_path.name}: Removed invalid literals on line {failure.line}")

    def _fix_duplicate_header(self, failure: DuplicateHeaderFailure) -> None:
        """Comments out duplicate 'p cnf ...' lines."""
        # Use regex to be flexible with whitespace
        header_pattern = re.compile(r"^\s*p\s+cnf")
        header_lines = [(i, line) for i, line in enumerate(self.lines) if header_pattern.match(line)]
        # The first header line is kept, others are commented out.
        for i, line in header_lines[1:]:
            self.lines[i] = "c " + line
            logger.debug(f"Fix applied to {self.file_path.name}: Commented out duplicate header on line {i + 1}")
        
        # After fixing, we need to re-parse to update the parsed_data object
        # so that subsequent fixes (like invalid literals) use correct max_vars.
        try:
            new_content = "\n".join(self.lines)
            self.parsed_data = cnf_xor_file_parser(new_content)
            self.max_vars = self.parsed_data.header.num_vars
        except Exception as e:
            logger.warning(f"Could not re-parse {self.file_path.name} after fixing duplicate headers: {e}")

    def get_fixed_content(self) -> Optional[str]:
        """Applies all fixes and returns the corrected file content."""
        fixable_error_types: List[Union[ParseFailure, InvalidLiteralFailure, DuplicateHeaderFailure]] = [
            f for f in self.failures if isinstance(f, (ParseFailure, InvalidLiteralFailure, DuplicateHeaderFailure))
        ]

        if not fixable_error_types:
            return None

        self._apply_fixes()
        return "\n".join(self.lines)