import click
from client.block import import_block
from client.state import initialize_state, transition_state


@click.group()
def main():
    """Python Jam Client"""
    pass


@main.command()
@click.argument('block_data')
def import_block_cmd(block_data):
    """Import a block"""
    success = import_block(block_data)
    if success:
        click.echo("Block imported successfully.")
    else:
        click.echo("Failed to import block.")


@main.command()
def init_state():
    """Initialize the state"""
    initialize_state()
    click.echo("State initialized.")


@main.command()
@click.argument('block_data')
def transition(block_data):
    """Transition state with a block"""
    success = transition_state(block_data)
    if success:
        click.echo("State transitioned successfully.")
    else:
        click.echo("State transition failed.")


if __name__ == '__main__':
    main()
