// .vscode/node-script/copy-dlls.js
const fs = require('fs').promises;
const path = require('path');

// 定义源目录（根目录）和目标目录
const sourceDir = path.resolve(__dirname, '../../'); // 回到根目录
const targetDir = path.resolve(sourceDir, 'build/bin/Debug');

// 确保目标目录存在
async function ensureTargetDir() {
    try {
        await fs.mkdir(targetDir, { recursive: true });
    } catch (err) {
        console.error('创建目标目录失败:', err);
        process.exit(1);
    }
}

// 递归查找所有 DLL 文件
async function findDllFiles(dir) {
    let dllFiles = [];
    try {
        const entries = await fs.readdir(dir, { withFileTypes: true });
        
        for (const entry of entries) {
            const fullPath = path.join(dir, entry.name);
            
            if (entry.isDirectory()) {
                // 递归处理子目录
                const subDirDlls = await findDllFiles(fullPath);
                dllFiles = dllFiles.concat(subDirDlls);
            } else if (entry.isFile() && 
                      path.extname(entry.name).toLowerCase() === '.dll') {
                // 添加 DLL 文件
                dllFiles.push(fullPath);
            }
        }
        
        return dllFiles;
    } catch (err) {
        console.error(`读取目录 ${dir} 时出错:`, err);
        return dllFiles;
    }
}

// 复制 DLL 文件
async function copyDllFiles() {
    try {
        // 获取所有 DLL 文件路径
        const dllFiles = await findDllFiles(sourceDir);

        if (dllFiles.length === 0) {
            console.log('未找到任何 DLL 文件');
            return;
        }

        // 复制每个 DLL 文件
        for (const sourcePath of dllFiles) {
            const fileName = path.basename(sourcePath);
            const targetPath = path.join(targetDir, fileName);
            
            await fs.copyFile(sourcePath, targetPath);
            console.log(`已复制: ${sourcePath} -> ${targetPath}`);
        }
        
        console.log(`完成！共复制 ${dllFiles.length} 个 DLL 文件`);
    } catch (err) {
        console.error('复制 DLL 文件时出错:', err);
        process.exit(1);
    }
}

// 主执行函数
async function main() {
    console.log('开始复制 DLL 文件...');
    console.log('源目录:', sourceDir);
    console.log('目标目录:', targetDir);
    
    await ensureTargetDir();
    await copyDllFiles();
}

// 运行
main().catch(err => {
    console.error('脚本执行失败:', err);
    process.exit(1);
});