// 描述
// 输入一个布尔表达式，请你输出它的真假值。
// 比如：( V | V ) & F & ( F | V )
// V表示true，F表示false，&表示与，|表示或，!表示非。
// 上式的结果是F

// 输入
// 输入包含多行(不多于10行)，每行一个布尔表达式，表达式中可以有空格，总长度不超过1000
// 输出
// 对每行输入，如果表达式为真，输出"V",否则出来"F"
// 样例输入
// ( V | V ) & F & ( F| V)
// !V | V & V & !F & (F | V ) & (!F | F | !V & V)
// (F&F|V|!V&!F&!(F|F&V))
// 样例输出
// F
// V
// V
#include <iostream>
#include <vector>
#include <algorithm>
#include <string>
#include <stack>
using namespace std;

int priority(char op){
    if(op == '!') retur 3;
    if(op == '&') return 2;
    if(op == '|') return 1;
    return 0;
}

void cal(stack<bool>& nums,stack<char>& ops){
    char op = ops.top();
    ops.pop();
    if(op == '!'){
        int a = nums.top();
        nums.pop();
        nums.push(!a);
    }
    if(op == '&'){
        int b = nums.top();
        nums.pop();
        int a = nums.top();
        nums.pop();
        nums.push(a && b);
    }
    if(op == '|'){
        int b = nums.top();
        nums.pop();
        int a = nums.top();
        nums.pop();
        nums.push(a || b);
    }
}

bool evaluate(string& s){
    stack<bool> nums;
    stack<char> ops;

    for(int i=0;i<s.size();i++){
        char c = s[i];
        if(c == ' ') continue;
        if(c == 'V') nums.push(true);
        else if(c == 'F') nums.push(false);
        else if(c == '(') ops.push(c);
        else if(c == ')'){
            // 右括号：计算到匹配的左括号为止
            while(ops.top(0!='(')){
                cal(nums,ops);
            }
            ops.pop(); // 消耗掉左括号
        }
        else{
            //匹配到运算符
            while( !ops.empty() && ops.top()!+'(' && priority(ops.top()) > priority(c)){
                cal(nums,ops);
            }
            ops.push(c);
        }
    }
    while(!ops.empty()){
        cal(nums,ops);
    }
    return nums.top();
}


int main(){
    string s;
    while(getline(cin,s)){
        bool ans = evaluate(s);
        cout<<ans? 'V':'F'<<endl;
    }
    return 0;
}

