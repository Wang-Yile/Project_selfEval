# 如果不希望设置能力，请设置 SETCAP 为 0 或者从命令行传入参数 SETCAP=0
SETCAP ?= 1

COMPILER = g++-13

# 如果在 WSL 中编译，请在 ARGS 末尾追加 -DWSL
ARGS = -std=c++2a -Wall -Wextra -Wshadow -Wconversion -O3

# 目录变量
BIN = bin
SRC = src
LIB = lib
BUILD = build

all: $(BIN)/sandbox $(BIN)/sandbox-tiny $(LIB)/constants.py

$(BIN):
	mkdir $(BIN)
$(BIN)/sandbox: Makefile $(SRC)/sandbox.cpp $(SRC)/sandbox.h | $(BIN)
	$(COMPILER) $(SRC)/sandbox.cpp -o $(BIN)/sandbox $(ARGS) -lseccomp -lcap
ifeq ($(SETCAP),1)
	sudo setcap cap_sys_nice+ep $(BIN)/sandbox
endif
$(BIN)/sandbox-tiny: Makefile $(SRC)/sandbox-tiny.cpp $(SRC)/sandbox.h | $(BIN)
	$(COMPILER) $(SRC)/sandbox-tiny.cpp -o $(BIN)/sandbox-tiny $(ARGS)
$(BUILD):
	mkdir $(BUILD)
$(BUILD)/gen: Makefile $(SRC)/gen.cpp | $(BUILD)
	$(COMPILER) $(SRC)/gen.cpp -o $(BUILD)/gen $(ARGS)
$(LIB)/constants.py: $(BUILD)/gen
	cd $(BUILD); ./gen
	cp $(BUILD)/constants.py $(LIB)/constants.py
