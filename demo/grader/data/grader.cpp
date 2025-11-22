#include <iostream>
#include <vector>
#include "strategy.h"

using namespace std; 

int main() {
    freopen("strategy.in","r",stdin);
    freopen("strategy.out","w",stdout);
    ios::sync_with_stdio(false); cin.tie(nullptr);
    int n, c, b;
    
    // Read input
    cin >> n >> c >> b;
    
    vector<int> a(n);
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }
    
    vector<int> v(n);
    for (int i = 0; i < n; i++) {
        cin >> v[i];
    }
    
    // Call the solution function and output result
    long long result = mow(n, c, b, a, v);
    cout << result << endl;
    
    return 0;
}
