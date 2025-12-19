#include "ros/ros.h"
#include "geometry_msgs/Twist.h"

// 声明一个全局的发布者对象
// 这样做是为了让回调函数能够访问并使用它来发布消息
ros::Publisher transformed_pub;

// 定义消息回调函数
// 当订阅者接收到来自 /teleop_turtle/cmd_vel 话题的消息时，此函数将被调用
void cmdVelCallback(const geometry_msgs::Twist::ConstPtr& msg)
{
    // --- 步骤1: 打印接收到的原始消息 ---
    // 使用ROS_INFO将接收到的线速度和角速度信息输出到终端
    ROS_INFO("Received  [Linear X: %.2f, Angular Z: %.2f]", msg->linear.x, msg->angular.z);

    // --- 步骤2: 创建一个新的Twist消息用于发布 ---
    geometry_msgs::Twist transformed_msg;

    // --- 步骤3: 自定义转换逻辑 ---
    // 1. 将前进方向（正的linear.x）变为后退方向（负的linear.x）
    transformed_msg.linear.x = -msg->linear.x;
    // 2. 将转向速度（angular.z）减半，使其转向更慢
    transformed_msg.angular.z = 0.5 * msg->angular.z;
    // 其他速度分量保持为0
    transformed_msg.linear.y = 0;
    transformed_msg.linear.z = 0;
    transformed_msg.angular.x = 0;
    transformed_msg.angular.y = 0;

    // --- 步骤4: 打印即将发布的新消息 ---
    // 使用ROS_INFO将转换后的速度信息输出到终端
    ROS_INFO("Published [Linear X: %.2f, Angular Z: %.2f]", transformed_msg.linear.x, transformed_msg.angular.z);
    ROS_INFO("-----------------------------------------"); // 添加分隔线使输出更清晰

    // --- 步骤5: 发布转换后的消息 ---
    // 使用全局发布者对象将新消息发布到 /turtlesim/cmd_vel_cov 话题
    transformed_pub.publish(transformed_msg);
}

int main(int argc, char **argv)
{
    // 初始化ROS节点，并命名为 "message_transform_node"
    ros::init(argc, argv, "message_transform_node");

    // 创建一个节点句柄
    ros::NodeHandle nh;

    // --- 初始化发布者 ---
    // 让 transformed_pub 在 "/turtlesim/cmd_vel_cov" 话题上发布 geometry_msgs::Twist 类型的消息
    // 队列大小设置为 10
    transformed_pub = nh.advertise<geometry_msgs::Twist>("/turtlesim/cmd_vel_cov", 10);

    // --- 初始化订阅者 ---
    // 订阅 "/teleop_turtle/cmd_vel" 话题，接收 geometry_msgs::Twist 类型的消息
    // 收到消息后，调用 cmdVelCallback 函数进行处理
    ros::Subscriber sub = nh.subscribe("/teleop_turtle/cmd_vel", 10, cmdVelCallback);

    // 进入一个循环，等待回调函数的触发
    ros::spin();

    return 0;
}