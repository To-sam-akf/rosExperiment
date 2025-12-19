#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import actionlib
import numpy as np
import tf
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from nav_msgs.msg import OccupancyGrid
from math import sqrt, pow, floor

class FrontierExplorerLite:
    def __init__(self):
        rospy.init_node('frontier_explorer_lite_node')

        # === 1. 核心参数 ===
        self.map_data = None
        self.map_info = None
        self.robot_pose = None
        
        # 场地范围限制 (米) - 你的场地是 5x3
        # 我们稍微放宽一点，避免边界的点被切掉
        self.limit_x_min = -4.0
        self.limit_x_max = 7.0
        self.limit_y_min = -4.0
        self.limit_y_max = 4.0

        # 聚类网格大小 (米)
        # 作用：将 0.5m 范围内的所有前沿点合并为一个目标点
        self.cluster_grid_size = 0.5 

        # 监听机器人位置
        self.tf_listener = tf.TransformListener()

        # 订阅地图
        self.map_sub = rospy.Subscriber('/map', OccupancyGrid, self.map_callback)

        # MoveBase 客户端
        self.client = actionlib.SimpleActionClient('move_base', MoveBaseAction)
        rospy.loginfo("正在连接 move_base...")
        self.client.wait_for_server()
        rospy.loginfo("move_base 连接成功！")

        # 失败黑名单 (如果某个点去不了，就把它记下来，不再尝试)
        self.blacklist = []

    def map_callback(self, msg):
        self.map_info = msg.info
        # 转为 numpy 2D 数组
        # 数据类型 int8: -1(未知), 0(自由), 100(占用)
        raw_data = np.array(msg.data, dtype=np.int8)
        self.map_data = raw_data.reshape((msg.info.height, msg.info.width))

    def get_robot_pose(self):
        """ 获取机器人当前的世界坐标 """
        try:
            (trans, rot) = self.tf_listener.lookupTransform('/map', '/base_link', rospy.Time(0))
            return trans[0], trans[1]
        except (tf.LookupException, tf.ConnectivityException, tf.ExtrapolationException):
            return None, None

    def find_frontiers_manual(self):
        """ 
        手动寻找前沿点：
        原理：找到值为0(自由)的点，且其上下左右有值为-1(未知)的点
        """
        if self.map_data is None:
            return []

        h, w = self.map_data.shape
        resolution = self.map_info.resolution
        origin_x = self.map_info.origin.position.x
        origin_y = self.map_info.origin.position.y

        # 1. 创建掩码
        # mask_free: 所有的自由空间
        mask_free = (self.map_data == 0)
        # mask_unknown: 所有的未知空间
        mask_unknown = (self.map_data == -1)

        # 2. 膨胀未知区域 (利用切片位移，速度极快，无需卷积库)
        # 只要上下左右有一个邻居是 Unknown，这个位置就标记为 True
        has_unknown_neighbor = np.zeros_like(mask_free, dtype=bool)
        
        # 检查上邻居
        has_unknown_neighbor[1:, :] |= mask_unknown[:-1, :]
        # 检查下邻居
        has_unknown_neighbor[:-1, :] |= mask_unknown[1:, :]
        # 检查左邻居
        has_unknown_neighbor[:, 1:] |= mask_unknown[:, :-1]
        # 检查右邻居
        has_unknown_neighbor[:, :-1] |= mask_unknown[:, 1:]

        # 3. 前沿点 = (自己是自由的) AND (邻居有未知的)
        frontier_mask = mask_free & has_unknown_neighbor

        # 4. 获取坐标索引
        # y_idxs, x_idxs 是满足条件的像素坐标
        y_idxs, x_idxs = np.where(frontier_mask)

        # 5. 转换为世界坐标
        world_points = []
        for y, x in zip(y_idxs, x_idxs):
            wx = origin_x + (x + 0.5) * resolution
            wy = origin_y + (y + 0.5) * resolution
            
            # 简单的范围过滤，只保留场地附近的点
            if (self.limit_x_min < wx < self.limit_x_max and 
                self.limit_y_min < wy < self.limit_y_max):
                world_points.append((wx, wy))

        return world_points

    def grid_clustering(self, points):
        """
        手动网格聚类法 (替代 DBSCAN)：
        把地图切成小格子，计算每个格子里所有点的平均值
        """
        if not points:
            return []

        grids = {} # 字典: key=(grid_x, grid_y), value=[sum_x, sum_y, count]

        for px, py in points:
            # 计算该点属于哪个网格索引
            gx = int(floor(px / self.cluster_grid_size))
            gy = int(floor(py / self.cluster_grid_size))
            key = (gx, gy)

            if key not in grids:
                grids[key] = [0.0, 0.0, 0]
            
            grids[key][0] += px
            grids[key][1] += py
            grids[key][2] += 1

        centroids = []
        for key in grids:
            total_x, total_y, count = grids[key]
            # 过滤：如果一个格子里点太少(比如小于3个)，说明是噪点，忽略
            if count >= 3:
                centroids.append((total_x / count, total_y / count))

        return centroids

    def send_goal(self, x, y):
        """ 发送导航目标 """
        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = "map"
        goal.target_pose.header.stamp = rospy.Time.now()
        goal.target_pose.pose.position.x = x
        goal.target_pose.pose.position.y = y
        goal.target_pose.pose.orientation.w = 1.0 # 朝向无所谓

        rospy.loginfo(f"导航至: ({x:.2f}, {y:.2f})")
        self.client.send_goal(goal)
        
        # 等待结果，最多等 15 秒 (场地小，不需要等太久)
        finished = self.client.wait_for_result(rospy.Duration(15))

        if not finished:
            self.client.cancel_goal()
            return False
        
        state = self.client.get_state()
        return state == actionlib.GoalStatus.SUCCEEDED

    def run(self):
        rate = rospy.Rate(1.0) # 1Hz
        start_time = rospy.Time.now()

        # 等待第一帧地图
        while self.map_data is None and not rospy.is_shutdown():
            rospy.loginfo("正在等待地图数据...")
            rospy.sleep(1)
        
        # 等待几秒让 gmapping 先把初始区域扫出来
        rospy.sleep(3) 

        rospy.loginfo(">>> 开始自主探索 <<<")

        while not rospy.is_shutdown():
            # 1. 获取机器人当前位置
            rx, ry = self.get_robot_pose()
            if rx is None: continue

            # 2. 获取原始前沿点 (像素级)
            raw_points = self.find_frontiers_manual()
            
            # 3. 聚类，得到候选目标点
            candidates = self.grid_clustering(raw_points)

            # 4. 选择最佳目标 (贪婪算法：找最近的)
            best_target = None
            min_dist = float('inf')

            for tx, ty in candidates:
                # 检查是否在黑名单 (之前去过但失败了)
                is_bad = False
                for bx, by in self.blacklist:
                    if sqrt((tx-bx)**2 + (ty-by)**2) < 0.8: # 0.8m 范围内视为同一个坑
                        is_bad = True
                        break
                if is_bad: continue

                # 计算距离
                dist = sqrt((tx-rx)**2 + (ty-ry)**2)

                # 过滤：距离太近的点不需要去 (雷达已经扫到了)
                if dist < 0.6: continue

                if dist < min_dist:
                    min_dist = dist
                    best_target = (tx, ty)

            # 5. 执行逻辑
            if best_target:
                success = self.send_goal(best_target[0], best_target[1])
                if not success:
                    rospy.logwarn("无法到达目标，加入黑名单")
                    self.blacklist.append(best_target)
                    # 原地小幅度旋转一下，尝试更新地图视角
                    # (可选) 发布 cmd_vel 让机器人转 30度
            else:
                rospy.loginfo("没有发现新的探索点，或者所有点都探索完毕。")
                break
            
            # 6. 超时强制回家 (例如 4分30秒)
            if (rospy.Time.now() - start_time).to_sec() > 270:
                rospy.logwarn("时间快到了，强制回家！")
                break

            rate.sleep()

        # 7. 任务结束，返回原点
        rospy.loginfo("探索结束，正在返回原点 (0, 0)...")
        self.send_goal(0.0, 0.0)
        rospy.loginfo("任务完成！")

if __name__ == '__main__':
    try:
        explorer = FrontierExplorerLite()
        explorer.run()
    except rospy.ROSInterruptException:
        pass#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import actionlib
import numpy as np
import tf
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from nav_msgs.msg import OccupancyGrid
from math import sqrt, pow, floor

class FrontierExplorerLite:
    def __init__(self):
        rospy.init_node('frontier_explorer_lite_node')

        # === 1. 核心参数 ===
        self.map_data = None
        self.map_info = None
        self.robot_pose = None
        
        # 场地范围限制 (米) - 你的场地是 5x3
        # 我们稍微放宽一点，避免边界的点被切掉
        self.limit_x_min = -4.0
        self.limit_x_max = 7.0
        self.limit_y_min = -4.0
        self.limit_y_max = 4.0

        # 聚类网格大小 (米)
        # 作用：将 0.5m 范围内的所有前沿点合并为一个目标点
        self.cluster_grid_size = 0.5 

        # 监听机器人位置
        self.tf_listener = tf.TransformListener()

        # 订阅地图
        self.map_sub = rospy.Subscriber('/map', OccupancyGrid, self.map_callback)

        # MoveBase 客户端
        self.client = actionlib.SimpleActionClient('move_base', MoveBaseAction)
        rospy.loginfo("正在连接 move_base...")
        self.client.wait_for_server()
        rospy.loginfo("move_base 连接成功！")

        # 失败黑名单 (如果某个点去不了，就把它记下来，不再尝试)
        self.blacklist = []

    def map_callback(self, msg):
        self.map_info = msg.info
        # 转为 numpy 2D 数组
        # 数据类型 int8: -1(未知), 0(自由), 100(占用)
        raw_data = np.array(msg.data, dtype=np.int8)
        self.map_data = raw_data.reshape((msg.info.height, msg.info.width))

    def get_robot_pose(self):
        """ 获取机器人当前的世界坐标 """
        try:
            (trans, rot) = self.tf_listener.lookupTransform('/map', '/base_link', rospy.Time(0))
            return trans[0], trans[1]
        except (tf.LookupException, tf.ConnectivityException, tf.ExtrapolationException):
            return None, None

    def find_frontiers_manual(self):
        """ 
        手动寻找前沿点：
        原理：找到值为0(自由)的点，且其上下左右有值为-1(未知)的点
        """
        if self.map_data is None:
            return []

        h, w = self.map_data.shape
        resolution = self.map_info.resolution
        origin_x = self.map_info.origin.position.x
        origin_y = self.map_info.origin.position.y

        # 1. 创建掩码
        # mask_free: 所有的自由空间
        mask_free = (self.map_data == 0)
        # mask_unknown: 所有的未知空间
        mask_unknown = (self.map_data == -1)

        # 2. 膨胀未知区域 (利用切片位移，速度极快，无需卷积库)
        # 只要上下左右有一个邻居是 Unknown，这个位置就标记为 True
        has_unknown_neighbor = np.zeros_like(mask_free, dtype=bool)
        
        # 检查上邻居
        has_unknown_neighbor[1:, :] |= mask_unknown[:-1, :]
        # 检查下邻居
        has_unknown_neighbor[:-1, :] |= mask_unknown[1:, :]
        # 检查左邻居
        has_unknown_neighbor[:, 1:] |= mask_unknown[:, :-1]
        # 检查右邻居
        has_unknown_neighbor[:, :-1] |= mask_unknown[:, 1:]

        # 3. 前沿点 = (自己是自由的) AND (邻居有未知的)
        frontier_mask = mask_free & has_unknown_neighbor

        # 4. 获取坐标索引
        # y_idxs, x_idxs 是满足条件的像素坐标
        y_idxs, x_idxs = np.where(frontier_mask)

        # 5. 转换为世界坐标
        world_points = []
        for y, x in zip(y_idxs, x_idxs):
            wx = origin_x + (x + 0.5) * resolution
            wy = origin_y + (y + 0.5) * resolution
            
            # 简单的范围过滤，只保留场地附近的点
            if (self.limit_x_min < wx < self.limit_x_max and 
                self.limit_y_min < wy < self.limit_y_max):
                world_points.append((wx, wy))

        return world_points

    def grid_clustering(self, points):
        """
        手动网格聚类法 (替代 DBSCAN)：
        把地图切成小格子，计算每个格子里所有点的平均值
        """
        if not points:
            return []

        grids = {} # 字典: key=(grid_x, grid_y), value=[sum_x, sum_y, count]

        for px, py in points:
            # 计算该点属于哪个网格索引
            gx = int(floor(px / self.cluster_grid_size))
            gy = int(floor(py / self.cluster_grid_size))
            key = (gx, gy)

            if key not in grids:
                grids[key] = [0.0, 0.0, 0]
            
            grids[key][0] += px
            grids[key][1] += py
            grids[key][2] += 1

        centroids = []
        for key in grids:
            total_x, total_y, count = grids[key]
            # 过滤：如果一个格子里点太少(比如小于3个)，说明是噪点，忽略
            if count >= 3:
                centroids.append((total_x / count, total_y / count))

        return centroids

    def send_goal(self, x, y):
        """ 发送导航目标 """
        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = "map"
        goal.target_pose.header.stamp = rospy.Time.now()
        goal.target_pose.pose.position.x = x
        goal.target_pose.pose.position.y = y
        goal.target_pose.pose.orientation.w = 1.0 # 朝向无所谓

        rospy.loginfo(f"导航至: ({x:.2f}, {y:.2f})")
        self.client.send_goal(goal)
        
        # 等待结果，最多等 15 秒 (场地小，不需要等太久)
        finished = self.client.wait_for_result(rospy.Duration(15))

        if not finished:
            self.client.cancel_goal()
            return False
        
        state = self.client.get_state()
        return state == actionlib.GoalStatus.SUCCEEDED

    def run(self):
        rate = rospy.Rate(1.0) # 1Hz
        start_time = rospy.Time.now()

        # 等待第一帧地图
        while self.map_data is None and not rospy.is_shutdown():
            rospy.loginfo("正在等待地图数据...")
            rospy.sleep(1)
        
        # 等待几秒让 gmapping 先把初始区域扫出来
        rospy.sleep(3) 

        rospy.loginfo(">>> 开始自主探索 <<<")

        while not rospy.is_shutdown():
            # 1. 获取机器人当前位置
            rx, ry = self.get_robot_pose()
            if rx is None: continue

            # 2. 获取原始前沿点 (像素级)
            raw_points = self.find_frontiers_manual()
            
            # 3. 聚类，得到候选目标点
            candidates = self.grid_clustering(raw_points)

            # 4. 选择最佳目标 (贪婪算法：找最近的)
            best_target = None
            min_dist = float('inf')

            for tx, ty in candidates:
                # 检查是否在黑名单 (之前去过但失败了)
                is_bad = False
                for bx, by in self.blacklist:
                    if sqrt((tx-bx)**2 + (ty-by)**2) < 0.8: # 0.8m 范围内视为同一个坑
                        is_bad = True
                        break
                if is_bad: continue

                # 计算距离
                dist = sqrt((tx-rx)**2 + (ty-ry)**2)

                # 过滤：距离太近的点不需要去 (雷达已经扫到了)
                if dist < 0.6: continue

                if dist < min_dist:
                    min_dist = dist
                    best_target = (tx, ty)

            # 5. 执行逻辑
            if best_target:
                success = self.send_goal(best_target[0], best_target[1])
                if not success:
                    rospy.logwarn("无法到达目标，加入黑名单")
                    self.blacklist.append(best_target)
                    # 原地小幅度旋转一下，尝试更新地图视角
                    # (可选) 发布 cmd_vel 让机器人转 30度
            else:
                rospy.loginfo("没有发现新的探索点，或者所有点都探索完毕。")
                break
            
            # 6. 超时强制回家 (例如 4分30秒)
            if (rospy.Time.now() - start_time).to_sec() > 270:
                rospy.logwarn("时间快到了，强制回家！")
                break

            rate.sleep()

        # 7. 任务结束，返回原点
        rospy.loginfo("探索结束，正在返回原点 (0, 0)...")
        self.send_goal(0.0, 0.0)
        rospy.loginfo("任务完成！")

if __name__ == '__main__':
    try:
        explorer = FrontierExplorerLite()
        explorer.run()
    except rospy.ROSInterruptException:
        pass