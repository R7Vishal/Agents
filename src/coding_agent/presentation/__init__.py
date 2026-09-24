from .chat_service import ChatSession, CopilotChatService


def create_app():
    from .web_app import create_app as _create_app

    return _create_app()


def main() -> None:
    from .web_app import main as _main

    _main()

__all__ = [
    "ChatSession",
    "CopilotChatService",
    "create_app",
    "main",
]
