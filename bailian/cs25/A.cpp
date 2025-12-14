#include <iostream>
#include <vector>
#include <algorithm>
using namespace std;

int main(){
    int n;
    cin>>n;
    vector<vector<int>> grid(n,vector<int>(n));
    vector<int> win(n,0);
    for(int i=0;i<n;i++){
        for(int j=0;j<n;j++){
            cin>>grid[i][j];
        }
    }
    int max_win=0;
    int ans_id=n+1;
    for(int i=0;i<n;i++){
        for(int j=0;j<n;j++){
            if(grid[i][j]==3){
                win[i]++;
            }
        }
    }
    for(int i=0;i<n;i++){
        if(win[i]>max_win){
            max_win=win[i];
            ans_id=min(ans_id,i+1);
        }else if(win[i]==max_win){
            ans_id=min(ans_id,i+1);
        }
    }
    cout<<ans_id<<endl;
    return 0;
}