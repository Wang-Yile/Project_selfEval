#include"testlib.h"

signed main(signed argc,char *argv[]){
    registerTestlibCmd(argc,argv);
    if(ouf.readLong()==ans.readLong())
        quitf(_ok,"ok equal");
    quitf(_wa,"wrong answer");
}