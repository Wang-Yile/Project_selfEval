/*
sandbox-tiny.cpp

微型沙箱，用于运行受信任程序。
*/

#include <fstream>
#include <sys/prctl.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <unistd.h>

#include "sandbox.h"

static inline int tracer() {
    for (;;) { // 监控子进程运行
        if (wait4(child_pid, &status, WUNTRACED, &usage) == -1 && errno == EINTR)
            continue;
        if (trans(usage) - start_time > time_limit) {
            kill(child_pid, SIGKILL);
            return BOX_TLE;
        }
        if ((usage.ru_maxrss << 10) > mem_limit) {
            kill(child_pid, SIGKILL);
            return BOX_MLE;
        }
        if (WIFEXITED(status))
            return BOX_EXIT | WEXITSTATUS(status);
        if (WIFSIGNALED(status))
            return BOX_SIG | WTERMSIG(status);
        if (WIFSTOPPED(status)) {
            int sig = WSTOPSIG(status);
            // cerr << "sig " << sig << endl;
            if (sig == SIGXFSZ)
                return BOX_OLE;
            else if (sig == SIGXCPU)
                return BOX_TLE;
            else if (sig == SIGCONT)
                ;
            else if (WIFSIGNALED(sig))
                return BOX_SIG | WTERMSIG(sig);
            else if (WIFEXITED(sig))
                return BOX_EXIT | WEXITSTATUS(sig);
        }
    }
}

static volatile sig_atomic_t child_overdue;

int main(int argc, char *argv[]) {
    pid = fork();
    char *prog_path = argv[1];
    char *output = argv[2];
    // argv[3] 是 auth_token
    time_limit = atol(argv[4]);
    mem_limit = atol(argv[5]);
    stack_limit = atol(argv[6]);
    fsize_limit = atol(argv[7]);
    // argv[8] 是 cpuset 的二进制掩码
    int file_cnt = atoi(argv[9]);
    int args_st = 10 + (file_cnt << 1);
    struct sigaction sa;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;
    if (pid == 0) {
        pid = getpid();
        prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0);
        prctl(PR_SET_PDEATHSIG, SIGKILL);
        char **args = new char *[argc - args_st + 2];
        args[0] = prog_path;
        for (int i = args_st; i < argc; ++i)
            args[i - args_st + 1] = argv[i];
        args[argc - args_st + 1] = nullptr;
        cpu_set_t mask;
        CPU_ZERO(&mask);
        for (int i = 0; argv[8][i]; ++i)
            if (argv[8][i] == '1')
                CPU_SET(i, &mask);
        sched_setaffinity(pid, sizeof(mask), &mask);
        kill(pid, SIGSTOP);
        apply_rlimit();
        execv(prog_path, args);
        perror("child.execv");
        delete[] args;
        return 128;
    } else if (pid > 0) {
        child_pid = pid;
        pid = getpid();
        sa.sa_handler = [](int sig) {
            if (sig == SIGALRM) {
                kill(child_pid, SIGKILL);
                child_overdue = 1;
            }
        };
        sigaction(SIGALRM, &sa, nullptr);
        wait4(child_pid, &status, WUNTRACED, &usage);
        start_time = trans(usage);
        kill(pid, SIGSTOP); // 挂起等待进一步指令
        time_limit += TIMER_REDUNDANCY;
        itimerval it;
        it.it_value.tv_sec = time_limit / 1000000;
        it.it_value.tv_usec = time_limit % 1000000;
        it.it_interval.tv_sec = it.it_interval.tv_usec = 0;
        kill(child_pid, SIGCONT);
        setitimer(ITIMER_REAL, &it, nullptr);
        int ret = tracer();
        if (child_overdue)
            ret = BOX_TLE | BOX_TLE_OVERDUE;
        std::ofstream out(output, std::ios::out);
        out << trans(usage) - start_time << '\n';
        out << (usage.ru_maxrss << 10) << '\n';
        out << ret << '\n';
        out.close();
        return 0;
    } else
        return 128;
}