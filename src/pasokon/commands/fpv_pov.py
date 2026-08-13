"""CLI command for launching the FPV POV Gradio app."""

import click
import sys
import os

# Force UTF-8 encoding immediately for Windows
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


@click.command()
def fpv_pov():
    """Launch the FPV POV image generation Gradio app."""
    # Import here to ensure UTF-8 is set first
    from ..gradio_app import launch
    
    click.echo("🚀 Launching FPV POV Image Generator...")
    click.echo("The app will open in your browser at http://127.0.0.1:7860")
    
    try:
        launch()
    except FileNotFoundError as e:
        click.echo(f"❌ Error: {e}", err=True)
        click.echo("\nMake sure fpv-pov-image.md and fpv-pov-review.md are in the project root.", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error launching app: {e}", err=True)
        sys.exit(1)
