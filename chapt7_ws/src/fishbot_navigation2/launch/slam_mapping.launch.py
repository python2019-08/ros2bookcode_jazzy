"""用调好的参数启动 slam_toolbox 在线异步建图。

用法：
    ros2 launch fishbot_navigation2 slam_mapping.launch.py use_sim_time:=True
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    default_params_file = os.path.join(
        get_package_share_directory('fishbot_navigation2'),
        'config', 'slam_toolbox_mapping.yaml')

    use_sim_time = LaunchConfiguration('use_sim_time')
    slam_params_file = LaunchConfiguration('slam_params_file')

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time', default_value='true',
            description='Use the Gazebo /clock topic'),
        DeclareLaunchArgument(
            'slam_params_file', default_value=default_params_file,
            description='Full path to the slam_toolbox parameter file'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(
                get_package_share_directory('slam_toolbox'),
                'launch', 'online_async_launch.py')),
            launch_arguments={
                'use_sim_time': use_sim_time,
                'slam_params_file': slam_params_file,
            }.items(),
        ),
    ])
