# PicoRV32 RV32IM verification (cocotb + Icarus).
#   make                              all tests
#   make NUM_PROGS=50 SEED=11         more random programs
#   make CORE=mutants/m03.v           run against a mutated core
SIM          ?= icarus
TOPLEVEL_LANG = verilog
CORE         ?= $(PWD)/rtl/picorv32.v
SEED         ?=
VERILOG_SOURCES = $(PWD)/rtl/dut_top.v $(abspath $(CORE))
COCOTB_TOPLEVEL = dut_top
COCOTB_TEST_MODULES = test_picorv32
export PYTHONPATH := $(PWD)/tb:$(PYTHONPATH)
COMPILE_ARGS += -g2012 -DRISCV_FORMAL
ifneq ($(SEED),)
export COCOTB_RANDOM_SEED = $(SEED)
export RANDOM_SEED = $(SEED)
endif
include $(shell cocotb-config --makefiles)/Makefile.sim

clean::
	rm -rf sim_build* results results.xml __pycache__ tb/__pycache__ mutants/*.v
