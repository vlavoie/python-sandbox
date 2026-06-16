"""Hello command for pasokon CLI."""

import click


@click.command()
@click.option("--name", default="World", help="Name to greet.")
@click.option("--count", default=1, help="Number of greetings.")
def hello(name: str, count: int) -> None:
    """Say hello to NAME COUNT times."""
    for _ in range(count):
        click.echo(f"Hello, {name}!")
