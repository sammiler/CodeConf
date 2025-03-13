const fs = require('fs');
const path = require('path');

const baseConfig = {
    type: "cppvsdbg",
    request: "launch",
    args: [],
    stopAtEntry: true,
    cwd: "${workspaceFolder}/build/bin",
    environment: [],
    console: "externalTerminal",
    setupCommands: [
        { description: "Enable pretty-printing for gdb", text: "-enable-pretty-printing", ignoreFailures: true },
        { description: "Set charset to UTF-8", text: "set charset UTF-8", ignoreFailures: true } ,
        { description: "将反汇编风格设置为 Intel", text: "-gdb-set disassembly-flavor intel",ignoreFailures: true}
    ],
    environment: [
        {
            "name": "PATH",
            "value": "${env:PATH};C:/vcpkg/installed/x64-windows/debug/bin;C:/Qt/Qt5.9.5/5.9.5/msvc2017_64/bin;"
        },
        {
            "name": "QT_PLUGIN_PATH",
            "value": "C:/vcpkg/installed/x64-windows/debug/Qt6/plugins"
        },
        {
            "name": "QML_PATH",
            "value": "C:/vcpkg/installed/x64-windows/debug/bin"
        },
        {
            "name": "QML2_IMPORT_PATH",
            "value": "C:/vcpkg/installed/x64-windows/debug/Qt6/qml"
        }
    ],
    preLaunchTask: "cmake-build",
    console: "integratedTerminal",
    sourceFileMap: {
        "C:/vcpkg/installed/x64-windows/debug": "C:/vcpkg/buildtrees/qtbase/src/here-src-6-c23658a936.clean/src",
        "C:/vcpkg/installed/x64-windows": "C:/vcpkg/buildtrees/qtbase/src/here-src-6-c23658a936.clean/src"
    }
};

// 从 .vscode 退一级到根目录，再进入 build
const buildDir = path.join(__dirname, '../../build/bin'); // 修正为退一级
console.log(`Reading build directory: ${buildDir}`);
const executables = fs.readdirSync(buildDir).filter(f => f.endsWith('.exe'));
console.log(`Found executables: ${executables}`);
const configurations = executables.map(exe => ({
    name: `Debug ${path.parse(exe).name}`,
    program: `\${workspaceFolder}/build/bin/${exe}`,
    ...baseConfig
}));
const vscodeDir = path.join(__dirname, '../../');
const launchJsonPath = path.join(vscodeDir, '/.vscode/launch.json');
fs.mkdirSync(vscodeDir, { recursive: true });
fs.writeFileSync(launchJsonPath, JSON.stringify({ version: "0.2.0", configurations }, null, 4));

console.log("launch.json generated successfully!");