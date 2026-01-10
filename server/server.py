"""
Blank pygls Language Server for VS Code Extension.

This is a minimal language server implementation using pygls that can be
extended with custom features.
"""

import logging
from pygls.server import LanguageServer
from lsprotocol import types

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create the language server instance
server = LanguageServer(
    name="sbhacks12-server",
    version="0.1.0"
)


@server.feature(types.INITIALIZE)
def initialize(params: types.InitializeParams) -> types.InitializeResult:
    """Handle the initialize request from the client."""
    logger.info(f"Server initialized with root: {params.root_uri}")
    
    return types.InitializeResult(
        capabilities=types.ServerCapabilities(
            # Add your server capabilities here
            # For example:
            # text_document_sync=types.TextDocumentSyncOptions(
            #     open_close=True,
            #     change=types.TextDocumentSyncKind.Incremental,
            # ),
            # hover_provider=True,
            # completion_provider=types.CompletionOptions(
            #     trigger_characters=["."],
            # ),
        ),
        server_info=types.ServerInfo(
            name="sbhacks12-server",
            version="0.1.0"
        )
    )


@server.feature(types.INITIALIZED)
def initialized(params: types.InitializedParams) -> None:
    """Handle the initialized notification."""
    logger.info("Server fully initialized and ready")


@server.feature(types.SHUTDOWN)
def shutdown(params: None) -> None:
    """Handle shutdown request."""
    logger.info("Server shutting down")


# Example feature: Handle document open
@server.feature(types.TEXT_DOCUMENT_DID_OPEN)
def did_open(params: types.DidOpenTextDocumentParams) -> None:
    """Handle document open notification."""
    logger.info(f"Document opened: {params.text_document.uri}")


# Example feature: Handle document close
@server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
def did_close(params: types.DidCloseTextDocumentParams) -> None:
    """Handle document close notification."""
    logger.info(f"Document closed: {params.text_document.uri}")


# Example feature: Handle document changes
@server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
def did_change(params: types.DidChangeTextDocumentParams) -> None:
    """Handle document change notification."""
    logger.info(f"Document changed: {params.text_document.uri}")


def main():
    """Start the language server."""
    logger.info("Starting SBHacks12 Language Server...")
    server.start_io()


if __name__ == "__main__":
    main()
