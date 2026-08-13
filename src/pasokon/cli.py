"""Main CLI entry point for pasokon."""

import click
import sys
import os

# Force UTF-8 encoding on Windows immediately
if sys.platform == 'win32':
    import io
    # Reconfigure stdout and stderr to use UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    else:
        # Fallback for older Python versions
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.environ['PYTHONUTF8'] = '1'

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
