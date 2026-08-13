"""Mouse control command for pasokon CLI."""

import click
import pyautogui
import random


@click.command()
@click.argument("x", type=int)
@click.argument("y", type=int)
@click.option("--duration", default=0.0, help="Duration of the movement in seconds (0 = instant).")
def move(x: int, y: int, duration: float) -> None:
    """Move the mouse cursor to X Y coordinates on the screen."""
    try:
        # Get screen size for validation
        screen_width, screen_height = pyautogui.size()
        
        if x < 0 or x > screen_width:
            click.echo(f"Error: X coordinate must be between 0 and {screen_width}", err=True)
            raise click.Abort()
        
        if y < 0 or y > screen_height:
            click.echo(f"Error: Y coordinate must be between 0 and {screen_height}", err=True)
            raise click.Abort()
        
        # Move the mouse
        pyautogui.moveTo(x, y, duration=duration)
        click.echo(f"Mouse moved to ({x}, {y})")
        
    except pyautogui.FailSafeException:
        click.echo("Error: PyAutoGUI fail-safe triggered (mouse moved to corner)", err=True)
        raise click.Abort()


@click.command()
def jiggle() -> None:
    try:
        x, y = pyautogui.position()
        
        # Move the mouse
        while True:
          x+=random.randint(-1, 1)
          y+=random.randint(-1, 1)
          pyautogui.moveTo(x, y)
        
    except pyautogui.FailSafeException:
        click.echo("Error: PyAutoGUI fail-safe triggered (mouse moved to corner)", err=True)
        raise click.Abort()


@click.command()
def position() -> None:
    """Get the current mouse position."""
    x, y = pyautogui.position()
    click.echo(f"Current position: ({x}, {y})")
