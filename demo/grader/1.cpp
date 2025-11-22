#include "strategy.h"
#include <iostream>
#include <vector>
#include <random>
#include <chrono>

using namespace std;

namespace Trava{

#define int long long

const int inf=1e18;

int n,m,T;
int a[200005];
int b[200005];

int cnt;
struct{
    int ls,rs,val=inf,tag;
}d[20000005];
static inline void pushup(int p){
    d[p].val=min(d[d[p].ls].val,d[d[p].rs].val);
}
static inline int pushadd(int p,int c){
    if(!p)
        p=++cnt;
    d[p].val+=c;
    d[p].tag+=c;
    return p;
}
static inline void pushdown(int p){
    if(!d[p].tag)
        return;
    d[p].ls=pushadd(d[p].ls,d[p].tag);
    d[p].rs=pushadd(d[p].rs,d[p].tag);
    d[p].tag=0;
}
static inline int update(int l,int r,int s,int t,int c,int p){
    if(!p)
        p=++cnt;
    if(l<=s&&r>=t){
        pushadd(p,c);
        return p;
    }
    int mid=(s+t)>>1;
    pushdown(p);
    if(l<=mid)
        d[p].ls=update(l,r,s,mid,c,d[p].ls);
    if(r>mid)
        d[p].rs=update(l,r,mid+1,t,c,d[p].rs);
    pushup(p);
    return p;
}
static inline int update(int x,int s,int t,int c,int p){
    if(!p)
        p=++cnt;
    if(s==t){
        d[p].val=c;
        return p;
    }
    int mid=(s+t)>>1;
    pushdown(p);
    if(x<=mid)
        d[p].ls=update(x,s,mid,c,d[p].ls);
    else
        d[p].rs=update(x,mid+1,t,c,d[p].rs);
    pushup(p);
    return p;
}
static inline int query(int l,int r,int s,int t,int p){
    if(!p)
        return inf;
    if(l<=s&&r>=t)
        return d[p].val;
    int mid=(s+t)>>1;
    pushdown(p);
    if(l<=mid&&r>mid)
        return min(query(l,r,s,mid,d[p].ls),query(l,r,mid+1,t,d[p].rs));
    else if(l<=mid)
        return query(l,r,s,mid,d[p].ls);
    return query(l,r,mid+1,t,d[p].rs);
}
int rt,sum;
static inline void update(int l,int r,int c){
    if(l>r)
        return;
    l=(l-sum+m)%m;
    r=(r-sum+m)%m;
    if(l>r){
        rt=update(0,r,0,m-1,c,rt);
        rt=update(l,m-1,0,m-1,c,rt);
    }else{
        rt=update(l,r,0,m-1,c,rt);
    }
}

static inline int solve(){
    int o=0;
    rt=update(0,0,m-1,0,0);
    for(int i=1;i<=n;++i){
        int t=(b[i]+m-1)/m;
        int r=b[i]%m;
        int w=d[rt].val+(b[i]+m-1)/m*(a[i]+T);
        if(r){
            update(1,m-r,b[i]/m*(a[i]+T)+a[i]);
            update(m-r+1,m-1,(b[i]+m-1)/m*(a[i]+T)+a[i]);
        }else{
            update(1,m-1,(b[i]+m-1)/m*(a[i]+T)+a[i]);
        }
        rt=update((m-sum)%m,0,m-1,w,rt);
        sum=(sum+b[i])%m;
    }
    return d[rt].val;
}

#undef int

}

long long mow(int n, int c, int b, vector<int> &a, vector<int> &v) {
    Trava::n=n;
    Trava::m=c;
    Trava::T=b;
    for(int i=0;i<n;++i)
        Trava::a[i+1]=a[i];
    for(int i=0;i<n;++i)
        Trava::b[i+1]=v[i];
    return Trava::solve();
}