# ch01.gazebo sim 窗口里  telop插件的 上下左右箭头 无法移动机器人小车
```sh 
# terminal 01中 
  ros2 launch fishbot_description gazebo_sim.launch.py

# terminal 02中
  ros2 launch slam_toolbox  online_async_launch.py  use_sim_time:=True

#   gazebo sim 窗口里 试图用 telop插件的 上下左右箭头 移动机器人小车，
#   其中 topic 设置为 "/cmd_vel". 但是小车没有移动.
# 请给出原因和解决方法
```
   
## 原因

小车不动，是因为Gazebo GUI 里的 Teleop 插件和 ROS 2 控制器根本不在同一个通信系统里，虽然话题名都叫 /cmd_vel：

┌───────────┬───────────────────┬────────────────────────────────────┐
│           │ Gazebo GUI Teleop │          你的机器人控制器             │
├───────────┼───────────────────┼────────────────────────────────────┤
│ 中间件     │ Gazebo Transport  │ ROS 2 / DDS                        │
├───────────┼───────────────────┼────────────────────────────────────┤
│ 话题       │ gz 的 /cmd_vel    │ ROS 2 的 /cmd_vel                  │
├───────────┼───────────────────┼────────────────────────────────────┤
│ 消息类型   │ gz.msgs.Twist     │ geometry_msgs/msg/TwistStamped     │
├───────────┼───────────────────┼────────────────────────────────────┤
│ 谁在发/收  │ Teleop 发布        │ fishbot_diff_drive_controller 订阅  │
└───────────┴───────────────────┴────────────────────────────────────┘

## 具体依据：

1. libTeleop.so 里只有 gz::msgs::Twist 和 /cmd_vel，说明 GUI 插件发的是 Gazebo Tra
2. fishbot.urdf.xacro:25 已经把 Gazebo 原生 gz::sim::systems::DiffDrive 注释掉了，所以 Gazebo 侧没有任何东西监听 gz 的 /cmd_vel。
3. 现在由 ros2_control 控制，fishbot.ros2_control.xacro:46 把控制器话题 remap 成了
4. Jazzy 的 diff_drive_controller 4.42.1 只订阅 ~/cmd_vel，类型是 geometry_msgs/msg/TwistStamped（库里没有 ~/cmd_vel_unstamped，也没有 use_stamped_vel 参数）。

所以：gz 的 /cmd_vel 和 ROS 的 /cmd_vel 只是同名，两者完全不连通；而且类型也不一样（Twist vs TwistStamped）。slam_toolbox 与此无关，它只消费 /scan 和 /tf。

---

## 解决方法

### 方法 1：给 Gazebo GUI Teleop 加一条桥接（推荐，继续用上下左右箭头）

ros_gz_bridge 支持 gz.msgs.Twist ↔ geometry_msgs/msg/TwistStamped 转换。在 gazebo_sim.launch.py 的 gz_bridge_node 参数里加一行（gazebo_sim.launch.py:105-126）：
'/cmd_vel@geometry_msgs/msg/TwistStamped[gz.msgs.Twist',

本机 ros_gz 1.0.24 实测：[ 表示 GZ → ROS，和现有 /clock、/scan 那些行的方向写法一致。

不想改文件的话，也可以临时在另一个终端直接起一个桥接节点：

ros2 run ros_gz_bridge parameter_bridge \
  '/cmd_vel@geometry_msgs/msg/TwistStamped[gz.msgs.Twist'

GUI 里 Teleop 的 topic 保持 /cmd_vel 即可。

验证：
```sh
ros2 topic info -v /cmd_vel
# 应能看到：
#   Publisher:  ros_gz_bridge   geometry_msgs/msg/TwistStamped
#   Subscriber: fishbot_diff_drive_controller
```

或者不按箭头，直接模拟一次 Teleop 按键：
```sh
gz topic -t /cmd_vel -m gz.msgs.Twist -p 'linear: {x: 0.5}'
```


### 方法 2：改用 ROS 键盘遥控（最快验证控制链）
```sh
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -p stamped:=true
```                                        
必须加 stamped:=true。不加的话它默认发 geometry_msgs/msg/Twist，Jazzy 的控制器同样收不到。这个节点发的是 ROS /cmd_vel，正

### 方法 3：改回 Gazebo 原生 DiffDrive（不推荐）                                                                            
取消 fishbot.urdf.xacro:25 的注释，并去掉 ros2_control（两套系统同时写同一对轮子会冲突），然后 Teleop topic 设为 gazebo_om/TF 链路，SLAM 还得重新配，不建议。
                                                                                           
- 点注意: 如果修改的是 src/ 下的 launch 文件，需要重新 colcon build --packages-select fish/ 里还是旧副本。
- fishbot_ros2_controller.yaml:49 的 cmd_vel_timeout: 0.5 意味着：GUI Teleop 每点一次箭头只发一条 Twist，小车会走约 0.5 秒后自动停。如果希望按一下走得更久，可以适当调大这个值（但它是安全超时，不建议调


========================================

# ch02.建图重影 / 扇形拖影（地图不理想）的原因与修复

```sh
# terminal 01中
cd chapt7_ws
source install/setup.bash
ros2 launch fishbot_description gazebo_sim.launch.py

# terminal 02中
cd chapt7_ws
source install/setup.bash
ros2 launch slam_toolbox  online_async_launch.py  use_sim_time:=True

# gazebo sim 窗口里，其中 topic 设置为 "/cmd_vel" ，用 telop插件的 上下左右箭头 移动机器人小车建图，
# 

# 然后用下面的命令保存地图
ROS_WS=/home/abner/a2/zdev/nv/adas-01/ros/ros2bookcode_jazzy/chapt7_ws/
ros2 run nav2_map_server map_saver_cli -f  ${ROS_WS}/src/fishbot_navigation2/maps/room02
# 但是地图不理想
```

## 现象

`map01.pgm` 里左边的房间比较干净，但右侧大厅出现明显的双层墙和扇形拖影，
墙线随着路径分叉。这不是雷达噪声，而是**偏航角里程计误差累积**导致
slam_toolbox 的扫描匹配(scan matching)逐步跟丢。

## 根因：圆柱轮的 ODE 接触点在轮子两端棱边上

原来的轮子碰撞体是圆柱：

```xml
<collision>
  <origin xyz="0 0 0" rpy="1.57079 0 0" />
  <geometry><cylinder length="0.04" radius="0.032" /></geometry>
</collision>
```

ODE 处理圆柱-平面接触时，会把接触点放在圆柱两端的棱边上，
也就是 y = ±(0.10 ± 0.02) m 的位置：

| 接触位置 | 等效轮距 | 偏航角比例 |
| --- | --- | --- |
| 内棱 | 0.16 m | 1.25 |
| 中心 | 0.20 m | 1.00 |
| 外棱 | 0.24 m | 0.833 |

实测（Gazebo 真值 vs 轮速积分）确实在 0.833 / 1.000 / 1.25 之间跳变。
`diff_drive_controller` 固定用 `wheel_separation: 0.20` 计算偏航，所以每次
转向都会产生 ±20%～25% 的角度误差；长时间 teleop 后，地图必然重影。

## 已做的修改

1. **`wheel.urdf.xacro`**：把轮子的 `<collision>` 从圆柱改成半径 0.032 的球体。
   球体与地面的接触点始终在轮心正下方（y=±0.10 m），等效轮距恒等于
   `wheel_separation: 0.20`。视觉仍是圆柱，外观不变。
2. **`fishbot_ros2_controller.yaml`**：`open_loop: true` → `false`，
   用轮子位置反馈计算 odom，而不是对 cmd_vel 开环积分；同时显式写
   `position_feedback: true`。轮子被挡住或打滑时 odom 不会继续“凭空前进”。
3. **`fishbot_navigation2/config/slam_toolbox_mapping.yaml`**：针对慢速小车
   调低 slam_toolbox 的默认阈值（0.5 m / 0.5 rad 太粗），并加长 TF 超时：
   - `minimum_travel_distance: 0.05`
   - `minimum_travel_heading: 0.05`
   - `minimum_time_interval: 0.1`
   - `transform_timeout: 0.5`
   - `map_update_interval: 1.0`
   - `max_laser_range: 8.0`（与雷达一致）
4. **`fishbot_navigation2/maps/.gitkeep`**：源码里原来只有 `maps-humble/`，
   但 `CMakeLists.txt` 安装的是 `maps/`，导致 `colcon build` 失败；补上目录。
5. 新增 `fishbot_navigation2/launch/slam_mapping.launch.py`，用上面的参数启动。
6. **`gazebo_sim.launch.py`**：给 `robot_state_publisher` 加上
   `use_sim_time: true`，让 TF 时间戳和 Gazebo 的 `/clock` 一致，避免
   slam_toolbox/RViz 查询 TF 时混用系统时间和仿真时间。

## 重新建图步骤（必须从零开始，旧地图作废）

```sh
cd /home/abner/a2/zdev/nv/adas-01/ros/ros2bookcode_jazzy/chapt7_ws
source /opt/ros/jazzy/setup.bash
rm -fr build/ log/ install/
# colcon build --symlink-install --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
colcon build --symlink-install --packages-select fishbot_description fishbot_navigation2
source install/setup.bash
```

先彻底关掉旧的 Gazebo、RViz 和 slam_toolbox（各终端 Ctrl-C），然后：

```sh
# 终端 1
cd /home/abner/a2/zdev/nv/adas-01/ros/ros2bookcode_jazzy/chapt7_ws
source install/setup.bash
ros2 launch fishbot_description gazebo_sim.launch.py

# 终端 2（注意用新 launch，参数已经调好）
cd /home/abner/a2/zdev/nv/adas-01/ros/ros2bookcode_jazzy/chapt7_ws
source install/setup.bash
ros2 launch fishbot_navigation2 slam_mapping.launch.py use_sim_time:=True
```

如果不想用新 launch，也可以显式指定参数文件：

```sh
ros2 launch slam_toolbox online_async_launch.py use_sim_time:=True \
  slam_params_file:=$(ros2 pkg prefix fishbot_navigation2)/share/fishbot_navigation2/config/slam_toolbox_mapping.yaml
```

Gazebo GUI 里 Teleop 的 topic 仍设为 `/cmd_vel`，然后用箭头建图。建议：

- **慢一点、连续地开**，不要频繁急停急转；每次转弯后让车直行一小段再转。
- 走一个**闭合回路**，最后回到起点附近；slam_toolbox 会做回环优化，把累计误差拉回来。
- 右侧大厅尽量沿墙走一圈，让雷达（最大 8 m）从多个角度看到同一面墙。
- 建图过程中可以在 RViz 里观察 `map` 和 `laser scan` 是否重合；如果墙开始分叉，
  说明已经跟丢，最好回到上一个干净的位置重新走。

保存地图（建议用新文件名，避免和旧地图混淆）：

```sh
ROS2_WS=/home/abner/a2/zdev/nv/adas-01/ros/ros2bookcode_jazzy/chapt7_ws

ros2 run nav2_map_server map_saver_cli -f \
  ${ROS2_WS}/src/fishbot_navigation2/maps/room02
```

保存后检查 `map02.pgm`：墙应该是单线，房间轮廓闭合，没有扇形拖影。

## 如果觉得车太慢

`fishbot.ros2_control.xacro` 里轮子的速度命令上限是 ±1 rad/s：

```xml
<command_interface name="velocity">
  <param name="min">-1</param>
  <param name="max">1</param>
</command_interface>
```

线速度只有 `1 × 0.032 ≈ 0.032 m/s`，走完 19 m × 11 m 的房间很花时间。
想快一点可以把 `min/max` 改成 `-10/10`（约 0.32 m/s）。建图时仍建议
用中等速度，不要开到最大。这个改动不影响本次重影修复。

## 验证里程计是否修好

重启后可以先做一个原地旋转测试：连续发布 `angular.z = 0.3 rad/s` 约 3 秒，
对比 `/odom` 的偏航角和 Gazebo 里 `fishbot` 的真实朝向（或在 RViz 里看
`base_footprint` 与 `map` 的关系）。修复后两者应在几个百分点以内一致；
如果仍然差 20% 左右，说明还在用旧的圆柱碰撞体（检查是否重新编译、
是否重启了 Gazebo）。

===================================
# ch03.地图还是不理想

```sh
# 终端 1
cd /home/abner/a2/zdev/nv/adas-01/ros/ros2bookcode_jazzy/chapt7_ws
source install/setup.bash
ros2 launch fishbot_description gazebo_sim.launch.py

# 终端 2（注意用新 launch，参数已经调好）
cd /home/abner/a2/zdev/nv/adas-01/ros/ros2bookcode_jazzy/chapt7_ws
source install/setup.bash
ros2 launch fishbot_navigation2 slam_mapping.launch.py use_sim_time:=True

# gazebo sim 窗口里，其中 topic 设置为 "/cmd_vel" ，用 telop插件的 上下左右箭头 移动机器人小车建图，
# 

# 然后用下面的命令保存地图
ROS_WS=/home/abner/a2/zdev/nv/adas-01/ros/ros2bookcode_jazzy/chapt7_ws/
ros2 run nav2_map_server map_saver_cli -f  ${ROS_WS}/src/fishbot_navigation2/maps/room02
# 但是地图不理想
```

<!-- claude code ： -->

## 0.1原因

根因是轮式里程计严重失真，slam_toolbox 拿到的先验位姿本身就是错的。 这与 slam 参数的关系不大。而里程计失真的根源是车速比设计值高了约 31 倍，并且在房间里频繁碰撞、打滑。

证据链如下（都是在同一场仿真里实测的）：

1. 实际速度是 1.0 m/s，设计值是 0.032 m/s。
   - 采样 /joint_states 得到轮速 31.25 rad/s：31.25 × 0.032 = 1.0 m/s；转向时两轮 ±1.5625 rad/s，对应车体角速度 0.5 rad/s。这两个值正好是 Gazebo GUI Teleop 插件的默认速度（1.0 m/s、0.5 rad/s）。
   - 本来应该限速的两处都没有生效：
     - URDF 里轮子命令接口的 ±1 rad/s：Gazebo 日志明确写着 Enforcing command limits is disabled. Command limits from URDF will be ignored.
     - diff_drive_controller 当前参数是 linear.x.max_velocity: nan、angular.z.max_velocity: nan、publish_limited_velocity: false，等于完全不限速。
2. 高速 + 点按遥控导致打滑，odom 与真实运动完全对不上。
   - 在 19 m × 11 m、布满家具的房间里，以 1 m/s 用方向键驾驶，必然频繁撞墙、卡在家具上；差速控制器仍按 1 m/s 命令驱动轮子，轮子在转、车没动，而 odom 只累计轮子转角，于是“车几乎没走，odom 却走了十几米”。
   - 实测同一时刻 /odom 与 Gazebo 真值 gz model -m fishbot -p 相差 8.7 m / 1.06 rad（另一时刻相差 15.2 m / 1.21 rad）；还直接看到 /odom 的 twist 是 1.0 m/s，而真值位置几乎不变。
   - GUI 方向键是“按一下发一条 Twist”，叠加 cmd_vel_timeout: 0.5，每次按键最多冲 0.5 m 再急停（1 m/s × 0.5 s），冲击式启停进一步加剧打滑。
3. slam_toolbox 无法纠正这么大的误差。
   - 它把 odom 当先验，扫描匹配只在先验附近小范围搜索（correlation_search_space_dimension: 0.5 m）。odom 错几米、几十度时，匹配必然失败，每帧扫描被放到错误位姿，于是出现你截图里的扇形拖影、双层墙、地图整体尺寸不对。
   - 另外这套参数是按“最大约 0.03 m/s”调的（yaml 注释里写明了），实际 1 m/s 时 10 Hz 雷达两帧之间车已移动 1 m，minimum_travel_distance: 0.05 等阈值完全失去意义。
4. 次要 / 流程因素：
   - 建图没有走闭合回环，没有机会靠回环闭合修正。
   - 之前出现过 Gazebo 重启而 slam_toolbox 不重启，会产生 TF_OLD_DATA 和时钟回跳（这次最终地图来自重启后的干净进程，但第 1～3 条已足以毁掉地图）。

## 0.2解决方法

### 第 1 步（关键）：把速度真正限制住。 
推荐在 src/fishbot_description/config/fishbot_ros2_controller.yaml 的 fishbot_diff_drive_controller 下加：

    publish_limited_velocity: true
    linear.x.has_velocity_limits: true
    linear.x.min_velocity: -0.05
    linear.x.max_velocity: 0.05
    angular.z.has_velocity_limits: true
    angular.z.min_velocity: -0.3
    angular.z.max_velocity: 0.3

也可再加加速度限制让启停更平滑（linear.x.has_acceleration_limits: true、  max_acceleration/max_deceleration 取 0.05～0.1，angular.z 同理）。改完要重新编译并重启仿真，因为 yaml 是从 install 目录读取的：
```sh
colcon build --packages-select fishbot_description
```

同时在 Gazebo GUI 的 Teleop 插件里把速度改成 0.05 m/s 和 0.3 rad/s（或直接用下一步的键盘遥控，不看插件设置）。

### 第 2 步：改用连续控制的键盘遥控，不要用 GUI 点按。
```sh
# 改用连续控制的键盘遥控，不要用 GUI 点按。
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args -p stamped:=true -p speed:=0.05 -p turn:=0.3
```
Jazzy 里控制器订阅的是 TwistStamped，所以 stamped:=true 必须加。连续按键可以平稳行驶，cmd_vel_timeout 也不会再造成走走停停。

### 第 3 步：建图前先校验里程计。 
先直行约 0.5 m、再原地转 90°，边开边对比：
```sh
ros2 topic echo /odom --field pose.pose --once
gz model -m fishbot -p
```
位移应在厘米级一致、yaw 在几度内一致。如果对不上，说明还在打滑/碰撞，先别建图。

### 第 4 步：按正确顺序和方式建图。
> - 先启动 Gazebo，用 ros2 control list_controllers 确认两个控制器都是 active，再启动 slam_mapping.launch.py。
> - 建图过程中不要重启 Gazebo；如果必须重启，先关 slam_toolbox，重启后重新启动 SLAM。
> - 低速沿墙走，尽量走成一个闭合回路并回到起点，全程盯着 RViz：墙应该是一条线。一旦出现双层墙或扇形拖影，立刻停下，退回上一个干净区域重来，或者重开 SLAM，不要继续硬建，最后确认干净再 map_saver_cli。

可选改进：
- 用 robot_localization 的 EKF 融合轮速和 IMU（IMU 已在发布），打滑时 odom 会比纯轮速稳得多，这是比调扫描匹配更根本的改善。
- base.urdf.xacro 里圆柱半径写成了 ${length}（0.12）而不是 ${radius}（0.10），建议顺手修掉；它不会造成这次地图问题，但碰撞体会比外观大。
- 如果以后确实需要更快速度，把轮子碰撞体换成薄圆柱（厚度约 0.005 m）并重新标定轮距，比球体有更好的侧向约束。


=========================================

# ch04. 地图滑移

## 结论先说

这次地图的问题不是里程计，也不是雷达/TF，而是 slam_toolbox 的 **扫描匹配** 在大厅里“合法地”滑移了：里程计和真值几乎一致，雷达在真值坐标系里也对得上墙，但 slam_toolbox 把一部分扫描放到了错误的位姿上，生成的地图自洽却整体/局部变形。右上角门口只是触发点，不是根因。

ch03 里“里程计严重失真”的结论不适用于这次运行——同一场仿真实测：

┌───────────────────────────────────────┬───────────────────────────────────────────────────────────────────────┐
│                对比项                 │                               实测结果                                │
├───────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ /odom vs gz model -m fishbot -p       │ 位置差 2.2 mm，yaw 差 ~0.00006 rad（跑了约 48 分钟）                  │
├───────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ /scan 在 world 系 vs 真值墙             │ 153 点落在 Wall_85（y=−2.714）、108 点落在 Wall_72、66 点落在 Wall_69 │
├───────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ map → odom                            │ 纯平移 (0.633, −2.185) m，yaw −0.010°                                 │
├───────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ SLAM 估计的机器人在 map 里 vs 真值        │ 偏 2.28 m                                                             │
├───────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ 实时 /scan 端点 vs 已保存地图占用栅格 │ 最近邻中位数 4.7 cm（p25 1.9 cm）                                     │
└───────────────────────────────────────┴───────────────────────────────────────────────────────────────────────┘

最后一行是关键：雷达和地图贴得非常好，但地图和真实世界差了 2.28 m。这说明 slam_toolbox 认为自己对，实际整体/局部偏了。

---

## 证据：保存下来的 room02 地图到底哪里坏了

room02.yaml/.pgm：361×244 @ 0.05 m/px，origin (-9.941, -7.190)，换算得到：

- 地图 x 范围：−9.941 … 8.109 m
- 地图 y 范围：−7.190 … 5.010 m

而 custom_room.world.sdf 里房间内壁是 x = −10.384 … +8.39，y = −6.494 … +4.606。也就是说：

1. 东墙（真值 x≈8.39–8.47）根本没被放到真实位置。 地图右边界 8.109 已经小于东墙内壁，东墙被画到了 6.6–7.7 m 一带，而且按 y 分段统计，它在不同高度分别落在 7.13 / 7.58–7.68 / 7.38–7.53 / 7.08–7.28 / 6.58–6.73，厚度 0.5–1.9 m（最厚约 38 个栅格）。这就是“扇形/双层墙”的典型形态。
2. 右上角（NE）被糊成一片：x∈(6.5, 8.5)、y∈(3.5, 4.7) 的 768 个栅格里 293 个是占用（38%），而真值那里只有一个约 2 m × 0.5 m 的书架（7.912, 4.685）。
3. 门口那面墙（Wall_80，真值 y≈−3.15、实墙从 x=−0.656 到 6.844，之后才是门洞到 8.47）被拆碎了：在 y∈(−3.35, −2.95) 带内，占用区间的 x 连续段是 (−2.5, 5.0)、(6.1, 6.6)、(6.7, 7.8)——中间 x 5.0–6.1 有一个 1.1 m 的假缺口，6.1–7.8 是一堆碎片，6.844 的门口门垛完全看不出来。这正是你说的“到右上角房间门口时地图变成不符合实际的样子”。
4. 起点附近是干净的：unit_box（−0.958, 2.778）、unit_cylinder（−0.961, 0.717）、Wall_71、Wall_72 东半段都在真值 ±0.1–0.2 m 内；越往右、往上越歪。地图是逐帧拼出来的非刚性结果：早期帧锚在起点附近，后期帧带着累积的匹配误差。

---

## 根因

大厅的几何对 扫描匹配 很不友好：

- 19 m × 11 m 的大厅 + 8 m 雷达，机器人在中间时经常只能看到两面长直平行墙；
- 沿大厅长轴（x 方向）平移时，扫描几乎不变——这就是 孔径问题（aperture problem），x 方向弱可观测；
- Karto 的匹配本来应该被 odom 先验约束住，但当前参数太松：
  - correlation_search_space_dimension: 0.5：在 odom 附近 ±0.25 m 内搜索，对“沿墙滑 0.3 m”这种错误几乎没有代价；
  - correlation_search_space_smear_deviation: 0.1：把响应峰抹平 10 cm，进一步削弱峰值的区分度；
  - link_match_minimum_response_fine: 0.1：几乎任何匹配都算“合格”，坏匹配被接受；
  - scan_buffer_size: 10：只链接最近 10 帧，minimum_travel_distance: 0.05 时大约只有几十厘米的局部约束，约束不到全局误差；
  - do_loop_closing: true + loop_search_maximum_distance: 5.0：日志里没有直接证据（slam_toolbox 日志太少），但存在误回环把两端往中间拉的可能。

触发点在右上角门口：机器人转向离开长直墙，视野里变成门垛、书架（7.912, 4.685）和家具，几何从“平行长墙”变成“杂乱小特征”。这时 8 m 外的墙对 yaw 误差极其敏感（8 m × 1° ≈ 14 cm），匹配一旦锁到错误局部结构，远端墙就被扫成一个 0.5–1.9 m 宽的扇面，并把误差沿位姿图固化下来。

所以现象是“先建大厅和左上角房间没问题，到右上角门口就崩”，本质是误差一直在累积，只是右上角的几何让它显现出来。

---

## 解决方法

参数文件是符号链接，改完不用重新 colcon build；但必须重启 slam_toolbox（参数只在启动时读），建议连 Gazebo 一起重启，从零建图。

### 方案 A（仅限仿真对照实验，不能用于真机建图）：直接用里程计建图

**先说清楚定位：这不是建图方案，只是一个诊断实验。** 真机上请直接看方案 B。

为什么真机不能用：仿真里 /odom 与 Gazebo 真值只差 2.2 mm，因为 Gazebo 的 diff_drive 插件基本按真值输出轮速、没有打滑。真机轮式里程计的误差来源完全不同：
- 轮径/轮距标定误差——差速底盘左右轮半径差 1%，直线走 10 m 就会累积出明显的 yaw 偏差；
- 转弯打滑、地毯/门槛、地面不平、万向轮侧滑；
- 编码器分辨率与时间戳抖动；
- 负载变化导致轮胎压缩和滑移。

典型未标定的差速底盘，位置漂移约为行进距离的 1%–5%，yaw 漂移更容易累积；走一个 20 m 的回路，回到起点时差几十厘米、几度很正常。而 2D 激光建图要求位姿误差在厘米级、角度误差约 0.3°（8 m 外的墙，0.3° 就是 4 cm），否则墙面立刻被涂成双层/扇形。

所以：
- 真机用 `use_scan_matching: false` 建图，只会得到“沿里程计轨迹弯曲的走廊、合不上的回环、双层墙”，比开匹配更糟，而且没有任何机制能事后修正；
- 里程计只能作为匹配的先验/初值，不能作为位姿来源——所有生产级 SLAM（slam_toolbox、Cartographer 等）都是这个结构；
- 真机上如果确实想“更信里程计”，正确做法是标定轮径/轮距、必要时把轮速与 IMU 做 EKF 融合，再按方案 B 收紧匹配搜索窗，而不是关掉匹配。

仿真里它仍然有价值：这是一个控制变量实验，用来证明轮子/TF/雷达没问题、问题全在匹配器。参数：
src/fishbot_navigation2/config/slam_toolbox_mapping.yaml
```yaml
    use_scan_matching: false      # 仅仿真对照实验：直接用 odom 位姿拼图
    do_loop_closing: false        # 没有匹配，回环也失去意义
```
其余参数保持不变。效果：地图由“已知正确的里程计”直接拼出，不会出现扇形、双层墙、墙被拉歪；map → odom 会一直≈单位变换。**这只说明仿真里的 odom/scan 是对的，不能作为建图策略写进真机流程。**
<!-- 注：经验证，确实建图 src/fishbot_navigation2/maps/room03_noScanMatch_noloopClosing.pgm 很干净. -->

### 方案 B（推荐，仿真和真机都适用）：把匹配收紧，让 odom 先验说话
```yaml
    use_scan_matching: true
    do_loop_closing: false              # 先关掉，排除误回环
    scan_buffer_size: 20                # 10 -> 20，局部约束更长
    correlation_search_space_dimension: 0.2     # 0.5 -> 0.2，搜索窗 ±0.1 m
    correlation_search_space_smear_deviation: 0.03   # 0.1 -> 0.03，让响应峰更尖
    link_match_minimum_response_fine: 0.35      # 0.1 -> 0.35，拒绝弱匹配
    link_scan_maximum_distance: 1.0             # 1.5 -> 1.0
```
<!-- 注：经验证，在 “use_scan_matching: true“ 且 “do_loop_closing: false“ 的配置下， 
建图的地图 
src/fishbot_navigation2/maps/room04B_t-scan-matching_f-loop-closing.pgm 
干净。 -->

等地图干净了，再打开回环。注意 `loop_search_maximum_distance` 不能收得比“回到旧区域时的预计漂移”还小——本次最终漂移就有 2.28 m，收到 3.0 m 几乎不留余量。正确做法是让搜索半径覆盖漂移（5~8 m），靠提高 `loop_match_minimum_response_*` 和 `loop_match_minimum_chain_size` 来拒绝误回环。完整原则见 ch07。

<!-- 注：经验证，在 “use_scan_matching: true“ 且 “do_loop_closing: true“ 的配置下，
   建图的地图 src/fishbot_navigation2/maps/room04B_final.pgm 干净。 -->

驾驶方式（两种方案都适用）

- 低速、连续，不要在门口原地转身；转弯前先直行一小段。
- 走一个闭合回路回到起点，让同一面墙被多个角度看到。
- 全程盯 RViz：/scan 应始终贴在已建墙上。一旦墙开始变厚/分叉，立即停，退回上一个干净位置或重开 SLAM，不要硬建到门口再存图。
- 东墙尽量走近一点再扫（距离越近，yaw 误差造成的扇面越窄）。

---

## 重新建图与验收
```sh
rm -fr build/ log/ install/
conda deactivate
# colcon build --symlink-install --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
colcon build --symlink-install --packages-select fishbot_description fishbot_navigation2
source install/setup.bash

# 全部关掉（Gazebo、RViz、slam），再按原流程重启
ros2 launch fishbot_description gazebo_sim.launch.py
ros2 launch fishbot_navigation2 slam_mapping.launch.py use_sim_time:=True

# 改用连续控制的键盘遥控，不要用 GUI 点按。
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args -p stamped:=true -p speed:=0.05 -p turn:=0.3
```



建图过程中随时检查（终端 3）：
```sh
ros2 run tf2_ros tf2_echo map odom
# 平移应始终 < 5 cm，yaw < 0.01 rad；一旦持续变大说明又在滑
ros2 topic echo /odom --field pose.pose --once
gz model -m fishbot -p        # 与上一条对比，应厘米级一致
```

保存为新文件名，保留 room02 做对比：
```sh
ROS2_WS=/home/abner/a2/zdev/nv/adas-01/ros/ros2bookcode_jazzy/chapt7_ws
# ros2 run nav2_map_server map_saver_cli -f ${ROS2_WS}/src/fishbot_navigation2/maps/room03
ros2 run nav2_map_server map_saver_cli -f ${ROS2_WS}/src/fishbot_navigation2/maps/room04B_t-scan-matching_f-loop-closing
```

保存后按这几条验收：
┌──────────────────────────────────┬─────────────────────────────────────────────┐
│              检查项              │                    期望                     │
├──────────────────────────────────┼─────────────────────────────────────────────┤
│ 地图右边界 origin_x + width×0.05   │ ≥ 8.39（最好到 8.47）                       │
├──────────────────────────────────┼─────────────────────────────────────────────┤
│ 地图左边界 origin_x                │ ≤ −10.38                                    │
├──────────────────────────────────┼─────────────────────────────────────────────┤
│ 东墙                              │ 单线，x≈8.42–8.47，厚度 ≤ 3 格              │
├──────────────────────────────────┼─────────────────────────────────────────────┤
│ Wall_80（y≈−3.15）                │ 从 x≈−0.58 连续到 6.84，门洞 6.84–8.47 干净 │
├──────────────────────────────────┼─────────────────────────────────────────────┤
│ 右上角                            │ 只有约 2×0.5 m 的书架轮廓，无大片填充       │
├──────────────────────────────────┼─────────────────────────────────────────────┤
│ map → odom                       │ 全程接近单位变换                            │
└──────────────────────────────────┴─────────────────────────────────────────────┘

另外，map_saver_cli 那两条 Free/Occupied threshold unspecified 只是用了默认 0.25/0.65，不是这次变形的原因，可以不管。

---

需要的话我可以直接按方案 B 把 slam_toolbox_mapping.yaml 改好，并把这一节作为 ch04 追加到 nav2_buildmap.md；方案 A 只在仿真里当一次对照实验跑。

============================================

# ch05.如何看待 “回环完成，地图被优化修正“
  
>  doubao-ai 认为，
>   方案 A：建图策略调整（最快见效，不用改代码）
>   1. 不要一次性一路冲到右上角房间
>      探索顺序：起点 → 大厅 → 左上房间 → 回到大厅（回环！），等回环完成，地图被优化修正之后，再去右上角。
>      回环闭合会把前面累积的漂移一次性修正，再去探索远处房间，地图不容易崩。
>   2. 到门口弱特征区域：放慢速度（0.03m/s），缓慢移动，不要原地快速旋转；原地急转最容易造成匹配丢失。
>   3. 尽量贴着墙角走，让激光持续观测墙角这类强特征。
 
<!-- claude code AI -->
这份建议作为驾驶习惯是合理的，但它对“为什么会坏”的因果判断和这次实测数据对不上。逐条看：

逐条评价

┌──────────────────────┬─────────────────────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│         建议         │          评价           │                                                                    理由                                                                    │
├──────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ① 先回大厅过回环，再 │ 可以照做，但它救不了这  │ 回环修正的是“位姿图里已累积的误差”。本次里程计与真值只差 2.2 mm，回环没有里程计误差可修；它只能去纠正扫描匹配自己滑出来的误差，而匹配并不  │
│ 去右上角             │ 次的地图                │ 知道自己错了。更关键的是：回环修正的是过去，之后照样会继续漂。先回环再去右上角，并不给右上角的匹配上保险                                   │
├──────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ② 门口放慢到 0.03    │ 降速作用很小，别原地急  │ 0.05 m/s + 10 Hz 雷达，每帧只走 5 mm，相邻帧重叠 99% 以上，速度根本不是丢匹配的原因。真正的问题是沿长直墙方向的弱可观测性（孔径问题），车  │
│ m/s、别原地急转      │ 转有用                  │ 停着匹配照样会滑。门口原地旋转确实容易在杂乱特征里锁错结构，这一点保留                                                                     │
├──────────────────────┼─────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ③ 贴墙角走，让雷达看 │ 同意，这是最有用的一条  │ 近距离 + 墙角/门垛给匹配提供强几何约束，能显著压低沿墙滑移。和我的建议一致                                                                 │
│ 到强特征             │                         │                                                                                                                                            │
└──────────────────────┴─────────────────────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

和实测数据的两处冲突

1. “回环闭合会把前面累积的漂移一次性修正”——前提是漂移来自里程计。这次不是：/odom 和 gz model -m fishbot -p 跑了 48 分钟只差 2.2 mm / 0.00006 rad。误差是扫描匹配自己引入的，回环要“修正”它，前提是回环能正确识别，而在已经歪掉的地图上，回环也可能闭错。而且回环只改历史位姿，之后的扫描仍会继续滑，所以“先回环再去右上角”不能保证右上角干净。
2. “等回环完成”没有可靠信号——slam_toolbox 的异步回环日志很少。可以这样判断：在同一位置前后看 ros2 run tf2_ros tf2_echo map odom 是否发生跳变，或 RViz 里地图是否整体被“拉”了一下。没跳变就是没闭合（或候选不满足 loop_match_minimum_chain_size: 10 等条件）。

还有一个直接反证：建图结束时 map → odom 是 (0.633, −2.185) m、yaw ≈ 0，即最终位姿本身就偏了 2.28 m。如果之前那次回环真的把图“修正好了”，后续又在右上角滑出去，这恰恰说明回环后的保险不存在。

我的建议：把两套方案组合起来，但你那份更稳

- 仿真里可以先用方案 A 做一次对照实验（**仅限仿真，真机不可用**）：`use_scan_matching: false`、`do_loop_closing: false` 时，地图直接由里程计拼出来，探索顺序、速度、走不走回环都不再影响结果。同一路线跑一遍，如果 room03 干净，就证明轮子/TF/雷达没问题、问题全在匹配器。但这只是诊断结论，真正的建图方案仍是方案 B。
- 如果一定要保留 SLAM，那就用它那份驾驶策略 + 我上一轮给的收紧参数：
  - scan_buffer_size: 20、correlation_search_space_dimension: 0.2、smear: 0.03、link_match_minimum_response_fine: 0.35；
  - 先关 do_loop_closing，确认局部地图干净后再开；
  - 回大厅过回环后再去右上角、贴墙走、别在门口原地转，这些都照做；
  - 全程用 tf2_echo map odom 盯着，平移一旦持续超过 5 cm 就停下回退。
- 速度保持 teleop speed:=0.05 turn:=0.3 即可，降到 0.03 只会让 19×11 m 的房间更耗时，换不来匹配精度。

一句话：它的“怎么开车”没问题，问题在于它默认“SLAM 的匹配和回环是可信的”；这次仿真实测显示里程计可信、匹配器不可信，所以仿真里可以用“让匹配器退场”做对照实验来定位问题；但真机上里程计并不可信，最终解法是把匹配收紧、用 odom 当先验（方案 B），而不是关掉匹配。


===================================

# ch06.怎么调参让回环更容易触发
 
先看回环到底要过哪几关

我挑了 jazzy 版 slam_toolbox 的 karto 源码看了一下，自动回环的判定顺序是（Mapper.cpp 里的 TryCloseLoop / FindPossibleLoopClosure）：

1. 找候选链：把历史扫描中，位姿距离当前扫描 < loop_search_maximum_distance 的扫描 段，且长度 ≥loop_match_minimum_chain_size，同时不能是和当前扫描已经有图链路的扫描。
2. 粗匹配：用 loop_search_space_* 这组参数建相关网格做匹配，要求
   - response > loop_match_minimum_response_coarse
   - 且 x、y 方向协方差都 < loop_match_maximum_variance_coarse（注意这是方差 m²，
3. 精匹配：要求 response >= loop_match_minimum_response_fine。

三关都过才会加约束并调用 CorrectPoses()。所以“更容易触发”就是放宽候选、降低门槛、扩大搜索窗。

另外注意：use_scan_matching 控制的 scan matching 每帧都在跑，不需要“调得更容易触发”；真正有门槛的是回环。

调参优先级

┌────────────────────────────────────┬────────────────┬───────────┬────────────────────────────────────────────────────────────────────────┐
│                参数                │      默认      │   建议    │                                           │
├────────────────────────────────────┼────────────────┼───────────┼────────────────────────────────────────────────────────────────────────┤
│ loop_search_maximum_distance       │ 3.0 m          │ 5.0~8.0   │ 候选搜索半径，                            │
├────────────────────────────────────┼────────────────┼───────────┼────────────────────────────────────────────────────────────────────────┤
│ loop_match_minimum_chain_size      │ 10 帧          │ 5~7       │ 连续候选帧数下 成链                       │
├────────────────────────────────────┼────────────────┼───────────┼────────────────────────────────────────────────────────────────────────┤
│ loop_match_minimum_response_coarse │ 0.35           │ 0.28~0.32 │ 粗匹配相关响应                            │
├────────────────────────────────────┼────────────────┼───────────┼────────────────────────────────────────────────────────────────────────┤
│ loop_match_minimum_response_fine   │ 0.45           │ 0.38~0.42 │ 精匹配响应门槛                            │
├────────────────────────────────────┼────────────────┼───────────┼────────────────────────────────────────────────────────────────────────┤
│ loop_match_maximum_variance_coarse │ 3.0 (m²)       │ 5.0~10.0  │ 粗匹配协方差上                            │
├────────────────────────────────────┼────────────────┼───────────┼────────────────────────────────────────────────────────────────────────┤
│ loop_search_space_dimension        │ 8.0 m          │ 10.0~12.0 │ 以当前位姿为中 差更宽容；计算量按平方增长 │
├────────────────────────────────────┼────────────────┼───────────┼────────────────────────────────────────────────────────────────────────┤
│ loop_search_space_smear_deviation  │ 0.03 m         │ 0.05~0.08 │ 相关网格模糊程更宽容                      │
├────────────────────────────────────┼────────────────┼───────────┼────────────────────────────────────────────────────────────────────────┤
│ loop_search_space_resolution       │ 0.05 m         │ 0.05~0.08 │ 搜索步长；需能ion（源码有 assert）        │
├────────────────────────────────────┼────────────────┼───────────┼────────────────────────────────────────────────────────────────────────┤
│ coarse_search_angle_offset         │ 0.349 rad(20°) │ 0.5~0.7   │ 回环方向差较大                            │
├────────────────────────────────────┼────────────────┼───────────┼────────────────────────────────────────────────────────────────────────┤
│ minimum_travel_distance            │ 0.5 m          │ 0.3       │ 节点更密 → 候 升                          │
├────────────────────────────────────┼────────────────┼───────────┼────────────────────────────────────────────────────────────────────────┤
│ minimum_travel_heading             │ 0.5 rad        │ 0.3       │ 同上                                      │
├────────────────────────────────────┼────────────────┼───────────┼────────────────────────────────────────────────────────────────────────┤
│ minimum_time_interval              │ 0.5 s          │ 0.2~0.3   │ 机器人快时避免                            │
└────────────────────────────────────┴────────────────┴───────────┴────────────────────────────────────────────────────────────────────────┘

scan_buffer_size 不是回环候选的主要开关（候选来自全部扫描，不是 running buffer），但如果你把 minimum_travel_distance 调小，建议按 scan_buffer_maximum_scan_distance / minimum_travel_distance
相应增大，否则顺序匹配窗口会变短。

link_match_minimum_response_fine、link_scan_maximum_distance 是顺序链路匹配用的， 。

一套可直接用的配置

建议先把系统的 mapper_params_online_async.yaml 复制出来，再改下面这些值：
```yaml
slam_toolbox:
  ros__parameters:
    mode: mapping                 # 必须是 mapping，localization 不会扩图/回环建图
    do_loop_closing: true

    # 1) 候选放宽（收益最大）
    loop_search_maximum_distance: 6.0
    loop_match_minimum_chain_size: 6

    # 2) 接受门槛放宽
    loop_match_minimum_response_coarse: 0.30
    loop_match_minimum_response_fine: 0.40
    loop_match_maximum_variance_coarse: 6.0

    # 3) 搜索窗放宽
    loop_search_space_dimension: 10.0
    loop_search_space_resolution: 0.05
    loop_search_space_smear_deviation: 0.06

    # 4) 可选：节点更密
    # minimum_travel_distance: 0.3
    # minimum_travel_heading: 0.3
```
启动时指定：
```sh
ros2 launch slam_toolbox online_async_launch.py use_sim_time:=True \
  slam_params_file:=/你的路径/mapper_params_online_async_tuned.yaml
```
如果还是不进回环，再逐步把 loop_search_maximum_distance 加到 8、coarse/fine 各降 0imension 加到 12。

验证与注意
- 参数是 configure 阶段读入的，ros2 param set /slam_toolbox ... 不会真正改 karto  改完必须重启节点。
- 自动回环在 Jazzy 里默认不打印日志（FireLoopClosureCheck 没有挂 listener），别指望在终端看到 “Loop closed”。看 RViz 的
  /slam_toolbox/graph_visualization（MarkerArray）：回环成功后会多出一条连接新旧区。
- 回环候选是按当前位姿图估计的距离找的。如果返回起点时累计漂移超过 loop_search_maximum_distance，怎么降阈值都不会有候选——这时加大这个半径比降 response 更管用。
- 降门槛的代价是误回环：长走廊、对称房间、重复结构很容易匹配错，地图会“折叠”。建议earch_maximum_distance 和降 chain_size，不够再降 response，最后才动 smear和角度搜索。
- 仿真里注意 /scan 频率和 TF 链正常、use_sim_time 一致；minimum_time_interval: 0.5


===================================

# ch07. 回环到底该怎么用

## 一句话回答

ch04的方案 B 里的 `do_loop_closing: false` 是**调试阶段的隔离手段，不是永久结论**。回环是 SLAM 的全局纠错层，真机建图和长期建图必须打开；但在局部匹配还没调好之前打开它，只会把错误放大。正确顺序是：

**先把局部地图建干净 → 再打开回环做全局闭环 → 用“有没有误折叠”来验收。**

## 先分清两层：局部匹配和全局回环

| 层级 | 机制 | 修正什么 | 失效的后果 |
|---|---|---|---|
| 局部 | 扫描匹配（`use_scan_matching`） | 每帧相对位姿，扫描到局部地图的对齐 | 误差逐帧累积，墙越来越厚、越来越歪 |
| 全局 | 回环检测 + 位姿图优化（`do_loop_closing`） | 已累积的漂移、非相邻帧之间的约束 | 回环处合不上，地图整体弯曲、起点终点错位 |

几个容易混淆的点：

- **回环不能替代扫描匹配。** 回环检测自己也是用相关匹配去验证候选的，同样受孔径问题影响。局部匹配会滑，回环匹配也会滑。
- **回环只修历史，不保险未来。** `CorrectPoses()` 改的是已经进图的历史位姿；改完之后新进来的扫描照样会继续漂。所以“先回环，再去右上角”不能保证右上角干净。
- **回环不是消灭误差，而是把误差摊平到全图。** 一圈走下来总误差本来就该在，回环让它分布均匀、闭合处对齐，不是凭空消失。
- **回环不是“另一种定位方式”。** 它是建立非相邻位姿约束，然后整体优化；位姿的连续来源仍然是 odom + 扫描匹配。

## 为什么方案 B 要先关回环

因为**误回环比没有回环更糟**：

1. 一条错误的回环边是一个很强的全局约束，位姿图优化会把它当真，把整张图“拉”过去——常见现象是墙折叠、房间重叠、原本干净的区域突然整体歪掉。
2. 本次运行结束时地图已经偏了 2.28 m。在这种状态下闭回环，优化器很可能把“已经歪掉的两段”锁在一起，把错误固化下来。
3. 回环只能在“局部地图是对的”前提下纠全局漂移。局部匹配还在滑的时候，回环无法判断哪一段才是对的。

## 正式建图只需要一次运行

先把话说清楚：**目标既然是“一次建图 OK”，正式建图就只有一次运行**——用最终确认的参数（匹配收紧 + 回环打开），把整屋完整走一遍、闭一个回环、存图。下面那套“阶段”不是建图流程，而是一次性的**调试/标定流程**：只在第一次上手、参数未知、或系统明显不正常时做；参数一旦验证通过，以后每次建图都直接按“正式建图”跑一遍，不再重复这些阶段。

### 一次性调试：什么时候需要，产出是什么

| 步骤 | 参数 | 用途 | 是否每次建图都做 |
|---|---|---|---|
| ① 隔离局部问题（可选） | 匹配收紧，回环关 | 判断局部地图能否建干净、确定安全参数区间；产出一组参数，不是交付地图 | 否，只在首次/大改后做一次 |
| ② 验证闭环 | 匹配收紧，回环开、门槛严 | 用 ① 得到的参数完整跑一遍，验证全局闭环；通过了，这张图本身就是交付地图 | 否，参数验证通过即结束 |
| ③ 生产配置 | 同 ② | 不是一次运行，只是把 ② 的参数固化下来 | — |

- ① 是可选的：如果你已经有一组可信参数，直接从 ② 开跑；② 失败再回头做 ① 定位问题。
- ① 的通过标准是局部的：/scan 贴墙、墙厚 ≤ 2~3 格、`map → odom` 稳定。它失败说明问题在轮子/标定/TF/匹配，不在回环。
- ② 的通过标准是全局的：回环处墙对齐、不出现整图折叠。通过后不必再跑第三次。
- 这两个步骤都是“完整建图一遍”，所以确实是多次建图；但它们属于**调试成本**，不是每次建图的操作流程。正常使用只需要承担 ② 这一次。

### 正式建图：一次跑完的流程

参数（调好后固定）：

```yaml
    use_scan_matching: true
    do_loop_closing: true
    # 匹配收紧参数 + 回环严格门槛，见上文
```

步骤：

1. 重启 Gazebo / RViz / slam_toolbox，从零开始；
2. 驾驶顺序：起点 → 大厅/左侧 → 回到已建区域闭回环 → 右上角 → 回起点；
3. 全程盯 /scan 是否贴墙、`tf2_echo map odom` 是否稳定、回环处是否有对齐跳变；
4. 结束时存图。

如果中途墙开始变厚/分叉，不要硬建完：退回或重开这一轮。**重开是重试，不是进入下一个阶段。**

### 关于“一次 OK”

- “一次 OK”靠的是：参数已经一次性调好 + 路线合理 + 全程监控；
- 做不到“第一次上线就保证 OK”：环境、传感器、轮子状态都会变，第一次在陌生环境里通常要先验证一次；
- 但一旦参数验证过，正常建图就是一次运行，不存在“左边阶段1、右边阶段2”，也不存在“每次都要跑三遍”。

### 换参数为什么必须重启

- `use_scan_matching`、`do_loop_closing` 和回环门槛都是 slam_toolbox 在 **configure 阶段**读入的，运行中 `ros2 param set` 不生效，必须重启节点；
- 重启 Gazebo / RViz 是为了从零、可复现（机器人回到起点、世界状态一致、RViz 不残留旧图），不是参数生效的必要条件，但推荐这样做；
- **不要用 serialize/deserialize 在两次建图之间“接着建”**：那会继承上一轮的位姿图，失去对照意义；序列化只用于误回环后的回滚。

## 为什么 SLAM 强调回环

因为**里程计和局部匹配的误差一定会累积，而回环是唯一能把它拉回来的全局机制**。

- 真机轮式里程计每走一段就有 1%–5% 的漂移，扫描匹配只能压住局部误差，压不住几十米后的整体偏移；
- 没有回环，走一圈回到起点，地图上起点和终点对不上，表现为地图“张开口”或弯曲成香蕉形；
- 回环通过“我又看到了以前见过的地方”建立远距离约束，再做位姿图优化，把累积误差分散到整条轨迹上；
- 大场景建图、多楼层、多段建图拼接、长期建图（lifelong mapping）都依赖回环；
- Cartographer 、 ORB-SLAM 这些系统的核心竞争力之一就是回环检测 + 全局优化。

所以“SLAM 强调回环”没有错，错的是把它当成万能补丁：**回环负责全局，局部必须先干净。**

## 回环的正确使用方式

### 1. 前提：局部地图已经干净

不要用回环去掩盖局部滑移。先按方案 B 的收紧参数跑到：

- RViz 里 /scan 始终贴在已建墙上；
- 同一面墙只出现一条线，厚度 ≤ 2~3 格；
- `tf2_echo map odom` 在一段时间内稳定（没有被优化器突然拉动）。

只有这个前提成立，回环的结果才可信。

### 2. 参数：搜索半径覆盖漂移，接受门槛先严

回环的判定分三关（见 ch06）：找候选 → 粗匹配 → 精匹配。调参时有两条原则：

- **`loop_search_maximum_distance` 必须大于“预计漂移”。** 候选是按当前位姿图里的距离找的；如果回到旧区域时漂移已经超过这个半径，就根本找不到候选，怎么降阈值都没用。本次漂移约 2.3 m，建议给到 **5~8 m**。
- **接受门槛宁严勿松。** `loop_match_minimum_response_coarse/fine` 调高、`loop_match_minimum_chain_size` 调大、`loop_match_maximum_variance_coarse` 调小，都是“拒绝弱候选”。只有“候选根本找不到”时才去放宽响应阈值；如果只是“回环不触发”，优先加大搜索半径和节点密度。

一套先严后松的起步配置：

```yaml
    do_loop_closing: true
    loop_search_maximum_distance: 6.0      # 覆盖预计漂移，不是越小越好
    loop_match_minimum_chain_size: 8       # 8~10，越小越容易误闭
    loop_match_minimum_response_coarse: 0.35
    loop_match_minimum_response_fine: 0.45
    loop_match_maximum_variance_coarse: 3.0
    loop_search_space_dimension: 8.0
    loop_search_space_resolution: 0.05
    loop_search_space_smear_deviation: 0.03
```

确认能正确闭环、且没有误折叠之后，再考虑放宽到 ch06 里那套“更容易触发”的参数。顺序不要反过来。

### 3. 驾驶：给回环创造好条件

- **走闭合轨迹**，回到已经建过图的区域，并让两段轨迹有足够的重叠；
- **尽量从相同视角、相同朝向接近旧区域**；视角差太大，相关匹配的响应会明显下降；
- **在回环点低速、连续通过**，不要原地急转；
- **选特征丰富的位置闭回环**（墙角、门垛、家具），不要在长直走廊、重复门洞、对称房间里硬闭——这些地方最容易误回环；
- 回环区域附近可以稍微靠近墙走，让雷达拿到更清晰的几何。

### 4. 验证：怎么知道回环是“对的”

- RViz 里看 `/slam_toolbox/graph_visualization`：正确闭环会在新旧两段之间多出一条连接；
- `tf2_echo map odom` 在闭环瞬间会跳一下，跳完之后应该保持稳定；
- 看回环接缝处：墙是否对齐、有没有双层墙、原来干净的区域有没有整体被拉走；
- 保存地图后检查：回环处的墙厚、房间尺寸、起点和终点是否重合。

回环成功但地图出现**整体折叠/房间重叠/原本干净的区域突然歪掉**，说明闭错了，不是“优化得不够”。

### 5. 闭错了怎么处理

- 先停，不要继续建图，也不要继续降门槛试图“再闭一次”；
- 回环已经优化过的位姿无法在线上简单撤销，最稳的是重启 SLAM 重新建图；
- 如果提前做了序列化（`/slam_toolbox/serialize_map`），可以在误闭环前保存位姿图，重启后用 `deserialize_map` 恢复；
- 下次把 `loop_match_minimum_response_*` 调高、`chain_size` 调大、搜索半径收到合理范围，而不是继续放宽。

## 什么时候可以真的关掉回环

| 场景 | 可以关吗 | 说明 |
|---|---|---|
| 单房间、短时间、明确不会回到旧区域 | 可以 | 累积漂移本来就小，回环没有用武之地 |
| 调试局部匹配/隔离变量 | 可以，且应该 | 方案 B 的阶段 ① |
| 已知匹配器不可靠，误回环代价更大 | 暂时可以 | 只是权宜之计，不是建图方案 |
| 纯定位模式（`mode: localization`） | 不涉及 | 定位模式不会扩图/建图，回环本来就不跑 |
| 真机、大场景、长期建图 | 不可以 | 没有回环，地图无法全局一致 |

## 和本项目的结论怎么统一

- 这次仿真里，局部匹配确实滑了，所以先用方案 B 的收紧参数、关回环，把局部地图建干净；
- 局部干净之后，回环是要打开的——它不是“这次问题的元凶”，只是在局部还没调好时不该先开；
- 真机上更离不开回环：里程计会漂，扫描匹配只能压局部误差，全局一致性必须靠回环；
- 判断标准始终是：**局部看墙厚和 /scan 贴合度，全局看回环接缝和有没有整图折叠。**


===================================

# ch08. 分段建图、checkpoint 与回滚续建
```txt
❯ 这个房子结构复杂： 左下是大厅，左上角是房间，右上和右下分别是房间。中间是十字形的通道。 试过几次都是左边建图正常，到右边突然垮掉。 是否可以边建图边保存，垮掉时回退到正常处继续建图？否则永远无法建图完成，因为各种误差一直存在
```
## 先说结论

- **可以做 checkpoint + 回滚 + 续建**：slam_toolbox 提供 `serialize_map` / `deserialize_map`，保存的是位姿图，不是普通 PGM/YAML，所以能接着建。
- **但回滚不是“右侧必垮”的解法**，它只是安全网。每次都在同一侧垮，说明是系统性问题（感知歧义、参数、路线、碰撞），不改变条件，回滚只会把同一段失败重放一遍。
- 真正能让这个复杂户型建完的，是**把长距离开放式探索改成“以十字通道为 hub 的短臂往返 + 频繁回环 + 在 hub 设 checkpoint”**。

## 1. checkpoint 到底保存什么

| 方式             | 保存内容         | 能否续建 | 用途          |
|-----------------|-----------------|--------|---------------|
| `map_saver_cli` | PGM/YAML 占用栅格 | **否** | 看地图、给导航用 |
| `serialize_map` | `.posegraph` + `.data`（位姿图 + 扫描） | **是** | 回滚、续建 |
| 两者都存 | — | — | 推荐做法 |

- `serialize_map` 的服务类型是 `slam_toolbox/srv/SerializePoseGraph`，只需要一个 `filename`；会生成 `<filename>.posegraph` 和 `<filename>.data`。
- 只存 `map_saver_cli` 的 PGM/YAML 是**不能**用来续建的——它没有位姿图和扫描数据。
- 序列化文件与 slam_toolbox 版本相关，升级后旧文件可能读不了。
- 保持 `stack_size_to_use: 40000000`，大图序列化需要更大的栈。

## 2. 什么时候存、存在哪

- **只在确认地图干净的时刻存**，不要盲目定时存：定时可能刚好把“已经开始垮”的中间状态存下来。
- 存在 **hub**：十字通道中心、大厅入口这类每次探索都会回到的位置。
- 每次进入一条风险臂之前存一份，保留最近 2~3 份即可。
- 命名带语义，便于回滚时选择：`ckpt_01_left`、`ckpt_02_cross`、`ckpt_03_topright`。

```bash
WS=/home/abner/a2/zdev/nv/adas-01/ros/ros2bookcode_jazzy/chapt7_ws
ros2 service call /slam_toolbox/serialize_map slam_toolbox/srv/SerializePoseGraph \
  "{filename: '${WS}/src/fishbot_navigation2/maps/ckpt_02_cross'}"
```

先 `ros2 service list | grep slam` 确认服务名是否带命名空间。

## 3. 回滚：怎么从 checkpoint 继续

### 方式 A：启动时加载（少一步）

在 params yaml 里加：

```yaml
    mode: mapping
    map_file_name: /absolute/path/to/ckpt_02_cross   # 绝对路径，不带扩展名
    map_start_pose: [x, y, theta]                    # 机器人当前在 map 系下的位姿
    # 或者 map_start_at_dock: true（与 map_start_pose 二选一）
```

然后重启 slam_toolbox。若启动时没有自动加载，节点起来后再手动调 `deserialize_map`。

### 方式 B：运行中调用服务

```bash
ros2 service call /slam_toolbox/deserialize_map slam_toolbox/srv/DeserializePoseGraph \
  "{filename: '/absolute/path/ckpt_02_cross', match_type: 2, initial_pose: {x: X, y: Y, theta: T}}"
```

`match_type` 以本机安装的 srv 为准（Jazzy 里是 `1=START_AT_FIRST_NODE`、`2=START_AT_GIVEN_POSE`、`3=LOCALIZE_AT_POSE`）。

### 最关键的约束：机器人必须回到 checkpoint 的物理位姿

- 最稳的做法：**Gazebo 不重启**，手动把车开回 hub（比如十字中心），停在 checkpoint 时的位置和朝向，再重启 slam_toolbox 并 deserialize；
- 如果重启 Gazebo，就要把车放回/开到同一个物理位姿，并把该位姿填进 `map_start_pose`；
- **位姿对不上会出现地图和扫描叠加、双层墙**（slam_toolbox 的已知问题）；宁可多花时间把车开回原位，也不要把 `map_start_pose` 随手填成 `[0,0,0]`；
- 重启 slam_toolbox 是必须的（参数只在 configure 读入），Gazebo/RViz 可以不重启，除非你想完全重置世界状态。

## 4. 为什么“回滚”救不了重复失败

同一位置、同一方向、同一参数，回滚只是回到过去，再走一遍还会在同一处垮。这时已经不是“误差一直存在”的随机累积，而是**系统性触发**，常见来源：

| 可能原因 | 怎么验证 |
|---|---|
| 十字通道/走廊的感知歧义或孔径问题 | 换一个进入方向（顺/逆时针）看是否同样垮 |
| 左侧小误差把右侧匹配带进错误局部极小 | 进右侧前先在 hub 闭一次回环，看 `map→odom` 是否跳、地图是否更干净 |
| 门口转向、贴墙碰撞导致里程计打滑 | 垮的瞬间对比 `/odom` 与 `gz model -m fishbot -p`，并看 Gazebo 有没有碰撞 |
| 匹配搜索窗太宽，允许沿走廊跳变 | `correlation_search_space_dimension` 从 0.5 收到 0.1~0.2 |
| 远墙放大 yaw 误差 | `max_laser_range` 从 20 降到 8~10 做对照 |

**每次回滚后至少改一个变量，并记录下来**：进入方向、速度、是否先在 hub 闭回环、搜索窗、雷达最大距离、路线。不改条件，回滚没有意义。

## 5. 针对这个户型的建图路线：hub-and-spoke

把“从大厅一路建到右侧”改成“每次只离开 hub 一条短臂，然后回来”：

1. 大厅绕一圈，回起点 → 回环；
2. 大厅 → 左上房间 → 绕回大厅 → 回环；
3. 大厅 → 十字中心（checkpoint A）→ 右上房间 → 回十字中心 → 回环（checkpoint B）；
4. 十字中心 → 右下房间 → 回十字中心/大厅 → 回环；
5. 全部走完后，再从起点绕一圈做最终验收。

这样做的理由：

- 每条臂都很短，误差来不及累积；
- 每次回到 hub 都创造一次回环机会，把误差压回去；
- checkpoint 都在 hub，回滚时机器人物理位置好找；
- 十字通道的相似臂不再是一次长穿越，而是多次短往返，感知歧义被回环约束住。

驾驶细节：

- 进右侧前先在 hub 确认 `map→odom` 稳定、地图干净，再存 checkpoint；
- 过门口直着进，不要在门框/走廊口原地转；转弯在房间内部开阔处做；
- 沿走廊走时靠一侧，让门垛/墙角进视野，不要一直在走廊正中只看两面平行墙；
- 宁愿多倒一次车、多走一段，也不要贴墙蹭——Gazebo 里的碰撞会让轮速和真实运动不一致。

## 6. 如果 hub 路线还是垮

按顺序试，不要一次改一堆：

1. **收紧匹配**：`correlation_search_space_dimension: 0.1~0.2`、`smear: 0.03`、`link_match_minimum_response_fine: 0.35~0.4`、`scan_buffer_size: 20`、`minimum_travel_distance/heading: 0.3`；
2. **降低远墙影响**：`max_laser_range` 降到 8~10 m；
3. **回环**：先在 hub 开严格回环，确认没有误折叠，再让每条臂回来时闭；
4. **换进入方向**：顺时针 vs 逆时针进右侧，验证是不是十字通道对称结构导致锁错；
5. **只建一条臂**：只做“十字中心 → 右上 → 回十字中心”。能成，说明问题是长距离开放式探索，不是右侧本身不能建；
6. **兜底：分段建图后合并**。右侧单独开一轮，从十字中心附近起步，再把两张图在十字通道处配准拼接。slam_toolbox 还有 `AddSubmap` / `lifelong` 模式可做多段地图合并，但配置更复杂，属于兜底而不是首选。

## 7. 关于“误差永远存在，所以永远建不完”

- 误差永远存在，但 SLAM 的目标不是消灭误差，而是**把误差约束在可闭合的范围内**：局部匹配压小误差，回环把累积误差摊平；
- 19 × 11 m 的室内场景对 2D SLAM 不算大，参数正确、路线合理时 slam_toolbox 可以建完；
- “每次都在右侧垮”是**系统性失败**，不是误差的宿命。把它当 bug 查，而不是当物理定律接受；
- checkpoint/回滚最大的价值是**调试加速**：不必每次从零开始，可以把左边干净的地图保住，专心在右侧做对照实验。它是安全网，不是建图方法本身。
