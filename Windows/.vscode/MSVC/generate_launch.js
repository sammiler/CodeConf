const fs = require('fs');
const path = require('path');

const baseConfig = {
    type: "cppvsdbg",
    request: "launch",
    args: [],
    stopAtEntry: true,
    cwd: "${workspaceFolder}/tempbuild/bin",
    environment: [],
    console: "externalTerminal",
    setupCommands: [
        { description: "Enable pretty-printing for gdb", text: "-enable-pretty-printing", ignoreFailures: true },
        { description: "Set charset to UTF-8", text: "set charset UTF-8", ignoreFailures: true } ,
        { description: "将反汇编风格设置为 Intel", text: "-gdb-set disassembly-flavor intel",ignoreFailures: true}
    ],
    environment: [
    {
        name: "PATH",
        value: "${env:PATH};C:/Program Files/MySQL/MySQL Server 8.0/lib;"
    }
    ],
    preLaunchTask: "cmake-build"
};

// 从 .vscode 退一级到根目录，再进入 build
const buildDir = path.join(__dirname, '../tempbuild/bin'); // 修正为退一级
console.log(`Reading build directory: ${buildDir}`);
const executables = fs.readdirSync(buildDir).filter(f => f.endsWith('.exe'));
console.log(`Found executables: ${executables}`);
const configurations = executables.map(exe => ({
    name: `Debug ${path.parse(exe).name}`,
    program: `\${workspaceFolder}/tempbuild/bin/${exe}`,
    ...baseConfig
}));
const vscodeDir = path.join(__dirname, '..');
const launchJsonPath = path.join(vscodeDir, '/.vscode/launch.json');
fs.mkdirSync(vscodeDir, { recursive: true });
fs.writeFileSync(launchJsonPath, JSON.stringify({ version: "0.2.0", configurations }, null, 4));

console.log("launch.json generated successfully!");