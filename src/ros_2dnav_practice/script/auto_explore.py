#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import actionlib
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal

class AutoExplorer:
    def __init__(self):
        rospy.init_node('auto_explorer_node', anonymous=False)
        self.client = actionlib.SimpleActionClient('move_base', MoveBaseAction)
        rospy.loginfo("等待 move_base 服务器连接...")
        self.client.wait_for_server()
        rospy.loginfo("move_base 已连接！")

        # ==========================================
        # 针对 5m * 3m 场地的路径点规划
        # ==========================================
        # 策略：以 (0,0) 为起点，向长轴(X)延伸，向宽轴(Y)摆动
        # 注意：这里假设机器人前方是 X 正方向
        # 安全余量：虽然场地宽3米(Y: -1.5 ~ 1.5)，但我们只走到 +/- 1.0，留出0.5m防撞
        # 虽然场地长5米(X: 0 ~ 5)，但我们只走到 4.0，留出1.0m余量
        
        self.waypoints = [
            # 1. 先直行一段，建立主轴地图
            (2.0, 0.0),  
            
            # 2. 去左前方探索障碍物
            (3.5, 1.0),
            
            # 3. 横穿到右前方 (覆盖宽度)
            (3.5, -1.0),
            
            # 4. 回撤到右后方 (填补中间区域)
            (1.5, -1.0),
            
            # 5. 横穿到左后方
            (1.5, 1.0),
            
            # 6. 回到中轴线远端 (确保远处闭合)
            (4.0, 0.0)
        ]

    def send_goal(self, x, y):
        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = "map" # 必须基于 map 坐标系
        goal.target_pose.header.stamp = rospy.Time.now()
        
        goal.target_pose.pose.position.x = x
        goal.target_pose.pose.position.y = y
        goal.target_pose.pose.orientation.w = 1.0 # 默认朝向

        rospy.loginfo(f">>> 前往目标点: X={x}, Y={y}")
        self.client.send_goal(goal)
        
        # 设定超时时间：每个点最多给 25 秒
        # 如果因为障碍物挡路过不去，这就很有用，超时后会自动去下一个点
        finished = self.client.wait_for_result(rospy.Duration(25))
        
        if not finished:
            self.client.cancel_goal()
            rospy.logwarn(f"目标 ({x}, {y}) 超时/不可达，跳过，执行下一个！")
        else:
            state = self.client.get_state()
            if state == actionlib.GoalStatus.SUCCEEDED:
                rospy.loginfo("到达目标！")
            else:
                rospy.logwarn("未能到达目标 (可能被障碍物阻挡)")

    def start_mission(self):
        # 1. 遍历所有探索点
        for x, y in self.waypoints:
            self.send_goal(x, y)
            # 稍微停顿一下，让雷达多扫几圈，提高建图质量
            rospy.sleep(0.5)

        # 2. 最终任务：返回原点 (自主导航返回至初始位姿)
        rospy.loginfo(">>> 所有巡逻点结束，准备返回原点 (0, 0)...")
        self.send_goal(0.0, 0.0)
        rospy.loginfo("任务全部完成！")

if __name__ == '__main__':
    try:
        explorer = AutoExplorer()
        # 启动后等待 3 秒，让 Gmapping 先稳定一下
        rospy.sleep(3)
        explorer.start_mission()
    except rospy.ROSInterruptException:
        pass