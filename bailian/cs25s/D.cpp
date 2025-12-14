// 描述
// 五一到了，PKU-ACM队组织大家去登山观光，队员们发现山上一个有N个景点，并且决定按照顺序来浏览这些景点，即每次所浏览景点的编号都要大于前一个浏览景点的编号。同时队员们还有另一个登山习惯，就是不连续浏览海拔相同的两个景点，并且一旦开始下山，就不再向上走了。队员们希望在满足上面条件的同时，尽可能多的浏览景点，你能帮他们找出最多可能浏览的景点数么？

// 输入
// Line 1： N (2 <= N <= 1000) 景点数
// Line 2： N个非负整数，每个景点的海拔 (≤1000)
// 输出
// 最多能浏览的景点数
// 样例输入
// 8
// 186 186 150 200 160 130 197 220
// 样例输出 186 200 160 130
// 4
// 相同海拔不能连续 && 只能有一个递减序列，可以用一个flag判断是否开始下坡
// 1.先判断相邻位置是否是相同海拔  2.求最长递增子序列  3.求最长递减子序列 
// 最终结果应该为：同海拔 + 最长递增长度 + 最长递减长度
#include <iostream>
#include <vector>
#include <algorithm>
#include <string>
#include <stack>
#include <queue>
using namespace std;

int main(){
    int N;
    cin>>N;
    vector<int> nums(N);
    vector<int> up(N,1);
    vector<int> down(N,1);
    for(int i=1;i<N;i++){
        for(int j=0;j<N;j++){
            if(nums[i]>nums[j]){
                up[i] = max(up[i],up[j]+1);
            }
        }
    }

    for(int i = N-2;i>=0;i--){
        for(int j = N-1;j>i;j--){
            if(nums[i]>nums[j]){
                down[i] = max(down[i],down[j]+1);
            }
        }
    }

    int ans = 0;
    for(int i=0;i<N;i++){
        ans = max(ans,up[i]+down[i]-1);
    }
    cout<<ans<<endl;
    return 0;
}