/*
sandbox.h

sandbox 和 sandbox-tiny 共用的宏定义、函数和全局变量。
*/

#define BOX_MASK 0xffff
#define BOX_EXIT 0x10000
#define BOX_SIG 0x20000
#define BOX_TLE 0x40000
#define BOX_MLE 0x80000
#define BOX_OLE 0x100000
#define BOX_FBD 0x200000

#define BOX_TLE_OVERDUE 1

#define TIMER_REDUNDANCY 1000 * 1000
#ifdef WSL
#define TIMER_REDUNDANCY_CHILD 200 * 1000
#else
#define TIMER_REDUNDANCY_CHILD 50 * 1000
#endif

#include <sys/resource.h>

static inline void setlimit(int code, rlim_t soft, rlim_t hard = 0) {
    if (hard == 0)
        hard = soft;
    rlimit limit;
    limit.rlim_cur = soft;
    limit.rlim_max = hard;
    setrlimit(code, &limit);
}
static inline time_t trans(const timeval &t) {
    return t.tv_sec * 1000000 + t.tv_usec;
}
static inline time_t trans(const rusage &x) {
    return trans(x.ru_stime) + trans(x.ru_utime);
}

pid_t pid, child_pid;
long time_limit;                          // 时间限制
long mem_limit, stack_limit, fsize_limit; // 空间限制，栈空间限制，创建文件大小限制
static inline void apply_rlimit() {
    setlimit(RLIMIT_CPU, ((rlim_t)time_limit + 999999) / 1000000);
    setlimit(RLIMIT_DATA, (rlim_t)mem_limit);
    setlimit(RLIMIT_STACK, (rlim_t)stack_limit);
    setlimit(RLIMIT_FSIZE, (rlim_t)fsize_limit);
}

time_t start_time;
int status;
rusage usage;
