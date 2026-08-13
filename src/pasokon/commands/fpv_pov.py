"""CLI command for launching the FPV POV Gradio app."""

import click
from ..gradio_app import launch


@click.command()
def fpv_pov():
    """Launch the FPV POV image generation Gradio app."""
    click.echo("🚀 Launching FPV POV Image Generator...")
    click.echo("The app will open in your browser at http://127.0.0.1:7860")
    launch()
