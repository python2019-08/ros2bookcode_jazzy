# ch01.gazebo_control_plugin.xacro

chapt7_ws/src/fishbot_description/urdf/fishbot/fishbot.ros2_control.xacro的内容如下,请改成 ros2jazzy版本:
```xml
<?xml version="1.0"?>
<robot xmlns:xacro="http://www.ros.org/wiki/xacro">
    <xacro:macro name="fishbot_ros2_control">
        <ros2_control name="FishBotGazeboSystem" type="system">
            <hardware>
                <plugin>gazebo_ros2_control/GazeboSystem</plugin>
            </hardware>
            <joint name="left_wheel_joint">
                <command_interface name="velocity">
                    <param name="min">-1</param>
                    <param name="max">1</param>
                </command_interface>
                <command_interface name="effort">
                    <param name="min">-0.1</param>
                    <param name="max">0.1</param>
                </command_interface>
                <state_interface name="position" />
                <state_interface name="velocity" />
                <state_interface name="effort" />
            </joint>
            <joint name="right_wheel_joint">
                <command_interface name="velocity">
                    <param name="min">-1</param>
                    <param name="max">1</param>
                </command_interface>
                <command_interface name="effort">
                    <param name="min">-0.1</param>
                    <param name="max">0.1</param>
                </command_interface>
                <state_interface name="position" />
                <state_interface name="velocity" />
                <state_interface name="effort" />
            </joint>
        </ros2_control>

        <gazebo>
        <plugin filename="libgazebo_ros2_control.so" name="gazebo_ros2_control">
            <parameters>$(find fishbot_description)/config/fishbot_ros2_controller.yaml</parameters>
            <ros>
                <remapping>/fishbot_diff_drive_controller/cmd_vel_unstamped:=/cmd_vel</remapping>
                <remapping>/fishbot_diff_drive_controller/odom:=/odom</remapping>
            </ros>
        </plugin>
        </gazebo>

    </xacro:macro>
</robot>
```
<!-- google AI  -->
## sec.1 改动核心说明

在 ROS 2 Jazzy Jalisco 中，如果你使用的是新版的 Gazebo（即原名 Ignition Gazebo，官方现称 Gazebo Sim），gazebo_ros2_control 插件和硬件接口的配置方式发生了一些关键变化。
针对 ROS 2 Jazzy 版本，修改后的完整 fishbot.ros2_control.xacro 内容如下：

```xml
<?xml version="1.0"?>
<robot xmlns:xacro="http://www.ros.org/wiki/xacro">
    <xacro:macro name="fishbot_ros2_control">
        <ros2_control name="FishBotGazeboSystem" type="system">
            <hardware>
                <!-- 1. 修改为新版 Gazebo Sim 的硬件插件 -->
                <plugin>gz_ros2_control/GazeboSimSystem</plugin>
            </hardware>
            <joint name="left_wheel_joint">
                <command_interface name="velocity">
                    <param name="min">-1</param>
                    <param name="max">1</param>
                </command_interface>
                <command_interface name="effort">
                    <param name="min">-0.1</param>
                    <param name="max">0.1</param>
                </command_interface>
                <state_interface name="position" />
                <state_interface name="velocity" />
                <state_interface name="effort" />
            </joint>
            <joint name="right_wheel_joint">
                <command_interface name="velocity">
                    <param name="min">-1</param>
                    <param name="max">1</param>
                </command_interface>
                <command_interface name="effort">
                    <param name="min">-0.1</param>
                    <param name="max">0.1</param>
                </command_interface>
                <state_interface name="position" />
                <state_interface name="velocity" />
                <state_interface name="effort" />
            </joint>
        </ros2_control>

        <gazebo>
            <!-- 2. 修改为新版 Gazebo 仿真插件名和文件名 (gz_ros2_control) -->
            <plugin filename="libgz_ros2_control-system.so" name="gz_ros2_control::GazeboSimROS2ControlPlugin">
                <parameters>$(find fishbot_description)/config/fishbot_ros2_controller.yaml</parameters>
                <ros>
                    <remapping>/fishbot_diff_drive_controller/cmd_vel_unstamped:=/cmd_vel</remapping>
                    <remapping>/fishbot_diff_drive_controller/odom:=/odom</remapping>
                </ros>
            </plugin>
        </gazebo>
    </xacro:macro>
</robot> 
```

💡 主要修改点说明：

1. 硬件插件（<hardware>）：从旧版 Gazebo Classic 的 gazebo_ros2_control/GazeboSystem 替换为了新版 Gazebo Sim 的 gz_ros2_control/GazeboSimSystem。
2. 仿真插件（<gazebo>）：从旧版的 libgazebo_ros2_control.so 替换为了新版的 libgz_ros2_control-system.so，且 name 属性改为了 gz_ros2_control::GazeboSimROS2ControlPlugin。
3. 闭合标签：补全了你提供的源码末尾缺失的 </gazebo>, </xacro:macro> 和 </robot> 闭合标签。
请问你当前在 Jazzy 中使用的仿真环境是新版的 Gazebo Sim (Harmonic) 还是依然在使用旧版的 Gazebo Classic？此外，你的控制配置文件 fishbot_ros2_controller.yaml 中的控制器类型 (plugin type) 是否也已经更新为兼容新版控制器的命名空间了？
 

## sec.2 Launch里面如何 用controller_manager 加载yaml 
 
```py
# controller_manager，放到事件里，spawn成功之后再启动
controller_manager_node = launch_ros.actions.Node(
    package='controller_manager',
    executable='ros2_control_node',
    parameters=[
        get_package_share_directory('fishbot_description') + '/config/fishbot_ros2_controller.yaml'
    ],
    remappings=[
        ('/fishbot_diff_drive_controller/odom', '/odom')
    ],
    output='screen'
)

# .........

ld = launch.LaunchDescription([
    action_declare_arg_mode_path,
    robot_state_publisher_node,
    launch_gazebo,
    spawn_entity_node,
    gz_bridge_node,
    # 事件链：spawn成功 → 启动controller_manager → 加载joint_state → 加载diff drive
    launch.actions.RegisterEventHandler(
        event_handler=launch.event_handlers.OnProcessExit(
            target_action=spawn_entity_node,
            on_exit=[controller_manager_node], #.....
        )
    ),
    launch.actions.RegisterEventHandler(
        event_handler=launch.event_handlers.OnProcessExit(
            target_action=controller_manager_node, #........
            on_exit=[load_joint_state_controller],
        )
    ),
    launch.actions.RegisterEventHandler(
        event_handler=launch.event_handlers.OnProcessExit(
            target_action=load_joint_state_controller,
            on_exit=[load_fishbot_diff_drive_controller],
        )
    ),
])
```

并且把 `controller_manager_node` 添加进`ld = LaunchDescription([...])`列表。

> 
> 提醒：controller_manager节点要在robot_state_publisher之后，spawn机器人之前启动。

### 这段Launch 代码和 fishbot.ros2_control.xacro 的关系

#### 1. 运行时的“互斥关系”（针对仿真）

在 Gazebo 仿真中，它们确实是水火不容的：
• Xacro 中的 Gazebo 插件：会在 Gazebo 进程内部自动启动一个 Controller Manager。
• Launch 中的 ros2_control_node：是在 Gazebo 外部手动启动一个 Controller Manager。

为什么互斥？
ROS 2 不允许同一个机器人的同一批关节有两个 Manager 同时去管理。如果你在启动 Gazebo 仿真的同时，又在 Launch 里运行了 ros2_control_node，它们会尝试读取同一个 YAML 文件，加载同名的控制器，从而导致命名空间冲突、硬件资源抢占报错，甚至导致控制器直接崩溃。

因此，在做仿真时，你必须把 Launch 里的 controller_manager_node 删掉或注释掉，完全交给 Xacro 里的 Gazebo 插件去处理。

#### 2. 逻辑上的“协作关系”（针对跨平台复用）

为什么写 ROS 2 项目时会同时看到这两个东西呢？因为设计 ros2_control 的初衷是为了实现“一套代码，仿真与实机完美切换”：

开发阶段/运行环境  | Xacro 文件里的 <ros2_control> 标签    | Launch 里的 ros2_control_node 节点 |
----------------|-------------------------------------|-----------------------------------
纯 Gazebo 仿真	 | 运行（由 Gazebo 插件加载它并读取硬件接口）| ❌ 关闭（不能启动，否则冲突）        |
真实机器人（实机） | 运行（提供给 robot_state_publisher 转换结构）|	运行（作为实机控制的中央大脑，驱动物理电机）|


在实机阶段，Xacro 负责告诉系统“我的机器人长什么样、有哪些接口”，而 Launch 里的 ros2_control_node 则作为真正的实体节点运行，两者协同工作。

#### 总结

你指出的互斥关系直击问题核心！如果你现在正在写 Gazebo 仿真的 Launch 脚本：
• 请果断删掉或不执行 Launch 里的 controller_manager_node。
• 只需要让 Launch 启动 Gazebo，Gazebo 会通过读取加载了 fishbot.ros2_control.xacro 的机器人模型，自己把控制器拉起来。
既然你已经注意到了这个冲突，需要我帮你看看你当前的 Launch 启动脚本吗？我可以帮你检查一下，确认是否需要移除这个独立的 ros2_control_node，或者如何优雅地通过 Launch 参数（如 use_sim_time） 来让它在仿真和实机之间自动切换。



==============================

# ch02.为何 fishbot.ros2_control.xacro的remapping没有起到作用

<!--   -->

## claude code结论

fishbot.ros2_control.xacro:42-45 里的 remapping 在你这套 Jazzy 环境里其实是生效的（gz_ros2_control 1.2.20 会解析 <ros><remapping>，ros2_control 4.48 的 determine_controller_node_options() 会把它继承给每个 controller 节点）。我按你的 URDF 做了一次无头复现，ros2 node info /fishbot_diff_drive_controller 显示：
```sh
Publishers:
  /odom_01by_ros2control: nav_msgs/msg/Odometry   ← odom 这条 remap 生效了
Subscribers:
  /fishbot_diff_drive_controller/cmd_vel: geometry_msgs/msg/TwistStamped  ← 没被 remap
```

你看到的“完全没作用”，是下面三件事叠加造成的：

1. 你 ros2 topic list 的时候，diff_drive 控制器根本没起来

你的列表里连 /fishbot_diff_drive_controller/transition_event 都没有（joint_state_broadcaster 的却有），说明当时控制器节点不在图里，自然也不会有任何 remap 后的 topic。控制器是在 spawn 之后约 6 秒才由事件链里的 ros2 control load_controller 拉起来的；启动早期执行 ros2 topic list 就会得到你贴的那份列表。

2. launch 里的 spawner 一开始就崩了（exit code 2）

~/.ros/log/latest/launch.log 里：

[ERROR] [spawner-4]: process has died [pid 719261, exit code 2, cmd '... spawner fishbot_diff_drive_controller
 --controller-manager /controller_manager --controller-ros-args --remap ... --remap ... --ros-args']

原因：Jazzy 的 spawner 里 --controller-ros-args 是 action="append"、每次只接受一个字符串参数（再按空格拆分，见 spawner.py:197,502）。你写成 --controller-ros-args --remap A --remap B，argparse 会认为 --remap 是下一个选项，直接报：

spawner: error: argument --controller-ros-args: expected one argument

所以实际把控制器拉起来的是后面 fallback 的 ros2 control load_controller（它不带 sp的 remap）。

3. cmd_vel_unstamped 这个 topic 在 Jazzy 里已经不存在了

Jazzy 的 diff_drive_controller 4.42.1 只订阅 ~/cmd_vel（geometry_msgs/TwistStampedD_TOPIC = "~/cmd_vel"，use_stamped_vel / cmd_vel_unstamped 是 Humble时代的写法。所以：

- cmd_vel_unstamped:=... 这条 remap 永远匹配不到任何 topic，静默失效（不会报错）；
- 你 yaml 里 fishbot_ros2_controller.yaml:51 的 use_stamped_vel: false 也是无效参

odom 那条名字是对的，所以它生效。

### 修改建议

#### 方案 A（推荐，改 xacro，保持现在的 load_controller 事件链）

fishbot.ros2_control.xacro:43：

<remapping>/fishbot_diff_drive_controller/cmd_vel:=/cmd_vel_01by_ros2control</rema
<remapping>/fishbot_diff_drive_controller/odom:=/odom_01by_ros2control</remapping>

并把 fishbot_ros2_controller.yaml:51 的 use_stamped_vel: false 删掉。注意：改完后 /cmd_vel_01by_ros2control 的类型是 geometry_msgs/msg/TwistStamped（不是 Twist），用 ros2 topic pub 测试时要带
header.stamp。

#### 方案 B（修 launch 里的 spawner，Jazzy 官方推荐方式）

gazebo_sim.launch.py:76-87 改成一次传入一个完整的字符串：

spawn_diff_drive = launch_ros.actions.Node(
    package="controller_manager",
    executable="spawner",
    arguments=[
        "fishbot_diff_drive_controller",
        "--controller-manager", "/controller_manager",
        "--controller-ros-args",
        "--ros-args "
        "--remap /fishbot_diff_drive_controller/cmd_vel:=/cmd_vel_01by_ros2control
        "--remap /fishbot_diff_drive_controller/odom:=/odom_01by_ros2control",
    ],
    output="screen",
)

####  两种方案二选一
两种方式二选一即可，不要两边都写（重复规则虽然一般无害，但容易混淆）。另外这个 spa，早于 controller_manager 出现；即使参数修好，也会先等待服务，或者移到 spawn 成功的 OnProcessExit 事件里更稳妥。

### 方案A验证

 我使用了方案A,验证:
 ```sh
  $ ros2 topic list
  /camera_sensor/camera_info
  /camera_sensor/depth_image
  /camera_sensor/image
  /camera_sensor/points
  /clock
  /cmd_vel_01by_ros2control
  /controller_manager/activity
  /controller_manager/introspection_data/full
  /controller_manager/introspection_data/names
  /controller_manager/introspection_data/values
  /controller_manager/statistics/full
  /controller_manager/statistics/names
  /controller_manager/statistics/values
  /diagnostics
  /dynamic_joint_states
  /fishbot_diff_drive_controller/transition_event
  /fishbot_joint_state_broadcaster/transition_event
  /gz/odom
  /imu
  /joint_states
  /odom_01by_ros2control
  /parameter_events
  /robot_description
  /rosout
  /scan
  /tf
  /tf_static
  ```


#### 先说结论：方案 A 已经生效了

你贴的 ros2 topic list 里 /cmd_vel_01by_ros2control、/odom_01by_ros2control 都在，而 /fishbot_diff_drive_controller/cmd_vel、/odom 都不在——这正是 remap 成功的样子。我直接查了正在跑的图：
```sh
$ ros2 node info /fishbot_diff_drive_controller
Subscribers:
  /cmd_vel_01by_ros2control: geometry_msgs/msg/TwistStamped
Publishers:
  /odom_01by_ros2control:    nav_msgs/msg/Odometry
```
并且实际发了指令验证链路：
```sh
ros2 topic pub -r 20 /cmd_vel_01by_ros2control geometry_msgs/msg/TwistStamped \
  "{header: {stamp: {sec: 0, nanosec: 0}, frame_id: base_link}, twist: {linear: {x: 0.2}}}"
→ /joint_states velocity = [6.25, 6.25] rad/s   (= 0.2 / wheel_radius 0.032)
→ 发零速度后 = [0, 0]
```
命令进得去、轮子转得动，remapping 是通的。


#### 但还有两个独立问题，让人误以为 remap 没起作用:

1. /odom_01by_ros2control 有 publisher，但没有数据

ros2 topic hz /odom_01by_ros2control 完全没输出（/joint_states 却是 100 Hz）。根因是没有人发布 /clock：
```sh
$ ros2 topic info -v /clock
Publisher count: 0        ← 只有 3 个 subscriber
```
ros_gz_sim 的 gz_sim.launch.py 不会桥接 clock（grep 过，里面没有），你的 gz_bridge_node 参数列表里也没有它（gazebo_sim.launch.py:107-120）。于是 controller_manager 和两个控制器都是 use_sim_time:=true 但时间恒为 0，导致：
- diff_drive_controller 的 publish_rate 节流条件 now - last_publish >= 1/publish_rate 永远不成立 → odom 一条都不发；
- cmd_vel_timeout 永远不过期 → 最后一条速度指令会一直被保持（危险）。我测试时轮子就以 6.25 rad/s 一直转，直到显式发 0 才停；
- odom/TF 的时间戳全是 0，RViz、nav2 都无法正常使用。



我临时起了一个 clock bridge 验证：odom 立刻开始发布，stamp 是 sec: 231。

修复：在 gazebo_sim.launch.py 的 bridge 参数里加一行：

'/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',

2. remap 后的 cmd_vel 话题类型是 TwistStamped

/cmd_vel_01by_ros2control 是 geometry_msgs/msg/TwistStamped。用 teleop_twist_keyboard（发 Twist）不会建立连接，测试时要用：

ros2 topic pub -r 10 /cmd_vel_01by_ros2control geometry_msgs/msg/TwistStamped \
"{header: {stamp: {sec: 0, nanosec: 0}, frame_id: base_link}, twist: {linear: {x: 0.2}, angular: {z: 0.5}}}"

或者加一个 twist_stamper 节点把 Twist 转成 TwistStamped。

3. yaml 里三个参数在 Jazzy 中不存在

fishbot_ros2_controller.yaml 的 use_stamped_vel、publish_odom、publish_odom_tf 都不是 Jazzy diff_drive_controller 的参数（ros2 param get 返回 Parameter not set）。真正控制 TF 发布的是 enable_odom_tf（默认 true）。删掉这几行即可，不影响行为。

---

另外说明一下：我在你正在运行的仿真里做了 0.2 m/s 的移动测试。因为时钟冻结导致 timeout 失效，机器人沿 +x 方向走了约 3.7 m，现在停在 x≈3.71, y≈0（可能已经顶到墙）。我已经发了零速度让它停下；如果想恢复原位，重启一下 launch 或重置世界即可。

需要我把 /clock 那行加进 gazebo_sim.launch.py，顺手清掉 yaml 里的无效参数吗？


重启 launch 后可以这样验证：
```sh
ros2 topic hz /clock               # 应该有频率（这个 bridge 大约 1kHz）
ros2 topic hz /odom_01by_ros2control   # 应为 50Hz（publish_rate）
ros2 run tf2_tools view_frames     # odom -> base_footprint 时间戳正常
```

======================================

# ch03.plugin filename

<plugin filename="libgz_ros2_control-system.so" 
                    name="gz_ros2_control::GazeboSimROS2ControlPlugin">
和
  <plugin filename="gz-sim-diff-drive-system" 
          name="gz::sim::systems::DiffDrive">
中的filename ,为何一个是lib***.so,另一个不是?

<!-- google AI -->
這兩個 filename 寫法不同的核心原因在於：現代 Gazebo（原名 Ignition）引入了「跨平台路徑自動補解析」機制，而不同外掛的開發規範與整合方式存在歷史或跨平台考量。

## 具體原因可以拆解為以下幾點：

1. 跨平台相容性與自動補全 (Cross-Platform Compatibility)

• gz-sim-diff-drive-system：這是 Gazebo 官方內建的系統外掛（System Plugin）。新版 Gazebo 為了支援跨平台（Linux、macOS、Windows），在讀取官方外掛時，不建議寫死前綴與副檔名。
	• Gazebo 底層會根據當前作業系統自動補全：
		• Linux：自動尋找 libgz-sim-diff-drive-system.so
		• macOS：自動尋找 libgz-sim-diff-drive-system.dylib
		• Windows：自動尋找 gz-sim-diff-drive-system.dll 
• libgz_ros2_control-system.so：這是由 ROS 2 社群（而非 Gazebo 官方核心）維護的第三方外掛。在 Linux (Ubuntu) 環境下，它被編譯並安裝在標準的 ROS 2 程式庫路徑中（例如 /opt/ros/<distro>/lib/）。因此通常習慣以完整的 Linux 共享庫檔名來指定它。

2. 搜尋路徑與外掛類型

Gazebo 在加載這兩個外掛時，背後的搜尋邏輯不同：
• 官方內建外掛：像 gz-sim-diff-drive-system 存放在 Gazebo 的預設外掛目錄中（由環境變數 GZ_SIM_SYSTEM_PLUGIN_PATH 定義）。Gazebo 對這些內部組件有完美的索引，直接寫外掛名稱（Project Target Name）即可識別。
• ROS 2 整合外掛：libgz_ros2_control-system.so 需要明確指示副檔名，以確保 Gazebo 的外掛加載器（基於 PluginLoader）能精確將其作為一個硬性共享庫檔（Shared Library）直接開啟。 

## 💡 結論與實務建議

其實在較新版本的 Gazebo（如 Harmonic、Ionic）中，gz_ros2_control 往往也已經支援省略前後綴的寫法。
• 最穩健的原則：如果是 Gazebo 官方內建的外掛，一律省略 lib 和 .so；如果是第三方或 ROS 專屬外挂，若遇到找不到外掛的錯誤，寫出完整的 lib***.so 通常是最安全、最直接的作法。


# ch04.ROS2Jazzy中,diff_drive_controller和Gazebo的原生 DiffDrive订阅topic
  

1. ROS2 Jazzy 的 diff_drive_controller

• 預設訂閱：geometry_msgs/msg/TwistStamped。
• 變更原因：ROS 2 官方社群為了提升控制系統的即時性（Real-time）與安全性，從 Jazzy 開始，許多官方控制器（如 ros2_controllers 中的差速驅動、非完整性驅動等）都強制或預設切換為帶有時間戳與座標系資訊的 TwistStamped。
• 影響：如果你直接執行舊版的鍵盤控制 ros2 run teleop_twist_keyboard teleop_twist_keyboard，它發布的是沒有時間戳的 Twist，控制器會完全忽略它。 

2. Gazebo (gz sim) 的原生 DiffDrive 外掛

• 預設訂閱：gz.msgs.Twist（不帶時間戳）。
• 對應 ROS 2 類型：在透過 ros_gz_bridge 進行橋接時，它對應的是 ROS 2 的 geometry_msgs/msg/Twist。
• 核心原因：Gazebo 的模擬核心外掛（如 gz-sim-diff-drive-system）為了保持通用性與內部訊息設計的簡潔，其底層接收的依舊是純粹的 Twist 速度向量。 

🛠️ 實務上如何解決這個不匹配？

根據你的架構選擇，通常有以下兩種解決方案：

方案 A：如果你使用 ros2_control（硬體抽象層整合）

如果你使用了 gz_ros2_control 外掛，ROS 2 的 diff_drive_controller 會直接跑在模擬器內。此時你不需要手動用 bridge 橋接 cmd_vel。
• 解決辦法：讓發布端發出帶時間戳的指令。例如執行鍵盤遙控時，必須加上 stamped 參數： [1] (/goto?url=CAESYAHrOzAVySlyi2SQE8NZt178EPe02B0FXvS2mnMbfBvjJIdMiHjf5ZGT4ffuWGy6ktulCIBht8fuoys31kWXTz4boBq1OEdmNJ-232wdSWzIEn4bFBwJyW3DvvWk0QrLvA)
bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -p stamped:=true -r /cmd_vel:=/diff_drive_controller/cmd_vel
請謹慎使用程式碼。

方案 B：如果你使用 ros_gz_bridge（純主題橋接）

如果你是直接用 Gazebo 原生外掛，並用 ros_gz_bridge 來傳遞鍵盤或 Nav2 的指令給 Gazebo。
• 解決辦法：新版的 ros_gz_bridge 已經支援在橋接時自動進行型態轉換。你可以在 Launch 檔或終端機中這樣設定，直接把 ROS 2 的 TwistStamped 轉成 Gazebo 的 Twist：bash
ros2 run ros_gz_bridge parameter_bridge /cmd_vel@geometry_msgs/msg/TwistStamped[gz.msgs.Twist
請謹慎使用程式碼。
(注意：後方的 [ 代表單向由 ROS 2 傳入 Gazebo) 
你目前正在處理的專案，是採取 方案 A（使用 ros2_control + gz_ros2_control） 還是 方案 B（單純用 ros_gz_bridge 連接 Gazebo 原生外掛） 呢？我可以依據你的架構提供具體的軟體包設定檔（.yaml 或 .sdf）修改範例。



