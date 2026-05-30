cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(pin_configurator_real_blinky_import)

target_sources(app PRIVATE src/main.c)

include(${CMAKE_CURRENT_SOURCE_DIR}/../../testbench/CMakeLists.txt)