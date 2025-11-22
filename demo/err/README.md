演示异常评测状态的处理。

各测试点的期望结果和原理：

1. TLE `while(1);`
2. MLE 不断 malloc + memset
3. OLE 不断向 stdout 写入大小为 1M 的缓冲区
4. RE (SIGABRT) `throw 0;`
5. FBD (SYS_open) 打开未授权的文件
6. RE (SIGSEGV) 解引用非法指针
7. FBD (SYS_open) 打开未授权且位于不存在的目录下的文件
8. FBD (SYS_open) 上一个的绝对路径版本
9. FBD (SYS_fork) fork
