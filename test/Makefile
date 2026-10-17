# Makefile for Cocotb simulation
# See https://docs.cocotb.org/

SIM ?= icarus
FST ?= -fst
TOPLEVEL_LANG ?= verilog
# Absolute path to test and src directories
TEST_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
SRC_DIR  := $(realpath $(TEST_DIR)/../src)

DUT ?= ternary_pe

ifeq ($(DUT),output_scaler)
    PROJECT_SOURCES = output_scaler.v
    TOPLEVEL = tb_output_scaler
    COCOTB_TEST_MODULES = test_output_scaler
else
    PROJECT_SOURCES = ternary_pe.v
    TOPLEVEL = tb_ternary_pe
    COCOTB_TEST_MODULES = test_ternary_pe
endif

SIM_BUILD = $(TEST_DIR)/sim_build/$(DUT)
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))
COMPILE_ARGS += -I$(SRC_DIR)
VERILOG_SOURCES += $(TEST_DIR)/$(TOPLEVEL).v

include $(shell cocotb-config --makefiles)/Makefile.sim
