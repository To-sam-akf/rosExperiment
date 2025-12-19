#include "ros/ros.h"
#include "ros_base_learning/AddTwoInts.h" // 自动生成的头文件

// 这是服务的回调函数。当收到请求时，ROS会调用这个函数
// 函数返回bool值，输入参数是请求和响应
bool add(ros_base_learning::AddTwoInts::Request  &req,
         ros_base_learning::AddTwoInts::Response &res)
{
  // 从请求中获取数据，进行计算
  res.sum = req.a + req.b;
  ROS_INFO("request: x=%ld, y=%ld", (long int)req.a, (long int)req.b);
  ROS_INFO("sending back response: [%ld]", (long int)res.sum);
  return true; // 返回true表示服务成功
}

int main(int argc, char **argv)
{
  ros::init(argc, argv, "add_two_ints_server");
  ros::NodeHandle n;

  // 创建一个服务，并告诉ROS当收到名为 "add_two_ints" 的请求时，
  // 调用名为 add 的函数
  ros::ServiceServer service = n.advertiseService("add_two_ints", add);
  ROS_INFO("Ready to add two ints.");
  ros::spin(); // 进入循环，等待服务请求

  return 0;
}
