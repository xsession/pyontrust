# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2025 Pyontrust Contributors
#
# Testbench CMake integration for Renode simulation.
#
# Inspired by Swedish Embedded SDK testbench architecture.
# Provides the following build targets:
#   - testbench:            Run interactive simulation (Renode console)
#   - testbench_xwt:        Run with Renode GUI (X Window)
#   - boardbench:           Run board-level simulation
#   - appbench:             Run app-specific simulation
#   - appbench_debugserver:  Run simulation + GDB server on port 3333
#   - robotbench:           Run automated RobotFramework tests
#
# Usage in your application CMakeLists.txt:
#   include(${PYONTRUST_BASE}/testbench/CMakeLists.txt)
#
# Or add to your prj.conf:
#   CONFIG_TESTBENCH=y
#

# ── Find tools ────────────────────────────────────────────────────────

find_program(RENODE renode HINTS
    "C:/Program Files/Renode/bin"
    "/opt/renode"
    "$ENV{HOME}/.local/bin"
)
find_program(RENODE_TEST NAMES renode-test renode-test.bat renode-test.exe HINTS
    "C:/Program Files/Renode/bin"
    "/opt/renode"
)

set(RENODE_TEST_COMMAND ${RENODE_TEST})
if(CMAKE_HOST_WIN32 AND RENODE_TEST AND NOT RENODE_TEST STREQUAL "RENODE_TEST-NOTFOUND")
    get_filename_component(RENODE_BIN_DIR "${RENODE_TEST}" DIRECTORY)
    get_filename_component(RENODE_ROOT_DIR "${RENODE_BIN_DIR}" DIRECTORY)
    set(RENODE_TEST_RUNNER "${RENODE_ROOT_DIR}/tests/run_tests.py")
    if(EXISTS "${RENODE_TEST_RUNNER}")
        if(NOT Python3_EXECUTABLE)
            find_package(Python3 REQUIRED COMPONENTS Interpreter)
        endif()
        set(RENODE_TEST_COMMAND
            ${Python3_EXECUTABLE}
            "${RENODE_TEST_RUNNER}"
            --css-file "${RENODE_ROOT_DIR}/tests/robot.css"
            --exclude skip_windows
            --robot-framework-remote-server-full-directory "${RENODE_ROOT_DIR}/bin"
        )
    endif()
endif()

if(NOT RENODE)
    message(STATUS "Renode not found — testbench targets will not be available")
    return()
endif()

message(STATUS "Renode found at: ${RENODE}")

# ── Resolve paths ─────────────────────────────────────────────────────

# PYONTRUST_BASE: root of the pin_configurator package
if(NOT DEFINED PYONTRUST_BASE)
    set(PYONTRUST_BASE "${CMAKE_CURRENT_LIST_DIR}/..")
endif()

set(RENODE_COMMON_SCRIPT "${APPLICATION_BINARY_DIR}/pincfg-renode-common.resc")
set(RENODE_COMMON_CONTENT
    "set bin @${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}\n"
    "set APPLICATION_BINARY_DIR @${APPLICATION_BINARY_DIR}\n"
)

if(DEFINED PROJECT_BASE)
    string(APPEND RENODE_COMMON_CONTENT "set PROJECT_BASE @${PROJECT_BASE}\n")
endif()

file(GENERATE OUTPUT "${RENODE_COMMON_SCRIPT}" CONTENT "${RENODE_COMMON_CONTENT}")

set(RENODE_RESULTS_DIR "${APPLICATION_BINARY_DIR}/robot-results")

# ── Board-level testbench ─────────────────────────────────────────────
# Look for <board>.resc in the board directory

if(DEFINED BOARD_DIR AND EXISTS "${BOARD_DIR}/${BOARD}.resc")
    set(BOARD_BENCH_SCRIPT "${APPLICATION_BINARY_DIR}/pincfg-boardbench.resc")
    set(BOARD_BENCH_CONTENT
        "include @${RENODE_COMMON_SCRIPT}\n"
        "include @${BOARD_DIR}/${BOARD}.resc\n"
        "start\n"
    )
    file(GENERATE OUTPUT "${BOARD_BENCH_SCRIPT}" CONTENT "${BOARD_BENCH_CONTENT}")

    add_custom_target(
        boardbench
        COMMAND ${RENODE} --console --disable-xwt
            -e "include @${BOARD_BENCH_SCRIPT}"
        COMMENT "Running board-level Renode simulation"
        WORKING_DIRECTORY ${APPLICATION_BINARY_DIR}
        DEPENDS ${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}
        USES_TERMINAL
    )

    add_custom_target(
        boardbench_xwt
        COMMAND ${RENODE}
            -e "include @${BOARD_BENCH_SCRIPT}"
        COMMENT "Running board-level Renode simulation (GUI)"
        WORKING_DIRECTORY ${APPLICATION_BINARY_DIR}
        DEPENDS ${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}
        USES_TERMINAL
    )
else()
    add_custom_target(
        boardbench
        COMMAND ${CMAKE_COMMAND} -E echo
            "No board-level .resc file found for ${BOARD}"
        COMMENT "No board-level simulation available"
    )
endif()

# ── Application-level testbench ───────────────────────────────────────
# Look for boards/<board>.resc in the application source directory

if(EXISTS "${APPLICATION_SOURCE_DIR}/boards/${BOARD}.resc")
    set(APP_BENCH_SCRIPT "${APPLICATION_BINARY_DIR}/pincfg-appbench.resc")
    set(APP_BENCH_DEBUG_SCRIPT "${APPLICATION_BINARY_DIR}/pincfg-appbench-debug.resc")
    set(APP_BENCH_CONTENT
        "include @${RENODE_COMMON_SCRIPT}\n"
        "include @${APPLICATION_SOURCE_DIR}/boards/${BOARD}.resc\n"
        "start\n"
    )
    set(APP_BENCH_DEBUG_CONTENT
        "include @${RENODE_COMMON_SCRIPT}\n"
        "machine StartGdbServer 3333\n"
        "include @${APPLICATION_SOURCE_DIR}/boards/${BOARD}.resc\n"
    )
    file(GENERATE OUTPUT "${APP_BENCH_SCRIPT}" CONTENT "${APP_BENCH_CONTENT}")
    file(GENERATE OUTPUT "${APP_BENCH_DEBUG_SCRIPT}" CONTENT "${APP_BENCH_DEBUG_CONTENT}")

    add_custom_target(
        appbench
        COMMAND ${RENODE} --console --disable-xwt
            -e "include @${APP_BENCH_SCRIPT}"
        COMMENT "Running application-specific Renode simulation"
        WORKING_DIRECTORY ${APPLICATION_BINARY_DIR}
        DEPENDS ${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}
        USES_TERMINAL
    )

    add_custom_target(
        appbench_xwt
        COMMAND ${RENODE}
            -e "include @${APP_BENCH_SCRIPT}"
        COMMENT "Running application Renode simulation (GUI)"
        WORKING_DIRECTORY ${APPLICATION_BINARY_DIR}
        DEPENDS ${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}
        USES_TERMINAL
    )

    # App bench with GDB debug server on port 3333
    add_custom_target(
        appbench_debugserver
        COMMAND ${RENODE} --console --disable-xwt
            -e "include @${APP_BENCH_DEBUG_SCRIPT}"
        COMMENT "Running Renode simulation + GDB server on :3333"
        WORKING_DIRECTORY ${APPLICATION_BINARY_DIR}
        DEPENDS ${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}
        USES_TERMINAL
    )
else()
    add_custom_target(
        appbench
        COMMAND ${CMAKE_COMMAND} -E echo
            "No application .resc found at ${APPLICATION_SOURCE_DIR}/boards/${BOARD}.resc"
        COMMENT "No application-level simulation available"
    )
endif()

# ── Testbench (Kconfig-selected) ──────────────────────────────────────
# Activated by CONFIG_TESTBENCH_<name>=y, uses testbench/<name>/ directory

if(DEFINED TESTBENCH AND EXISTS "${PYONTRUST_BASE}/testbench/${TESTBENCH}/testbench.resc")
    set(TESTBENCH_DIR "${PYONTRUST_BASE}/testbench/${TESTBENCH}")
    set(TESTBENCH_SCRIPT "${APPLICATION_BINARY_DIR}/pincfg-testbench.resc")
    set(TESTBENCH_DEBUG_SCRIPT "${APPLICATION_BINARY_DIR}/pincfg-testbench-debug.resc")
    set(TESTBENCH_CONTENT
        "include @${RENODE_COMMON_SCRIPT}\n"
        "include @${TESTBENCH_DIR}/testbench.resc\n"
        "s\n"
    )
    set(TESTBENCH_DEBUG_CONTENT
        "include @${RENODE_COMMON_SCRIPT}\n"
        "include @${TESTBENCH_DIR}/testbench.resc\n"
        "machine StartGdbServer 3333\n"
    )
    file(GENERATE OUTPUT "${TESTBENCH_SCRIPT}" CONTENT "${TESTBENCH_CONTENT}")
    file(GENERATE OUTPUT "${TESTBENCH_DEBUG_SCRIPT}" CONTENT "${TESTBENCH_DEBUG_CONTENT}")

    add_custom_target(
        testbench
        COMMAND ${RENODE} --console --disable-xwt
            -e "include @${TESTBENCH_SCRIPT}"
        COMMENT "Running testbench: ${TESTBENCH}"
        WORKING_DIRECTORY ${APPLICATION_BINARY_DIR}
        DEPENDS ${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}
        USES_TERMINAL
    )

    add_custom_target(
        testbench_xwt
        COMMAND ${RENODE}
            -e "include @${TESTBENCH_SCRIPT}"
        COMMENT "Running testbench (GUI): ${TESTBENCH}"
        WORKING_DIRECTORY ${APPLICATION_BINARY_DIR}
        DEPENDS ${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}
        USES_TERMINAL
    )

    add_custom_target(
        testbench_debugserver
        COMMAND ${RENODE} --console --disable-xwt
            -e "include @${TESTBENCH_DEBUG_SCRIPT}"
        COMMENT "Running testbench + GDB server: ${TESTBENCH}"
        WORKING_DIRECTORY ${APPLICATION_BINARY_DIR}
        DEPENDS ${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}
        USES_TERMINAL
    )
else()
    add_custom_target(
        testbench
        COMMAND ${CMAKE_COMMAND} -E echo
            "No testbench configured. Set TESTBENCH variable or CONFIG_TESTBENCH_<name>=y"
        COMMENT "No testbench available"
    )
endif()

# ── RobotFramework automated testing ──────────────────────────────────
# Looks for testbench.robot in the testbench directory

if(RENODE_TEST AND DEFINED TESTBENCH
   AND EXISTS "${PYONTRUST_BASE}/testbench/${TESTBENCH}/testbench.robot")

    add_custom_target(
        robotbench
        COMMAND
            ${CMAKE_COMMAND} -E env
                PROJECT_BASE=${PROJECT_BASE}
                APPLICATION_BINARY_DIR=${APPLICATION_BINARY_DIR}
                APPLICATION_SOURCE_DIR=${APPLICATION_SOURCE_DIR}
                BOARD=${BOARD}
            ${RENODE_TEST_COMMAND} --show-log
                --results-dir ${RENODE_RESULTS_DIR}
                ${PYONTRUST_BASE}/testbench/${TESTBENCH}/testbench.robot
        COMMENT "Running RobotFramework automated tests"
        WORKING_DIRECTORY ${APPLICATION_BINARY_DIR}
        DEPENDS ${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}
        USES_TERMINAL
    )
else()
    add_custom_target(
        robotbench
        COMMAND ${CMAKE_COMMAND} -E echo
            "No robot test file found. Create testbench/<name>/testbench.robot"
        COMMENT "No RobotFramework tests available"
    )
endif()

# ── Run sample.robot from application source ──────────────────────────

if(RENODE_TEST AND EXISTS "${APPLICATION_SOURCE_DIR}/sample.robot")
    add_custom_target(
        run_robot
        COMMAND
            ${CMAKE_COMMAND} -E env
                PROJECT_BASE=${PROJECT_BASE}
                APPLICATION_BINARY_DIR=${APPLICATION_BINARY_DIR}
                APPLICATION_SOURCE_DIR=${APPLICATION_SOURCE_DIR}
                BOARD=${BOARD}
            ${RENODE_TEST_COMMAND} --show-log
                --results-dir ${RENODE_RESULTS_DIR}
                ${APPLICATION_SOURCE_DIR}/sample.robot
        COMMENT "Running application robot script"
        WORKING_DIRECTORY ${APPLICATION_BINARY_DIR}
        DEPENDS ${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}
        USES_TERMINAL
    )
endif()
