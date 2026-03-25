cmake_minimum_required(VERSION 3.12 FATAL_ERROR)

project(mybetatron VERSION 0.1 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(USE_GEANT4 "Enable Geant4 support" ON)
option(USE_ROOT   "Enable ROOT support" FALSE)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Debug)
endif()

# Optional user-provided install dirs
# set(ROOT_DIR "/home/mtzmo/sofeware/root/install/root")
set(Geant4_DIR "/home/mtz/sofeware/geant4/geant4-mt-install/lib/Geant4-10.6.2")

if(USE_ROOT)
  find_package(ROOT REQUIRED COMPONENTS RIO Net Hist Tree)
  if(DEFINED ROOT_USE_FILE)
    include(${ROOT_USE_FILE}) # compatibility with older ROOT CMake config
  endif()
  message(STATUS "Found ROOT ${ROOT_VERSION}")
endif()

if(USE_GEANT4)
  find_package(Geant4 REQUIRED vis_all ui_all )
  include(${Geant4_USE_FILE})
  message(STATUS "Found Geant4 ${Geant4_VERSION}")
endif()

file(GLOB sources ${PROJECT_SOURCE_DIR}/src/*.cc)
file(GLOB includes ${PROJECT_SOURCE_DIR}/include/*.hh)
file(GLOB MAC_FILE ${PROJECT_SOURCE_DIR}/*.cc)
file(GLOB macro_file ${PROJECT_SOURCE_DIR}/*.mac)
file(COPY ${macro_file} DESTINATION ${PROJECT_BINARY_DIR})
file(GLOB data_file ${PROJECT_SOURCE_DIR}/*.dat)
file(COPY ${data_file} DESTINATION ${PROJECT_BINARY_DIR})

add_executable(main main.cc ${sources} ${includes} ${MAC_FILE})

# compile options and conditional definitions
target_compile_options(main PRIVATE -Wno-shadow)
target_compile_definitions(main PRIVATE $<$<BOOL:${USE_GEANT4}>:myGEANT4RUN> $<$<BOOL:${USE_ROOT}>:myROOTRUN>)

# include directories
target_include_directories(main PRIVATE ${PROJECT_SOURCE_DIR}/include)
if(USE_ROOT)
  target_include_directories(main PRIVATE ${ROOT_INCLUDE_DIRS})
endif()
if(USE_GEANT4)
  target_include_directories(main PRIVATE ${Geant4_INCLUDE_DIRS})
endif()

# link libraries (prefer modern imported targets where available)
if(USE_GEANT4)
  target_link_libraries(main PRIVATE ${Geant4_LIBRARIES})
endif()

if(USE_ROOT)
  if(TARGET ROOT::RIO)
    target_link_libraries(main PRIVATE ROOT::RIO ROOT::Net ROOT::Hist ROOT::Tree)
  else()
    target_link_libraries(main PRIVATE ${ROOT_LIBRARIES})
  endif()
endif()

add_custom_target(x_ray_image DEPENDS main)

message(STATUS "Configuration summary: USE_ROOT=${USE_ROOT}, USE_GEANT4=${USE_GEANT4}")

# 创建符号链接
add_custom_target(create_symlink ALL
  COMMAND ${CMAKE_COMMAND} -E create_symlink
          ${CMAKE_BINARY_DIR}/compile_commands.json
          ${CMAKE_SOURCE_DIR}/compile_commands.json
  COMMENT "Symlinking compile_commands.json to ../compile_commands.json"
  VERBATIM
)
















