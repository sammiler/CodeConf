#该文件放在源目录cmake文件夹下
set(BASE_INCLUDE_DIR "${CMAKE_CURRENT_LIST_DIR}/../../include")
set(OPENTIMELINEIO_INCLUDE_SUBDIR "${BASE_INCLUDE_DIR}/opentimelineio")
set(OPENTIMELINEIO_INCLUDE_DIRS "${OPENTIMELINEIO_INCLUDE_SUBDIR}")

if(NOT EXISTS "${OPENTIMELINEIO_INCLUDE_SUBDIR}")
    message(FATAL_ERROR "OpenTimelineIO include directory ${OPENTIMELINEIO_INCLUDE_SUBDIR} does not exist!")
endif()

file(GLOB_RECURSE ALL_FILES "${OPENTIMELINEIO_INCLUDE_SUBDIR}/*.h" "${OPENTIMELINEIO_INCLUDE_SUBDIR}/*.hpp")
if(NOT ALL_FILES)
    message(WARNING "No header files found in ${OPENTIMELINEIO_INCLUDE_SUBDIR}")
endif()

function(add_parent_dirs DIR_PATH INCLUDE_LIST)
    file(TO_CMAKE_PATH "${DIR_PATH}" CURRENT_DIR)
    file(TO_CMAKE_PATH "${OPENTIMELINEIO_INCLUDE_SUBDIR}" NORMALIZED_SUBDIR)
    file(TO_CMAKE_PATH "${BASE_INCLUDE_DIR}" NORMALIZED_BASE_DIR)
    set(ITERATION 0)
    while(TRUE)
        list(APPEND ${INCLUDE_LIST} "${CURRENT_DIR}")
        get_filename_component(PARENT_DIR "${CURRENT_DIR}" DIRECTORY)
        file(TO_CMAKE_PATH "${PARENT_DIR}" PARENT_DIR)
        if("${PARENT_DIR}" STREQUAL "${NORMALIZED_SUBDIR}" OR 
           "${PARENT_DIR}" STREQUAL "${NORMALIZED_BASE_DIR}" OR 
           "${PARENT_DIR}" STREQUAL "" OR 
           "${CURRENT_DIR}" STREQUAL "${PARENT_DIR}")
            break()
        endif()
        set(CURRENT_DIR "${PARENT_DIR}")
        math(EXPR ITERATION "${ITERATION} + 1")
        if(ITERATION GREATER 100)
            message(FATAL_ERROR "Infinite loop detected in add_parent_dirs: CURRENT_DIR = ${CURRENT_DIR}")
        endif()
    endwhile()
    set(${INCLUDE_LIST} ${${INCLUDE_LIST}} PARENT_SCOPE)
endfunction()

foreach(FILE ${ALL_FILES})
    get_filename_component(FILE_DIR "${FILE}" DIRECTORY)
    add_parent_dirs("${FILE_DIR}" OPENTIMELINEIO_INCLUDE_DIRS)
endforeach()
list(REMOVE_DUPLICATES OPENTIMELINEIO_INCLUDE_DIRS)

set(LIB_DIR "${CMAKE_CURRENT_LIST_DIR}/../../lib")
set(BIN_DIR "${CMAKE_CURRENT_LIST_DIR}/../../bin")
set(DEBUG_LIB_DIR "${CMAKE_CURRENT_LIST_DIR}/../../debug/lib")
set(DEBUG_BIN_DIR "${CMAKE_CURRENT_LIST_DIR}/../../debug/bin")

if(NOT EXISTS "${LIB_DIR}")
    message(FATAL_ERROR "LIB_DIR ${LIB_DIR} does not exist!")
endif()
if(NOT EXISTS "${DEBUG_LIB_DIR}")
    message(FATAL_ERROR "DEBUG_LIB_DIR ${DEBUG_LIB_DIR} does not exist!")
endif()
if(NOT EXISTS "${BIN_DIR}")
    message(FATAL_ERROR "BIN_DIR ${BIN_DIR} does not exist!")
endif()
if(NOT EXISTS "${DEBUG_BIN_DIR}")
    message(FATAL_ERROR "DEBUG_BIN_DIR ${DEBUG_BIN_DIR} does not exist!")
endif()

# 定义导入目标 OpenTimelineIO::opentimelineio
add_library(OpenTimelineIO::OpenTimelineIO SHARED IMPORTED)

# 设置 Release 版本属性
set_target_properties(OpenTimelineIO::OpenTimelineIO PROPERTIES
    IMPORTED_LOCATION "${BIN_DIR}/opentimelineio.dll"
    IMPORTED_IMPLIB "${LIB_DIR}/opentimelineio.lib"
    INTERFACE_INCLUDE_DIRECTORIES "${OPENTIMELINEIO_INCLUDE_DIRS}"
    INTERFACE_LINK_LIBRARIES "${LIB_DIR}/opentime.lib"
)

# 设置 Debug 版本属性
set_target_properties(OpenTimelineIO::OpenTimelineIO PROPERTIES
    IMPORTED_LOCATION_DEBUG "${DEBUG_BIN_DIR}/opentimelineiod.dll"
    IMPORTED_IMPLIB_DEBUG "${DEBUG_LIB_DIR}/opentimelineiod.lib"
    INTERFACE_LINK_LIBRARIES_DEBUG "${DEBUG_LIB_DIR}/opentimed.lib"
)

# 检查文件存在性
foreach(lib "${LIB_DIR}/opentime.lib" "${BIN_DIR}/opentimelineio.dll" "${DEBUG_LIB_DIR}/opentimed.lib" "${DEBUG_BIN_DIR}/opentimelineiod.dll")
    if(NOT EXISTS "${lib}")
        message(FATAL_ERROR "Library file ${lib} does not exist!")
    endif()
endforeach()
