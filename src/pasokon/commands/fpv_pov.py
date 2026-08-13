"""CLI command for launching the FPV POV Gradio app."""

import click
import sys
import os


@click.command()
def fpv_pov():
    """Launch the FPV POV image generation Gradio app."""
    # Force UTF-8 mode on Windows before importing gradio_app
    if sys.platform == 'win32':
        os.environ.setdefault('PYTHONUTF8', '1')
    
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
