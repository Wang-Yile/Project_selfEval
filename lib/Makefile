COMPILER = g++-13
# 如果在 WSL 中编译，请在 ARGS 末尾追加 -DWSL
ARGS = -std=c++2a -Wall -Wextra -Wshadow -Wconversion -O3

all: sandbox sandbox-tiny

sandbox: Makefile sandbox.cpp sandbox.h
	$(COMPILER) sandbox.cpp -o sandbox $(ARGS) -lseccomp
sandbox-tiny: Makefile sandbox-tiny.cpp sandbox.h
	$(COMPILER) sandbox-tiny.cpp -o sandbox-tiny $(ARGS)
