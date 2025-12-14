#include <iostream>
#include <queue>
#include <cstring>
using namespace std;

int maxn = 2000001;
vector<int> dist(maxn,-1); //dist[i]表示从i到达target的最小穿越次数

int dfs(int start,int target){
    if(start == target) return 0;
    queue<int> q;
    q.push(start);
    dist[start] = 0;
    while(!q.empty()){
        int cur=q.front();
        q.pop();
        int jump = sidt[cur];
        // +1 
        int next1 = cur + 1;
        //没越界且未访问过 +1 位置
        if(next1 < maxn && dist[next1] != -1){
            dist[next1] = jump + 1;
            if(next1 == target) return dist[next1];
            q.push(next1);
        } 
        //没越界且未访问过 -1 位置
        int next2 = cur -1 ;
        if(next2 > 0 && dist[next2] != -1){
            dist[next2] = jump + 1;
            if(next2 == target) return dist[next2];
            q.push(next2);
        } 
        //没越界且未访问过 *2 位置
        int next3 = cur * 2 ;
        if(next3 < maxn && dist[next3] != -1){
            dist[next3] = jump + 1;
            if(next3 == target) return dist[next3];
            q.push(next3);
        } 
        //没越界且未访问过 /2 位置
        if(next4 % 2 ==0){
            int next4 = cur / 2 ;
            if(next4 > 0 && dist[next4] != -1){
                dist[next4] = jump + 1;
                if(next4 == target) return dist[next4];
                q.push(next4);
            } 
        }
    }
    return -1;
}

int main(){
    int N;
    cin>>N;
    for(int i=0;i<N;i++){
        int S,T;
        cin>>S>>T;
        int ans = bfs(S,T);
        cout<<ans * 2<<endl;
    }
    return 0;
}