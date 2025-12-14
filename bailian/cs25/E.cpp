// 描述
// 一个正整数数列，可以将它切割成若干个数据段，每个数据段由值相同的相邻元素构成。该数列的神奇之处在于，每次切除一个数据段后，
// 该数据段前后的元素自动连接在一起成为邻居。例如从数列“2 8 9 7 7 6 9 4”中切除数据段“7 7 ”后，余下的元素会构成数列“2 8 9 6 9 4”
// 请问若要将该数列切割成若干个数据段，则至少会切出来几个数据段？
// 样例： 按下列顺序切割数列“2 8 9 7 7 6 9 4”，只要切割成 6段
//   切割出“7 7”，余下 “2 8 9 6 9 4”
//   切割出 “6”，余下 “2 8 9 9 4”
//   切割出 “9 9”，余下 “2 8 4”
//   切割出 “2”，余下 “8 4”
//   切割出 “8”，余下 “4”


// 输入
// 第一行是一个整数，示共有多少组测试数据。每组测试数据的输入包括两行：第一行是整数N, N<=200,表示数列的长度，第二行是N个正整数。
// 输出
// 每个测试案例的输出占一行，是一个整数。格式是：
// Case n: x
// n是测试数据组编号，x是答案
// 样例输入
// 2
// 8
// 2 8 9 7 7 6 9 4
// 16
// 2 8 9 7 7 6 9 4 4 2 8 4 2 7 6 9
// 样例输出
// Case 1: 6
// Case 2: 11
#include <iostream>
#include <vector>
#include <algorithm>
#include <string>
#include <stack>
using namespace std;

int main(){
    int T;
    cin>>T;
    for(int t=1;t<=T;t++){
        int n;
        cin>>n;
        vector<int> nums(n);
        for(int i=0;i<n;i++) cin>>nums[i];
        vector<vector<int>> dp(n,vector<int>(n,INT_MAX));
        for(int i=0;i<n;i++) dp[i][i]=1;
        for(int len=2;len<=n;i++){
            for(int i=0;i<n-len+1;len++){ //枚举起点
                int j=i+len-1; //终点
                if(nums[i]==nums[j]) dp[i][j]=dp[i][j-1];
                for(int k=i;k<j;k++){ //枚举分割点
                    // 情况1：普通分割，左右两边独立处理
                    dp[i][j] = min(dp[i][j],dp[i][k]+dp[k+1][j]);
                    // 情况2：如果nums[k]==nums[j]，j可以和k合并
                    if(nums[k]==nums[j]){
                        int mid = (k+1 <= j-1) ? dp[k+1][j-1] : 0; 
                        dp[i][j] = min( dp[i][j],dp[i][k] + mid );
                    }
                    
                }
            }
        }
        cout<<"Case "<<t<<": "<<dp[0][n-1]<<endl;
    }
    return 0;
}