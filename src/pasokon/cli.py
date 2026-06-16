"""Main CLI entry point for pasokon."""

import click
from pasokon.commands import hello


@click.group()
@click.version_option()
def main() -> None:
    """Pasokon CLI - A Python command-line application."""
    pass


# Register commands
main.add_command(hello.hello)


if __name__ == "__main__":
    main()
