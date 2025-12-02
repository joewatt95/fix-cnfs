from collections.abc import Generator
from typing import List, NamedTuple, Any, Optional

from parsy import Parser, generate, regex, string, eof, seq


# --- NamedTuple Definitions for Parsed Data ---
class Header(NamedTuple):
    num_vars: int
    num_clauses: int


class CnfClause(NamedTuple):
    literals: List[int]


class XorClause(NamedTuple):
    literals: List[int]


# Union type for clauses
Clause = CnfClause | XorClause


class CnfXorFile(NamedTuple):
    header: Header
    clauses: List[Clause]
    original_content: Optional[str] = None


def _get_line_col_from_index(content: str, index: int) -> tuple[int, int]:
    """Calculates line and column number from a character index."""
    lines = content.splitlines(keepends=True)
    line_num = 1
    col_num = 1
    current_index = 0
    for line in lines:
        if current_index + len(line) > index:
            col_num = index - current_index + 1
            break
        current_index += len(line)
        line_num += 1
    return line_num, col_num


# --- Parsy-based CNF-XOR Parser Elements ---


# Define a robust whitespace separator
# Includes spaces, tabs, and newlines
ws: Parser = regex(r'[ \t\n]+').desc("whitespace")
ws_opt: Parser = ws.optional()


# Basic elements
integer: Parser = regex(r"-?[0-9]+").map(int)
line_end: Parser = string("\n") | regex(
    r"$")  # Handle final line without newline

comment: Parser = regex(r"c[^\n]*") << line_end
consumable_item: Parser = ws | comment
# A separator is one or more chunks of consumable content
separator: Parser = consumable_item.at_least(1)

# Clause type parsers (CNF and XOR)
literal_parser_with_ws = integer.skip(ws) | integer.skip(
    ws_opt)  # Allow trailing whitespace
terminator_parser: Parser = string("0").map(int).desc("clause terminator '0'")

# Use `sep_by` for the list of literals, followed by the terminator


@generate
def clause_core_parser() -> Generator[Parser, Any, Optional[List[int]]]:
    """Parses the sequence of literals ending with '0'."""
    # Parsy's `sep_by` can be tricky with a terminating element.
    # A cleaner way is to parse the list of all integers (literals + 0)
    # and then assert the last one is 0.

    # Parse all integers separated by optional whitespace
    all_ints: List[int] = yield integer.sep_by(ws, min=1)

    # Check for the mandatory 0 terminator
    if all_ints[-1] != 0:
        # If you want to handle this as a parse error (more robust)
        # you'd need a custom parser, but for now, we'll assume the format is correct
        # or use a different structure.

        # Let's stick to a simpler parsy approach by parsing the literals
        # and then the terminator, skipping all intervening whitespace:

        # Parse literals separated by required whitespace
        literals: List[int] = yield integer.sep_by(ws, min=0)

        # Now require the terminator, preceded by optional whitespace
        yield ws_opt
        yield terminator_parser  # Which is a string("0").map(int)

        return literals

# Simpler version focusing on parsing:


@generate
def cnf_clause_parser() -> Generator[Parser, Any, CnfClause]:
    """Parses a CNF clause: literals (ws-separated) 0, skipping intervening ws."""
    # Parse literals separated by one or more whitespace characters (including newlines)
    lits: List[int] = yield integer.sep_by(ws, min=0)

    # Must be followed by optional whitespace before the final '0'
    yield ws_opt
    yield terminator_parser

    # After the 0, we still need to account for the actual line ending or comment,
    # but that is best handled in the main loop.
    return CnfClause(literals=lits)

# The xor_clause_parser would be adjusted similarly:


@generate
def xor_clause_parser() -> Generator[Parser, Any, XorClause]:
    """Parses an XOR clause: x <literals> 0, skipping intervening ws."""
    yield string("x") >> ws  # Require "x" followed by whitespace
    lits: List[int] = yield integer.sep_by(ws, min=0)

    yield ws_opt
    yield terminator_parser

    return XorClause(literals=lits)


# Combined clause parser
clause_parser_instance: Parser = (
    cnf_clause_parser | xor_clause_parser).desc("CNF or XOR clause")

# Redefine the main parser to use a separator for comments/whitespace

ignored: Parser = (comment | ws).many()  # Sequence of comments and whitespace

# Header line: "p cnf <num_vars> <num_clauses>"
p_line: Parser = (
    string("p")
    >> ws
    >> string("cnf")
    >> ws
    # Use seq() on the two items we actually want to keep/return
    >> seq(
        integer.skip(ws),  # Result 1: num_vars
        integer.skip(ws_opt)  # Result 2: num_clauses
    )
).desc("header line 'p cnf <num_vars> <num_clauses>'")


@generate
def header_parser() -> Generator[Parser, Any, Header]:
    """Parses the header, skipping any preceding comments/ws, returning a Header NamedTuple."""
    yield (comment | ws).many()

    # h_tuple will be (num_vars, num_clauses)
    h_tuple: tuple[int, int] = yield p_line

    # After the header, consume the rest of the line/comments
    yield (ws_opt >> comment | ws_opt >> line_end).optional()

    # Unpack the tuple positionally
    return Header(num_vars=h_tuple[0], num_clauses=h_tuple[1])


# @generate
# def header_parser() -> Generator[Parser, Any, Header]:
#     """Parses the header, skipping any preceding comments, returning a Header NamedTuple."""
#     # Skip any comments and whitespace before the 'p' line
#     yield (comment | ws).many()

#     h_dict = yield p_line

#     # After the header, consume the rest of the line (newline, comment, or EOF)
#     yield (comment | line_end).optional()

#     return Header(num_vars=h_dict["num_vars"], num_clauses=h_dict["num_clauses"])

@generate
def _cnf_xor_data_parser() -> Generator[Parser, Any, CnfXorFile]:

    # Consume all initial junk (comments/whitespace) before header
    yield consumable_item.many()

    header: Header = yield header_parser

    # Parse all clauses, separated by required, consumable content
    # Note: We must allow zero clauses in case num_clauses is 0, so we use optional() or min=0.
    clauses: List[Clause] = yield clause_parser_instance.sep_by(separator, min=0)

    # Consume all trailing junk (comments/whitespace)
    yield consumable_item.many()
    yield eof

    return CnfXorFile(header=header, clauses=clauses)


def cnf_xor_file_parser(content: str) -> CnfXorFile:
    """
    Parses the full content of a CNF-XOR file and returns a CnfXorFile object
    that includes the original content.
    """
    parsed_data = _cnf_xor_data_parser.parse(content)
    # print("\n01234\n")
    return parsed_data._replace(original_content=content)
