#include <ros/ros.h>
#include <actionlib/client/simple_action_client.h>
#include <actionlib/client/terminal_state.h>
#include "ros_base_learning/CounterAction.h"

// 当任务完成时，会调用这个回调函数一次
void doneCb(const actionlib::SimpleClientGoalState& state,
            const ros_base_learning::CounterResultConstPtr& result)
{
  ROS_INFO("Finished in state [%s]", state.toString().c_str());
  ROS_INFO("Final count is: %d", result->final_count);
  ros::shutdown();
}

// 当任务被激活（服务器开始处理）时，会调用这个回调函数一次
void activeCb()
{
  ROS_INFO("Goal just went active");
}

// 当服务器发送Feedback时，会调用这个回调函数
void feedbackCb(const ros_base_learning::CounterFeedbackConstPtr& feedback)
{
  ROS_INFO("Got feedback of count: %d", feedback->current_number);
}

int main (int argc, char **argv)
{
  ros::init(argc, argv, "counter_client");

  // 创建一个简单的动作客户端，连接到名为 "counter" 的服务器
  actionlib::SimpleActionClient<ros_base_learning::CounterAction> ac("counter", true);

  ROS_INFO("Waiting for action server to start.");
  ac.waitForServer(); // 无限期等待服务器启动

  ROS_INFO("Action server started, sending goal.");
  
  // 创建一个Goal并发送给服务器
  ros_base_learning::CounterGoal goal;
  goal.target_number = 10; // 设置目标为数到10
  
  // 注册回调函数
  ac.sendGoal(goal, &doneCb, &activeCb, &feedbackCb);

  ros::spin(); // 等待结果

  return 0;
}