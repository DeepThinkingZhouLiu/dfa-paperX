// 描述
// 忍者道具有很多种，苦无，飞镖，震爆弹。L君热衷于收集忍者道具，现在他有N个道具，每个道具的重量分别是C1、C2…CN。现在他想把这N个道具装到载重量为W的工具包里，请问他最少需要多少个工具包？

// 输入
// 第一行包含两个用空格隔开的整数，N和W。
// 接下来N行每行一个整数，其中第i+1行的整数表示第i个道具的重量Ci。
// 输出
// 输出一个整数，最少需要多少个工具包。
// 样例输入
// 5 1996
// 1
// 2
// 1994
// 12
// 29
// 样例输出
// 2
#include <iostream>
#include <vector>
#include <algorithm>
#include <string>
#include <stack>
using namespace std;

int main(){
    int n,w;
    cin>>n>>w;
    vector<int> item(n);
    for(int i=0;i<n;i++) cin>>item[i];
    sort(item.begin(),item.end(),greater<int>());
    vector<int> bins;
    for(int i=0;i<n;i++){
        bool flag=false;
        for(int j=0;j<bins.size();j++){
            if(bins[j] + item[i] <= w){
                bins[j] += item[i];
                flag=true;
                break;
            }
        }
        if(!flag){
            bins.push_back(item[i]);
        }
    }
    cout<<bins.size()<<endl;
    return 0;
}