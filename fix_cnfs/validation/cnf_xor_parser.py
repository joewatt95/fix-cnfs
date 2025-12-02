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

# --- 1. Base Definitions ---

# Matches any sequence of whitespace (space, tab, newline, carriage return)
# We use \s+ which includes \n and \r.
whitespace = regex(r'\s+')

# Matches a comment: starts with 'c', eats until end of line, eats the newline.
# We handle both \n and \r\n.
comment = regex(r'c.*')

# "Junk" is any combination of whitespace or comments.
# It matches completely empty strings (optional), so it's safe to use everywhere.
junk = (whitespace | comment).many()

# --- 2. The Lexeme Factory ---

def lexeme(p: Parser) -> Parser:
    """
    Wraps a parser 'p' so that it consumes 'p' AND any trailing junk.
    This is the secret to avoiding 'separator' hell.
    """
    return p << junk

# --- 3. Atomic Tokens ---

# The terminator '0'. We treat it as a string token.
token_zero = lexeme(string("0"))

# The keyword 'p'.
token_p = lexeme(string("p"))

# The keyword 'cnf'.
token_cnf = lexeme(string("cnf"))

# The keyword 'x'.
token_x = lexeme(string("x"))

# A "Literal" is a non-zero integer.
# We explicitly exclude 0 here to prevent the literal parser from eating the terminator.
# Regex logic: Optional minus, then (1-9 followed by digits) OR (just 1-9)
token_literal = lexeme(regex(r"-?[1-9][0-9]*").map(int)).desc("non-zero integer")

# A generic integer (for the header, where 0 is theoretically possible as a count)
token_int = lexeme(regex(r"-?[0-9]+").map(int))

# --- 4. Structural Parsers ---

@generate
def header_parser():
    yield token_p
    yield token_cnf
    n_vars = yield token_int
    n_clauses = yield token_int
    return Header(num_vars=n_vars, num_clauses=n_clauses)

@generate
def cnf_clause_parser():
    # A CNF clause is just a list of literals followed by zero
    lits = yield token_literal.many()
    yield token_zero
    return CnfClause(literals=lits)

@generate
def xor_clause_parser():
    # An XOR clause is 'x', list of literals, followed by zero
    yield token_x
    lits = yield token_literal.many()
    yield token_zero
    return XorClause(literals=lits)

# Combined clause parser (Try XOR first, then CNF)
clause_parser = xor_clause_parser | cnf_clause_parser

@generate
def cnf_xor_file_parser_internal():
    # 1. Eat initial junk (BOM, leading comments, empty lines)
    yield junk
    
    # 2. Parse Header
    header = yield header_parser
    
    # 3. Parse Clauses
    # Since 'junk' is eaten by the tokens themselves, 
    # we just look for 'many' clauses.
    clauses = yield clause_parser.many()
    
    # 4. Ensure we are at the end of the file
    # (The last token parsed (0) already ate trailing junk, so we just check eof)
    yield eof
    
    return CnfXorFile(header=header, clauses=clauses)


def cnf_xor_file_parser(content: str) -> CnfXorFile:
    """
    Parses the full content of a CNF-XOR file and returns a CnfXorFile object
    that includes the original content.
    """
    parsed_data = cnf_xor_file_parser_internal.parse(content)
    # print("\n01234\n")
    return parsed_data._replace(original_content=content)
