"""ctxforge CLI application."""

import typer

from ctxforge.__version__ import __version__
from ctxforge.console.commands.clean import clean_command
from ctxforge.console.commands.init import init_command
from ctxforge.console.commands.profile import profile_app
from ctxforge.console.commands.run import run_command

app = typer.Typer(
    name="ctxforge",
    help="AI role-matrix context manager.",
    no_args_is_help=True,
    add_completion=False,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"ctxforge {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """AI role-matrix context manager."""


app.command(name="init")(init_command)
app.command(name="run")(run_command)
app.command(name="clean")(clean_command)
app.add_typer(profile_app, name="profile")


def main() -> None:
    app()
