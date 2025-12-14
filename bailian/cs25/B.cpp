#include <iostream>
#include <vector>
#include <algorithm>
#include <string>
using namespace std;

int main(){
    string s,t; //判断s是否是t的子串
    while(cin>>s>>t){
        int m=s.size(),n=t.size();
        int i=0,j=0;
        while(i<m && j<n){
            if(s[i]==t[j]){
                i++,j++;
            }else j++;
        }
        if(i==m) cout<<"YES"<<endl;
        else cout<<"NO"<<endl;
    }
    return 0;
}