__all__ = [
    "libc", "libcap",
    "kernel_warning", "kernel_error", "kernel_fatal",
    "selfEvalFatalError",
]

import ctypes

libc = ctypes.CDLL("libc.so.6")
libcap = ctypes.CDLL("libcap.so.2")

libcap.cap_to_text.restype = ctypes.c_char_p

class selfEvalFatalError(Exception):
    pass

def kernel_warning(e: str | Exception):
    if isinstance(e, Exception):
        print("Kernel Warning:", e.__class__.__qualname__, e)
    else:
        print("Kernel Warning:", e)
def kernel_error(e: str | Exception):
    print("Kernel Error")
    if isinstance(e, Exception):
        print(e.__class__.__qualname__, e)
        for x in e.__notes__:
            print(x)
    else:
        print(e)
def kernel_fatal(e: Exception):
    print()
    print("Kernel FATAL Error")
    if isinstance(e, Exception):
        print(e.__class__.__qualname__, e)
        for x in e.__notes__:
            print(x)
    else:
        print(e)
    print()
