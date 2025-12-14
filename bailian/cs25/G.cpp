// 描述
// 火星人的血缘关系体系已经够让人困惑了。实际上，火星人想发芽的时候就在他们想发芽的地方。他们分成不同的小组聚集在一起，这样一个火星人可以同时拥有一个父母，也可以有十个。一百个孩子没人会感到惊讶。火星人已经习惯了这种生活方式，他们的生活方式对他们来说很自然。
// 而在行星理事会中，复杂的家谱系统也带来了一些尴尬。在那里，最有价值的火星人会面，因此为了在所有讨论中不冒犯任何人，首先给年长的火星人发言权，然后是年轻的火星人，最后是最年轻且无子的评估者。然而，维持这一秩序并非易事。火星人并不总是认识所有父母（而且关于祖父母也没什么可说的！）。但如果误会先说出孙子，然后才说出他年轻的曾祖父，那就是真正的丑闻。
// 你的任务是制定一个纲领，彻底定义一个命令，确保议会中每位成员都比其后代更早发言。
// 输入
// 标准输入的第一行仅包含一个数字N，1<= N <= 100——火星行星理事会的成员数量。根据数百年的传统，委员会成员以自然数从1到N进行计数。此外，恰好有N行，且第1行包含第1条成员的子嗣列表。子节点列表是一组子节点序列号，按任意顺序排列，中间用空格分隔。孩子名单可能是空的。列表（即使为空）结尾为0。
// 输出
// 标准输出的唯一行应包含一组发言者编号，中间用空格分隔。如果有多个序列满足问题条件，则应将其中任意序列写入标准输出。至少有一个这样的序列总是存在。
// 样例输入
// 5
// 0
// 4 5 1 0
// 1 0
// 5 3 0
// 3 0
// 样例输出
// 2 4 5 3 1


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
    vector<vector<int>> children(n+1);
    vector<int> indegree(n+1,0);
    vector<int> ans;
    for(int i=1;i<=n;i++){
        int child;
        while(cin>>child){
            children[i].push_back(child);
            indegree[i]++;
        }
    }
    queue<int> q;
    for(int i=1;i<=n;i++){
        if(indegree[i]==0) q.push(i);
    }
    while(!q.empty()){
        int cur=q.front();
        q.pop();
        ans.push_back(cur);
        //遍历所有cur的孩子，这些孩子入度都-1
        for(x:children[cur]){
            indegree[x]--;
            //如果孩子入度为0，加入队列
            if(indegree[x]==0) q.push(x);
        }
    }
    for(int x:ans) cout<<x<<" ";
    cout<<endl;
    return 0;
}