// 描述
// Dzx从日本回来了，并为TN准备了礼物----一个恐龙模型。TN想把它尽快拼好，但是由于模型很庞大，TN又实在比较懒，所以他希望你为他寻找一个最节省时间的拼装方案。

// 模型是由N个零件组成的，每次TN可以选取两个零件拼装在一起来组成一个新的零件，直到得到完整的模型。由于零件的复杂程度不同，TN每次拼装所需要的时间也是不同的，对于两个零件A和B，假设他们的复杂程度分别为a和b，则TN要将这两个零件拼装在一起所需要的时间为a+b，而这由两个零件所组成的新零件的复杂程度为a+b。

// 现在TN已经统计出了每个零件的复杂程度，你能告诉他最快的拼装方发需要多少时间么？

// 输入
// Line 1： N (1 <= N <= 10000)，零件数目
// Line 2： N Integers，表示每个零件的复杂程度
// 输出
// 最快的拼装方案所需要的时间
// 样例输入
// 3
// 1 2 9
// 样例输出
// 15
#include <iostream>
#include <vector>
#include <algorithm>
#include <string>
#include <stack>
#include <queue>
using namespace std;

// int main(){
//     int n;
//     cin>>n;
//     vector<int> nums(n);
//     int ans=0,cur=0;
//     for(int i=0;i<n;i++) cin>>nums[i];
//     sort(nums.begin(),nums.end());
//     for(int i=0;i<n-1;i++){
//         sort(nums.begin(),nums.end());
//         cur = nums[0] + nums[1];
//         ans += cur;
//         nums[1] = cur;
//         nums[0] = INT_MAX;
//     }
//     cout<<ans<<endl;
//     return 0;
// }

int main(){
    int n;
    cin>>n;
    int ans=0;
    priority_queue<int,vector<int>,greater<int>> q;
    for(int i=0;i<n;i++){
        int x;
        cin>>x;
        q.push(x);
    }
    int ans=0;
    while(!q.empty()){
        int a = q.top();
        a.pop();
        int b = q.top();
        b.pop(); 
        ans += a + b;
        q.push(a+b);
    }
    cout<<ans<<endl;
    return 0;
}

