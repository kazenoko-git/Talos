# Makefile for Cocotb simulation
# See https://docs.cocotb.org/

SIM ?= icarus
FST ?= -fst
TOPLEVEL_LANG ?= verilog
# Absolute path to test and src directories
TEST_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
SRC_DIR  := $(realpath $(TEST_DIR)/../src)

PROJECT_SOURCES = ternary_pe.v

SIM_BUILD = $(TEST_DIR)/sim_build/ternary_pe
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))
COMPILE_ARGS += -I$(SRC_DIR)
VERILOG_SOURCES += $(TEST_DIR)/tb_ternary_pe.v
TOPLEVEL = tb_ternary_pe
COCOTB_TEST_MODULES = test_ternary_pe

include $(shell cocotb-config --makefiles)/Makefile.sim
