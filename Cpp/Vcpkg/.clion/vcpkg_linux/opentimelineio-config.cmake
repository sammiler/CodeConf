include_guard(GLOBAL)

# --- 路径设置 (保持不变) ---
set(BASE_INCLUDE_DIR "${CMAKE_CURRENT_LIST_DIR}/../../include")
set(OPENTIMELINEIO_INCLUDE_SUBDIR "${BASE_INCLUDE_DIR}/opentimelineio")
set(OPENTIME_INCLUDE_SUBDIR "${BASE_INCLUDE_DIR}/opentime")
set(OPENTIMELINEIO_INCLUDE_DIRS "${OPENTIMELINEIO_INCLUDE_SUBDIR}")

if(NOT EXISTS "${OPENTIMELINEIO_INCLUDE_SUBDIR}")
    message(FATAL_ERROR "OpenTimelineIO include directory ${OPENTIMELINEIO_INCLUDE_SUBDIR} does not exist!")
endif()
if(NOT EXISTS "${OPENTIME_INCLUDE_SUBDIR}")
    message(FATAL_ERROR "OpenTimelineIO include directory ${OPENTIME_INCLUDE_SUBDIR} does not exist!")
endif()

list(APPEND OPENTIMELINEIO_INCLUDE_DIRS ${OPENTIME_INCLUDE_SUBDIR} ${BASE_INCLUDE_DIR})

set(LIB_DIR "${CMAKE_CURRENT_LIST_DIR}/../../lib")
set(DEBUG_LIB_DIR "${CMAKE_CURRENT_LIST_DIR}/../../debug/lib")

if(NOT EXISTS "${LIB_DIR}")
    message(FATAL_ERROR "LIB_DIR ${LIB_DIR} does not exist!")
endif()
if(NOT EXISTS "${DEBUG_LIB_DIR}")
    message(FATAL_ERROR "DEBUG_LIB_DIR ${DEBUG_LIB_DIR} does not exist!")
endif()

# --- 检查文件存在性 (保持不变) ---
foreach(lib
        "${LIB_DIR}/libopentime.so"
        "${LIB_DIR}/libopentimelineio.so"
        "${DEBUG_LIB_DIR}/libopentime.so"
        "${DEBUG_LIB_DIR}/libopentimelineio.so"
)
    if(NOT EXISTS "${lib}")
        message(FATAL_ERROR "Library file ${lib} does not exist!")
    endif()
endforeach()

# --- 定义导入目标 OpenTimelineIO::opentime ---
if(NOT TARGET OpenTimelineIO::opentime)
    add_library(OpenTimelineIO::opentime SHARED IMPORTED)

    set_target_properties(OpenTimelineIO::opentime PROPERTIES
            INTERFACE_INCLUDE_DIRECTORIES "${OPENTIMELINEIO_INCLUDE_DIRS}" # 或者更具体的 OPENTIME_INCLUDE_SUBDIR
    )

    # Release 版本属性
    set_target_properties(OpenTimelineIO::opentime PROPERTIES
            IMPORTED_LOCATION_RELEASE "${LIB_DIR}/libopentime.so"
    )
    # Debug 版本属性
    set_target_properties(OpenTimelineIO::opentime PROPERTIES
            IMPORTED_LOCATION_DEBUG "${DEBUG_LIB_DIR}/libopentime.so"
    )
    # 明确声明支持的配置
    set_property(TARGET OpenTimelineIO::opentime APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
    set_property(TARGET OpenTimelineIO::opentime APPEND PROPERTY IMPORTED_CONFIGURATIONS DEBUG)
endif()

# --- 定义导入目标 OpenTimelineIO::OpenTimelineIO ---
if(NOT TARGET OpenTimelineIO::OpenTimelineIO)
    add_library(OpenTimelineIO::OpenTimelineIO SHARED IMPORTED)

    set_target_properties(OpenTimelineIO::OpenTimelineIO PROPERTIES
            INTERFACE_INCLUDE_DIRECTORIES "${OPENTIMELINEIO_INCLUDE_DIRS}"
            # 链接到 OpenTimelineIO::opentime 目标，而不是具体路径
            INTERFACE_LINK_LIBRARIES "OpenTimelineIO::opentime"
    )

    # Release 版本属性
    set_target_properties(OpenTimelineIO::OpenTimelineIO PROPERTIES
            IMPORTED_LOCATION_RELEASE "${LIB_DIR}/libopentimelineio.so"
    )
    # Debug 版本属性
    set_target_properties(OpenTimelineIO::OpenTimelineIO PROPERTIES
            IMPORTED_LOCATION_DEBUG "${DEBUG_LIB_DIR}/libopentimelineio.so"
    )
    # 明确声明支持的配置
    set_property(TARGET OpenTimelineIO::OpenTimelineIO APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
    set_property(TARGET OpenTimelineIO::OpenTimelineIO APPEND PROPERTY IMPORTED_CONFIGURATIONS DEBUG)
endif()

# 确保旧变量仍然可用（如果其他地方直接使用它们）
# 但理想情况下，消费者应该只链接到 OpenTimelineIO::OpenTimelineIO
set(OPENTIMELINEIO_LIBRARY OpenTimelineIO::OpenTimelineIO)
set(OPENTIMELINEIO_LIBRARIES OpenTimelineIO::OpenTimelineIO)

message(STATUS "OpenTimelineIO imported targets OpenTimelineIO::OpenTimelineIO and OpenTimelineIO::opentime configured.")
