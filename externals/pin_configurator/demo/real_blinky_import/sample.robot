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
    Wait For Line On Uart     Pin Configurator demo boot    timeout=10

Application blinks over console
    Boot
    Wait For Line On Uart     Blink    timeout=10

*** Keywords ***

Boot
    Execute Command           set bin @${APPLICATION_BINARY_DIR}/zephyr/zephyr.elf
    Execute Command           include @${APPLICATION_SOURCE_DIR}/boards/${BOARD}.resc
    Create Terminal Tester    ${UART}
    Start Emulation