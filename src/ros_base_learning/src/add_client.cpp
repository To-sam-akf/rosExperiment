#include <cstdlib>
#include "ros/ros.h"
#include "ros_base_learning/AddTwoInts.h"

int main(int argc, char **argv)
{
  ros::init(argc, argv, "add_two_ints_client");
  // 检查命令行参数是否正确
  if (argc != 3)
  {
    ROS_INFO("usage: add_two_ints_client X Y");
    return 1;
  }

  ros::NodeHandle n;
  // 创建一个客户端，连接到名为 "add_two_ints" 的服务
  // 服务类型是 ros_base_learning::AddTwoInts
  ros::ServiceClient client = n.serviceClient<ros_base_learning::AddTwoInts>("add_two_ints");

  // 创建一个服务对象
  ros_base_learning::AddTwoInts srv;
  // 从命令行参数填充请求数据
  srv.request.a = atoll(argv[1]);
  srv.request.b = atoll(argv[2]);

  // 调用服务
  if (client.call(srv))
  {
    // 如果服务调用成功，打印响应结果
    ROS_INFO("Sum: %ld", (long int)srv.response.sum);
  }
  else
  {
    ROS_ERROR("Failed to call service add_two_ints");
    return 1;
  }

  return 0;
}
