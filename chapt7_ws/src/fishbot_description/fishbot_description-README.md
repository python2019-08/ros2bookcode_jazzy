# ch01.如何做fishbot_description验证验收
<!-- written by claudeCode AI -->
fishbot 的机器人描述功能包，包含：

- `urdf/`：URDF / xacro 机器人模型（底盘、轮子、激光雷达、IMU、深度相机）
- `world/`、`models/`：Gazebo Harmonic 仿真世界与模型资源
- `config/`：ros2_control 控制器配置、RViz 配置
- `launch/`：RViz 显示、Gazebo 仿真启动文件
- `env/set_gz_paths.dsv`：环境钩子，把 `models/` 自动加入 `GZ_SIM_RESOURCE_PATH`

本文档给出从构建到验收的完整步骤与命令，可直接复制执行。

## 0. 环境要求

| 项目 | 版本 |
| --- | --- |
| 操作系统 | Ubuntu 24.04 |
| ROS 2 | Jazzy |
| Gazebo | Harmonic（`gz sim` 8.15） |

依赖安装：

```bash
sudo apt install \
  ros-$ROS_DISTRO-ros-gz \
  ros-$ROS_DISTRO-gz-ros2-control \
  ros-$ROS_DISTRO-ros2-controllers \
  ros-$ROS_DISTRO-xacro \
  ros-$ROS_DISTRO-robot-state-publisher \
  ros-$ROS_DISTRO-joint-state-publisher \
  ros-$ROS_DISTRO-rviz2 \
  ros-$ROS_DISTRO-tf2-tools
```

## 1. 构建

```bash
cd <chapt7_ws>  # 例如 ~/a2/zdev/nv/adas-01/ros/ros2bookcode_jazzy/chapt7_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select fishbot_description --symlink-install \
  --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
source install/setup.bash
```

> **为什么要加 `-DPython3_EXECUTABLE=/usr/bin/python3`？**
> 如果终端里激活了 conda（`base` 环境），CMake 会优先使用 `~/miniconda3/bin/python3`，
> 而该解释器没有安装 `catkin_pkg`，构建会报：
>
> ```text
> ModuleNotFoundError: No module named 'catkin_pkg'
> ```
>
> 也可以先 `conda deactivate` 再构建。只使用系统自带的 ROS 2 环境时，可不加该参数。

验收点：

```bash
ros2 pkg prefix fishbot_description
# 输出 .../install/fishbot_description

ls "$(ros2 pkg prefix fishbot_description)/share/fishbot_description"
# 应看到 config  env  launch  models  urdf  world
```

## 2. 静态验收（无需启动仿真）

### 2.1 xacro 展开与 URDF 结构检查

```bash
URDF="$(ros2 pkg prefix fishbot_description)/share/fishbot_description/urdf/fishbot/fishbot.urdf.xacro"
xacro "$URDF" > /tmp/fishbot.urdf
check_urdf /tmp/fishbot.urdf
```

通过标准：输出 `Successfully Parsed XML`，且链接树与下面一致：

```text
robot name is: fishbot
---------- Successfully Parsed XML ---------------
root Link: base_footprint has 1 child(ren)
    child(1):  base_link
        child(1):  back_caster_link
        child(2):  camera_link
            child(1):  camera_optical_link
        child(3):  front_caster_link
        child(4):  imu_link
        child(5):  laser_cylinder_link
            child(1):  laser_link
        child(6):  left_wheel_link
        child(7):  right_wheel_link
```

再确认关键插件/接口确实被展开：

```bash
grep -n -E 'gz_ros2_control|ros2_control name|command_interface' /tmp/fishbot.urdf
```

应看到 `FishBotGazeboSystem`、`libgz_ros2_control-system.so`、`GazeboSimROS2ControlPlugin`，
以及左右轮的 `velocity` 命令接口。

> 说明：`plugins/gazebo_control_plugin.xacro`（Gazebo 原生 `DiffDrive` 插件）虽然被 include，
> 但在 `fishbot.urdf.xacro` 中并没有调用 `<xacro:gazebo_control_plugin />`（已注释）。
> 因此当前运动控制完全由 ros2_control 的 `fishbot_diff_drive_controller` 负责。

### 2.2 env hook 与 Gazebo 资源路径

```bash
echo "$GZ_SIM_RESOURCE_PATH"
```

通过标准：输出中包含

```text
.../install/fishbot_description/share/fishbot_description/models
```

并可解析 `model://cafe_table/...`：

```bash
MODELS="$(ros2 pkg prefix fishbot_description)/share/fishbot_description/models"
ls -l "$MODELS/cafe_table/meshes/cafe_table.dae"
# 文件存在即可
```

### 2.3 无界面加载仿真世界

```bash
WORLD="$(ros2 pkg prefix fishbot_description)/share/fishbot_description/world/custom_room.world.sdf"
timeout 30 gz sim -s -r --iterations 200 "$WORLD"
echo "exit=$?"
```

通过标准：`exit=0`，且日志中**没有**

```text
[Err] ... uri [model://cafe_table/meshes/cafe_table.dae] could not be resolved
[Err] ... Failed to load a world
```

该步骤专门验证 env hook 是否生效。若报 URI 解析失败，见第 6 节排查。

## 3. RViz 显示验收

```bash
ros2 launch fishbot_description display_robot.launch.py \
  model:="$(ros2 pkg prefix fishbot_description)/share/fishbot_description/urdf/fishbot/fishbot.urdf.xacro"
```

> `display_robot.launch.py` 默认加载的是 `urdf/first_robot.urdf`，
> 要查看 fishbot 必须显式传 `model:=` 参数。

通过标准：

- RViz 中能看到 fishbot 完整模型（蓝色圆柱底盘、两个黑轮、前后万向轮、激光雷达、IMU、相机）
- 没有红色 URDF/TF 报错

另开终端检查：

```bash
source install/setup.bash

ros2 topic echo /joint_states --once
# name 中包含 left_wheel_joint、right_wheel_joint

ros2 topic echo /tf_static --once | head -40
# 能看到 base_footprint -> base_link、laser_link、camera_link 等静态变换

cd /tmp && ros2 run tf2_tools view_frames
# 生成 frames_*.pdf，TF 树完整
```

## 4. Gazebo 仿真验收

终端 A：

```bash
source install/setup.bash
ros2 launch fishbot_description gazebo_sim.launch.py
```

通过标准：日志中出现（顺序可能略有差异）：

```text
Successfully loaded controller fishbot_joint_state_broadcaster into state active
Successfully loaded controller fishbot_diff_drive_controller into state active
```

并且没有 `process has died`、`Failed to load a world` 等错误。

### 4.1 控制器与硬件接口

终端 B：

```bash
source install/setup.bash

ros2 control list_controllers
```

期望：

```text
fishbot_diff_drive_controller    diff_drive_controller/DiffDriveController    active
fishbot_joint_state_broadcaster  joint_state_broadcaster/JointStateBroadcaster active
```

```bash
ros2 control list_hardware_interfaces
```

期望左右轮的 `velocity` 命令接口为 `[claimed]`：

```text
left_wheel_joint/velocity  [available] [claimed]
right_wheel_joint/velocity [available] [claimed]
```

### 4.2 话题与频率

```bash
ros2 topic list
ros2 topic hz /clock        # 约 1000 Hz（仿真时钟桥接正常）
ros2 topic hz /odom         # 约 50 Hz（publish_rate）
ros2 topic hz /joint_states # 稳定发布
ros2 topic hz /imu          # 约 100 Hz（依赖传感器渲染）
```

实测参考：`/clock ≈ 1000 Hz`，`/odom ≈ 50 Hz`。

### 4.3 运动测试（Jazzy 必须用 TwistStamped）

终端 B 发布速度指令：

```bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/TwistStamped \
  "{header: {frame_id: base_link}, twist: {linear: {x: 0.2}}}"
```

终端 C 观察里程计：

```bash
ros2 topic echo /odom --once --field pose.pose.position
```

通过标准：

- `x` 随时间增大（约 0.2 m/s）
- Gazebo 中机器人向前移动
- `Ctrl+C` 停止发布后，日志出现 `Velocity command timed out. Braking.`，机器人停下

> **重要：** Jazzy 的 `diff_drive_controller` 订阅的是 `geometry_msgs/msg/TwistStamped`。
> 使用 `geometry_msgs/msg/Twist` 发布不会生效（类型不匹配，控制器收不到消息），
> 表现为 `/odom` 不动、机器人不动。

### 4.4 TF 检查

```bash
ros2 run tf2_tools view_frames          # 建议在 /tmp 下运行
ros2 run tf2_ros tf2_echo odom base_footprint
ros2 run tf2_ros tf2_echo base_footprint laser_link
```

通过标准：

- TF 树为 `odom -> base_footprint -> base_link -> {wheels, laser, imu, camera}`
- 变换时间戳为仿真时间（非 0），且随仿真推进
- `odom -> base_footprint` 由 `fishbot_diff_drive_controller` 发布（`enable_odom_tf: true`）

### 4.5 传感器检查

**IMU：**

```bash
ros2 topic echo /imu --once
ros2 topic hz /imu
```

期望有 `orientation`、`angular_velocity`、`linear_acceleration`，
`frame_id` 为 `fishbot/base_footprint/imu_sensor`。

**激光雷达：**

```bash
gz topic -e -t /scan1 -n 1     # Gazebo 原生话题，应有数据
ros2 topic hz /scan            # 当前配置下无数据（见 4.6 已知问题）
```

**深度相机：**

```bash
ros2 topic hz /camera_sensor/image
ros2 topic hz /camera_sensor/depth_image
ros2 topic echo /camera_sensor/camera_info --once
```

期望话题：`/camera_sensor/image`、`/camera_sensor/depth_image`、
`/camera_sensor/camera_info`、`/camera_sensor/points`。

> 相机/GPU 雷达依赖可用的 OpenGL/EGL。若启动日志出现
> `libEGL warning: egl: failed to create dri2 screen`，图像话题可能一直没有数据，
> 这是图形环境问题，不是 URDF/插件配置问题。

### 4.6 已知问题：`/scan` 无数据

`sensor/gazebo_sensor_plugin.xacro` 中雷达话题配置为：

```xml
<topic>/scan1</topic>
```

而 `gazebo_sim.launch.py` 的 bridge 配置桥接的是 `/scan`：

```python
'/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan',
```

两者不一致，因此 `/scan` 收不到数据，Gazebo 侧 `/scan1` 正常。
任选一种方式修复：

1. 把传感器话题改为 `/scan`（推荐，与 bridge 一致）：
   ```xml
   <topic>/scan</topic>
   ```
2. 或把 bridge 参数改为 `/scan1`。

修改后重新 `colcon build --symlink-install`（xacro 为符号链接时通常无需重编）并重新启动 launch。

### 4.7 `/gz/odom` 说明

launch 中桥接了 `/gz/odom`，但 Gazebo 原生 `DiffDrive` 插件当前未被启用
（`gazebo_control_plugin.xacro` 中的宏没有实例化），所以 `/gz/odom` 没有发布者。
里程计请使用 ros2_control 控制器发布的 `/odom`。
不要同时启用原生 DiffDrive 插件和 `fishbot_diff_drive_controller`，否则会出现两个里程计/TF 源。

## 5. 验收清单

| # | 检查项 | 命令 | 通过标准 |
| --- | --- | --- | --- |
| 1 | 构建成功 | `colcon build --packages-select fishbot_description` | `Finished <<< fishbot_description` |
| 2 | xacro 可展开 | `xacro .../fishbot.urdf.xacro > /tmp/fishbot.urdf` | 无报错，文件非空 |
| 3 | URDF 结构正确 | `check_urdf /tmp/fishbot.urdf` | `Successfully Parsed XML` |
| 4 | 资源路径生效 | `echo $GZ_SIM_RESOURCE_PATH` | 含 `.../share/fishbot_description/models` |
| 5 | 世界可加载 | `gz sim -s -r --iterations 200 $WORLD` | exit 0，无 URI 错误 |
| 6 | RViz 模型正常 | `display_robot.launch.py model:=...` | 模型与 TF 正常显示 |
| 7 | 控制器加载 | `ros2 control list_controllers` | 两个控制器均 `active` |
| 8 | 时钟正常 | `ros2 topic hz /clock` | 约 1000 Hz |
| 9 | 里程计正常 | `ros2 topic hz /odom` | 约 50 Hz |
| 10 | 速度控制生效 | 发布 `TwistStamped` 到 `/cmd_vel` | `/odom` 位置变化、机器人移动 |
| 11 | TF 正常 | `tf2_echo odom base_footprint` | 变换随时间更新 |
| 12 | IMU 正常 | `ros2 topic echo /imu --once` | 有完整 IMU 数据 |
| 13 | 雷达正常 | `gz topic -e -t /scan1 -n 1` | 有 `ranges` 数据（`/scan` 见 4.6） |
| 14 | 相机正常 | `ros2 topic hz /camera_sensor/image` | 有稳定图像帧率（需图形环境正常） |

## 6. 常见问题排查

### 6.1 构建时报 `No module named 'catkin_pkg'`

conda 的 Python 被 CMake 选中。解决：

```bash
conda deactivate
# 或
colcon build --packages-select fishbot_description \
  --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
```

### 6.2 Gazebo 报 `model://cafe_table/... could not be resolved`

依次检查：

```bash
# 1. 重新构建并 source
colcon build --packages-select fishbot_description --symlink-install
source install/setup.bash

# 2. 确认 hook 已注册
cat "$(ros2 pkg prefix fishbot_description)/share/fishbot_description/environment/set_gz_paths.dsv" 2>/dev/null
# 或查看 install 后的 hook 文件
echo "$GZ_SIM_RESOURCE_PATH"

# 3. 确认模型文件确实被安装
ls "$(ros2 pkg prefix fishbot_description)/share/fishbot_description/models/cafe_table/meshes/cafe_table.dae"
```

`CMakeLists.txt` 中以下两步缺一不可：

```cmake
install(DIRECTORY env models DESTINATION share/${PROJECT_NAME})
ament_environment_hooks("env/set_gz_paths.dsv")
```

### 6.3 发布 `/cmd_vel` 机器人不动

- Jazzy 必须用 `geometry_msgs/msg/TwistStamped`，不能用 `Twist`
- 检查订阅者类型：`ros2 topic info /cmd_vel -v`
- 检查控制器是否 active：`ros2 control list_controllers`

### 6.4 `/scan` 无数据

见 4.6，统一传感器话题与 bridge 话题名称。

### 6.5 相机图像无数据

先看 launch 日志是否有 `libEGL` / OGRE 渲染错误；确认在带图形界面的桌面环境运行，
并检查 `gz topic -l | grep camera`。

### 6.6 控制器未加载

```bash
ros2 pkg prefix gz_ros2_control
ls /opt/ros/jazzy/lib/libgz_ros2_control-system.so
```

确认 URDF 中的插件名与配置文件路径正确：

```xml
<plugin filename="libgz_ros2_control-system.so"
        name="gz_ros2_control::GazeboSimROS2ControlPlugin">
    <parameters>$(find fishbot_description)/config/fishbot_ros2_controller.yaml</parameters>
```

### 6.7 `/odom`、TF 时间戳为 0

确认 `/clock` 桥接存在且 `use_sim_time: true`：

```bash
ros2 topic hz /clock
ros2 param get /controller_manager use_sim_time   # true
```

## 7. 目录结构

```text
fishbot_description/
├── CMakeLists.txt
├── package.xml
├── launch/
│   ├── display_robot.launch.py   # RViz 显示
│   └── gazebo_sim.launch.py      # Gazebo + ros2_control + 传感器桥接
├── urdf/
│   ├── first_robot.urdf(.xacro)  # 入门示例
│   └── fishbot/                  # fishbot 模型
│       ├── fishbot.urdf.xacro
│       ├── fishbot.ros2_control.xacro
│       ├── base.urdf.xacro
│       ├── actuator/             # 主动轮、万向轮
│       ├── sensor/               # 激光、IMU、相机
│       └── plugins/              # Gazebo 插件配置
├── config/
│   ├── fishbot_ros2_controller.yaml
│   └── rviz/display_model.rviz
├── world/custom_room.world.sdf
├── models/                       # cafe_table、room 等模型资源
└── env/set_gz_paths.dsv          # GZ_SIM_RESOURCE_PATH 环境钩子
```

## 8.总结

我在本机实际跑通了这些命令，并据此记录了三个关键注意点：

- Jazzy 的 /cmd_vel 必须用 geometry_msgs/msg/TwistStamped，用 Twist 控制器收不到（实测修正后 /odom 正常增长，/odom 频率 49.997 Hz）.      注:'ros2 run teleop_twist_keyboard teleop_twist_keyboard' 作用是读取键盘按键，发布 `/cmd_vel`（`geometry_msgs/msg/Twist`）速度话题，用来控制差速小车。
- 激光雷达话题不匹配：传感器发布 /scan1，launch 里 bridge 桥接的是 /scan，导致 /scan 无数据；README 给了两种修复方式
- 相机在无正常 EGL/OpenGL 的环境下无图像（日志出现 libEGL ... failed to create dri2 screen），属图形环境问题


