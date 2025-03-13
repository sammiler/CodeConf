// .vscode/node-script/generate-qrc.js
const fs = require('fs').promises;
const path = require('path');

async function generateQrc() {
    const rootDir = path.resolve(__dirname, '../..');
    
    // 检查是否为Qt项目
    const cmakePath = path.join(rootDir, 'CMakeLists.txt');
    try {
        const cmakeContent = await fs.readFile(cmakePath, 'utf8');
        if (!cmakeContent.includes('find_package(Qt')) {
            console.log('不是Qt项目，未找到find_package(Qt)');
            process.exit(0);
        }
    } catch (error) {
        console.log('未找到CMakeLists.txt或读取失败');
        process.exit(0);
    }

    const utilDir = path.join(rootDir, '.vscode/util');
    const qrcJsonPath = path.join(utilDir, 'qrc-snippets.json');
    const defaultQrc = {
        "run": true,
        "ignore": ["h", "cpp", "c", "hpp", "mm", "qml", "js", "ui", "json", "sh", "webp", "txt", ".qrc"],
        "ignoreName": ["忽略的文件名1", "忽略的文件名2"],
        "resources": [
            { "path": "是相对于根目录的路径1", "prefix": "/" },
            { "path": "是相对于根目录的路径2", "prefix": "/" }
        ]
    };

    let qrcConfig;
    try {
        await fs.access(qrcJsonPath);
        qrcConfig = JSON.parse(await fs.readFile(qrcJsonPath, 'utf8'));
    } catch (error) {
        await fs.mkdir(utilDir, { recursive: true });
        await fs.writeFile(qrcJsonPath, JSON.stringify(defaultQrc, null, 2));
        qrcConfig = defaultQrc;
    }

    if (qrcConfig.run !== true) {
        console.log('run属性为false，脚本退出');
        process.exit(0);
    }

    async function getFilesRecursively(dir, ignoreExts, ignoreNames) { // 修改函数参数
        let results = [];
        const list = await fs.readdir(dir, { withFileTypes: true });
        for (const file of list) {
            const fullPath = path.join(dir, file.name);
            const relativePath = path.relative(rootDir, fullPath).replace(/\\/g, '/');
            if (file.isDirectory()) {
                results = results.concat(await getFilesRecursively(fullPath, ignoreExts, ignoreNames)); // 递归调用时传递 ignoreNames
            } else {
                const ext = path.extname(file.name).slice(1);
                if (!ignoreExts.includes(ext) && !ignoreNames.includes(file.name)) { // 增加 ignoreNames 判断
                    results.push(relativePath);
                }
            }
        }
        return results;
    }

    const newSnippets = {};

    for (const resource of qrcConfig.resources) {
        const sourceDir = path.join(rootDir, resource.path);
        const files = await getFilesRecursively(sourceDir, qrcConfig.ignore,qrcConfig.ignoreName);
        
        let xmlContent = '<RCC>\n';
        xmlContent += `    <qresource prefix="${resource.prefix}">\n`;
        
        for (const file of files) {
            const relativePath = path.relative(resource.path, file).replace(/\\/g, '/');
            xmlContent += `        <file>${relativePath}</file>\n`;

            // 根据 prefix 生成资源路径
            const resourcePath = resource.prefix === '/' 
                ? `":/${relativePath}"` 
                : `":${resource.prefix}/${relativePath}"`;
            const fileName = path.basename(relativePath);
            const snippetName = `qrc_${relativePath.replace(/\//g, '_')}`;
            newSnippets[snippetName] = {
                "prefix": fileName,
                "body": [resourcePath],
                "description": `Qt resource path for ${relativePath}`,
                "scope": "cpp,qml" // 只在 C++ 中生效
            };
        }
        
        xmlContent += '    </qresource>\n';
        xmlContent += '</RCC>\n';

        const outputPath = path.join(sourceDir, 'resources.qrc');
        await fs.writeFile(outputPath, xmlContent);
        console.log(`已生成: ${outputPath}`);
    }

    // 生成 .vscode 下的 .code-snippets 文件
    const snippetsDir = path.join(rootDir, '.vscode');
    const snippetsPath = path.join(snippetsDir, 'qrc.code-snippets');
    let existingSnippets = {};

    try {
        await fs.access(snippetsPath);
        existingSnippets = JSON.parse(await fs.readFile(snippetsPath, 'utf8'));
    } catch (error) {
        console.log('未找到现有snippets文件，将创建新的');
    }

    const updatedSnippets = {
        ...existingSnippets,
        ...newSnippets
    };

    await fs.mkdir(snippetsDir, { recursive: true });
    await fs.writeFile(snippetsPath, JSON.stringify(updatedSnippets, null, 2));
    console.log(`已更新代码片段: ${snippetsPath}`);
}

generateQrc().catch(console.error);