# SPDX-License-Identifier: Apache-2.0
# Sample RobotFramework testbench template for Renode simulation.
#
# Inspired by Swedish Embedded SDK testbench patterns.
# This file is meant to be customized per-project.
#
# Usage:
#   west build -t robotbench    (automated)
#   west build -t testbench     (interactive)

*** Settings ***
Suite Setup                   Setup
Suite Teardown                Teardown
Test Setup                    Reset Emulation
Test Teardown                 Test Teardown
Resource                      ${RENODEKEYWORDS}

*** Variables ***
${APPLICATION_BINARY_DIR}     %{APPLICATION_BINARY_DIR}
${APPLICATION_SOURCE_DIR}     %{APPLICATION_SOURCE_DIR}
${BOARD}                      %{BOARD}
${UART}                       sysbus.uart0

*** Test Cases ***

Firmware boots successfully
    Boot
    Wait For Line On Uart     Booting Zephyr OS    timeout=10

Application prints hello
    Boot
    Wait For Line On Uart     Hello                timeout=5

*** Keywords ***

Boot
    Execute Command           set bin @${APPLICATION_BINARY_DIR}/zephyr/zephyr.elf
    Execute Command           include @${APPLICATION_SOURCE_DIR}/boards/${BOARD}.resc
    Create Terminal Tester    ${UART}
    Start Emulation
