from __future__ import annotations
from typing import ClassVar
import shlex
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header, Input, RichLog
from textual.binding import Binding, BindingType
from textual.suggester import Suggester


class CommandSuggester(Suggester):
    """Suggests commands based on the first word of input."""

    def __init__(self, commands: list[str]):
        super().__init__(use_cache=False)
        self.commands = commands

    async def get_suggestion(self, value: str) -> str | None:
        if not value or ' ' in value:
            return None

        for cmd in self.commands:
            if cmd.startswith(value.lower()) and cmd != value:
                return cmd
        return None


class CommandInput(Input):
    def __init__(self, log_widget: RichLog, **kwargs):
        super().__init__(**kwargs)
        self.log_widget = log_widget
        self.commands = [attr[4:] for attr in dir(self) if attr.startswith('cmd_')]
        self.suggester = CommandSuggester(self.commands)

    def execute_command(self, raw_text: str) -> None:
        """Parses arguments safely using shlex and executes the command."""
        text = raw_text.strip()
        if not text:
            return

        self.log_widget.write(f'> {text}')

        try:
            parts = shlex.split(text)
        except ValueError as e:
            self.log_widget.write(f'Parsing Error: {e}')
            return

        cmd_name = parts[0].lower()
        args = parts[1:]

        method_name = f'cmd_{cmd_name}'
        if hasattr(self, method_name):
            method = getattr(self, method_name)
            try:
                method(*args)
            except TypeError:
                self.log_widget.write(f"Error: Invalid arguments for '{cmd_name}'.")
        else:
            self.log_widget.write(f"Unknown command: '{cmd_name}'")

    def cmd_help(self) -> None:
        """List available commands."""
        self.log_widget.write(f'Available commands: {", ".join(self.commands)}')

    def cmd_send(self, user_id: str, message: str) -> None:
        """Example with 2 arguments: send <user_id> <message>"""
        self.log_widget.write(f"Sending '{message}' to User {user_id}...")

    def cmd_clear(self) -> None:
        """Clear the console."""
        self.log_widget.write('')  # Bugfix helper for Textual spacing
        self.log_widget.clear()

    def cmd_exit(self) -> None:
        """Exit the application."""
        self.app.exit()


class TextualDashboard(App[None]):
    """A lightweight Textual dashboard for observing bot startup logs."""

    CSS = """
    Screen {
        align: center middle;
    }

    #main {
        layout: vertical;
        width: 100%;
        height: 100%;
    }

    RichLog {
        width: 100%;
        height: 1fr;
        margin: 1 1 0 1;
        border: solid #4d4d4d;
        padding: 0 1;
    }
    
    Input.-valid {
        border: tall $success 60%;
    }
    Input.-valid:focus {
        border: tall $success;
    }
    Input {
        width: 100%;
        margin: 1 1 1 1;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding('ctrl+q', 'quit', 'Quit the application', priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.log_widget = RichLog(
            markup=True,
            highlight=False,
            wrap=True,
            auto_scroll=True,
        )
        self.input_widget = CommandInput(
            log_widget=self.log_widget, placeholder='Type a command…',
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id='main'):
            yield self.log_widget
            yield self.input_widget
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = 'Terminal yep'
        self.log_widget.write('TUI initialized\n')

    def set_status(self, status: str) -> None:
        self.sub_title = status

    @on(Input.Submitted)
    def handle_submitted(self, event: Input.Submitted) -> None:
        if isinstance(event.input, CommandInput):
            log = self.query_one(RichLog)
            log.write(event.value)
            event.input.execute_command(event.value)
            event.input.value = ''

    def stop(self) -> None:
        self.exit()
