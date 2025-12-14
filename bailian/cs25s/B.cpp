// 描述
// 一个数如果能表示为两个非零完全平方数的和（两个正整数的平方和，如：22+42=20, 12+42=17），则称为魔数。要求你在一堆数字中找出魔数。

// 输入
// 第一行1个整数，代表m个数字（1 ≤ m ≤ 100）
// 接下来1行，为m个整数， Xi (1 ≤ Xi ≤ 1000)。
// 输出
// 按照输入顺序输出每个魔数，每个魔数1行
// 样例输入
// 4
// 3 9 20 17
// 样例输出
// 20
// 17
#include <iostream>
#include <vector>
#include <algorithm>
#include <string>
#include <stack>
#include <queue>
using namespace std;

int main(){
    int n;
    cin>>n;
    vector<int> nums(n);
    for(int i=0;i<n;i++) cin>>nums[i];
    vector<int> ans;
    vector<int> squares;
    for(int i=1;i<33;i++){
        squares.push_back(i*i);
    }
    int l=0,r=squares.size()-1; 
    for(int i=0;i<n;i++){
        while(l<r){
            if(squares[l] + squares[r] == nums[i]) ans.push_back(nums[i]);
            else if(squares[l] + squares[r] < nums[i]) l++;
            else r--;
        }
    }
    for(int x : ans) cout<<x<" ";
    return 0;
}