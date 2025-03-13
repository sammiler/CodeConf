const fs = require('fs');
const path = require('path');

// 定义要添加的内容
const contentToAdd = `
#自动添加的配置
#添加头文件路径和库文件路径
include_directories($ENV{INCLUDE})
link_directories($ENV{LIB})

`;

// 指定 CMakeLists.txt 文件路径（假设在当前目录）
const cmakeFilePath = path.join(__dirname, "../../",'CMakeLists.txt');

// 读取文件内容
fs.readFile(cmakeFilePath, 'utf8', (err, data) => {
    if (err) {
        console.error('读取 CMakeLists.txt 失败:', err);
        return;
    }

    // 分割文件内容为行数组
    const lines = data.split('\n');
    
    // 查找 project(Poco) 的位置
    const projectIndex = lines.findIndex(line => line.trim().startsWith('project('));
    if (projectIndex === -1) {
        console.error('未找到 project(Poco)');
        return;
    }



    // 在 project(Poco) 下一行插入内容
    lines.splice(projectIndex + 1, 0, contentToAdd.trim());

    // 将修改后的内容写回文件
    const newContent = lines.join('\n');
    fs.writeFile(cmakeFilePath, newContent, 'utf8', (err) => {
        if (err) {
            console.error('写入 CMakeLists.txt 失败:', err);
            return;
        }
        console.log('成功将配置添加到 CMakeLists.txt');
    });
});