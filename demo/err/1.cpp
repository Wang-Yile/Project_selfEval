#include<iostream>
#include<string.h>
#include<unistd.h>

using namespace std;

signed main(){
    ios::sync_with_stdio(false);
    cin.tie(0);
    int n;
    cin>>n;
    if(n==1){
        while(1);
    }else if(n==2){
        for(;;)
            memset((char*)malloc(1048576),'c',1048576);
    }else if(n==3){
        char buf[1<<20];
        memset(buf,'0',sizeof buf);
        for(;;){
            fwrite(buf,sizeof(buf),1<<20,stdout);
            fflush(stdout);
        }
    }else if(n==4){
        throw 0;
    }else if(n==5){
        fopen("1.in","r");
    }else if(n==6){
        cout<<(*(int*)(114514))<<endl;
    }else if(n==7){
        fopen("114514/1.in","r");
    }else if(n==8){
        fopen("/114514/1.in","r");
    }else if(n==9){
        fork();
    }
    return 0;
}