#!/usr/bin/python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Point32, Twist
import sensor_msgs_py.point_cloud2 as pc2
from std_msgs.msg import Header
import time
import math

rosNode = None

def scan_callback(scanMsg):
    global rosNode
    angle = scanMsg.angle_min + math.pi/2
    obstacles = []
    cmd_debug_points_left = []
    cmd_debug_points_right = []

    for aDistance in scanMsg.ranges:
        if 0.1 < aDistance < 3.0:
            aPoint = [
                aDistance * math.cos(angle),
                aDistance * math.sin(angle),
                0.0
            ]
            obstacles.append(aPoint)
            if (0.01 < aPoint[0] < 0.2 and 0.3 < aPoint[1] < 0.7) or (0.01 < aPoint[0] < 0.1 and 0.1 < aPoint[1] < 0.3):
                obstacles_right = True
                cmd_debug_points_right.append(aPoint)
            if (-0.2 < aPoint[0] < -0.01 and 0.3 < aPoint[1] < 0.7) or (-0.1 < aPoint[0] < -0.01 and 0.1 < aPoint[1] < 0.3):
                obstacles_left = True
                cmd_debug_points_left.append(aPoint)
        angle += scanMsg.angle_increment

    velo = Twist()

    # Linear velocity adjustment
    velo.linear.x = max(0.0, 0.3 - 0.1 * (3.0 - min(scanMsg.ranges)))

    if (len(cmd_debug_points_right) - len(cmd_debug_points_left)) > 15:
        print("go Left")
        velo.angular.z = 0.01 * (len(cmd_debug_points_right) + len(cmd_debug_points_left)) + 0.005 * (len(cmd_debug_points_right) - len(cmd_debug_points_left))
    
    elif (len(cmd_debug_points_left) - len(cmd_debug_points_right)) > 15:
        print("go right")
        velo.angular.z = 0.005 * (len(cmd_debug_points_right) + len(cmd_debug_points_left)) + 0.01 * (len(cmd_debug_points_right) - len(cmd_debug_points_left))

    else:
        target_angular_velocity = 0.01 * (len(cmd_debug_points_right) - len(cmd_debug_points_left))
        velo.angular.z = 0.9 * velo.angular.z + 0.1 * target_angular_velocity

    min_angular_velocity = 0.1  # Adjust as needed
    velo.angular.z = max(min_angular_velocity, velo.angular.z)

    print(velo.linear.x)
    print(velo.angular.z)

    velocity_publisher.publish(velo)
    cloudPoints = pc2.create_cloud_xyz32(Header(frame_id='laser_link'), obstacles)
    cloud_publisher.publish(cloudPoints)

if __name__ == '__main__':
    print("move move move")
    rclpy.init()
    rosNode = Node('PC_Publisher')
    velocity_publisher = rosNode.create_publisher(Twist, '/multi/cmd_nav', 10)
    cloud_publisher = rosNode.create_publisher(pc2.PointCloud2, 'laser_link', 10)
    rosNode.create_subscription(LaserScan, 'scan', scan_callback, 10)

    while True:
        rclpy.spin_once(rosNode, timeout_sec=0.1)
    
    # Clean up
    rosNode.destroy_node()
    rclpy.shutdown()