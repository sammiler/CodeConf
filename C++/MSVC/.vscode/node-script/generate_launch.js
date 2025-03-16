const fs = require('fs');
const path = require('path');

const baseConfig = {
    type: "cppvsdbg",
    request: "launch",
    args: [],
    stopAtEntry: true,
    cwd: "${workspaceFolder}/build/bin/Debug",
    environment: [],
    console: "externalTerminal",
    visualizerFile: "C:/Users/sammiler/MyFile/My Doc/Visual Studio 2022/Visualizers/qt5.natvis",
    environment: [
        {
            "name": "PATH",
            "value": "${env:PATH};C:/vcpkg/installed/x64-windows/debug/bin;"
        },
        {
            "name": "QT_PLUGIN_PATH",
            "value": "C:/vcpkg/installed/x64-windows/debug/plugins"
        },
        {
            "name": "QML_PATH",
            "value": "C:/vcpkg/installed/x64-windows/debug/bin"
        },
        {
            "name": "QML2_IMPORT_PATH",
            "value": "C:/vcpkg/installed/x64-windows/debug/qml"
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
const buildDir = path.join(__dirname, '../../build/bin/Debug'); // 修正为退一级
console.log(`Reading build directory: ${buildDir}`);
const executables = fs.readdirSync(buildDir).filter(f => f.endsWith('.exe'));
console.log(`Found executables: ${executables}`);
const configurations = executables.map(exe => ({
    name: `Debug ${path.parse(exe).name}`,
    program: `\${workspaceFolder}/build/bin/Debug/${exe}`,
    ...baseConfig
}));
const vscodeDir = path.join(__dirname, '../../');
const launchJsonPath = path.join(vscodeDir, '/.vscode/launch.json');
fs.mkdirSync(vscodeDir, { recursive: true });
fs.writeFileSync(launchJsonPath, JSON.stringify({ version: "0.2.0", configurations }, null, 4));

console.log("launch.json generated successfully!");