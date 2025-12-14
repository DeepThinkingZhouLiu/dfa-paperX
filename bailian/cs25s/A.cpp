// 描述
// 小明在一条河上从西向东顺序测得n个水位监测点的水位。如果一个监测点的水位比上一个和下一个监测点的水位都高，则称该监测点是一个波峰。最西边的监测点水位只要比下一个监测点高，就算波峰；最东边的监测点，水位只要比上一个监测点高，也算波峰。求波峰数目。

// 输入
// 第一行是整数n ( 2 <= n <= 100)，表示监测点数目
// 第二行有n个整数，即从西向东n个监测点的水位
// 输出
// 波峰数目
// 样例输入
// 样例1：
// 5
// 8 12 7 3 6
// 样例2：
// 7
// 8 2 3 1 1 2 1
// 样例3:
// 5
// 1 2 3 3 2
// 样例4:
// 2
// 1 2
// 样例输出
// 样例1：
// 2
// 样例2：
// 3
// 样例3:
// 0
// 样例4:
// 1


#include <iostream>
#include <vector>
#include <algorithm>
#include <string>
#include <stack>
#include <queue>
using namespace std;

int main(){
    int n;
    while(cin>>n){
        vector<int> nums(n);
        int x;
        while(cin>>x){
            for(int i=0;i<n;i++) nums[i]=x;
        }
        int ans=0;
        if(nums[0] > nums[1]) ans++;
        if(nums[n-1] > nums[n-2]) ans++;
        for(int i=1;i<n-1;i++){
            if(nums[i] > nums[i-1] && nums[i] > nums[i+1]) ans++;
        }
        cout<<ans<<endl;
    }
    return 0;
}

