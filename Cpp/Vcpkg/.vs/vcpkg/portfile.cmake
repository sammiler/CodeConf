
#该文件和vcpkg.json 放在 port/OpenTimelineIO 下面

# 设置源路径
set(SOURCE_PATH "C:/Qt/OpenTimelineIO/install_dir")

# 创建目标目录
file(MAKE_DIRECTORY ${CURRENT_PACKAGES_DIR}/lib)
file(MAKE_DIRECTORY ${CURRENT_PACKAGES_DIR}/debug/lib)
file(MAKE_DIRECTORY ${CURRENT_PACKAGES_DIR}/bin)
file(MAKE_DIRECTORY ${CURRENT_PACKAGES_DIR}/debug/bin)
file(MAKE_DIRECTORY ${CURRENT_PACKAGES_DIR}/include)

# 复制所有头文件（包括子文件夹）
file(COPY ${SOURCE_PATH}/include/ DESTINATION ${CURRENT_PACKAGES_DIR}/include)

# 复制 Release 版本的所有 .lib 文件
file(GLOB RELEASE_LIBS "${SOURCE_PATH}/Release/lib/*.lib")
file(COPY ${RELEASE_LIBS} DESTINATION ${CURRENT_PACKAGES_DIR}/lib)

# 复制 Release 版本的所有 .dll 文件
file(GLOB RELEASE_DLLS "${SOURCE_PATH}/Release/bin/*.dll")
file(COPY ${RELEASE_DLLS} DESTINATION ${CURRENT_PACKAGES_DIR}/bin)

# 复制 Debug 版本的所有 .lib 文件
file(GLOB DEBUG_LIBS "${SOURCE_PATH}/Debug/lib/*.lib")
file(COPY ${DEBUG_LIBS} DESTINATION ${CURRENT_PACKAGES_DIR}/debug/lib)

# 复制 Debug 版本的所有 .dll 文件
file(GLOB DEBUG_DLLS "${SOURCE_PATH}/Debug/bin/*.dll")
file(COPY ${DEBUG_DLLS} DESTINATION ${CURRENT_PACKAGES_DIR}/debug/bin)

# 安装 CMake 配置文件
file(COPY ${SOURCE_PATH}/cmake/OpenTimelineIO-config.cmake DESTINATION ${CURRENT_PACKAGES_DIR}/share/OpenTimelineIO)

# 可选：安装版权文件（如果有）
if(EXISTS "${SOURCE_PATH}/LICENSE.txt")
    vcpkg_install_copyright(FILE "${SOURCE_PATH}/LICENSE.txt")
endif()