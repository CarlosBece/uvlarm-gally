#!/usr/bin/python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import numpy as np
import pyrealsense2 as rs
import math
import cv2 as cv

class ObjectDetectionNode(Node):
    def __init__(self):
        super().__init__('object_detection_node')
        
        # RealSense setup
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        self.colorizer = rs.colorizer()

        # FPS set to 30
        self.config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        self.config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

        self.pipeline.start(self.config)

        self.align_to = rs.stream.depth
        self.align = rs.align(self.align_to)

        self.color_info = (0, 0, 255)
        self.rayon = 10

        # List of template files to compare
        self.template_files = ['template.png', 'car.png']

        # Dictionary to store threshold values for each template
        self.thresholds = {'template.png': 0.3, 'car.png': 0.5}

        # Flag to check if any template is detected
        self.object_detected = False

        # Creating morphological kernel
        self.kernel = np.ones((3, 3), np.uint8)

        # Create a dictionary to store templates
        self.templates = {}
        for template_file in self.template_files:
            self.templates[template_file] = cv.imread(template_file, 0)

        # Image publisher
        self.image_pub = self.create_publisher(Image, 'object_detection_image', 10)

        # Initialize CV Bridge
        self.bridge = CvBridge()

    def run(self):
        try:
            while rclpy.ok():
                # RealSense frames
                frames = self.pipeline.wait_for_frames()
                aligned_frames = self.align.process(frames)
                depth_frame = aligned_frames.get_depth_frame()
                aligned_color_frame = aligned_frames.get_color_frame()

                if not depth_frame or not aligned_color_frame:
                    continue

                # Colorized depth map
                colorized_depth = self.colorizer.colorize(depth_frame)
                depth_colormap = np.asanyarray(colorized_depth.get_data())

                # Set background to black
                depth_colormap[depth_colormap == 0] = 0

                color_intrin = aligned_color_frame.profile.as_video_stream_profile().intrinsics
                color_image = np.asanyarray(aligned_color_frame.get_data())

                depth_colormap_dim = depth_colormap.shape
                color_colormap_dim = color_image.shape

                # Use pixel value of depth-aligned color image to get 3D axes
                x, y = int(color_colormap_dim[1] / 2), int(color_colormap_dim[0] / 2)
                depth = depth_frame.get_distance(x, y)
                dx, dy, dz = rs.rs2_deproject_pixel_to_point(color_intrin, [x, y], depth)
                distance = math.sqrt(((dx) ** 2) + ((dy) ** 2) + ((dz) ** 2))

                # Check if the object is within the specified distance
                if distance < 1.0:  # Adjust as needed
                    # Convert color image to HSV
                    hsv_image = cv.cvtColor(color_image, cv.COLOR_BGR2HSV)

                    # Segmentation in HSV color space
                    mask = cv.inRange(hsv_image, np.array([45, 50, 50]), np.array([75, 255, 255]))
                    mask = cv.erode(mask, self.kernel, iterations=1)
                    mask = cv.dilate(mask, self.kernel, iterations=1)
                    image_segmented = cv.bitwise_and(color_image, color_image, mask=mask)

                    # Loop over templates for comparison
                    for template_file, template in self.templates.items():
                        res = cv.matchTemplate(cv.cvtColor(image_segmented, cv.COLOR_BGR2GRAY), template,
                                               cv.TM_CCOEFF_NORMED)
                        loc = np.where(res >= self.thresholds[template_file])

                        # Update the object_detected flag
                        if len(loc[0]) > 0:
                            self.object_detected = True

                        # Draw rectangles around detected areas
                        for pt in zip(*loc[::-1]):
                            cv.rectangle(color_image, pt, (pt[0] + template.shape[1], pt[1] + template.shape[0]),
                                         (0, 0, 255), 2)

                    # Show images
                    images = np.hstack((color_image, depth_colormap, image_segmented))

                    cv.circle(images, (int(x), int(y)), int(self.rayon), self.color_info, 2)
                    cv.circle(images, (int(x + color_colormap_dim[1]), int(y)), int(self.rayon), self.color_info, 2)

                    cv.putText(images, "D=" + str(round(distance, 2)), (int(x) + 10, int(y) - 10),
                                cv.FONT_HERSHEY_DUPLEX, 1, self.color_info, 1, cv.LINE_AA)
                    cv.putText(images, "D=" + str(round(distance, 2)), (int(x + color_colormap_dim[1]) + 10, int(y) - 10),
                                cv.FONT_HERSHEY_DUPLEX, 1, self.color_info, 1, cv.LINE_AA)

                    # Show images
                    cv.imshow('RealSense', images)
                    cv.waitKey(7)

                    # Publish the image
                    img_msg = self.bridge.cv2_to_imgmsg(images, encoding="bgr8")
                    self.image_pub.publish(img_msg)

                    # Print object detection status in real-time
                    if self.object_detected:
                        self.get_logger().info("Object detected!")
                    else:
                        self.get_logger().info("Object not detected.")

        except Exception as e:
            self.get_logger().error(str(e))

        finally:
            self.pipeline.stop()
            cv.destroyAllWindows()

def main(args=None):
    rclpy.init(args=args)
    object_detection_node = ObjectDetectionNode()
    object_detection_node.run()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
