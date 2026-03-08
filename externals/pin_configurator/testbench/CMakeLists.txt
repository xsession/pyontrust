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
find_program(RENODE_TEST renode-test HINTS
    "C:/Program Files/Renode/bin"
    "/opt/renode"
)

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

# Standard Renode command preamble
set(RENODE_COMMANDS "")
string(APPEND RENODE_COMMANDS
    "set bin @${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}\;")
string(APPEND RENODE_COMMANDS
    "set APPLICATION_BINARY_DIR @${APPLICATION_BINARY_DIR}\;")

if(DEFINED PROJECT_BASE)
    string(APPEND RENODE_COMMANDS "set PROJECT_BASE @${PROJECT_BASE}\;")
endif()

# ── Board-level testbench ─────────────────────────────────────────────
# Look for <board>.resc in the board directory

if(DEFINED BOARD_DIR AND EXISTS "${BOARD_DIR}/${BOARD}.resc")
    set(BOARD_BENCH_COMMANDS "include @${BOARD_DIR}/${BOARD}.resc\;")

    add_custom_target(
        boardbench
        COMMAND ${RENODE} --console --disable-xwt
            -e "${RENODE_COMMANDS}"
            -e "${BOARD_BENCH_COMMANDS}"
            -e "start\;"
        COMMENT "Running board-level Renode simulation"
        WORKING_DIRECTORY ${APPLICATION_BINARY_DIR}
        DEPENDS ${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}
        USES_TERMINAL
    )

    add_custom_target(
        boardbench_xwt
        COMMAND ${RENODE}
            -e "${RENODE_COMMANDS}"
            -e "${BOARD_BENCH_COMMANDS}"
            -e "start\;"
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
    set(APP_BENCH_COMMANDS
        "include @${APPLICATION_SOURCE_DIR}/boards/${BOARD}.resc\;")

    add_custom_target(
        appbench
        COMMAND ${RENODE} --console --disable-xwt
            -e "${RENODE_COMMANDS}"
            -e "${APP_BENCH_COMMANDS}"
            -e "start\;"
        COMMENT "Running application-specific Renode simulation"
        WORKING_DIRECTORY ${APPLICATION_BINARY_DIR}
        DEPENDS ${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}
        USES_TERMINAL
    )

    add_custom_target(
        appbench_xwt
        COMMAND ${RENODE}
            -e "${RENODE_COMMANDS}"
            -e "${APP_BENCH_COMMANDS}"
            -e "start\;"
        COMMENT "Running application Renode simulation (GUI)"
        WORKING_DIRECTORY ${APPLICATION_BINARY_DIR}
        DEPENDS ${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}
        USES_TERMINAL
    )

    # App bench with GDB debug server on port 3333
    add_custom_target(
        appbench_debugserver
        COMMAND ${RENODE} --console --disable-xwt
            -e "${RENODE_COMMANDS}\;"
            -e "machine StartGdbServer 3333\;"
            -e "${APP_BENCH_COMMANDS}"
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
    set(TB_COMMANDS
        "include @${TESTBENCH_DIR}/testbench.resc\; s\;")

    add_custom_target(
        testbench
        COMMAND ${RENODE} --console --disable-xwt
            -e "${RENODE_COMMANDS}"
            -e "${TB_COMMANDS}"
        COMMENT "Running testbench: ${TESTBENCH}"
        WORKING_DIRECTORY ${APPLICATION_BINARY_DIR}
        DEPENDS ${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}
        USES_TERMINAL
    )

    add_custom_target(
        testbench_xwt
        COMMAND ${RENODE}
            -e "${RENODE_COMMANDS}"
            -e "${TB_COMMANDS}"
        COMMENT "Running testbench (GUI): ${TESTBENCH}"
        WORKING_DIRECTORY ${APPLICATION_BINARY_DIR}
        DEPENDS ${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}
        USES_TERMINAL
    )

    add_custom_target(
        testbench_debugserver
        COMMAND ${RENODE} --console --disable-xwt
            -e "${RENODE_COMMANDS}\;"
            -e "${TB_COMMANDS}"
            -e "machine StartGdbServer 3333\;"
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
            ${RENODE_TEST} --show-log
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
            ${RENODE_TEST} --show-log
                ${APPLICATION_SOURCE_DIR}/sample.robot
        COMMENT "Running application robot script"
        WORKING_DIRECTORY ${APPLICATION_BINARY_DIR}
        DEPENDS ${APPLICATION_BINARY_DIR}/zephyr/${KERNEL_ELF_NAME}
        USES_TERMINAL
    )
endif()
