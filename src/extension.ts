import * as path from 'path';
import * as vscode from 'vscode';
import {
    LanguageClient,
    LanguageClientOptions,
    ServerOptions,
    TransportKind
} from 'vscode-languageclient/node';

let client: LanguageClient | undefined;

export function activate(context: vscode.ExtensionContext) {


    const didChangeEmitter = new vscode.EventEmitter<void>();

    context.subscriptions.push(vscode.lm.registerMcpServerDefinitionProvider('exampleProvider', {
        onDidChangeMcpServerDefinitions: didChangeEmitter.event,
        provideMcpServerDefinitions: async () => {
            let servers: vscode.McpServerDefinition[] = [];

        // Example of a simple stdio server definition
        servers.push(new vscode.McpStdioServerDefinition(
            'myServer',
            'python',
            ['server/server.py'],
            {
                TL_API_KEY: '',
                TL_ID: ''
            }
        ));

            return servers;
        },
        resolveMcpServerDefinition: async (server: vscode.McpStdioServerDefinition) => {

            if (server.label === 'myServer') {
                // Get the API key from the user, e.g. using vscode.window.showInputBox
                // Update the server definition with the API key
                const api_key = await vscode.window.showInputBox({ prompt: 'Enter your TwelveLabs API key' });
                const tl_id = await vscode.window.showInputBox({ prompt: 'Enter your TwelveLabs ID' });
                server.env = {
                    TL_API_KEY: api_key || '',
                    TL_ID: tl_id || ''
                };
            }

            // Return undefined to indicate that the server should not be started or throw an error
            // If there is a pending tool call, the editor will cancel it and return an error message
            // to the language model.
            return server;
        }
    }));




    // console.log('SBHacks12 extension is now active!');

    // // Register command to start the server
    // const startServerCommand = vscode.commands.registerCommand('sbhacks12.startServer', async () => {
    //     await startLanguageServer(context);
    // });

    // // Register command to stop the server
    // const stopServerCommand = vscode.commands.registerCommand('sbhacks12.stopServer', async () => {
    //     await stopLanguageServer();
    // });

    // context.subscriptions.push(startServerCommand, stopServerCommand);

    // // Auto-start the language server
    // startLanguageServer(context);
}

async function startLanguageServer(context: vscode.ExtensionContext) {
    if (client) {
        vscode.window.showInformationMessage('Language server is already running.');
        return;
    }

    // Path to the Python server script
    const serverPath = path.join(context.extensionPath, 'server', 'server.py');

    // Get Python path - try to use the uv virtual environment
    const pythonPath = getPythonPath(context.extensionPath);

    const serverOptions: ServerOptions = {
        command: pythonPath,
        args: [serverPath],
        transport: TransportKind.stdio
    };

    const clientOptions: LanguageClientOptions = {
        // Register the server for all documents
        documentSelector: [{ scheme: 'file', language: '*' }],
        synchronize: {
            // Notify the server about file changes
            fileEvents: vscode.workspace.createFileSystemWatcher('**/*')
        },
        outputChannelName: 'SBHacks12 Language Server'
    };

    client = new LanguageClient(
        'sbhacks12',
        'SBHacks12 Language Server',
        serverOptions,
        clientOptions
    );

    try {
        await client.start();
        vscode.window.showInformationMessage('Language server started successfully.');
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to start language server: ${error}`);
        client = undefined;
    }
}

async function stopLanguageServer() {
    if (!client) {
        vscode.window.showInformationMessage('Language server is not running.');
        return;
    }

    try {
        await client.stop();
        client = undefined;
        vscode.window.showInformationMessage('Language server stopped.');
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to stop language server: ${error}`);
    }
}

function getPythonPath(extensionPath: string): string {
    // Check for uv virtual environment first
    const uvVenvPath = path.join(extensionPath, '.venv', 'bin', 'python');
    
    // On Windows, use different path
    const isWindows = process.platform === 'win32';
    const venvPython = isWindows 
        ? path.join(extensionPath, '.venv', 'Scripts', 'python.exe')
        : uvVenvPath;

    // Try to get Python path from VS Code settings
    const pythonConfig = vscode.workspace.getConfiguration('python');
    const configuredPython = pythonConfig.get<string>('defaultInterpreterPath');
    
    if (configuredPython) {
        return configuredPython;
    }

    // Default to venv python or system python
    return venvPython;
}

export function deactivate(): Thenable<void> | undefined {
    if (!client) {
        return undefined;
    }
    return client.stop();
}
