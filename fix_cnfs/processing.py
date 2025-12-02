import asyncio
from pathlib import Path
from typing import Any, Callable, Coroutine, List, AsyncGenerator, Optional

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)


async def process_files_with_progress(
    files: List[Path],
    coro_builder: Callable[[Path], Coroutine[Any, Any, Any]],
    description: str,
    result_handler: Optional[Callable[[Any, Any, Any], None]] = None,
    progress_cols: Optional[tuple] = None,
    **task_fields,
):
    """
    Processes a list of files with a progress bar, running a given coroutine for each file.

    Args:
        files: A list of file paths to process.
        coro_builder: A function that takes a Path and returns a coroutine.
        description: The description to display on the progress bar.
        result_handler: An optional function to call with the progress object, task ID, and result.
        progress_cols: An optional tuple of progress columns for Rich Progress.
        **task_fields: Additional fields to add to the progress task.
    """
    if not progress_cols:
        progress_cols = (
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
        )
    with Progress(*progress_cols) as progress:
        p_task = progress.add_task(description, total=len(files), **task_fields)
        async with asyncio.TaskGroup() as tg:
            tasks = {tg.create_task(coro_builder(file)): file for file in files}
            for task in asyncio.as_completed(tasks):
                result = await task
                if result_handler:
                    result_handler(progress, p_task, result)
                progress.update(p_task, advance=1)


async def find_cnf_files(directory: Path) -> AsyncGenerator[Path, None]:
    """Asynchronously yields all CNF files (.cnf) in a given directory."""
    for path in directory.glob("*.cnf"):
        yield path
