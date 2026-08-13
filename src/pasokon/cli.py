"""Main CLI entry point for pasokon."""

import click
import sys
import os

# Force UTF-8 encoding on Windows
if sys.platform == 'win32':
    os.environ.setdefault('PYTHONUTF8', '1')

from pasokon.commands import hello, mouse, fpv_pov


@click.group()
@click.version_option()
def main() -> None:
    """Pasokon CLI - A Python command-line application."""
    pass


# Register commands
main.add_command(hello.hello)
main.add_command(mouse.move)
main.add_command(mouse.position)
main.add_command(mouse.jiggle)
main.add_command(fpv_pov.fpv_pov, name="fpv-pov")


if __name__ == "__main__":
    main()
