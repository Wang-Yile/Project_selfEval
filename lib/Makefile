# 如果不希望设置能力，请设置 SETCAP 为 0 或者从命令行传入参数 SETCAP=0
SETCAP ?= 1

COMPILER = g++-13

# 如果在 WSL 中编译，请在 ARGS 末尾追加 -DWSL
ARGS = -std=c++2a -Wall -Wextra -Wshadow -Wconversion -O3

all: sandbox sandbox-tiny constants.py

sandbox: Makefile sandbox.cpp sandbox.h
	$(COMPILER) sandbox.cpp -o sandbox $(ARGS) -lseccomp -lcap
ifeq ($(SETCAP),1)
	sudo setcap cap_sys_nice+ep sandbox
endif
sandbox-tiny: Makefile sandbox-tiny.cpp sandbox.h
	$(COMPILER) sandbox-tiny.cpp -o sandbox-tiny $(ARGS)
gen: Makefile gen.cpp
	$(COMPILER) gen.cpp -o gen $(ARGS)
constants.py: gen
	./gen
