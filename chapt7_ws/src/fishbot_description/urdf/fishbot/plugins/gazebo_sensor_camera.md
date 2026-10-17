# ch01.camera sensor
chapt7_ws/src/fishbot_description/urdf/fishbot/plugins/gazebo_sensor_plugin.xacro
中 的 camera如下:
```xml
<gazebo reference="camera_link">
    <sensor type="depth" name="camera_sensor">
        <plugin name="depth_camera" filename="libgazebo_ros_camera.so">
            <frame_name>camera_optical_link</frame_name>
        </plugin>
        <always_on>true</always_on>
        <update_rate>10</update_rate>
        <camera name="camera">
            <horizontal_fov>1.5009831567</horizontal_fov>
            <image>
                <width>800</width>
                <height>600</height>
                <format>R8G8B8</format>
            </image>
            <distortion>
                <k1>0.0</k1>
                <k2>0.0</k2>
                <k3>0.0</k3>
                <p1>0.0</p1>
                <p2>0.0</p2>
                <center>0.5 0.5</center>
            </distortion>
        </camera>
    </sensor>
</gazebo>
```

请改成 ros2jazzy的版本

Humble 使用 `gazebo_ros_camera.so`（Gazebo Classic）；**Jazzy + Gazebo Harmonic(gz-sim) 不再使用这个插件**。
Harmonic 原生深度相机：

- 传感器 `type="depth"` 保留
- 去掉 `libgazebo_ros_camera.so`
- 使用 **gz 原生传感器**，再依靠 `ros_gz_bridge` 把图像、深度消息桥接到ROS2话题

> 
> 注意：Harmonic 的 `<sensor type="depth">` 本身就可以输出彩色图 + 深度图，不需要老的 gazebo_ros_camera 插件。

## 修改后 gazebo_sensor_plugin.xacro 片段

```xml
<gazebo reference="camera_link">
    <sensor type="depth" name="camera_sensor">
        <always_on>true</always_on>
        <update_rate>10</update_rate>
        <camera name="camera">
            <horizontal_fov>1.5009831567</horizontal_fov>
            <image>
                <width>800</width>
                <height>600</height>
                <format>R8G8B8</format>
            </image>
            <distortion>
                <k1>0.0</k1>
                <k2>0.0</k2>
                <k3>0.0</k3>
                <p1>0.0</p1>
                <p2>0.0</p2>
                <center>0.5 0.5</center>
            </distortion>
        </camera>
        <!-- 【Harmonic 不需要 libgazebo_ros_camera.so，直接删掉原来的plugin块！】 -->
    </sensor>
</gazebo>
```

✅ 改动点：**直接删除 `<plugin name="depth_camera" filename="libgazebo_ros_camera.so">...</plugin>` 这一整段**。
gz sim 会自动发布 gz transport 消息：

- `/camera_sensor/image` 彩色图 gz.msgs.Image
- `/camera_sensor/depth_image` 深度图 gz.msgs.Image
- `/camera_sensor/camera_info` 相机参数 gz.msgs.CameraInfo

## 必须配套：在launch.py 的 ros_gz_bridge 添加相机桥接规则

把下面几条加到 `parameter_bridge` 的 arguments 列表：

```py
'/camera_sensor/image@sensor_msgs/msg/Image[gz.msgs.Image',
'/camera_sensor/depth_image@sensor_msgs/msg/Image[gz.msgs.Image',
'/camera_sensor/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo',
```

完整 bridge 示例：

```py
gz_bridge_node = launch_ros.actions.Node(
    package='ros_gz_bridge',
    executable='parameter_bridge',
    arguments=[
        '/imu@sensor_msgs/msg/Imu[gz.msgs.IMU',
        '/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan',
        '/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model',
        '/camera_sensor/image@sensor_msgs/msg/Image[gz.msgs.Image',
        '/camera_sensor/depth_image@sensor_msgs/msg/Image[gz.msgs.Image',
        '/camera_sensor/camera_info@sensor_msgs/msg/CameraInfo',
    ],
    output='screen'
)
```

## 额外两个关键点

1. TF：你的 `camera_optical_link` 需要在URDF里定义（相机光学坐标系z轴向前），RViz可视化图像需要这个TF。
2. 话题名称：
   - gz侧：`/camera_sensor/image`
   - ROS2侧桥接后同名，`/camera_sensor/image`> 
   > 如果你想改成传统 `/camera/image_raw`，可以在bridge里做重映射：

```py
'/camera_sensor/image@/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image'
```

## 可选：如果需要点云（深度转点云）

Harmonic depth sensor 可以直接输出点云，在`<sensor>`内部增加：

```xml
<depth_camera>
  <point_cloud>true</point_cloud>
</depth_camera>
```

gz会发布 `/camera_sensor/points`（gz.msgs.PointCloudPacked），再增加桥接：

```
'/camera_sensor/points@sensor_msgs/msg/PointCloud2[gz.msgs.PointCloudPacked'
```

## 小结

- Gazebo Classic(Humble)：靠 `libgazebo_ros_camera.so` 插件直接发布ROS话题
- Gazebo Harmonic(Jazzy)：删掉这个so插件，gz原生输出gz消息，**ros_gz_bridge中转成ROS2消息**

你现在的xacro里还有激光雷达的gazebo插件吗？我可以一并改成Harmonic版本。


========================================

# ch02. ros2jazzy中 如何在 URDF 里定义camera_optical_link  
```xml
<!-- ros2humble  urdf -->
<plugin name="depth_camera" filename="libgazebo_ros_camera.so">
    <frame_name>camera_optical_link</frame_name>
</plugin>
```
这里 camera_optical_link在ros2jazzy中 不需要 实现吗 ?

## 一句话结论
**`camera_optical_link` 这个TF链路，Jazzy+Gazebo Harmonic 仍然必须定义！但是不再靠 `<plugin><frame_name>` 来设置。**

> 
> Humble(Gazebo Classic)：
> `libgazebo_ros_camera.so` 插件里写 `<frame_name>camera_optical_link</frame_name>`
> 作用：插件发布ROS图像话题时，自动把消息header.frame_id填成 `camera_optical_link`。

> 
> Jazzy(Gazebo Harmonic)：
> ❌ 删掉 `libgazebo_ros_camera.so` 整个plugin块，**没有 `<frame_name>` 这个标签了**
> ✅ 但图像/深度消息的 `frame_id` 由Gazebo sensor标签的 `<frame_id>` 控制
> ✅ URDF 里面 `camera_link` → `camera_optical_link` 的fixed关节**依旧要写，不能省**

## 新旧对比

### Humble 旧写法（你原来的）

```xml
<sensor type="depth" name="camera_sensor">
  <plugin name="depth_camera" filename="libgazebo_ros_camera.so">
    <frame_name>camera_optical_link</frame_name> <!-- 插件参数指定frame_id -->
  </plugin>
```

### Jazzy Harmonic 新写法

```xml
<!-- src/fishbot_description/urdf/fishbot/plugins/gazebo_sensor_plugin.xacro -->
<sensor type="depth" name="camera_sensor">
  <frame_id>camera_optical_link</frame_id> <!-- 放到sensor下，不再属于plugin -->
  <always_on>true</always_on>
  <update_rate>10</update_rate>
  <camera name="camera">
    ...
  </camera>
  <depth_camera>
    <point_cloud>true</point_cloud>
  </depth_camera>
</sensor>
```

1. `<frame_id>` 是Gazebo Harmonic sensor原生标签，用来设置gz消息里的frame_id
2. 之后 ros_gz_bridge 桥接到ROS2，ROS消息 header.frame_id 自动继承为 `camera_optical_link`

## 重点：URDF的TF关节不能省略

不管是Humble还是Jazzy：
必须在URDF/xacro中定义：
`camera_link`（机械坐标系） → fixed joint → `camera_optical_link`（光学坐标系）

```xml
<!-- src/fishbot_description/urdf/fishbot/sensor/camera.urdf.xacro -->
<link name="camera_optical_link"/>
<joint name="camera_optical_joint" type="fixed">
  <parent link="camera_link"/>
  <child link="camera_optical_link"/>
  <origin xyz="0 0 0" rpy="-1.5708 0 -1.5708"/>
</joint>
```

原因：
- `frame_id=camera_optical_link` 只是填在消息头里的**名字字符串**
- TF树需要真实存在这个坐标系，robot_state_publisher发布TF变换，RViz、图像处理节点才能找到这个坐标系。> 
> 只写`<frame_id>`，但URDF没有camera_optical_link这个link和joint → TF lookup失败，RViz点云/图像无法正常渲染。

## 完整精简版xacro片段（直接替换你原来的）

```xml
<gazebo reference="camera_link">
    <sensor type="depth" name="camera_sensor">
        <frame_id>camera_optical_link</frame_id>
        <always_on>true</always_on>
        <update_rate>10</update_rate>
        <camera name="camera">
            <horizontal_fov>1.5009831567</horizontal_fov>
            <image>
                <width>800</width>
                <height>600</height>
                <format>R8G8B8</format>
            </image>
            <distortion>
                <k1>0.0</k1>
                <k2>0.0</k2>
                <k3>0.0</k3>
                <p1>0.0</p1>
                <p2>0.0</p2>
                <center>0.5 0.5</center>
            </distortion>
        </camera>
        <depth_camera>
          <point_cloud>true</point_cloud>
        </depth_camera>
    </sensor>
</gazebo>
```

## 验证命令

```
# 查看消息帧ID
ros2 topic echo /camera_sensor/image --no-arr
# 查询TF
ros2 run tf2_ros tf_echo camera_link camera_optical_link
```

## 一句话区分

- `<frame_id>camera_optical_link</frame_id>`：**消息头字符串标记**（告诉ROS这个数据属于哪个坐标系）
- URDF里camera_optical_link + fixed joint：**TF树的实际坐标变换**（告诉机器人这个坐标系相对camera_link在哪里）
两者配合，缺一不可。

=======================================
=======================================
# ch03.camera_optical_link
## 核心知识点

ROS 相机约定：

- `camera_link`：相机机械安装坐标系（通常Z朝上，X向前）
- `camera_optical_link`：**光学坐标系**，规则：**Z轴指向镜头前方（拍摄方向），X向右，Y向下**> 
> 光学坐标系和机械坐标系有旋转差，必须用 `fixed` 关节连接。

## 加到你的 fishbot.urdf.xacro

在相机 `<link name="camera_link">` 之后添加：

```xml
<!-- src/fishbot_description/urdf/fishbot/sensor/camera.urdf.xacro -->

<!-- 相机机械坐标系 -->
<link name="camera_link">
  <visual>
    <geometry>
      <box size="0.05 0.03 0.03"/>
    </geometry>
    <material name="blue">
      <color rgba="0 0 1 0.7"/>
    </material>
  </visual>
  <collision>
    <geometry>
      <box size="0.05 0.03 0.03"/>
    </geometry>
  </collision>
</link>

<!-- 相机光学坐标系 camera_optical_link -->
<link name="camera_optical_link"/>

<!-- fixed关节：camera_link → camera_optical_link -->
<joint name="camera_optical_joint" type="fixed">
  <parent link="camera_link"/>
  <child link="camera_optical_link"/>
  <!-- rpy: roll -90°, pitch 0°, yaw -90°
       作用：把 camera_link X向前，转为 optical Z向前 -->
  <origin xyz="0 0 0" rpy="-1.5708 0 -1.5708"/>
</joint>
```

> 
> `1.5708 rad = π/2 ≈ 90度`
> `xyz="0 0 0"`：光学原点和机械原点重合；如果你镜头有偏移，按需改xyz。

## 和你上面depth sensor xacro配套

```xml
<!-- src/fishbot_description/urdf/fishbot/plugins/gazebo_sensor_plugin.xacro -->
<gazebo reference="camera_link">
    <sensor type="depth" name="camera_sensor">
        <always_on>true</always_on>
        <update_rate>10</update_rate>
        <camera name="camera">
            <horizontal_fov>1.5009831567</horizontal_fov>
            <image>
                <width>800</width>
                <height>600</height>
                <format>R8G8B8</format>
            </image>
            <distortion>
                <k1>0.0</k1>
                <k2>0.0</k2>
                <k3>0.0</k3>
                <p1>0.0</p1>
                <p2>0.0</p2>
                <center>0.5 0.5</center>
            </distortion>
        </camera>
        <depth_camera>
          <point_cloud>true</point_cloud>
        </depth_camera>
    </sensor>
</gazebo>
```

> 
> sensor 在 `camera_link`，但是**图像消息里的 frame_id 是 `camera_optical_link`**，Gazebo Harmonic depth camera 默认 frame_id 就是 sensor 的 parent link，所以**需要手动指定传感器frame_id**：

### 补充：指定sensor的frame_id（关键！）

在 `<sensor>` 内部增加 `<frame_id>`：

```xml
<sensor type="depth" name="camera_sensor">
    <frame_id>camera_optical_link</frame_id>
    <always_on>true</always_on>
    ...
</sensor>
```

这样发布的 `/camera_sensor/image`、`/camera_info` 的 header.frame_id = `camera_optical_link`，RViz 显示图像、点云才不会错位。

## 校验 TF 是否生效

启动launch之后：

```sh
ros2 run tf_ros2_tools tf_echo camera_link camera_optical_link
```

查看变换。
```sh
ros2 topic echo /camera_sensor/image | grep frame_id
```

确认 frame_id 输出为 `camera_optical_link`。

## 坐标系简易记忆

- 机械 camera_link：X向前，Z向上（机器人标准右手系）
- 光学 camera_optical_link：**Z向前（视线方向），X向右，Y向下（图像像素行向下）**，OpenCV标准。

如果你相机不是朝前，而是斜向下安装，我可以帮你调整origin rpy参数。

要不要我把这一段合并进你的xacro完整片段？