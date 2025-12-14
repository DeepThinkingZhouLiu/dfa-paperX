// 描述
// 给你一个字符串 path ，表示指向某一文件或目录的 Unix 风格 绝对路径 （以 '/' 开头），请你将其转化为 更加简洁的规范路径。

// 在 Unix 风格的文件系统中规则如下：

// 一个点 '.' 表示当前目录本身。

// 此外，两个点 '..' 表示将目录切换到上一级（指向父目录）。

// 任意多个连续的斜杠（即，'//' 或 '///'）都被视为单个斜杠 '/'。

// 任何其他格式的点（例如，'...' 或 '....'）均被视为有效的文件/目录名称。

// 返回的 简化路径 必须遵循下述格式：

// 始终以斜杠 '/' 开头。

// 两个目录名之间必须只有一个斜杠 '/' 。

// 最后一个目录名（如果存在）不能 以 '/' 结尾。

// 此外，路径仅包含从根目录到目标文件或目录的路径上的目录（即，不含 '.' 或 '..'）。

// 返回简化后得到的 规范路径 。


// 1 <= len(path) <= 3000

// path 由英文字母，数字，'.'，'/' 或 '_' 组成。

// path 是一个有效的 Unix 风格绝对路径。

// 输入
// 字符串 path
// 输出
// 字符串，表示简化后得到的 规范路径
// 样例输入
// sample1 input:
// /home/

// sample1 output:
// /home

// # 应删除尾随斜杠。

// sample2 input:
// /home//foo/

// sample2 output:
// /home/foo

// # 多个连续的斜杠被单个斜杠替换。
// 样例输出
// sample3 input:
// /home/user/Documents/../Pictures

// sample3 output:
// /home/user/Pictures

// # 两个点 ".." 表示上一级目录（父目录）。

// sample4 input:
// /../

// sample4 output:
// /

// # 不可能从根目录上升一级目录。

// sample5 input:
// /.../a/../b/c/../d/./

// sample5 output:
// /.../b/d

// # `"..."` 在这个问题中是一个合法的目录名。
#include <iostream>
#include <vector>
#include <algorithm>
#include <string>
#include <stack>
#include <queue>
using namespace std;
// int main(){
//     string path;
//     cin>>path;
//     vector<string> stk;  // 用 vector 模拟栈，方便最后拼接
//     string token; // 
//     for(int i=0;i<path.size();i++){
//         if(path[i]=='/'){
//             // 遇到分隔符，处理之前收集的token
//             if(!token.empty()){//token非空才处理
//                 if(token == ".."){// 回到上一级目录
//                     if(!stk.empty()) stk.pop_back();
//                 }
//                 else if(token == "."){ // 当前目录，不处理
//                     continue;
//                 }
//                 else { // 其他类型的token，入栈
//                     stl.push_back(token);
//                 }
//                 token = ""; //读取完当前token后清空
//             }
//         }
//         else token += path[i]; // 不是分隔符，当前位追加到token
//     }
//     // 循环结束后，可能还有最后一个 token 没处理
//     // 比如 "/home/user" 最后没有 '/'
//     if(!token.empty()){
//         if(token == ".."){
//             if(!stk.empty()) stk.pop_back();
//         }else if(token == ".") continue;
//         else stk.push_back(token);
//     }

//     if(stk.empty()) cout<<"/"<<endl;
//     else{
//         for(auto x:stk){
//             cout<<"/" <<x;
//         }
//         cout<<endl;
//     }
//     return 0;
// }

int main(){
    string path;
    cin>>path;
    stack<string> stk;
    stringstream ss(path);
    string token;
    while(getline(ss,token,'/')){
        if(token == "." || token == "") continue;
        else if(token == ".."){
            if(!stk.empty()) stk.pop();
        }
        else stk.push(token);
    }
    if(stk.empty()) cout<<"/"<<endl;
    else{
        string ans; 
        while(!stk.empty()){
            ans = "/" + stk.pop() + ans;
            stk.pop();
        }
        cout<<ans<<endl;
    }
    return 0;
}
