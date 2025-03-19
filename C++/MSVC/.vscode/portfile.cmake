if("subpixel-rendering" IN_LIST FEATURES)
    set(SUBPIXEL_RENDERING_PATCH "subpixel-rendering.patch")
endif()

string(REPLACE "." "-" VERSION_HYPHEN "${VERSION}")
#以防外一vcpkg无法下载的情况
set(FREETYPE_ARCHIVE "C:/vcpkg/downloads/freetype-VER-2-13-3.tar.gz")
# 设置 SOURCE_PATH 到嵌套的实际源代码目录
set(SOURCE_PATH "${CURRENT_BUILDTREES_DIR}/src/freetype-2.13.3/freetype-2.13.3")

# 解压到上一级目录
vcpkg_extract_source_archive(
    "${FREETYPE_ARCHIVE}"
    "${CURRENT_BUILDTREES_DIR}/src/freetype-2.13.3"
)

# 应用补丁，使用正确的 SOURCE_PATH
vcpkg_apply_patches(
    SOURCE_PATH "${SOURCE_PATH}"
    PATCHES
        0003-Fix-UWP.patch
        brotli-static.patch
        bzip2.patch
        fix-exports.patch
        ${SUBPIXEL_RENDERING_PATCH}
)

vcpkg_check_features(OUT_FEATURE_OPTIONS FEATURE_OPTIONS
    FEATURES
        zlib          FT_REQUIRE_ZLIB
        bzip2         FT_REQUIRE_BZIP2
        error-strings FT_ENABLE_ERROR_STRINGS
        png           FT_REQUIRE_PNG
        brotli        FT_REQUIRE_BROTLI
    INVERTED_FEATURES
        zlib          FT_DISABLE_ZLIB
        bzip2         FT_DISABLE_BZIP2
        png           FT_DISABLE_PNG
        brotli        FT_DISABLE_BROTLI
)

vcpkg_cmake_configure(
    SOURCE_PATH "${SOURCE_PATH}"
    OPTIONS
        -DFT_DISABLE_HARFBUZZ=ON
        ${FEATURE_OPTIONS}
)

vcpkg_cmake_install()
vcpkg_copy_pdbs()
vcpkg_cmake_config_fixup(CONFIG_PATH lib/cmake/freetype)

# Rename for easy usage (VS integration; CMake and autotools will not care)
file(RENAME "${CURRENT_PACKAGES_DIR}/include/freetype2/freetype" "${CURRENT_PACKAGES_DIR}/include/freetype")
file(RENAME "${CURRENT_PACKAGES_DIR}/include/freetype2/ft2build.h" "${CURRENT_PACKAGES_DIR}/include/ft2build.h")
file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/include/freetype2")
file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/include")

# Fix the include dir [freetype2 -> freetype]
file(READ "${CURRENT_PACKAGES_DIR}/share/freetype/freetype-targets.cmake" CONFIG_MODULE)
string(REPLACE "\${_IMPORT_PREFIX}/include/freetype2" "\${_IMPORT_PREFIX}/include" CONFIG_MODULE "${CONFIG_MODULE}")
string(REPLACE "\${_IMPORT_PREFIX}/lib/brotlicommon-static.lib" [[\$<\$<NOT:\$<CONFIG:DEBUG>>:${_IMPORT_PREFIX}/lib/brotlicommon-static.lib>;\$<\$<CONFIG:DEBUG>:${_IMPORT_PREFIX}/debug/lib/brotlicommon-static.lib>]] CONFIG_MODULE "${CONFIG_MODULE}")
string(REPLACE "\${_IMPORT_PREFIX}/lib/brotlidec-static.lib" [[\$<\$<NOT:\$<CONFIG:DEBUG>>:${_IMPORT_PREFIX}/lib/brotlidec-static.lib>;\$<\$<CONFIG:DEBUG>:${_IMPORT_PREFIX}/debug/lib/brotlidec-static.lib>]] CONFIG_MODULE "${CONFIG_MODULE}")
string(REPLACE "\${_IMPORT_PREFIX}/lib/brotlidec.lib" [[\$<\$<NOT:\$<CONFIG:DEBUG>>:${_IMPORT_PREFIX}/lib/brotlidec.lib>;\$<\$<CONFIG:DEBUG>:${_IMPORT_PREFIX}/debug/lib/brotlidec.lib>]] CONFIG_MODULE "${CONFIG_MODULE}")
string(REPLACE "\${_IMPORT_PREFIX}/lib/brotlidec.lib" [[\$<\$<NOT:\$<CONFIG:DEBUG>>:${_IMPORT_PREFIX}/lib/brotlidec.lib>;\$<\$<CONFIG:DEBUG>:${_IMPORT_PREFIX}/debug/lib/brotlidec.lib>]] CONFIG_MODULE "${CONFIG_MODULE}")
file(WRITE ${CURRENT_PACKAGES_DIR}/share/freetype/freetype-targets.cmake "${CONFIG_MODULE}")

find_library(FREETYPE_DEBUG NAMES freetyped PATHS "${CURRENT_PACKAGES_DIR}/debug/lib/" NO_DEFAULT_PATH)
if(NOT VCPKG_BUILD_TYPE)
    file(READ "${CURRENT_PACKAGES_DIR}/debug/lib/pkgconfig/freetype2.pc" _contents)
    if(FREETYPE_DEBUG)
        string(REPLACE "-lfreetype" "-lfreetyped" _contents "${_contents}")
    endif()
    string(REPLACE "-I\${includedir}/freetype2" "-I\${includedir}" _contents "${_contents}")
    file(WRITE "${CURRENT_PACKAGES_DIR}/debug/lib/pkgconfig/freetype2.pc" "${_contents}")
endif()

file(READ "${CURRENT_PACKAGES_DIR}/lib/pkgconfig/freetype2.pc" _contents)
string(REPLACE "-I\${includedir}/freetype2" "-I\${includedir}" _contents "${_contents}")
file(WRITE "${CURRENT_PACKAGES_DIR}/lib/pkgconfig/freetype2.pc" "${_contents}")


vcpkg_fixup_pkgconfig()

file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/include")
file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/share")

if(VCPKG_TARGET_IS_WINDOWS)
  set(dll_linkage 1)
  if(VCPKG_LIBRARY_LINKAGE STREQUAL "static")
    set(dll_linkage 0)
  endif()
  vcpkg_replace_string("${CURRENT_PACKAGES_DIR}/include/freetype/config/public-macros.h" "#elif defined( DLL_IMPORT )" "#elif ${dll_linkage}")
endif()

configure_file("${CMAKE_CURRENT_LIST_DIR}/vcpkg-cmake-wrapper.cmake"
    "${CURRENT_PACKAGES_DIR}/share/${PORT}/vcpkg-cmake-wrapper.cmake" @ONLY)
file(INSTALL "${CMAKE_CURRENT_LIST_DIR}/usage" DESTINATION "${CURRENT_PACKAGES_DIR}/share/${PORT}")
vcpkg_install_copyright(
    FILE_LIST
        "${SOURCE_PATH}/LICENSE.TXT"
        "${SOURCE_PATH}/docs/FTL.TXT"
        "${SOURCE_PATH}/docs/GPLv2.TXT"
)
