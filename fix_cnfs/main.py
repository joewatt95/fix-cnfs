import async_typer
from pathlib import Path
from typing_extensions import Annotated, Optional
from . import runner, logging_config
from .logging_config import LogLevel

app = async_typer.AsyncTyper(
    name="fix-cnfs",
    help="A CLI tool to validate and fix DIMACS CNF files.",
    add_completion=False,
)

Verbosity = Annotated[
    bool,
    async_typer.Option(
        "--verbose",
        "-v",
        help="Enable verbose (DEBUG) logging.",
        show_default=False,
    ),
]


@app.callback()
def main(verbose: Verbosity = True):
    """
    Manage CNF files.
    """
    level = LogLevel.DEBUG if verbose else LogLevel.INFO
    logging_config.setup_logging(level)


@app.async_command()
async def validate_and_fix(
    target_dir: Annotated[
        Path, async_typer.Argument(
            help="The directory containing CNF files to validate.")
    ],
    summary_path: Annotated[
        Path,
        async_typer.Option(help="Path to save the validation summary report."),
    ] = Path("validation_summary.log"),
    details_path: Annotated[
        Path,
        async_typer.Option(
            help="Path to save the detailed validation error log."),
    ] = Path("validation_details.log"),
    output: Annotated[
        Optional[Path],
        async_typer.Option(
            "--output",
            help="Enable fixing and specify the directory to save fixed files. "
                 "If this option is provided, fixing will be attempted. "
                 "Fixed files will be saved to the specified directory. "
                 "Example: --output-dir my_fixed_files",
            show_default=False,
        ),
    ] = None,
):
    """
    Validates all CNF files in a directory and generates reports.
    """
    await runner.validate_and_fix_all_cnfs(
        target_dir, summary_path, details_path, output_dir=output)


if __name__ == "__main__":
    app()
