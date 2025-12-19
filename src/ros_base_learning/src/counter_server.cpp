#include <ros/ros.h>
#include <actionlib/server/simple_action_server.h>
#include "ros_base_learning/CounterAction.h" // 自动生成的头文件

class CounterActionServer
{
protected:
  ros::NodeHandle nh_;
  // 定义一个简单的动作服务器
  actionlib::SimpleActionServer<ros_base_learning::CounterAction> as_;
  std::string action_name_;
  // 定义反馈和结果对象
  ros_base_learning::CounterFeedback feedback_;
  ros_base_learning::CounterResult result_;

public:
  CounterActionServer(std::string name) :
    as_(nh_, name, boost::bind(&CounterActionServer::executeCB, this, _1), false),
    action_name_(name)
  {
    as_.start(); // 启动服务器
    ROS_INFO("Action server started.");
  }

  // 收到Goal后的回调函数
  void executeCB(const ros_base_learning::CounterGoalConstPtr &goal)
  {
    ros::Rate r(2); // 设置频率为2Hz
    bool success = true;

    ROS_INFO("%s: Executing, counting up to %d", action_name_.c_str(), goal->target_number);

    // 主循环，执行计数任务
    for(int i=1; i<=goal->target_number; i++)
    {
      // 检查客户端是否请求取消任务
      if (as_.isPreemptRequested() || !ros::ok())
      {
        ROS_INFO("%s: Preempted", action_name_.c_str());
        as_.setPreempted(); // 将当前任务设置为“已抢占”
        success = false;
        break;
      }
      
      // 发送反馈
      feedback_.current_number = i;
      as_.publishFeedback(feedback_);
      
      r.sleep();
    }

    // 任务完成后，发送最终结果
    if(success)
    {
      result_.final_count = feedback_.current_number;
      ROS_INFO("%s: Succeeded", action_name_.c_str());
      as_.setSucceeded(result_);
    }
  }
};

int main(int argc, char** argv)
{
  ros::init(argc, argv, "counter_server");
  CounterActionServer server("counter");
  ros::spin();
  return 0;
}