import asyncio
import logging
from collections import defaultdict
from pathlib import Path
from typing import List, Optional

import aiofiles
from returns.result import Success, Failure
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    TextColumn,
    TimeElapsedColumn,
)

from .processing import find_cnf_files, process_files_with_progress
from .validation.validator import validate_and_fix_cnf_file, ValidationResult, ValidationFixed
from .validation.checks import ValidationFailure

logger = logging.getLogger(__name__)


async def _write_details_report(
    errors: List[ValidationFailure], details_path: Path
) -> None:
    """Writes a detailed log of all validation errors."""
    try:
        async with aiofiles.open(details_path, "w") as f:
            await f.write("--- CNF Detailed Validation Errors Log ---\n\n")
            for error in errors:
                await f.write(f"File: {error.file.name}\n")
                await f.write(f"Error Type: {error.error_type}\n")
                await f.write(f"Error Message Snippet: {error.message}\n")
                await f.write("---" * 20 + "\n")
        logger.info(f"Detailed logs saved to '{details_path}'")
    except IOError as e:
        logger.error(f"Failed to write summary report to {details_path}: {e}")


async def _write_summary_report(
    results: List[ValidationResult], errors: List[ValidationFailure], summary_path: Path
) -> None:
    """Writes a summary report grouping errors by type."""
    error_groups = defaultdict(list)
    for error in errors:
        error_groups[error.error_type].append(error.file.name)

    try:
        async with aiofiles.open(summary_path, "w") as f:
            await f.write("--- CNF Validation Summary ---\n")
            await f.write(f"Total files checked: {len(results)}\n")

            fixed_count = sum(
                1 for r in results
                if isinstance(r, Success) and isinstance(r.unwrap(), ValidationFixed)
            )
            await f.write(f"Total files fixed: {fixed_count}\n")
            await f.write(f"Total files with unfixable errors: {len(errors)}\n")

            await f.write("---" * 40 + "\n")
            await f.write("Errors Grouped by Exception Type:\n\n")

            if error_groups:
                sorted_groups = sorted(
                    error_groups.items(), key=lambda item: len(item[1]), reverse=True
                )
                for error_type, file_list in sorted_groups:
                    count = len(file_list)
                    await f.write(f"**{error_type}**: {count} files\n")
                    sample_files = ", ".join(file_list[:5])
                    await f.write(f"  Sample files: {sample_files}\n")
                    if count > 5:
                        await f.write(f"  (and {count - 5} more files...)\n")
                    await f.write("\n")
            else:
                await f.write("No errors found! Congratulations.\n")
        logger.info(f"Summary of errors saved to '{summary_path}'")
    except IOError as e:
        logger.error(f"Failed to write summary report to {summary_path}: {e}")


def _handle_validation_result(
    progress, p_task, result: ValidationResult, results: List, errors: List, fixed: List
) -> None:
    """Callback to handle the result of a single file validation."""
    results.append(result)

    match result:
        case Success(ValidationFixed(file=file, content=_)):
            logger.debug(f"FIXED: {file.name}")
            fixed.append(result.unwrap())
        case Success(file):
            logger.debug(
                f"OK: {file.name if isinstance(file, Path) else file.file}")
        case Failure(failure_details):
            logger.debug(
                f"FAILED: {failure_details.file.name} ({failure_details.error_type})")
            errors.append(failure_details)

    successes = len(results) - len(errors) - len(fixed)
    progress.update(
        p_task, successes=successes, errors=len(errors), fixed=len(fixed)
    )


async def _run_validation_tasks(
    files_to_check: List[Path], output_dir: Optional[Path]
) -> tuple[List[ValidationResult], List[ValidationFailure]]:
    """Runs validation tasks concurrently for a list of files."""
    results: List[ValidationResult] = []
    errors: List[ValidationFailure] = []
    fixed: List[ValidationFixed] = []

    progress_cols = (
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[bold green]✓ {task.fields[successes]}"),
        TextColumn("[bold yellow]✓ {task.fields[fixed]} (fixed)"),
        TextColumn("[bold red]✗ {task.fields[errors]}"),
        TimeElapsedColumn(),
    )

    await process_files_with_progress(
        files=files_to_check,
        coro_builder=lambda file: validate_and_fix_cnf_file(file, output_dir=output_dir),
        description="Validating...",
        result_handler=lambda p, t, r: _handle_validation_result(
            p, t, r, results, errors, fixed
        ),
        progress_cols=progress_cols,
        successes=0,
        errors=0,
        fixed=0,
    )

    return results, errors


async def validate_and_fix_all_cnfs(
    directory: Path, summary_path: Path, details_path: Path, output_dir: Optional[Path] = None
) -> None:
    """
    Validates all CNF files in a directory concurrently and generates reports.
    """
    logger.info(f"Starting validation of files in: {directory}")

    if not directory.is_dir():
        logger.error(f"Directory not found: '{directory}'")
        return

    if output_dir:
        output_dir.mkdir(exist_ok=True)
        logger.info(f"Fixed files will be saved in: '{output_dir}'")

    files_to_check = [path async for path in find_cnf_files(directory)]
    if not files_to_check:
        logger.warning(f"No CNF files found in '{directory}'. Nothing to do.")
        return

    results, errors = await _run_validation_tasks(files_to_check, output_dir)

    logger.debug(f"Generating reports for {len(results)} files.")
    async with asyncio.TaskGroup() as tg:
        tg.create_task(_write_details_report(errors, details_path))
        tg.create_task(_write_summary_report(results, errors, summary_path))

    logger.info("Validation finished.")
