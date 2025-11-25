/*
sandbox.cpp

完整的沙箱。

时间单位是微秒，空间单位是字节。
*/

#include <fcntl.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <linux/filter.h>
#include <poll.h>
#include <seccomp.h>
#include <signal.h>
#include <string.h>
#include <string>
#include <sys/capability.h>
#include <sys/ioctl.h>
#include <sys/prctl.h>
#include <sys/signalfd.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/time.h>
#include <sys/timerfd.h>
#include <sys/uio.h>
#include <sys/wait.h>
#include <unistd.h>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "sandbox.h"

namespace fs = std::filesystem;

using std::cerr;
using std::endl;

#define TRUNK 128
static inline std::string read_string(long addr) {
    std::string result;
    char buffer[TRUNK];
    struct iovec local_iov = {
        .iov_base = buffer,
        .iov_len = TRUNK,
    };
    struct iovec remote_iov = {
        .iov_base = nullptr,
        .iov_len = TRUNK,
    };
    for (;;) {
        remote_iov.iov_base = (void *)addr;
        ssize_t bytes_read = process_vm_readv(child_pid, &local_iov, 1, &remote_iov, 1, 0);
        if (bytes_read <= 0)
            break;
        int null_pos = -1;
        for (int i = 0; i < bytes_read; ++i)
            if (buffer[i] == '\0') {
                null_pos = i;
                break;
            }
        if (null_pos == -1) {
            result.append(buffer, buffer + TRUNK);
            addr += bytes_read;
        } else {
            result.append(buffer, buffer + null_pos);
            break;
        }
    }
    return result;
}
#undef TRUNK
fs::path child_dirfd_path;
/*
注意事项
没有放行 unlink rmdir rename 等删除/重命名文件/文件夹的系统调用，因此下面的方法没有考虑这种情况。
没有放行 pipe socket 等系统调用，因此涉及管道和套接字的操作被直接认为是安全的。
认为从 /proc/<pid>/fd/ 读出正常文件/文件夹/设备的路径必定是绝对路径，因此对于非相对路径通过正则表达式判断是否是管道和套接字。
认为如果 trace_on_prohibition 为真，则不批准调用时程序会立刻退出，因此不会检查 permission_violation 指针是否可能泄漏。
*/
// const std::regex pattern_pipe("(^pipe:\\[\\d+\\]$)");
// const std::regex pattern_socket("(^socket:\\[\\d+\\]$)");
struct permission_node {
    std::unordered_map<std::string, permission_node *> tr;
    std::unordered_map<std::string, int> mp;
    ~permission_node() {
        for (auto p : tr)
            delete p.second;
    }
} permission_root;
struct permission_violation {
    fs::path attempt;
    int acc, permitted;
} *permission_violation;
static inline void add_permission(const fs::path &path, int acc) {
    ++acc;
    fs::path p;
    try {
        p = fs::canonical(path.parent_path());
    } catch (const fs::filesystem_error &e) {
        exit(1);
    }
    permission_node *now = &permission_root;
    for (auto it = std::next(p.begin()); it != p.end(); ++it) {
        std::string s = it->string();
        if (!now->tr.count(s))
            now->tr[s] = new permission_node;
        now = now->tr[s];
    }
    now->mp[path.filename()] |= acc;
}
static inline bool _is_permitted(const fs::path &path, int acc, bool trace_on_prohibition) {
    ++acc;
    fs::path p;
    try {
        p = fs::canonical(path.parent_path());
    } catch (const fs::filesystem_error &e) {
        if (trace_on_prohibition)
            permission_violation = new (struct permission_violation){.attempt = path, .acc = acc, .permitted = 0};
        return false;
    }
    permission_node *now = &permission_root;
    int permitted = 0;
    for (auto it = std::next(p.begin()); it != p.end(); ++it) {
        std::string s = it->string();
        if (now->mp.count(s)) {
            int x = now->mp[s];
            if ((x & acc) == acc)
                return true;
            permitted |= x;
        }
        if (!now->tr.count(s)) {
            if (trace_on_prohibition)
                permission_violation = new (struct permission_violation){.attempt = path, .acc = acc, .permitted = 0};
            return false;
        }
        now = now->tr[s];
    }
    std::string s = path.filename();
    if (now->mp.count(s) && (now->mp[s] & acc) == acc)
        return true;
    cerr << "not permitted: " << path << endl;
    if (trace_on_prohibition)
        permission_violation = new (struct permission_violation){.attempt = path, .acc = acc, .permitted = permitted};
    return false;
}
static inline bool is_permitted(const fs::path &path, int acc, bool trace_on_prohibition) {
    if (path.is_relative()) {
        auto s = path.filename().string();
        if (s.starts_with("pipe:") || s.starts_with("socket:"))
            return true;
        // if (std::regex_match(path.filename().string(), pattern_pipe))
        //     return true;
        // if (std::regex_match(path.filename().string(), pattern_socket))
        //     return true;
        return false;
    }
    return _is_permitted(path, acc, trace_on_prohibition);
}
static inline bool check_fd_operation(int fd, int acc, bool trace_on_prohibition = true) {
    try {
        return is_permitted(fs::read_symlink(child_dirfd_path / std::to_string(fd)), acc, trace_on_prohibition);
    } catch (const fs::filesystem_error &e) {
        cerr << e.what() << endl;
        return false;
    }
}
static inline bool check_file_operation(long addr, int acc, bool trace_on_prohibition = true) {
    return is_permitted(fs::absolute(fs::path(read_string(addr)).lexically_normal()), acc, trace_on_prohibition);
}
static inline bool check_file_operation_at(int dirfd, long addr, int acc, bool trace_on_prohibition = true) {
    fs::path path = read_string(addr);
    if (path.is_absolute())
        return is_permitted(path, acc, trace_on_prohibition);
    if (dirfd == AT_FDCWD) // 相对当前工作目录的路径
        return is_permitted(fs::absolute(path), (int)acc, trace_on_prohibition);
    try {
        return is_permitted(fs::absolute(fs::read_symlink(child_dirfd_path / std::to_string(dirfd)) / path), acc, trace_on_prohibition);
    } catch (const fs::filesystem_error &e) {
        cerr << e.what() << endl;
        return false;
    }
}
static inline bool check_ioctl(int fd, unsigned long request) {
    // 只允许访问终端或被授权的文件
    if (check_fd_operation(fd, -1, false))
        return true;
    return _IOC_DIR(request) == _IOC_NONE || _IOC_DIR(request) == _IOC_READ;
}

#define BPF_ALLOW(x)                                \
    BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, (x), 0, 1), \
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW)
static inline int install_filter_raw() {
    struct sock_filter filter[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
        // 常用操作
        BPF_ALLOW(SYS_read),
        BPF_ALLOW(SYS_write),
        BPF_ALLOW(SYS_close),
        // 内存
        BPF_ALLOW(SYS_brk),
        BPF_ALLOW(SYS_mmap),
        BPF_ALLOW(SYS_munmap),
        BPF_ALLOW(SYS_mprotect),
        BPF_ALLOW(SYS_msync),
        BPF_ALLOW(SYS_madvise),
        // 系统运行需要
        BPF_ALLOW(SYS_getpid),
        BPF_ALLOW(SYS_gettid),
        BPF_ALLOW(SYS_getcwd),
        BPF_ALLOW(SYS_tgkill),
        BPF_ALLOW(SYS_arch_prctl),
        BPF_ALLOW(SYS_sendmsg),
        BPF_ALLOW(SYS_exit),
        BPF_ALLOW(SYS_exit_group),
        // 默认
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_USER_NOTIF),
        // BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_LOG),
    };
    struct sock_fprog prog = {
        .len = sizeof(filter) / sizeof(filter[0]),
        .filter = filter,
    };
    // cerr << "BPF: " << prog.len << " instructions" << endl;
    prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0);
    return (int)syscall(__NR_seccomp, SECCOMP_SET_MODE_FILTER, SECCOMP_FILTER_FLAG_NEW_LISTENER, &prog);
}
static inline int install_signalfd() {
    sigset_t mask;
    sigemptyset(&mask);
    sigaddset(&mask, SIGCHLD);
    sigprocmask(SIG_BLOCK, &mask, NULL);
    return signalfd(-1, &mask, SFD_NONBLOCK);
}
static inline int install_timerfd(time_t t) {
    struct itimerspec its{
        .it_interval = {0, 0},
        .it_value = {.tv_sec = t / 1000000, .tv_nsec = (t % 1000000) * 1000},
    };
    int fd = timerfd_create(CLOCK_MONOTONIC_COARSE, TFD_CLOEXEC);
    timerfd_settime(fd, 0, &its, nullptr);
    return fd;
}
static inline void send_fd(int socket, int fd) {
    struct cmsghdr *cmsg;
    char buf[CMSG_SPACE(sizeof(fd))];
    char dummy = '!';
    struct iovec io = {.iov_base = &dummy, .iov_len = 1};
    struct msghdr msg{
        .msg_name = nullptr,
        .msg_namelen = 0,
        .msg_iov = &io,
        .msg_iovlen = 1,
        .msg_control = buf,
        .msg_controllen = sizeof(buf),
        .msg_flags = 0,
    };
    cmsg = CMSG_FIRSTHDR(&msg);
    cmsg->cmsg_level = SOL_SOCKET;
    cmsg->cmsg_type = SCM_RIGHTS;
    cmsg->cmsg_len = CMSG_LEN(sizeof(fd));
    memcpy(CMSG_DATA(cmsg), &fd, sizeof(fd));
    sendmsg(socket, &msg, 0);
}
static inline int recv_fd(int socket) {
    struct cmsghdr *cmsg;
    char buf[CMSG_SPACE(sizeof(int))];
    char dummy;
    struct iovec io = {.iov_base = &dummy, .iov_len = 1};
    struct msghdr msg{
        .msg_name = nullptr,
        .msg_namelen = 0,
        .msg_iov = &io,
        .msg_iovlen = 1,
        .msg_control = buf,
        .msg_controllen = sizeof(buf),
        .msg_flags = 0,
    };
    if (recvmsg(socket, &msg, 0) < 0)
        return -1;
    cmsg = CMSG_FIRSTHDR(&msg);
    if (cmsg && cmsg->cmsg_level == SOL_SOCKET && cmsg->cmsg_type == SCM_RIGHTS) {
        int fd;
        memcpy(&fd, CMSG_DATA(cmsg), sizeof(fd));
        return fd;
    }
    return -1;
}

bool child_execved;
static inline bool handle_syscall(int syscall, unsigned long long args[]) {
    switch (syscall) {
    case SYS_open:
        return check_file_operation(args[1], args[2] & O_ACCMODE);
    case SYS_openat:
        return check_file_operation_at((int)args[0], args[1], args[2] & O_ACCMODE);
    case SYS_ioctl:
        return check_ioctl((int)args[0], args[1]);
    // 文件系统操作
    case SYS_statx:
    case SYS_newfstatat:
    case SYS_statfs:
    case SYS_fstatfs:
    case SYS_stat:
    case SYS_lstat:
    case SYS_fstat:
    case SYS_access:
    case SYS_faccessat:
    // 文件操作
    case SYS_lseek:
    case SYS_pread64:
    case SYS_pwrite64:
    case SYS_readv:
    case SYS_writev:
    case SYS_preadv:
    case SYS_pwritev:
    case SYS_preadv2:
    case SYS_pwritev2:
    case SYS_dup:
    case SYS_dup2:
    case SYS_dup3:
    // 信号
    case SYS_rt_sigaction: // 开放这些调用可能导致 SIGPROF 被覆盖，只能被主进程/ulimit 杀死
    case SYS_rt_sigprocmask:
    case SYS_rt_sigreturn:
    case SYS_setitimer:
    case SYS_getitimer:
    case SYS_timer_create:
    case SYS_timer_delete:
    // 资源限制
    case SYS_getrlimit:
    case SYS_setrlimit:
    case SYS_prlimit64:
    // 时间
    case SYS_gettimeofday:
    case SYS_clock_gettime: // 获取时钟时间
    case SYS_time:          // 获取秒级时间
    case SYS_times:         // 获取进程时间
    // 系统
    case SYS_set_tid_address:
    case SYS_set_robust_list:
    case SYS_rseq:
    case SYS_futex:
    // 随机
    case SYS_getrandom:
    // 其他
    case SYS_sched_yield: // 让出CPU
        return true;
    case SYS_execve: {
        if (child_execved)
            return false;
        child_execved = true;
        return true;
    }
    default: {
        cerr << "forbidden syscall: " << syscall << endl;
        return false;
    }
    }
}
static inline int tracer(int listener_fd, int signal_fd, int timer_fd) {
    seccomp_notif_sizes sizes;
    syscall(SYS_seccomp, SECCOMP_GET_NOTIF_SIZES, 0, &sizes);
    seccomp_notif *notif = (struct seccomp_notif *)malloc(sizes.seccomp_notif);
    seccomp_notif_resp *resp = (struct seccomp_notif_resp *)malloc(sizes.seccomp_notif_resp);
    kill(child_pid, SIGCONT);
    struct pollfd pfds[3]{
        {.fd = listener_fd, .events = POLLIN | POLLPRI, .revents = 0},
        {.fd = signal_fd, .events = POLLIN | POLLPRI, .revents = 0},
        {.fd = timer_fd, .events = POLLIN | POLLPRI, .revents = 0},
    };
    int ret = 0;
    for (;;) {
        int poll_result = poll(pfds, 3, -1);
        if (poll_result < 0) {
            if (errno == EINTR)
                continue;
            perror("poll failed");
            ret = -1;
            break;
        }
        if (pfds[2].revents & (POLLIN | POLLPRI)) {
            uint64_t val;
            ssize_t s = read(timer_fd, &val, sizeof(val));
            if (s == sizeof(val)) {
                kill(child_pid, SIGKILL);
                ret = TLE | TLE_OVERDUE;
                break;
            } else
                cerr << "Failed to read from timerfd" << endl;
        }
        if (pfds[1].revents & (POLLIN | POLL_PRI)) {
            signalfd_siginfo siginfo;
            ssize_t s = read(signal_fd, &siginfo, sizeof(siginfo));
            if (s == sizeof(siginfo)) {
                if (siginfo.ssi_signo == SIGCHLD) {
                    if (siginfo.ssi_code == CLD_EXITED || siginfo.ssi_code == CLD_KILLED || siginfo.ssi_code == CLD_DUMPED)
                        break;
                }
            } else
                cerr << "Failed to read from signalfd" << endl;
        }
        if (pfds[0].revents & (POLLIN | POLL_PRI)) {
            memset(notif, 0, sizes.seccomp_notif);
            memset(resp, 0, sizes.seccomp_notif_resp);
            if (ioctl(listener_fd, SECCOMP_IOCTL_NOTIF_RECV, notif) < 0) {
                if (errno == EINTR)
                    continue;
                perror("seccomp receive failed");
                ret = -1;
                break;
            }
            resp->id = notif->id;
            if (handle_syscall(notif->data.nr, notif->data.args)) {
                resp->flags = SECCOMP_USER_NOTIF_FLAG_CONTINUE;
                resp->val = 0;
                resp->error = 0;
            } else {
                // 软拦截
                // resp->flags = 0;
                // resp->val = -1;
                // resp->error = -EPERM;
                // 硬拦截
                kill(child_pid, SIGKILL);
                ret = FBD | notif->data.nr;
                break;
            }
            if (ioctl(listener_fd, SECCOMP_IOCTL_NOTIF_SEND, resp) < 0) {
                perror("seccomp send failed");
                ret = -1;
                break;
            }
        }
    }
    free(notif);
    free(resp);
    return ret;
}

int main(int argc, char *argv[]) {
    char *prog_path = argv[1];
    char *output = argv[2];
    time_limit = atol(argv[3]);
    mem_limit = atol(argv[4]);
    stack_limit = atol(argv[5]);
    fsize_limit = atol(argv[6]);
    // argv[7] 是 cpuset 的二进制掩码
    int file_cnt = atoi(argv[8]);
    int args_st = 9 + (file_cnt << 1);
    int socket_pair[2];
    socketpair(AF_UNIX, SOCK_STREAM, 0, socket_pair);
    pid = fork();
    if (pid == 0) {
        pid = getpid();
        close(socket_pair[0]);
        char **args = new char *[argc - args_st + 2];
        args[0] = prog_path;
        for (int i = args_st; i < argc; ++i)
            args[i - args_st + 1] = argv[i];
        args[argc - args_st + 1] = nullptr;
        cpu_set_t mask;
        CPU_ZERO(&mask);
        for (int i = 0; argv[7][i]; ++i)
            if (argv[7][i] == '1')
                CPU_SET(i, &mask);
        sched_setaffinity(pid, sizeof(mask), &mask);
        apply_rlimit();
        cap_t cap = cap_get_pid(pid);
        cap_flag_value_t capval;
        cap_get_flag(cap, CAP_SYS_NICE, CAP_EFFECTIVE, &capval);
        if (capval == CAP_SET) {
            if (!(nice(-20) == -1 && errno)) {
                sched_param param;
                param.sched_priority = sched_get_priority_max(SCHED_FIFO);
                sched_setscheduler(pid, SCHED_RR, &param);
            }
        }
        cap_free(cap);
        send_fd(socket_pair[1], install_filter_raw());
        close(socket_pair[1]);
        itimerval it;
        it.it_value.tv_sec = time_limit / 1000000;
        it.it_value.tv_usec = time_limit % 1000000;
        it.it_interval.tv_sec = it.it_interval.tv_usec = 0;
        tgkill(pid, gettid(), SIGSTOP);
        setitimer(ITIMER_PROF, &it, nullptr); // 如果选手程序处理 SIGPROF，高精度计时器会失效
        execv(prog_path, args);
        perror("execv failed");
        delete[] args;
        return 128;
    } else if (pid > 0) {
        child_pid = pid;
        pid = getpid();
        close(socket_pair[1]);
        add_permission("/etc/ld.so.preload", 0);
        add_permission("/etc/ld.so.cache", 0);
        add_permission("/lib", 0);
        add_permission("/usr/lib", 0);
        add_permission("/dev/random", 0);
        add_permission("/dev/urandom", 0);
        add_permission("/dev/null", 0);
        add_permission("/etc/localtime", 0);
        if (char *p = ttyname(stdin->_fileno); p != nullptr)
            add_permission(p, 0);
        if (char *p = ttyname(stdout->_fileno); p != nullptr)
            add_permission(p, 1);
        if (char *p = ttyname(stderr->_fileno); p != nullptr)
            add_permission(p, 1);
        for (int i = 0; i < file_cnt; ++i)
            add_permission(fs::path(argv[9 + (i << 1)]).lexically_normal(), atoi(argv[9 + (i << 1 | 1)]));
        child_dirfd_path = fs::path("/proc/" + std::to_string(child_pid) + "/fd/");
        wait4(child_pid, &status, WUNTRACED, &usage);
        start_time = trans(usage);
        kill(pid, SIGSTOP); // 挂起等待进一步指令
        int listener_fd = recv_fd(socket_pair[0]);
        close(socket_pair[0]);
        int signal_fd = install_signalfd();
        int timer_fd = install_timerfd(time_limit + TIMER_REDUNDANCY);
        int ret = tracer(listener_fd, signal_fd, timer_fd);
        if (ret == -1)
            return 1;
        if (wait4(child_pid, &status, WUNTRACED, &usage) == child_pid) {
            if (!ret) {
                if (WIFEXITED(status))
                    ret = EXIT | WEXITSTATUS(status);
                else if (WIFSIGNALED(status)) {
                    int sig = WTERMSIG(status);
                    if (sig == SIGXCPU || sig == SIGPROF)
                        ret = TLE;
                    else if (sig == SIGXFSZ)
                        ret = OLE;
                    else
                        ret = SIG | WTERMSIG(status);
                } else
                    ret = -1;
            }
        } else {
            perror("waitpid failed");
            ret = -1;
        }
        time_t t = trans(usage) - start_time;
        if (!(ret & TLE) && t >= time_limit)
            ret = TLE;
        close(listener_fd);
        close(signal_fd);
        close(timer_fd);
        if (ret == -1)
            return 1;
        std::ofstream out(output, std::ios::out);
        out << t << '\n';
        out << (usage.ru_maxrss << 10) << '\n';
        out << ret << '\n';
#ifndef TINY
        if (permission_violation != nullptr) {
            out << "not permitted";
            switch (permission_violation->acc) {
            case 0: {
                out << "[visit]";
                break;
            }
            case 1: {
                out << "[R] ";
                break;
            }
            case 2: {
                out << "[W] ";
                break;
            }
            case 3: {
                out << "[RW] ";
                break;
            }
            default: {
                out << "[?] ";
                break;
            }
            }
            out << permission_violation->attempt;
            if (permission_violation->permitted) {
                out << " (permitted ";
                switch (permission_violation->permitted) {
                case 1: {
                    out << "R";
                    break;
                }
                case 2: {
                    out << "W";
                    break;
                }
                case 3: {
                    out << "RW";
                    break;
                }
                default: {
                    out << "?";
                    break;
                }
                }
                out << ")\n";
            } else
                out << " (not exists)\n";
        }
#endif
        out.close();
        return 0;
    }
    return 1;
}