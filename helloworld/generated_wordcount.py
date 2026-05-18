"""
wordcount.py — CLI Word Frequency Counter

Reads a plain-text UTF-8 file, tokenizes and normalizes its words,
counts frequencies using collections.Counter, and prints a ranked
table of the top-N most frequent words to stdout.

Usage:
    python wordcount.py <file> [--top N]
"""

import argparse
import collections
import re
import sys
import os
from typing import Iterable, List, Tuple


# ---------------------------------------------------------------------------
# Tokenization / normalization
# ---------------------------------------------------------------------------

# Matches one or more Unicode word characters (letters, digits, underscore)
# plus apostrophes that appear *between* word characters (intra-word).
# We build tokens by splitting on whitespace first, then stripping punctuation.

# Characters considered "punctuation" at word boundaries.
# We strip anything that is NOT a Unicode letter, digit, or an intra-word apostrophe.
_STRIP_PATTERN = re.compile(r"^[^\w']+|[^\w']+$", re.UNICODE)
_ONLY_NON_WORD = re.compile(r"^[\W_]+$", re.UNICODE)


def tokenize_line(line: str) -> List[str]:
    """
    Split *line* into normalized word tokens.

    Steps per raw token (whitespace-split):
      1. Lowercase.
      2. Strip leading/trailing punctuation (anything that is not a Unicode
         letter, digit, or apostrophe).
      3. Discard the token if it is empty or consists solely of non-word
         characters after stripping (e.g. bare apostrophes, underscores).

    Intra-word apostrophes (e.g. "don't") are preserved.
    """
    tokens: List[str] = []
    for raw in line.split():
        # Step 1: lowercase
        word = raw.lower()
        # Step 2: strip leading/trailing punctuation
        word = _STRIP_PATTERN.sub("", word)
        # Step 3: discard empty or all-non-word tokens
        if not word:
            continue
        # Discard tokens that contain no letter or digit at all
        # (e.g. a bare apostrophe or underscore left after stripping)
        if not any(ch.isalpha() or ch.isdigit() for ch in word):
            continue
        tokens.append(word)
    return tokens


# ---------------------------------------------------------------------------
# File reading
# ---------------------------------------------------------------------------

def stream_tokens(filepath: str) -> Iterable[str]:
    """
    Open *filepath* with UTF-8 encoding (replacing undecodable bytes) and
    yield normalized tokens line-by-line to keep memory usage bounded.
    """
    with open(filepath, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            yield from tokenize_line(line)


# ---------------------------------------------------------------------------
# Frequency counting
# ---------------------------------------------------------------------------

def count_words(filepath: str) -> collections.Counter:
    """Return a Counter mapping each normalized word to its total frequency."""
    counter: collections.Counter = collections.Counter()
    counter.update(stream_tokens(filepath))
    return counter


# ---------------------------------------------------------------------------
# Ranked output
# ---------------------------------------------------------------------------

def ranked_words(counter: collections.Counter, top: int) -> List[Tuple[str, int]]:
    """
    Return up to *top* (word, count) pairs sorted by:
      1. Descending count.
      2. Ascending alphabetical order (tie-break).
    """
    sorted_words = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return sorted_words[:top]


def print_results(ranked: List[Tuple[str, int]]) -> None:
    """Print the ranked word list to stdout in the required format."""
    for rank, (word, count) in enumerate(ranked, start=1):
        print(f"{rank}. {word}: {count}")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wordcount.py",
        description="Count word frequencies in a plain-text file and print the top-N results.",
    )
    parser.add_argument(
        "file",
        help="Path to the plain-text UTF-8 file to analyse.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        metavar="N",
        help="Number of top words to display (default: 10, must be a positive integer).",
    )
    return parser


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_args(args: argparse.Namespace) -> None:
    """
    Validate parsed arguments.  Raises SystemExit(1) with a stderr message
    on any user/input error.
    """
    # Validate --top
    if args.top <= 0:
        _exit_error(
            f"Error: --top must be a positive integer, got {args.top}.",
            code=1,
        )

    # Validate file path
    if not os.path.exists(args.file):
        _exit_error(
            f"Error: File not found: '{args.file}'.",
            code=1,
        )
    if not os.path.isfile(args.file):
        _exit_error(
            f"Error: Path is not a regular file: '{args.file}'.",
            code=1,
        )
    if not os.access(args.file, os.R_OK):
        _exit_error(
            f"Error: File is not readable: '{args.file}'.",
            code=1,
        )


# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------

def _exit_error(message: str, code: int = 1) -> None:
    """Print *message* to stderr and exit with *code*."""
    print(message, file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()

    # argparse itself exits with code 2 on parse errors (missing required
    # positional arg, wrong type for --top, etc.), which satisfies the spec's
    # requirement that user errors exit non-zero.  We override the exit code
    # for type errors to be 1 by catching them explicitly.
    try:
        args = parser.parse_args()
    except SystemExit as exc:
        # argparse already printed the error to stderr; re-raise with code 1
        # for type/value errors (argparse uses code 2 by default — acceptable
        # per spec which says "non-zero", but we normalise to 1 for user errors).
        sys.exit(1 if exc.code != 0 else 0)

    # Validate inputs (exits with code 1 on failure)
    validate_args(args)

    # Count words
    counter = count_words(args.file)

    # Handle empty file gracefully
    if not counter:
        # No words found — print nothing and exit successfully
        sys.exit(0)

    # Rank and print
    ranked = ranked_words(counter, args.top)
    print_results(ranked)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        # Re-raise SystemExit so that explicit sys.exit() calls propagate
        # correctly without being swallowed by the broad except below.
        raise
    except Exception as exc:  # pylint: disable=broad-except
        print(
            f"Error: An unexpected error occurred: {exc}",
            file=sys.stderr,
        )
        sys.exit(2)
