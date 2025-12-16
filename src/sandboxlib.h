// 实验性内容

#include <unistd.h>

#define __NR_auth_login 20251214
#define __NR_auth_logout 20251215
#define __NR_auth_shot 20251216
#define SYS_auth_login __NR_auth_login
#define SYS_auth_logout __NR_auth_logout
#define SYS_auth_shot __NR_auth_shot

typedef unsigned token_t;
typedef unsigned token_shot_t;

// 获得特权。如果 token 不正确，程序将立刻被杀死。
static inline void auth_login(token_t token) {
    syscall(SYS_auth_login, token);
}
// 解除特权。
static inline void auth_logout() {
    syscall(SYS_auth_logout);
}
// 获得持续 shot 次的特权。如果 shot 为 0，则获取永久特权直到被 auth_logout 解除。
static inline void auth_shot(token_t token, token_shot_t shot) {
    syscall(SYS_auth_shot, token, shot);
}
