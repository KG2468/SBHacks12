import * as path from 'path';
import * as fs from 'fs';
import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {


    const didChangeEmitter = new vscode.EventEmitter<void>();

    context.subscriptions.push(vscode.lm.registerMcpServerDefinitionProvider('Visual Testing MCP', {
        onDidChangeMcpServerDefinitions: didChangeEmitter.event,
        provideMcpServerDefinitions: async () => {
            let servers: vscode.McpServerDefinition[] = [];

            // Get workspace folder for proper paths
            const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || context.extensionPath;
            const serverPath = path.join(workspaceFolder, 'server', 'server.py');
            const pythonPath = path.join(workspaceFolder, '.venv', 'bin', 'python');

            // Load environment variables from .env file if it exists
            let envVars: Record<string, string> = {
                TL_API_KEY: '',
                TL_ID: ''
            };
            
            const envFilePath = path.join(workspaceFolder, '.env');
            if (fs.existsSync(envFilePath)) {
                const envContent = fs.readFileSync(envFilePath, 'utf-8');
                for (const line of envContent.split('\n')) {
                    const trimmedLine = line.trim();
                    if (trimmedLine && !trimmedLine.startsWith('#')) {
                        const match = trimmedLine.match(/^([^=]+)=['"]?([^'"]*)['"]?$/);
                        if (match) {
                            envVars[match[1].trim()] = match[2].trim();
                        }
                    }
                }
            }

            // Use the venv python if it exists, otherwise fall back to system python
            const pythonCommand = fs.existsSync(pythonPath) ? pythonPath : 'python';

            const serverDef = new vscode.McpStdioServerDefinition(
                'myServer',
                pythonCommand,
                [serverPath],
                envVars
            );
            // Set the working directory to the workspace folder
            (serverDef as any).cwd = workspaceFolder;
            
            servers.push(serverDef);

            return servers;
        },
        resolveMcpServerDefinition: async (server: vscode.McpStdioServerDefinition) => {

            if (server.label === 'myServer') {
                // Only prompt for values that are missing
                const currentEnv = server.env || {};
                
                if (!currentEnv.TL_API_KEY) {
                    const api_key = await vscode.window.showInputBox({ 
                        prompt: 'Enter your TwelveLabs API key',
                        ignoreFocusOut: true
                    });
                    if (api_key === undefined) {
                        // User cancelled
                        return undefined;
                    }
                    currentEnv.TL_API_KEY = api_key;
                }
                
                if (!currentEnv.TL_ID) {
                    const tl_id = await vscode.window.showInputBox({ 
                        prompt: 'Enter your TwelveLabs Index ID',
                        ignoreFocusOut: true
                    });
                    if (tl_id === undefined) {
                        // User cancelled
                        return undefined;
                    }
                    currentEnv.TL_ID = tl_id;
                }
                
                server.env = currentEnv;
            }

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
    // Nothing to clean up - MCP servers are managed by VS Code
    return undefined;
}
